"""PyVista-based 3D renderer for point cloud frames (Phase 3).

The renderer owns a ``pyvistaqt.QtInteractor`` (a QWidget) and a single
point cloud actor. Colormaps and camera presets are switchable at runtime
without reloading the data.

Threading rule: every method must be called from the GUI thread (Qt/VTK
requirement). Cross-thread updates are routed through the MainWindow's
signals.
"""

from __future__ import annotations

import time

import numpy as np
import pyvista as pv
from PySide6.QtCore import QObject, Signal
from pyvistaqt import QtInteractor

from data.frame import PointCloudFrame
from data.processor import distance_from_origin


class PointCloudRenderer(QObject):
    """Owns the QtInteractor widget and the point cloud actor."""

    fpsUpdated = Signal(float)

    COLORING_DISTANCE = "distance"
    COLORING_INTENSITY = "intensity"
    COLORING_HEIGHT = "height"

    _COLORMAPS = {
        COLORING_DISTANCE: "turbo",
        COLORING_INTENSITY: "gray",
        COLORING_HEIGHT: "viridis",
    }

    # Camera presets: [position, focal_point, view_up]
    CAMERA_PRESETS: dict[str, list[object]] = {
        "front": [(-35.0, 0.0, 2.5), (150.0, 0.0, 2.0), (0.0, 0.0, 1.0)],
        "top": [(150.0, 0.0, 150.0), (150.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        "side": [(150.0, -90.0, 4.0), (150.0, 0.0, 2.0), (0.0, 0.0, 1.0)],
    }

    def __init__(self, parent_widget, parent=None) -> None:
        super().__init__(parent)
        self._plotter = QtInteractor(parent_widget)
        self._coloring = self.COLORING_DISTANCE
        self._frame: PointCloudFrame | None = None
        self._cloud_actor = None
        self._floor_actor = None
        self._point_size = 2

        self._render_count = 0
        self._fps_anchor = time.monotonic()

        self._setup_scene()
        self._wire_render_fps()

    # --- Widget / scene ----------------------------------------------------

    def plotter_widget(self) -> QtInteractor:
        """Return the Qt widget that embeds the VTK render window."""
        return self._plotter

    def _setup_scene(self) -> None:
        plotter = self._plotter
        plotter.set_background("#16181d")
        plotter.add_axes(interactive=False, line_width=2)

        # Semi-transparent floor plane along the track (X: 0..320 m).
        floor = pv.Plane(
            center=(160.0, 0.0, 0.0),
            direction=(0.0, 0.0, 1.0),
            i_size=330.0,
            j_size=12.0,
        )
        self._floor_actor = plotter.add_mesh(
            floor, color="#22262e", opacity=0.55, name="floor"
        )
        plotter.reset_camera()

    def _wire_render_fps(self) -> None:
        try:
            self._plotter.iren.add_observer("RenderEvent", self._on_render_event)
        except Exception:  # noqa: BLE001 - interactor may not be ready yet
            pass

    def _on_render_event(self, *_args) -> None:
        self._render_count += 1
        now = time.monotonic()
        elapsed = now - self._fps_anchor
        if elapsed >= 1.0:
            self.fpsUpdated.emit(self._render_count / elapsed)
            self._render_count = 0
            self._fps_anchor = now

    # --- Point cloud -------------------------------------------------------

    def set_frame(self, frame: PointCloudFrame) -> None:
        """Replace the displayed point cloud (rebuilds the actor)."""
        if frame.num_points == 0:
            return
        self._frame = frame
        self._update_cloud()

    def current_coloring(self) -> str:
        return self._coloring

    def set_coloring(self, mode: str) -> None:
        """Switch the scalar coloring mode and re-apply it to the cloud."""
        if mode not in self._COLORMAPS:
            raise ValueError(f"unknown coloring mode: {mode}")
        if mode == self._coloring:
            return
        self._coloring = mode
        if self._frame is not None:
            self._update_cloud()

    def set_point_size(self, size: int) -> None:
        """Change the rendered point size (radius in pixels)."""
        self._point_size = max(1, int(size))
        if self._cloud_actor is not None:
            self._cloud_actor.GetProperty().SetPointSize(self._point_size)
            self._plotter.render()

    def _compute_scalar(self, frame: PointCloudFrame) -> np.ndarray:
        if self._coloring == self.COLORING_DISTANCE:
            return distance_from_origin(frame.xyz)
        if self._coloring == self.COLORING_INTENSITY:
            if frame.intensity is not None:
                return frame.intensity
            return np.full(frame.num_points, 0.5, dtype=np.float32)
        # height
        return frame.xyz[:, 2]

    def _update_cloud(self) -> None:
        assert self._frame is not None
        mesh = pv.PolyData(self._frame.xyz)
        mesh.point_data["scalar"] = self._compute_scalar(self._frame)

        if self._cloud_actor is not None:
            self._plotter.remove_actor(self._cloud_actor)
        self._cloud_actor = self._plotter.add_mesh(
            mesh,
            scalars="scalar",
            cmap=self._COLORMAPS[self._coloring],
            point_size=self._point_size,
            name="cloud",
        )
        self._plotter.render()

    # --- Camera / overlays -------------------------------------------------

    def reset_view(self) -> None:
        self._plotter.reset_camera()
        self._plotter.render()

    def set_camera(self, preset: str) -> None:
        """Apply one of the CAMERA_PRESETS ('front', 'top', 'side')."""
        if preset not in self.CAMERA_PRESETS:
            raise ValueError(f"unknown camera preset: {preset}")
        self._plotter.camera_position = list(self.CAMERA_PRESETS[preset])
        self._plotter.render()

    def set_grid_visible(self, visible: bool) -> None:
        if self._floor_actor is not None:
            self._floor_actor.SetVisibility(bool(visible))
            self._plotter.render()

    # --- Debug / capture ---------------------------------------------------

    def screenshot(self, path: str) -> None:
        """Save the current render to an image file (for tests/debugging)."""
        self._plotter.screenshot(path)