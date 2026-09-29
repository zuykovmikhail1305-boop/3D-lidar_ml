"""Container for a single LiDAR scan shared across the data, ML and UI layers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class PointCloudFrame:
    """A single LiDAR scan.

    Attributes:
        xyz: (N, 3) float32 array of point coordinates in meters.
            Convention: X is along the track, Z points up.
        intensity: optional (N,) float32 reflectivity values in [0, 1].
        timestamp: seconds since epoch (float); 0.0 if unknown.
        frame_id: optional scan identifier string (e.g. file name).
    """

    xyz: np.ndarray
    intensity: np.ndarray | None = None
    timestamp: float = 0.0
    frame_id: str = ""

    def __post_init__(self) -> None:
        self.xyz = np.asarray(self.xyz, dtype=np.float32)
        if self.xyz.ndim != 2 or self.xyz.shape[1] != 3:
            raise ValueError(f"xyz must have shape (N, 3), got {self.xyz.shape}")
        if self.intensity is not None:
            self.intensity = np.asarray(self.intensity, dtype=np.float32)
            if self.intensity.shape != (self.xyz.shape[0],):
                raise ValueError(
                    "intensity length must match number of points: "
                    f"{self.intensity.shape} vs {self.xyz.shape}"
                )

    @property
    def num_points(self) -> int:
        """Number of points in this frame."""
        return int(self.xyz.shape[0])

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (min, max) corner coordinates as (3,) float32 arrays."""
        return self.xyz.min(axis=0), self.xyz.max(axis=0)