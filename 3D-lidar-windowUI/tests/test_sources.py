"""Tests for data sources: synthetic tunnel and PCD/PLY/KITTI file loaders."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from data.frame import PointCloudFrame
from data.processor import PointCloudProcessor
from data.sources import (
    BinKittiSource,
    PcdFileSource,
    PlyFileSource,
    SyntheticTunnelSource,
    load_point_cloud,
)


# ---------------------------------------------------------------------------
# Synthetic tunnel
# ---------------------------------------------------------------------------


def test_synthetic_tunnel_counts_and_bounds() -> None:
    src = SyntheticTunnelSource(
        length_m=60.0, radius_m=2.8, points_per_meter=400, obstacle_m=40.0, seed=7
    )
    frame = src.read_frame()

    assert isinstance(frame, PointCloudFrame)
    assert frame.num_points == src.expected_point_count
    assert frame.intensity is not None
    assert frame.intensity.shape == (frame.num_points,)

    mn, mx = frame.bounds()
    assert mn[0] >= 0.0 and mx[0] <= 60.0        # along the track
    assert mn[1] >= -2.85 and mx[1] <= 2.85      # within tunnel radius
    assert mn[2] >= -0.02 and mx[2] <= 5.65      # floor .. top of arch


def test_synthetic_tunnel_without_obstacle() -> None:
    src = SyntheticTunnelSource(
        length_m=20.0, radius_m=2.0, points_per_meter=200,
        obstacle_m=None, seed=1,
    )
    frame = src.read_frame()
    assert frame.num_points == src.expected_point_count


def test_synthetic_through_processor() -> None:
    """Acceptance criterion: synthetic frame -> filtered frame with expected count."""
    src = SyntheticTunnelSource(
        length_m=50.0, points_per_meter=500, obstacle_m=30.0, seed=11
    )
    raw = src.read_frame()
    processed = PointCloudProcessor(leaf_size=0.5, max_points=1000, seed=3).process(raw)

    assert processed.num_points <= 1000
    assert processed.num_points < raw.num_points
    assert processed.intensity is not None
    assert processed.intensity.shape == (processed.num_points,)


# ---------------------------------------------------------------------------
# File helpers (generate small sample files inside tmp_path)
# ---------------------------------------------------------------------------


def _write_pcd_ascii(path: Path, xyz: np.ndarray, intensity: np.ndarray | None = None) -> None:
    n = len(xyz)
    has_i = intensity is not None
    fields = "x y z" + (" intensity" if has_i else "")
    sizes = "4 4 4" + (" 4" if has_i else "")
    types = "F F F" + (" F" if has_i else "")
    counts = "1 1 1" + (" 1" if has_i else "")
    lines = [
        "# .PCD v0.7 - Point Cloud Data file format",
        "VERSION 0.7",
        f"FIELDS {fields}",
        f"SIZE {sizes}",
        f"TYPE {types}",
        f"COUNT {counts}",
        f"WIDTH {n}",
        "HEIGHT 1",
        "VIEWPOINT 0 0 0 1 0 0 0",
        f"POINTS {n}",
        "DATA ascii",
    ]
    rows = []
    for i in range(n):
        row = f"{xyz[i, 0]:.6f} {xyz[i, 1]:.6f} {xyz[i, 2]:.6f}"
        if has_i:
            row += f" {intensity[i]:.6f}"
        rows.append(row)
    path.write_text("\n".join(lines + rows) + "\n", encoding="utf-8")


def _write_pcd_binary(path: Path, xyz: np.ndarray, intensity: np.ndarray | None = None) -> None:
    n = len(xyz)
    has_i = intensity is not None
    data = xyz if intensity is None else np.hstack([xyz, intensity[:, None]])
    ncols = 3 + (1 if has_i else 0)
    header = (
        "VERSION 0.7\n"
        f"FIELDS {'x y z intensity' if has_i else 'x y z'}\n"
        f"SIZE {'4 ' * ncols}\n"
        f"TYPE {'F ' * ncols}\n"
        f"COUNT {'1 ' * ncols}\n"
        f"WIDTH {n}\n"
        "HEIGHT 1\n"
        "VIEWPOINT 0 0 0 1 0 0 0\n"
        f"POINTS {n}\n"
        "DATA binary\n"
    )
    path.write_bytes(
        header.encode("ascii")
        + np.ascontiguousarray(data, dtype=np.float32).tobytes()
    )


def _write_ply_ascii(path: Path, xyz: np.ndarray, intensity: np.ndarray | None = None) -> None:
    n = len(xyz)
    props = ["property float x", "property float y", "property float z"]
    if intensity is not None:
        props.append("property float intensity")
    lines = ["ply", "format ascii 1.0", f"element vertex {n}", *props, "end_header"]
    rows = []
    for i in range(n):
        row = f"{xyz[i, 0]} {xyz[i, 1]} {xyz[i, 2]}"
        if intensity is not None:
            row += f" {intensity[i]}"
        rows.append(row)
    path.write_text("\n".join(lines + rows) + "\n", encoding="ascii")


# ---------------------------------------------------------------------------
# PCD loader
# ---------------------------------------------------------------------------


def test_pcd_ascii_roundtrip(tmp_path: Path) -> None:
    xyz = np.array([[0, 0, 0], [1, 1, 1], [2, 3, 4]], dtype=np.float32)
    path = tmp_path / "scan.pcd"
    _write_pcd_ascii(path, xyz)

    frame = PcdFileSource(path).read_frame()
    np.testing.assert_allclose(frame.xyz, xyz, atol=1e-4)
    assert frame.intensity is None
    assert frame.frame_id == "scan"


def test_pcd_ascii_with_intensity(tmp_path: Path) -> None:
    xyz = np.array([[0, 0, 0], [1, 1, 1]], dtype=np.float32)
    intensity = np.array([0.1, 0.9], dtype=np.float32)
    path = tmp_path / "scan_i.pcd"
    _write_pcd_ascii(path, xyz, intensity)

    frame = PcdFileSource(path).read_frame()
    np.testing.assert_allclose(frame.xyz, xyz, atol=1e-4)
    np.testing.assert_allclose(frame.intensity, intensity, atol=1e-4)


def test_pcd_binary_roundtrip(tmp_path: Path) -> None:
    rng = np.random.default_rng(5)
    xyz = rng.uniform(-5.0, 5.0, (500, 3)).astype(np.float32)
    path = tmp_path / "scan_bin.pcd"
    _write_pcd_binary(path, xyz)

    frame = PcdFileSource(path).read_frame()
    np.testing.assert_allclose(frame.xyz, xyz, atol=1e-4)


# ---------------------------------------------------------------------------
# PLY loader
# ---------------------------------------------------------------------------


def test_ply_ascii_roundtrip(tmp_path: Path) -> None:
    xyz = np.array([[0, 0, 0], [1, 2, 3], [4, 5, 6]], dtype=np.float32)
    intensity = np.array([0.2, 0.5, 0.8], dtype=np.float32)
    path = tmp_path / "scan.ply"
    _write_ply_ascii(path, xyz, intensity)

    frame = PlyFileSource(path).read_frame()
    np.testing.assert_allclose(frame.xyz, xyz, atol=1e-4)
    np.testing.assert_allclose(frame.intensity, intensity, atol=1e-4)


# ---------------------------------------------------------------------------
# KITTI loader + dispatcher
# ---------------------------------------------------------------------------


def test_kitti_bin_roundtrip(tmp_path: Path) -> None:
    rng = np.random.default_rng(6)
    cols = rng.uniform(-3.0, 3.0, (300, 4)).astype(np.float32)
    path = tmp_path / "scan.bin"
    path.write_bytes(cols.tobytes())

    frame = BinKittiSource(path).read_frame()
    np.testing.assert_allclose(frame.xyz, cols[:, :3], atol=1e-5)
    np.testing.assert_allclose(frame.intensity, cols[:, 3], atol=1e-5)


def test_kitti_bin_invalid_size(tmp_path: Path) -> None:
    path = tmp_path / "bad.bin"
    path.write_bytes(np.zeros(7, dtype=np.float32).tobytes())
    with pytest.raises(ValueError):
        BinKittiSource(path).read_frame()


def test_load_point_cloud_dispatch(tmp_path: Path) -> None:
    rng = np.random.default_rng(8)
    cols = rng.uniform(-2.0, 2.0, (200, 4)).astype(np.float32)
    path = tmp_path / "velodyne.bin"
    path.write_bytes(cols.tobytes())

    frame = load_point_cloud(path)
    np.testing.assert_allclose(frame.xyz, cols[:, :3], atol=1e-5)


def test_load_point_cloud_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "scan.xyz"
    path.write_text("not a point cloud")
    with pytest.raises(ValueError):
        load_point_cloud(path)