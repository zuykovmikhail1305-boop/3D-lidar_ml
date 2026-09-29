"""Data layer: point cloud frames, processing and data sources.

The modules in this package depend only on NumPy (and the standard library),
so they can be unit-tested with pytest without a GUI or VTK.
"""

from __future__ import annotations

from .frame import PointCloudFrame
from .processor import (
    PointCloudProcessor,
    colorize_by_distance,
    colorize_by_scalar,
    decimate,
    distance_from_origin,
    voxel_downsample,
)

__all__ = [
    "PointCloudFrame",
    "PointCloudProcessor",
    "colorize_by_distance",
    "colorize_by_scalar",
    "decimate",
    "distance_from_origin",
    "voxel_downsample",
]