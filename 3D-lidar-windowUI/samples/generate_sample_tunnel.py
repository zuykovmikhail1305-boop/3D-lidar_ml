"""Generate a sample tunnel point cloud for development without LiDAR hardware.

Produces:
- samples/tunnel_300m.pcd    binary PCD (~360k points) with an obstacle at 280 m
- samples/tunnel_preview.png off-screen render of that cloud (headless-safe)

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

from data.frame import PointCloudFrame
from data.processor import distance_from_origin
from data.sources import SyntheticTunnelSource, write_pcd_binary


def render_preview(frame: PointCloudFrame, out_path: Path) -> None:
    """Render the cloud off-screen (works without a GPU/display) to a PNG.

    Mirrors the scene of the in-app QtInteractor: dark background, turbo
    colormap by distance, semi-transparent floor plane, front camera.
    """
    import numpy as np
    import pyvista as pv

    plotter = pv.Plotter(off_screen=True, window_size=(1200, 700))
    plotter.set_background("#16181d")

    mesh = pv.PolyData(frame.xyz)
    mesh.point_data["scalar"] = distance_from_origin(frame.xyz)
    plotter.add_mesh(mesh, scalars="scalar", cmap="turbo", point_size=2, name="cloud")

    floor = pv.Plane(
        center=(160.0, 0.0, 0.0),
        direction=(0.0, 0.0, 1.0),
        i_size=330.0,
        j_size=12.0,
    )
    plotter.add_mesh(floor, color="#22262e", opacity=0.55)
    plotter.camera_position = [(-35.0, 0.0, 2.5), (150.0, 0.0, 2.0), (0.0, 0.0, 1.0)]

    plotter.screenshot(str(out_path))
    plotter.close()


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    pcd_path = out_dir / "tunnel_300m.pcd"
    preview_path = out_dir / "tunnel_preview.png"

    source = SyntheticTunnelSource(
        length_m=300.0,
        radius_m=2.8,
        points_per_meter=1200,
        obstacle_m=280.0,
        seed=42,
    )
    frame = source.read_frame()

    write_pcd_binary(pcd_path, frame)
    render_preview(frame, preview_path)

    mn, mx = frame.bounds()
    print(
        f"wrote {pcd_path} | {frame.num_points:,} точек | "
        f"X [{mn[0]:.0f} … {mx[0]:.0f}] м | препятствие на {source.obstacle_m} м"
    )
    print(f"wrote {preview_path}")


if __name__ == "__main__":
    main()