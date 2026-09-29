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

import random
import sys
from collections.abc import Mapping

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


class MainWindow(QMainWindow):
    """Main window: left panel with zone cards + table, right 3D viewport."""

    DEMO_INTERVAL_MS = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._demo_tick)

        self._setup_zone_cards()
        self._setup_zones_table()
        self._setup_viewport_placeholder()
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

    def _setup_viewport_placeholder(self) -> None:
        """Placeholder until pyvistaqt.QtInteractor is embedded (Phase 3)."""
        container = self.ui.viewportContainer
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        placeholder = QLabel(
            "3D-вьюпорт будет подключён на Фазе 3\n(PyVista / QtInteractor)",
            container,
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            "color: #5b6270; font-size: 14px; background-color: #16181d;"
        )
        layout.addWidget(placeholder)

    def _setup_connections(self) -> None:
        """Wire buttons, menu actions and the demo stream."""
        self.ui.openFileButton.clicked.connect(self._on_open_file)
        self.ui.streamButton.clicked.connect(self._toggle_demo_stream)
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

    # --- Demo stream (temporary, replaced by MLDataSource in Phase 5) ------

    def _demo_tick(self) -> None:
        probabilities = {
            distance: random.random() for distance in ZONE_DISTANCES
        }
        self.set_zone_probabilities(probabilities)

    def _toggle_demo_stream(self) -> None:
        if self._demo_timer.isActive():
            self._demo_timer.stop()
            self.ui.streamButton.setText("▶ Стрим")
            self.statusBar().showMessage("Демо-поток остановлен", 3000)
        else:
            self._demo_timer.start(self.DEMO_INTERVAL_MS)
            self.ui.streamButton.setText("⏸ Пауза")
            self.statusBar().showMessage(
                "Демо-поток запущен (mock-вероятности; в Фазе 5 заменим на MLDataSource)",
                5000,
            )

    # --- Placeholder handlers ---------------------------------------------

    def _on_open_file(self) -> None:
        QMessageBox.information(
            self,
            "Открыть файл",
            "Загрузка облака точек будет реализована в Фазе 2.",
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
