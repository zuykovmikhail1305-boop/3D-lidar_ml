"""Generate a sample tunnel point cloud for development without LiDAR hardware.

Produces samples/tunnel_300m.pcd (binary PCD, ~360k points) with an
obstacle around 280 m so the whole pipeline can be exercised.

Run from the 3D-lidar-windowUI directory:
    .venv\\Scripts\\python.exe samples\\generate_sample_tunnel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running this file directly from anywhere:
#     .venv\Scripts\python.exe samples\generate_sample_tunnel.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.sources import SyntheticTunnelSource, write_pcd_binary


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    out_path = out_dir / "tunnel_300m.pcd"

    source = SyntheticTunnelSource(
        length_m=300.0,
        radius_m=2.8,
        points_per_meter=1200,
        obstacle_m=280.0,
        seed=42,
    )
    frame = source.read_frame()

    write_pcd_binary(out_path, frame)

    mn, mx = frame.bounds()
    print(
        f"wrote {out_path} | {frame.num_points:,} точек | "
        f"X [{mn[0]:.0f} … {mx[0]:.0f}] м | препятствие на {source.obstacle_m} м"
    )


if __name__ == "__main__":
    main()