"""Pure NumPy processing of point cloud frames (no GUI/VTK dependencies).

All functions are deterministic when a seed / Generator is provided, which
makes them straightforward to unit test.
"""

from __future__ import annotations

import numpy as np

from .frame import PointCloudFrame

# ---------------------------------------------------------------------------
# Downsampling
# ---------------------------------------------------------------------------


def voxel_downsample(
    xyz: np.ndarray,
    leaf_size: float,
    intensity: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Average all points inside each voxel of side ``leaf_size``.

    The output point of a voxel is the centroid of its member points
    (mirrors the behaviour of Open3D's VoxelGrid).

    Args:
        xyz: (N, 3) float array of point coordinates.
        leaf_size: voxel side length in meters (> 0).
        intensity: optional (N,) float array kept alongside the geometry.

    Returns:
        (downsampled_xyz, downsampled_intensity) tuple. If no intensity was
        given the second element is None.
    """
    if leaf_size <= 0:
        raise ValueError(f"leaf_size must be > 0, got {leaf_size}")
    n = xyz.shape[0]
    if n == 0:
        empty = xyz.copy()
        return empty, (intensity.copy() if intensity is not None else None)

    voxel_id = np.floor(xyz / leaf_size).astype(np.int64)
    _, inverse = np.unique(voxel_id, axis=0, return_inverse=True)
    n_voxels = int(inverse.max()) + 1

    sums = np.zeros((n_voxels, 3), dtype=np.float64)
    np.add.at(sums, inverse, xyz)
    counts = np.bincount(inverse)[:, None].astype(np.float64)
    out_xyz = (sums / counts).astype(np.float32)

    out_intensity = None
    if intensity is not None:
        i_sums = np.zeros(n_voxels, dtype=np.float64)
        np.add.at(i_sums, inverse, intensity)
        out_intensity = (i_sums / counts[:, 0]).astype(np.float32)

    return out_xyz, out_intensity


def decimate(
    xyz: np.ndarray,
    max_points: int,
    intensity: np.ndarray | None = None,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Uniformly subsample to at most ``max_points`` (random, no replacement).

    Returns the input arrays unchanged if the point count already fits.
    """
    n = xyz.shape[0]
    if n <= max_points:
        return xyz, intensity
    rng = rng if rng is not None else np.random.default_rng()
    keep = np.sort(rng.choice(n, size=max_points, replace=False))
    out_intensity = intensity[keep] if intensity is not None else None
    return xyz[keep], out_intensity


# ---------------------------------------------------------------------------
# Coloring helpers (used by the renderer in Phase 3)
# ---------------------------------------------------------------------------

# A compact blue -> cyan -> green -> yellow -> orange -> red gradient.
_COLORMAP = np.array(
    [
        [0.00, 0.00, 0.55],
        [0.00, 0.55, 1.00],
        [0.00, 1.00, 0.45],
        [1.00, 1.00, 0.00],
        [1.00, 0.30, 0.00],
        [0.70, 0.00, 0.00],
    ],
    dtype=np.float32,
)


def distance_from_origin(xyz: np.ndarray) -> np.ndarray:
    """Euclidean distance of every point from the sensor (origin)."""
    return np.linalg.norm(xyz, axis=1)


def colorize_by_scalar(
    values: np.ndarray,
    vmin: float | None = None,
    vmax: float | None = None,
) -> np.ndarray:
    """Map 1-D scalars to an (N, 3) uint8 RGB array via linear interpolation.

    ``vmin``/``vmax`` fix the colormap range; by default the observed
    min/max of ``values`` are used.
    """
    v = np.asarray(values, dtype=np.float32).ravel()
    lo = float(np.min(v)) if vmin is None else float(vmin)
    hi = float(np.max(v)) if vmax is None else float(vmax)
    if hi <= lo:
        hi = lo + 1e-6
    t = np.clip((v - lo) / (hi - lo), 0.0, 1.0)

    n_stops = _COLORMAP.shape[0]
    scaled = t * (n_stops - 1)
    i0 = np.clip(np.floor(scaled).astype(np.int64), 0, n_stops - 2)
    frac = (scaled - i0)[:, None]
    rgb = _COLORMAP[i0] * (1.0 - frac) + _COLORMAP[i0 + 1] * frac
    return (np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)


def colorize_by_distance(xyz: np.ndarray) -> np.ndarray:
    """Color every point by its distance from the origin."""
    return colorize_by_scalar(distance_from_origin(xyz))


# ---------------------------------------------------------------------------
# Processor pipeline
# ---------------------------------------------------------------------------


class PointCloudProcessor:
    """Raw frame -> render-ready frame.

    Pipeline order:
        1. voxel downsample (skipped when ``leaf_size`` is 0),
        2. hard cap at ``max_points``.

    This class is stateful only through its RNG and is safe to reuse.
    """

    def __init__(
        self,
        leaf_size: float = 0.2,
        max_points: int = 1_500_000,
        seed: int | None = None,
    ) -> None:
        if leaf_size < 0:
            raise ValueError(f"leaf_size must be >= 0, got {leaf_size}")
        if max_points <= 0:
            raise ValueError(f"max_points must be > 0, got {max_points}")
        self.leaf_size = float(leaf_size)
        self.max_points = int(max_points)
        self._rng = np.random.default_rng(seed)

    def process(self, frame: PointCloudFrame) -> PointCloudFrame:
        """Apply the downsampling pipeline and return a new frame."""
        xyz = frame.xyz
        intensity = frame.intensity
        if self.leaf_size > 0:
            xyz, intensity = voxel_downsample(xyz, self.leaf_size, intensity)
        xyz, intensity = decimate(xyz, self.max_points, intensity, self._rng)
        return PointCloudFrame(
            xyz=xyz,
            intensity=intensity,
            timestamp=frame.timestamp,
            frame_id=frame.frame_id,
        )