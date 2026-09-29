"""Детектор скоплений на лидарных кадрах: U-Net восстанавливает развёртку, скопления ищутся в объёме."""

from .detector import Bag, Detector, Result

__all__ = ["Bag", "Detector", "Result"]
