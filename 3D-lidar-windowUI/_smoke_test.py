"""Temporary smoke test for the Phase 1 UI skeleton.

Run from the 3D-lidar-windowUI directory:
    .venv\\Scripts\\python.exe -m _smoke_test
"""

from __future__ import annotations

import os
import sys
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from mainwindow import APP_STYLESHEET, MainWindow
from zonetable_model import ZoneTableModel


def has_border_color(img, card, red, green, blue, tolerance=70) -> bool:
    """Scan the top border row of a card for a color near (r, g, b)."""
    origin = card.mapTo(card.window(), card.rect().topLeft())
    y = origin.y() + 1  # top border row (2px border)
    for x in range(origin.x() + 4, origin.x() + card.width() - 4):
        c = img.pixelColor(x, y)
        if (
            abs(c.red() - red) < tolerance
            and abs(c.green() - green) < tolerance
            and abs(c.blue() - blue) < tolerance
        ):
            return True
    return False


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.resize(1440, 900)
    window.set_zone_probabilities({100: 0.12, 200: 0.45, 300: 0.87})
    window.show()
    app.processEvents()

    # --- Assertions on zone cards -----------------------------------------
    assert window.ui.zoneProb_100.text() == "12 %", window.ui.zoneProb_100.text()
    assert window.ui.zoneProb_200.text() == "45 %", window.ui.zoneProb_200.text()
    assert window.ui.zoneProb_300.text() == "87 %", window.ui.zoneProb_300.text()
    assert window.ui.zoneProgress_300.value() == 87
    assert window.ui.zoneStatus_100.text() == "ОК"
    assert window.ui.zoneStatus_200.text() == "ВНИМАНИЕ"
    assert window.ui.zoneStatus_300.text() == "СТОП"

    # --- Assertions on the table model ------------------------------------
    model: ZoneTableModel = window._table_model
    assert model.rowCount() == 3 and model.columnCount() == 3
    assert model.probability(300) == 0.87
    cell_100 = model.index(0, 1).data(Qt.ItemDataRole.DisplayRole)
    cell_300 = model.index(2, 2).data(Qt.ItemDataRole.DisplayRole)
    assert cell_100 == "12 %", cell_100
    assert cell_300 == "СТОП", cell_300

    # --- Offscreen render + pixel verification (deterministic values) ------
    pix = window.grab()
    img = pix.toImage()

    assert has_border_color(img, window.ui.zoneCard_300, 231, 76, 60), "300m red border"
    assert has_border_color(img, window.ui.zoneCard_200, 241, 196, 15), "200m yellow border"
    assert has_border_color(img, window.ui.zoneCard_100, 46, 204, 113), "100m green border"
    assert window.ui.zoneCard_300.property("status") == "stop"
    assert window.ui.zoneCard_200.property("status") == "warn"
    assert window.ui.zoneCard_100.property("status") == "ok"

    corner = img.pixelColor(10, 40)
    assert corner.red() < 80 and corner.green() < 80, "background not dark"

    ok = pix.save("_smoke_preview.png")

    # --- Demo stream produces fresh probabilities --------------------------
    window._demo_tick()
    assert 0.0 <= (model.probability(200) or 0.0) <= 1.0

    # --- Thread-safety: emit the signal from a worker thread ----------------
    def _emit_from_thread() -> None:
        window.zoneProbabilitiesUpdated.emit({100: 0.9, 200: 0.9, 300: 0.9})

    worker = threading.Thread(target=_emit_from_thread)
    worker.start()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and window.ui.zoneProb_300.text() != "90 %":
        app.processEvents()
        time.sleep(0.01)
    worker.join(timeout=1.0)
    assert window.ui.zoneProb_300.text() == "90 %", "signal not delivered from thread"
    assert window.ui.zoneStatus_300.text() == "СТОП"

    print(
        f"SMOKE TEST OK | preview saved={ok} | size={pix.width()}x{pix.height()}"
        " | statuses + border colors verified"
    )

    window.close()
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())