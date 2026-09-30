"""QAbstractTableModel implementation for the zone probability table.

This model is the single 'source of truth' for obstacle probabilities.
The three zone cards in the left panel are visual projections of the
same data (model-view pattern): cards and table always stay in sync.
"""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
)
from PySide6.QtGui import QColor, QFont

from app.core.constants import (
    COLOR_NONE,
    STATUS_COLORS,
    ZONE_DISTANCES,
    status_for_probability,
    status_label,
)

COLUMN_DISTANCE = 0
COLUMN_PROBABILITY = 1
COLUMN_STATUS = 2

HEADERS: tuple[str, ...] = ("Дистанция", "Вероятность", "Статус")


def _color_for_status(status: str) -> QColor:
    return QColor(STATUS_COLORS.get(status, COLOR_NONE))


class ZoneTableModel(QAbstractTableModel):
    """One row per zone (100/200/300 m), three columns as in HEADERS."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._probabilities: dict[int, float | None] = {
            distance: None for distance in ZONE_DISTANCES
        }

    # --- Qt model API ------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(ZONE_DISTANCES)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        distance = ZONE_DISTANCES[index.row()]
        probability = self._probabilities.get(distance)
        column = index.column()
        status = status_for_probability(probability)

        if role == Qt.ItemDataRole.DisplayRole:
            if column == COLUMN_DISTANCE:
                return f"{distance} м"
            if column == COLUMN_PROBABILITY:
                return "—" if probability is None else f"{probability * 100:.0f} %"
            if column == COLUMN_STATUS:
                return status_label(probability)
        elif role == Qt.ItemDataRole.ForegroundRole:
            if column in (COLUMN_PROBABILITY, COLUMN_STATUS):
                return _color_for_status(status)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        elif role == Qt.ItemDataRole.FontRole and column == COLUMN_PROBABILITY:
            font = QFont()
            font.setBold(True)
            return font
        return None

    # --- Public helpers ----------------------------------------------------

    def probability(self, distance: int) -> float | None:
        """Return the current probability for a zone (None if unknown)."""
        return self._probabilities.get(distance)

    def set_probability(self, distance: int, probability: float | None) -> None:
        """Update a single zone and emit dataChanged for its row."""
        if distance not in self._probabilities:
            return
        if self._probabilities[distance] == probability:
            return
        self._probabilities[distance] = probability
        row = ZONE_DISTANCES.index(distance)
        top_left = self.index(row, COLUMN_DISTANCE)
        bottom_right = self.index(row, COLUMN_STATUS)
        self.dataChanged.emit(top_left, bottom_right, [])

    def update_probabilities(
        self, probabilities: Mapping[int, float | None]
    ) -> None:
        """Bulk-update several zones in one shot (dataChanged-style refresh)."""
        changed = False
        for distance in ZONE_DISTANCES:
            if distance in probabilities and self._probabilities[distance] != probabilities[distance]:
                self._probabilities[distance] = probabilities[distance]
                changed = True
        if changed:
            top_left = self.index(0, COLUMN_DISTANCE)
            bottom_right = self.index(self.rowCount() - 1, COLUMN_STATUS)
            self.dataChanged.emit(top_left, bottom_right, [])