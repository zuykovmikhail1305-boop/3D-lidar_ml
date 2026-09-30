"""Main application window for the LiDAR obstacle monitor.

Phase 1 scope:
- UI skeleton: splitter, three zone cards + zone table (model-view sync),
  dark QSS theme.
- Temporary demo stream ("▶ Стрим") that feeds mock probabilities via a
  QTimer so the card/table update pipeline can be verified visually.
- The 3D viewport placeholder will be replaced by pyvistaqt.QtInteractor
  in Phase 3; real data sources arrive in Phases 2 and 5.
"""


from __future__ import annotations

import json
import random
import sys
from collections.abc import Mapping
import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
)

from core.constants import (
    STATUS_COLORS,
    STATUS_LABELS,
    ZONE_DISTANCES,
    status_for_probability,
)
from ros_worker import RosWorker
from ui_form import Ui_MainWindow
from zonetable_model import ZoneTableModel

APP_STYLESHEET = """
QMainWindow, QWidget#centralwidget {
    background-color: #1e2128;
    color: #e8eaed;
}
QWidget { font-size: 13px; }

QLabel { color: #e8eaed; }

QFrame#leftPanel {
    background-color: #23262e;
    border-right: 1px solid #2f3440;
}

QLabel#leftTitleLabel {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 2px;
    color: #9aa4b2;
    padding: 2px 0 4px 0;
}

QFrame[class="zoneCard"] {
    background-color: #262b34;
    border: 2px solid #3a3f4b;
    border-radius: 8px;
}
QFrame[class="zoneCard"][status="ok"]   { border-color: #2ecc71; }
QFrame[class="zoneCard"][status="warn"] { border-color: #f1c40f; }
QFrame[class="zoneCard"][status="stop"] { border-color: #e74c3c; }

QLabel#zoneTitle_300, QLabel#zoneTitle_200, QLabel#zoneTitle_100 {
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
    color: #9aa4b2;
}
QLabel#zoneProb_300, QLabel#zoneProb_200, QLabel#zoneProb_100 {
    font-size: 28px;
    font-weight: 800;
}
QLabel#zoneStatus_300, QLabel#zoneStatus_200, QLabel#zoneStatus_100 {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1px;
}

QProgressBar {
    background-color: #16181d;
    border: none;
    border-radius: 3px;
    height: 10px;
    text-align: center;
    color: transparent;
}

QTableView {
    background-color: #1a1d23;
    alternate-background-color: #20242c;
    border: 1px solid #2f3440;
    border-radius: 6px;
    selection-background-color: #2f3542;
    gridline-color: transparent;
}
QHeaderView::section {
    background-color: #23262e;
    color: #9aa4b2;
    border: none;
    padding: 6px;
    font-weight: 600;
}

QPushButton {
    background-color: #2f3542;
    color: #e8eaed;
    border: 1px solid #3a4150;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton:hover  { background-color: #3a4150; }
QPushButton:pressed{ background-color: #262b34; }

QGroupBox {
    border: 1px solid #2f3440;
    border-radius: 6px;
    margin-top: 10px;
    color: #9aa4b2;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}

QRadioButton, QCheckBox { color: #e8eaed; spacing: 6px; }

QDoubleSpinBox {
    background-color: #1a1d23;
    border: 1px solid #2f3440;
    border-radius: 4px;
    padding: 3px 6px;
    color: #e8eaed;
}

QMenuBar { background-color: #1e2128; color: #e8eaed; }
QMenuBar::item:selected { background-color: #2f3542; }
QMenu { background-color: #23262e; color: #e8eaed; border: 1px solid #2f3440; }
QMenu::item:selected { background-color: #2f3542; }
QStatusBar { background-color: #1a1d23; color: #9aa4b2; }
QSplitter::handle { background-color: #2f3440; }
"""

# Маппинг блоков ответа модели (BLOCKS из lidar_api/api.py) на дистанции зон интерфейса.
BLOCK_TO_DISTANCE: dict[str, int] = {
    "0-100": 100,
    "100-200": 200,
    "200-300": 300,
}


class MainWindow(QMainWindow):
    """Main window: left panel with zone cards + table, right 3D viewport."""

    DEMO_INTERVAL_MS = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._demo_tick)
        self._ros_worker: RosWorker | None = None

        self._setup_zone_cards()
        self._setup_zones_table()
        self._setup_3d_viewport()
        self._setup_connections()

        # Initialize cards to the "no data" state.
        for distance in ZONE_DISTANCES:
            self._apply_zone_state(distance, None)

    # --- Setup -------------------------------------------------------------

    def _setup_zone_cards(self) -> None:
        """Collect zone card widgets keyed by distance in meters."""
        ui = self.ui
        self._zone_cards = {
            300: (ui.zoneProb_300, ui.zoneProgress_300, ui.zoneStatus_300, ui.zoneCard_300),
            200: (ui.zoneProb_200, ui.zoneProgress_200, ui.zoneStatus_200, ui.zoneCard_200),
            100: (ui.zoneProb_100, ui.zoneProgress_100, ui.zoneStatus_100, ui.zoneCard_100),
        }
        # Shared QSS class used by attribute selectors (equal specificity,
        # so the status-based border colors actually win over the base rule).
        for _, _, _, card in self._zone_cards.values():
            card.setProperty("class", "zoneCard")
            card.style().unpolish(card)
            card.style().polish(card)

    def _setup_zones_table(self) -> None:
        """Attach the ZoneTableModel to the QTableView and size columns."""
        self._table_model = ZoneTableModel(self)
        self.ui.zonesTable.setModel(self._table_model)
        header = self.ui.zonesTable.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def _setup_3d_viewport(self) -> None:
        """Встраиваем PyVista QtInteractor в viewportContainer."""
        pv.global_theme.allow_empty_mesh = True

        container = self.ui.viewportContainer
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Создаем 3D-движок и вставляем его в интерфейс
        self.plotter = QtInteractor(container)
        layout.addWidget(self.plotter.interactor)

        self.plotter.enable_terrain_style()
        
        # Настраиваем цвета и сетку
        self.plotter.set_background("#16181d")
        self.plotter.add_axes()
        self.plotter.show_grid(color="#5b6270")
        self.plotter.set_scale(xscale=1.0, yscale=5.0, zscale=5.0)
        
        # Создаем "контейнер" для точек лидара
        self.point_cloud = pv.PolyData()
        self.plotter.add_mesh(
            self.point_cloud,
            color="cyan",
            point_size=3.0,
            render_points_as_spheres=True,
            name="lidar_points",
            reset_camera=False
        )

    def _setup_connections(self) -> None:
        """Wire buttons, menu actions and the demo stream."""
        self.ui.openFileButton.clicked.connect(self._on_open_file)
        self.ui.streamButton.clicked.connect(self._toggle_stream)
        self.ui.actionQuit.triggered.connect(self.close)

        for action in (
            self.ui.actionOpenPointCloud,
            self.ui.actionOpenMLReport,
            self.ui.actionResetView,
            self.ui.actionCameraFront,
            self.ui.actionCameraTop,
        ):
            action.triggered.connect(
                lambda _checked=False, a=action: self.statusBar().showMessage(
                    f"«{a.text()}» — будет реализовано в следующих фазах", 3000
                )
            )

    # --- Zone update API ---------------------------------------------------

    def _apply_zone_state(self, distance: int, probability: float | None) -> None:
        """Refresh one zone card from a probability value."""
        prob_label, progress, status_label, card = self._zone_cards[distance]
        status = status_for_probability(probability)
        color = STATUS_COLORS[status]

        prob_label.setText(
            "— %" if probability is None else f"{probability * 100:.0f} %"
        )
        progress.setValue(
            0 if probability is None else int(round(probability * 100))
        )
        status_label.setText(STATUS_LABELS[status])
        status_label.setStyleSheet(f"color: {color}; font-weight: 700;")
        progress.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}"
        )

        # Dynamic QSS property drives the card border color.
        card.setProperty("status", status)
        card.style().unpolish(card)
        card.style().polish(card)

    def set_zone_probabilities(
        self, probabilities: Mapping[int, float | None]
    ) -> None:
        """Update cards and the table model with new obstacle probabilities."""
        for distance in ZONE_DISTANCES:
            if distance in probabilities:
                self._apply_zone_state(distance, probabilities[distance])
        self._table_model.update_probabilities(probabilities)
        self.statusBar().showMessage("Вероятности препятствий обновлены", 2000)

    #--- Demo stream (temporary, replaced by MLDataSource in Phase 5) ------

    def _demo_tick(self) -> None:
        probabilities = {
            distance: random.random() for distance in ZONE_DISTANCES
       }
        self.set_zone_probabilities(probabilities)
    
        x = np.random.uniform(0, 300, 2000)
        y = np.random.uniform(-5, 5, 2000)
        z = np.random.uniform(-5, 5, 2000)
    
        points = np.column_stack((x, y, z))
    
        new_cloud = pv.PolyData(points)
       
        self.plotter.add_mesh(
            new_cloud,
            name="lidar_points",
            color="cyan",
            point_size=3.0,
            render_points_as_spheres=True
        )

    def _toggle_stream(self) -> None:
        """Переключает источник данных: ROS2 (живой стрим) либо демо-fallback."""
        if self._ros_worker is not None and self._ros_worker.isRunning():
            self._stop_ros_stream()
            return
        if self._demo_timer.isActive():
            self._demo_timer.stop()
            self.ui.streamButton.setText("▶ Стрим")
            self.statusBar().showMessage("Демо-поток остановлен", 3000)
            return
        if RosWorker.available():
            self._start_ros_stream()
        else:
            self._start_demo_stream()

    def _start_demo_stream(self) -> None:
        """Демо-fallback (нет ROS2): mock-вероятности и случайное облако точек."""
        self._demo_timer.start(self.DEMO_INTERVAL_MS)
        self.ui.streamButton.setText("⏸ Пауза")
        self.statusBar().showMessage(
            "ROS2 (rclpy) не найден — включён демо-поток с mock-данными", 5000
        )

    def _start_ros_stream(self) -> None:
        """Запускает RosWorker: lidar_points/model_out → Qt-сигналы → виджеты."""
        self._demo_timer.stop()
        self._prepare_real_viewport()

        self._ros_worker = RosWorker(self)
        self._ros_worker.cloud_ready.connect(self._on_cloud_ready)
        self._ros_worker.prediction_ready.connect(self._on_prediction_ready)
        self._ros_worker.error.connect(self._on_worker_error)
        self._ros_worker.finished.connect(self._on_worker_finished)
        self._ros_worker.start()

        self.ui.streamButton.setText("⏸ Пауза")
        self.statusBar().showMessage(
            "ROS2-поток: lidar_points → модель → UI. Ожидание данных…", 0
        )

    def _stop_ros_stream(self) -> None:
        """Останавливает воркер и ждёт завершения его потока."""
        worker, self._ros_worker = self._ros_worker, None
        if worker is not None:
            worker.requestInterruption()
            worker.wait(3000)
        self.ui.streamButton.setText("▶ Стрим")
        self.statusBar().showMessage("ROS2-поток остановлен", 3000)

    def _shutdown_streams(self) -> None:
        """Полная остановка источников (вызывается при закрытии окна)."""
        self._demo_timer.stop()
        worker, self._ros_worker = self._ros_worker, None
        if worker is not None:
            worker.requestInterruption()
            worker.wait(5000)

    def _on_worker_error(self, message: str) -> None:
        """Ошибка воркера — показываем в statusbar (поток сам завершится)."""
        self.statusBar().showMessage(message, 5000)

    def _on_worker_finished(self) -> None:
        """Воркер завершился сам — возвращаем кнопку в исходное состояние."""
        if self.sender() is not self._ros_worker:
            return
        self._ros_worker = None
        if self.ui.streamButton.text().startswith("⏸"):
            self.ui.streamButton.setText("▶ Стрим")
        self.statusBar().showMessage("ROS2-поток завершён", 3000)

    # --- ROS2-данные: реальные предсказания и облако точек -------------------

    def _on_prediction_ready(self, json_str: str) -> None:
        """Разбирает JSON результата модели и обновляет карточки/таблицу/statusbar."""
        try:
            result = json.loads(json_str)
        except (json.JSONDecodeError, TypeError) as exc:
            self.statusBar().showMessage(f"Ошибка разбора результата модели: {exc}", 5000)
            return

        # Семантика: detected=1 → СТОП (вероятность 1.0), detected=0 → ОК (0.0).
        # Дополнительно в статус зоны добавляем число скоплений и ближайшее расстояние.
        probabilities: dict[int, float] = {}
        details: dict[int, str] = {}
        for block in result.get("blocks", []):
            distance = BLOCK_TO_DISTANCE.get(block.get("block"))
            if distance is None:
                continue
            detected = int(block.get("detected") or 0)
            probabilities[distance] = 1.0 if detected else 0.0

            clusters = int(block.get("clusters") or 0)
            nearest = block.get("nearest_m")
            status = status_for_probability(probabilities[distance])
            parts = [STATUS_LABELS[status]]
            if clusters:
                parts.append(f"{clusters} скопл.")
            if nearest is not None:
                parts.append(f"{nearest:.0f} м")
            details[distance] = " · ".join(parts)

        self.set_zone_probabilities(probabilities)
        for distance, text in details.items():
            self._zone_cards[distance][2].setText(text)

        # Служебная информация кадра: detected | points_in → points_out (+added) | time_ms.
        frame = result.get("frame") or {}
        parts = [f"detected: {int(result.get('detected') or 0)}"]
        pin, pout, added = frame.get("points_in"), frame.get("points_out"), frame.get("added")
        if pin is not None and pout is not None:
            sign = "+" if (added or 0) >= 0 else ""
            parts.append(f"points: {pin} → {pout} ({sign}{added or 0})")
        if result.get("time_ms") is not None:
            parts.append(f"{result['time_ms']} ms")
        self.statusBar().showMessage(" | ".join(parts), 0)

    def _on_cloud_ready(self, points) -> None:
        """Обновляет реальное облако в существующем mesh (без пересоздания add_mesh)."""
        try:
            points = np.asarray(points, dtype=np.float32)
        except (TypeError, ValueError) as exc:
            self.statusBar().showMessage(f"Ошибка формата облака: {exc}", 5000)
            return
        if points.ndim != 2 or points.shape[1] < 3:
            self.statusBar().showMessage("Неожиданный формат облака точек", 3000)
            return

        # Собираем новый PolyData и copy_from-им его в существующий: объект vtk
        # не меняется, актор «lidar_points» продолжает на него ссылаться, при этом
        # точки, скаляры и размер кадра обновляются целиком (между кадрами число
        # точек может отличаться — прямое присваивание .points это не переживёт).
        cloud = pv.PolyData(points[:, :3])
        if points.shape[1] >= 4:
            cloud.point_data["intensity"] = points[:, 3]
            cloud.set_active_scalars("intensity")
        self.point_cloud.copy_from(cloud)

        if points.shape[1] >= 4:
            self._enable_intensity_coloring(points[:, 3])
        self.plotter.render()

    def _enable_intensity_coloring(self, intensity) -> None:
        """Включает раскраску точек по интенсивности на существующем акторе."""
        actor = self.plotter.actors.get("lidar_points")
        if actor is None:
            return
        actor.mapper.scalar_visibility = True
        finite = intensity[np.isfinite(intensity)]
        if finite.size:
            actor.mapper.scalar_range = (float(finite.min()), float(finite.max()))

    def _prepare_real_viewport(self) -> None:
        """Настройка вьюпорта под реальные данные лидара (z вверх, тоннель вдоль -y)."""
        # Убираем декоративный масштаб демо: реальные точки отображаем 1:1.
        self.plotter.set_scale(xscale=1.0, yscale=1.0, zscale=1.0)
        # Камера — с +y сверху, взгляд вдоль тоннеля (-y) уходит вглубь экрана.
        self.plotter.camera_position = [
            (0.0, 150.0, 110.0),
            (0.0, 0.0, 2.0),
            (0.0, 0.0, 1.0),
        ]
        self.plotter.render()

    # --- Placeholder handlers ---------------------------------------------

    def _on_open_file(self) -> None:
        QMessageBox.information(
            self,
            "Открыть файл",
            "Загрузка облака точек будет реализована в Фазе 2.",
        )

    def closeEvent(self, event) -> None:
        """Останавливаем фоновые источники перед закрытием окна."""
        self._shutdown_streams()
        super().closeEvent(event)


def main():
    if __name__ == "__main__":
        app = QApplication(sys.argv)
        app.setStyleSheet(APP_STYLESHEET)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
