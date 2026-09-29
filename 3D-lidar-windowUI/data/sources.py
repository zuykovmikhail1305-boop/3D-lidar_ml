"""Point cloud data sources: file loaders and the synthetic tunnel generator.

The module depends only on NumPy and the standard library, so it can be
unit-tested without a GUI or VTK. Threading / Qt-signal wrapping happens
later (Phase 6).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from .frame import PointCloudFrame


class PointCloudSource(ABC):
    """Base class for any point cloud provider (file / stream / synthetic)."""

    @abstractmethod
    def read_frame(self) -> PointCloudFrame:
        """Return the next available scan as a PointCloudFrame."""


# ---------------------------------------------------------------------------
# Synthetic tunnel (development without LiDAR hardware)
# ---------------------------------------------------------------------------


class SyntheticTunnelSource(PointCloudSource):
    """Generates a plausible metro-tunnel scan for development.

    Geometry (meters): X is along the track, Z points up. The tunnel
    cross-section is an upper semicircle of radius ``radius_m`` centered at
    ``z = radius_m`` (so the floor lies at z = 0); the lower half is
    flattened into a track bed spanning the full tunnel width.

    An optional box-shaped obstacle can be placed around ``obstacle_m``.

    Args:
        length_m: tunnel length along X.
        radius_m: tunnel radius.
        points_per_meter: approximate number of points per meter of tunnel.
        obstacle_m: X position of the obstacle (None disables it).
        seed: RNG seed for reproducible scans.
    """

    def __init__(
        self,
        length_m: float = 300.0,
        radius_m: float = 2.8,
        points_per_meter: int = 1200,
        obstacle_m: float | None = 280.0,
        seed: int = 42,
    ) -> None:
        if length_m <= 0 or radius_m <= 0:
            raise ValueError("length_m and radius_m must be positive")
        self.length_m = float(length_m)
        self.radius_m = float(radius_m)
        self.points_per_meter = int(points_per_meter)
        self.obstacle_m = obstacle_m
        self._rng = np.random.default_rng(seed)

    def read_frame(self) -> PointCloudFrame:
        rng = self._rng
        spacing = 0.5  # ring-to-ring distance along X
        n_rings = int(self.length_m / spacing)
        per_ring = max(8, int(self.points_per_meter * spacing))
        n_wall = n_rings * per_ring

        ring_id = np.repeat(np.arange(n_rings, dtype=np.float32), per_ring)
        x_wall = ring_id * spacing + rng.uniform(0.0, spacing, n_wall)
        theta = rng.uniform(-np.pi, np.pi, n_wall)

        r = self.radius_m
        upper = theta >= 0.0  # upper semicircle becomes the arch
        y_wall = r * np.cos(theta)
        z_wall = np.where(upper, r + r * np.sin(theta), 0.0)

        # Measurement noise: small on walls, tiny on the flat floor.
        y_wall += rng.normal(0.0, 0.010, n_wall)
        z_wall += np.where(upper, rng.normal(0.0, 0.010, n_wall),
                           rng.normal(0.0, 0.004, n_wall))

        wall_xyz = np.column_stack([x_wall, y_wall, z_wall]).astype(np.float32)
        wall_intensity = (
            0.35 + 0.60 * np.clip(1.0 - x_wall / self.length_m, 0.0, 1.0)
        ).astype(np.float32)

        parts_xyz = [wall_xyz]
        parts_int = [wall_intensity]

        if self.obstacle_m is not None:
            n_obs = 4000
            obs_xyz = np.column_stack(
                [
                    rng.uniform(self.obstacle_m, self.obstacle_m + 1.2, n_obs),
                    rng.uniform(-0.9, 0.9, n_obs),
                    rng.uniform(0.0, 2.0, n_obs),
                ]
            ).astype(np.float32)
            parts_xyz.append(obs_xyz)
            parts_int.append(
                (0.88 + 0.07 * rng.random(n_obs)).astype(np.float32)
            )

        xyz = np.concatenate(parts_xyz, axis=0)
        intensity = np.concatenate(parts_int, axis=0)

        order = rng.permutation(xyz.shape[0])
        return PointCloudFrame(
            xyz=xyz[order],
            intensity=intensity[order],
            frame_id="synthetic",
        )

    @property
    def expected_point_count(self) -> int:
        """Deterministic point count for the configured parameters."""
        spacing = 0.5
        n_rings = int(self.length_m / spacing)
        per_ring = max(8, int(self.points_per_meter * spacing))
        count = n_rings * per_ring
        if self.obstacle_m is not None:
            count += 4000
        return count


# ---------------------------------------------------------------------------
# File loaders
# ---------------------------------------------------------------------------


def _require_x_y_z(columns: dict[str, int]) -> tuple[int, int, int]:
    missing = [name for name in ("x", "y", "z") if name not in columns]
    if missing:
        raise ValueError(
            f"point cloud is missing required coordinate fields: {missing}"
        )
    return columns["x"], columns["y"], columns["z"]


def _make_frame(
    data: np.ndarray, columns: dict[str, int], frame_id: str
) -> PointCloudFrame:
    """Build a frame from a column matrix and a field-name -> column map."""
    ix, iy, iz = _require_x_y_z(columns)
    xyz = np.ascontiguousarray(data[:, [ix, iy, iz]], dtype=np.float32)
    intensity = None
    for name in ("intensity", "reflectance", "i"):
        if name in columns:
            intensity = np.ascontiguousarray(
                data[:, columns[name]], dtype=np.float32
            )
            break
    return PointCloudFrame(xyz=xyz, intensity=intensity, frame_id=frame_id)


class PcdFileSource(PointCloudSource):
    """Reader for the PCL Point Cloud Data (PCD) format.

    Supports ASCII and raw binary data sections (not binary_compressed).
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read_frame(self) -> PointCloudFrame:
        with open(self.path, "rb") as f:
            header, data_start = _read_pcd_header(f)
            data_kind = header["DATA"].lower()
            fields = header["FIELDS"]
            sizes = header["SIZE"]
            types = header["TYPE"]
            counts = header["COUNT"]

            if data_kind == "ascii":
                f.seek(data_start)
                text = f.read().decode("utf-8", errors="replace")
                arr = np.loadtxt(
                    text.splitlines(), dtype=np.float32, ndmin=2
                )
            elif data_kind == "binary":
                f.seek(data_start)
                raw = f.read()
                arr = _unpack_binary_columns(raw, fields, sizes, types, counts)
            else:
                raise ValueError(
                    f"unsupported PCD DATA section '{data_kind}' "
                    "(supported: ascii, binary)"
                )

        columns: dict[str, int] = {}
        offset = 0
        for name, count in zip(fields, counts):
            for k in range(count):
                columns[name if count == 1 else f"{name}_{k}"] = offset + k
            offset += count
        return _make_frame(arr, columns, self.path.stem)


class PlyFileSource(PointCloudSource):
    """Reader for the PLY polygon format (ASCII and binary_little_endian)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read_frame(self) -> PointCloudFrame:
        with open(self.path, "rb") as f:
            fmt, props, n_vertex, data_start = _read_ply_header(f)

            if fmt == "ascii":
                f.seek(data_start)
                text = f.read().decode("utf-8", errors="replace")
                arr = np.loadtxt(
                    text.splitlines(), dtype=np.float32, ndmin=2
                )[:n_vertex]
            elif fmt == "binary_little_endian":
                f.seek(data_start)
                dtype = np.dtype(
                    [(p.name, p.numpy_dtype) for p in props]
                ).newbyteorder("<")
                raw = f.read(dtype.itemsize * n_vertex)
                structured = np.frombuffer(raw, dtype=dtype, count=n_vertex)
                arr = np.stack(
                    [structured[p.name] for p in props], axis=1
                ).astype(np.float32)
            else:
                raise ValueError(
                    f"unsupported PLY format '{fmt}' "
                    "(supported: ascii, binary_little_endian)"
                )

        columns = {p.name: i for i, p in enumerate(props)}
        return _make_frame(arr, columns, self.path.stem)


class BinKittiSource(PointCloudSource):
    """Reader for KITTI-style raw scans: N x 4 float32 (x, y, z, intensity)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read_frame(self) -> PointCloudFrame:
        raw = np.fromfile(self.path, dtype=np.float32)
        if raw.size % 4 != 0:
            raise ValueError(
                f"{self.path.name}: size {raw.size * 4} bytes is not a "
                "multiple of 4 floats (x, y, z, intensity)"
            )
        cols = raw.reshape(-1, 4)
        return PointCloudFrame(
            xyz=np.ascontiguousarray(cols[:, :3], dtype=np.float32),
            intensity=np.ascontiguousarray(cols[:, 3], dtype=np.float32),
            frame_id=self.path.stem,
        )


# ---------------------------------------------------------------------------
# Helpers shared by the PCD loader
# ---------------------------------------------------------------------------


def _read_pcd_header(f) -> tuple[dict[str, Any], int]:
    """Read the PCD header; return (parsed header, byte offset of DATA)."""
    header: dict[str, Any] = {
        "FIELDS": [], "SIZE": [], "TYPE": [], "COUNT": []
    }
    while True:
        pos = f.tell()
        line = f.readline()
        if not line:
            raise ValueError("unexpected end of PCD file while reading header")
        stripped = line.strip().decode("utf-8", errors="replace")
        if not stripped or stripped.startswith("#"):
            continue
        key, _, value = stripped.partition(" ")
        key = key.upper()
        if key == "DATA":
            header["DATA"] = value
            return header, pos + len(line)
        if key == "FIELDS":
            header["FIELDS"] = value.split()
        elif key == "SIZE":
            header["SIZE"] = [int(v) for v in value.split()]
        elif key == "TYPE":
            header["TYPE"] = value.split()
        elif key == "COUNT":
            header["COUNT"] = [int(v) for v in value.split()]
        elif key == "POINTS":
            header["POINTS"] = int(value)


def _unpack_binary_columns(
    raw: bytes, fields: list[str], sizes: list[int],
    types: list[str], counts: list[int],
) -> np.ndarray:
    """Decode a raw PCD binary section into a (N, total_cols) float32 matrix."""
    row_size = sum(s * c for s, c in zip(sizes, counts))
    if row_size == 0:
        raise ValueError("invalid PCD binary header (empty row)")
    n_rows = len(raw) // row_size
    rows = np.frombuffer(raw, dtype=np.uint8)[: n_rows * row_size]
    rows = rows.reshape(n_rows, row_size)

    out_cols: list[np.ndarray] = []
    offset = 0
    for name, size, typ, count in zip(fields, sizes, types, counts):
        if typ == "F":
            code = "f"
        elif typ in ("I", "U"):
            code = "u" if typ == "U" else "i"
        else:
            raise ValueError(
                f"unsupported PCD scalar type '{typ}' for field '{name}'"
            )
        dt = np.dtype(f"<{code}{size}")
        chunk = rows[:, offset : offset + size * count].copy().ravel()
        values = chunk.view(dt).reshape(n_rows, count).astype(np.float32)
        if count > 1:
            # Multi-value fields are expanded into separate columns.
            for k in range(count):
                out_cols.append(values[:, k])
        else:
            out_cols.append(values[:, 0])
        offset += size * count

    return np.column_stack(out_cols)


# ---------------------------------------------------------------------------
# PLY header parsing
# ---------------------------------------------------------------------------


class _PlyProperty:
    __slots__ = ("name", "numpy_dtype")

    def __init__(self, name: str, numpy_dtype: str) -> None:
        self.name = name
        self.numpy_dtype = numpy_dtype


_PLY_TYPE_MAP = {
    "float": "f4",
    "double": "f8",
    "uchar": "u1",
    "uint8": "u1",
    "int": "i4",
    "int32": "i4",
    "short": "i2",
}


def _read_ply_header(f) -> tuple[str, list[_PlyProperty], int, int]:
    """Parse a PLY header; return (format, vertex props, count, data offset)."""
    first = f.readline().strip().decode("utf-8", errors="replace")
    if first != "ply":
        raise ValueError("not a PLY file (missing 'ply' magic line)")

    fmt: str | None = None
    props: list[_PlyProperty] = []
    n_vertex: int | None = None
    data_start = 0

    while True:
        pos = f.tell()
        line = f.readline()
        if not line:
            raise ValueError("unexpected end of PLY file while reading header")
        data_start = pos + len(line)
        tokens = line.strip().decode("utf-8", errors="replace").split()
        if not tokens:
            continue
        if tokens[0] == "format":
            fmt = tokens[1]
        elif tokens[0] == "element" and tokens[1] == "vertex":
            n_vertex = int(tokens[2])
        elif tokens[0] == "property":
            if tokens[1] == "list":
                continue  # list properties (faces) are ignored
            dt = _PLY_TYPE_MAP.get(tokens[1])
            if dt is None:
                raise ValueError(
                    f"unsupported PLY property type '{tokens[1]}'"
                )
            props.append(_PlyProperty(tokens[2], dt))
        elif tokens[0] == "end_header":
            break

    if fmt is None:
        raise ValueError("PLY header missing 'format' line")
    if n_vertex is None:
        raise ValueError("PLY header missing 'element vertex'")
    return fmt, props, n_vertex, data_start


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_LOADERS: dict[str, Callable[[Path], PointCloudSource]] = {
    ".pcd": PcdFileSource,
    ".ply": PlyFileSource,
    ".bin": BinKittiSource,
}


def load_point_cloud(path: str | Path) -> PointCloudFrame:
    """Load any supported point cloud file based on its extension.

    Supported extensions: .pcd, .ply, .bin (KITTI).
    """
    p = Path(path)
    loader = _LOADERS.get(p.suffix.lower())
    if loader is None:
        raise ValueError(
            f"unsupported point cloud format '{p.suffix}' "
            f"(supported: {', '.join(sorted(_LOADERS))})"
        )
    return loader(p).read_frame()


def write_pcd_binary(path: str | Path, frame: PointCloudFrame) -> None:
    """Write a frame to an uncompressed binary PCD file (round-trip safe)."""
    fields = ["x", "y", "z"]
    cols = [frame.xyz]
    if frame.intensity is not None:
        fields.append("intensity")
        cols.append(frame.intensity[:, None])
    data = np.hstack(cols)
    n = frame.num_points
    ncols = len(fields)
    header = (
        "VERSION 0.7\n"
        f"FIELDS {' '.join(fields)}\n"
        f"SIZE {' '.join(['4'] * ncols)}\n"
        f"TYPE {' '.join(['F'] * ncols)}\n"
        f"COUNT {' '.join(['1'] * ncols)}\n"
        f"WIDTH {n}\n"
        "HEIGHT 1\n"
        "VIEWPOINT 0 0 0 1 0 0 0\n"
        f"POINTS {n}\n"
        "DATA binary\n"
    )
    Path(path).write_bytes(
        header.encode("ascii")
        + np.ascontiguousarray(data, dtype=np.float32).tobytes()
    )