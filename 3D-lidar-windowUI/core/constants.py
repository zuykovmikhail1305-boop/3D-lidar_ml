"""Shared constants and pure logic for obstacle probability zones.

All functions in this module are pure and unit-testable without any
GUI or rendering stack (pytest-friendly).
"""

from __future__ import annotations

# Zone distances in meters, in the order shown as table rows / cards.
ZONE_DISTANCES: tuple[int, ...] = (100, 200, 300)

# Probability thresholds for status classification.
WARN_THRESHOLD: float = 0.3
STOP_THRESHOLD: float = 0.6

# Status identifiers used for QSS dynamic-property styling.
STATUS_NONE = "none"
STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_STOP = "stop"

STATUS_LABELS: dict[str, str] = {
    STATUS_NONE: "НЕТ ДАННЫХ",
    STATUS_OK: "ОК",
    STATUS_WARN: "ВНИМАНИЕ",
    STATUS_STOP: "СТОП",
}

# Accent colors (hex) used by QSS and the table model.
COLOR_NONE = "#7f8c8d"
COLOR_OK = "#2ecc71"
COLOR_WARN = "#f1c40f"
COLOR_STOP = "#e74c3c"

STATUS_COLORS: dict[str, str] = {
    STATUS_NONE: COLOR_NONE,
    STATUS_OK: COLOR_OK,
    STATUS_WARN: COLOR_WARN,
    STATUS_STOP: COLOR_STOP,
}


def status_for_probability(probability: float | None) -> str:
    """Map a probability value to a status identifier.

    Args:
        probability: obstacle probability in [0, 1], or None if unknown.

    Returns:
        One of STATUS_NONE / STATUS_OK / STATUS_WARN / STATUS_STOP.
    """
    if probability is None:
        return STATUS_NONE
    if probability >= STOP_THRESHOLD:
        return STATUS_STOP
    if probability >= WARN_THRESHOLD:
        return STATUS_WARN
    return STATUS_OK


def status_label(probability: float | None) -> str:
    """Return the human-readable status label for a probability value."""
    return STATUS_LABELS[status_for_probability(probability)]