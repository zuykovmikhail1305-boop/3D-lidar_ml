"""ROS2-источник данных для GUI (3D-lidar-windowUI).

RosWorker живёт в отдельном QThread и слушает два топика:

- ``lidar_points`` (sensor_msgs/PointCloud2) → numpy-массив (N, 4) x y z intensity
  → сигнал ``cloud_ready`` → обновление 3D-вьюпорта.
- ``model_out`` (std_msgs/String, JSON от src/model/model/node.py)
  → сигнал ``prediction_ready`` → обновление карточек зон и таблицы.

ROS2 опционален: все импорты rclpy спрятаны за try/except ImportError.
Без rclpy ``RosWorker.available()`` возвращает False, воркер не стартует,
и MainWindow переключается на демо-режим (mock-данные).

Колбэки rclpy выполняются в потоке воркера (spin идёт здесь же), поэтому
наружу данные передаются ТОЛЬКО через потокобезопасные Qt-сигналы
(queued connection между потоком воркера и GUI-потоком).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QThread, Signal

try:  # ROS2 ставится вместе с дистрибутивом ROS2 (apt/rosdep), а не через pip
    import rclpy
    from rclpy.qos import qos_profile_sensor_data, qos_profile_services_default
    from sensor_msgs.msg import PointCloud2
    from sensor_msgs_py import point_cloud2 as pc2
    from std_msgs.msg import String

    ROS_AVAILABLE = True
except ImportError:  # pragma: no cover — зависит от окружения
    rclpy = None
    qos_profile_sensor_data = qos_profile_services_default = None
    PointCloud2 = None
    String = None
    pc2 = None
    ROS_AVAILABLE = False

LIDAR_TOPIC = "lidar_points"
MODEL_TOPIC = "model_out"
NODE_NAME = "model_ui"
SPIN_TIMEOUT_S = 0.1


def _cloud_to_numpy(msg) -> np.ndarray:
    """PointCloud2 → np.ndarray (N, 4) float32: x, y, z, intensity.

    Основной путь — read_points_numpy (быстро, без цикла по точкам).
    Если поле intensity отсутствует или формат другой — собираем массив
    вручную через read_points с пропуском NaN-точек.
    """
    if pc2 is None:
        raise RuntimeError("sensor_msgs_py недоступен")
    try:
        pts = pc2.read_points_numpy(msg, field_names=("x", "y", "z", "intensity"))
    except ValueError:
        rows = [
            (p.x, p.y, p.z, p.intensity)
            for p in pc2.read_points(
                msg, field_names=("x", "y", "z", "intensity"), skip_nans=True
            )
        ]
        pts = np.asarray(rows, dtype=np.float32) if rows else np.zeros((0, 4), dtype=np.float32)
    pts = np.asarray(pts, dtype=np.float32)
    if pts.dtype.names:  # structured array → плоский массив (N, 4)
        names = pts.dtype.names
        cols = [pts[name] for name in ("x", "y", "z", "intensity") if name in names]
        if len(cols) != 4:
            raise ValueError("в PointCloud2 нет полей x/y/z/intensity")
        pts = np.column_stack(cols)
    # Отбрасываем невалидные точки (NaN/inf) — детектор и вьюпорт их не любят.
    pts = pts[np.isfinite(pts[:, :3]).all(axis=1)]
    return np.ascontiguousarray(pts, dtype=np.float32)


class RosWorker(QThread):
    """QThread-воркер: ROS2-подписки → Qt-сигналы для GUI-потока."""

    #: np.ndarray (N, 4) x y z intensity — реальное облако точек кадра.
    cloud_ready = Signal(object)
    #: str — JSON-строка результата модели (контракт lidar_api/api.py).
    prediction_ready = Signal(str)
    #: str — сообщение об ошибке (показывается в statusbar).
    error = Signal(str)

    @staticmethod
    def available() -> bool:
        """True, если rclpy и sensor_msgs_py установлены — можно стартовать стрим."""
        return ROS_AVAILABLE

    def __init__(self, parent=None):
        super().__init__(parent)
        self._owns_init = False

    def run(self) -> None:
        """Точка входа потока: инициализация rclpy, подписки, цикл spin."""
        if not ROS_AVAILABLE:
            self.error.emit("ROS2 (rclpy) не установлен — включён демо-режим")
            return

        node = None
        self._owns_init = False
        try:
            try:
                already_ok = bool(rclpy.ok())
            except Exception:  # noqa: BLE001 — до инициализации контекст ещё не готов
                already_ok = False
            if not already_ok:
                rclpy.init()
                self._owns_init = True

            node = rclpy.create_node(NODE_NAME)
            node.create_subscription(
                PointCloud2, LIDAR_TOPIC, self._on_pointcloud, qos_profile_sensor_data
            )
            node.create_subscription(
                String, MODEL_TOPIC, self._on_model_out, qos_profile_services_default
            )

            # Цикл событий ROS2 в этом же потоке; requestInterruption() останавливает нас.
            while not self.isInterruptionRequested():
                rclpy.spin_once(node, timeout_sec=SPIN_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 — ошибка уходит сигналом, без падения GUI
            self.error.emit(f"Ошибка ROS2-потока: {exc}")
        finally:
            if node is not None:
                try:
                    node.destroy_node()
                except Exception:  # noqa: BLE001
                    pass
            if self._owns_init and rclpy.ok():
                try:
                    rclpy.shutdown()
                except Exception:  # noqa: BLE001
                    pass

    # --- Колбэки rclpy (выполняются в потоке воркера!) -----------------------

    def _on_pointcloud(self, msg) -> None:
        """lidar_points → numpy-массив → cloud_ready."""
        try:
            points = _cloud_to_numpy(msg)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(f"Ошибка конвертации облака точек: {exc}")
            return
        self.cloud_ready.emit(points)

    def _on_model_out(self, msg) -> None:
        """model_out → prediction_ready (JSON пересылаем как есть)."""
        data = getattr(msg, "data", None)
        if data:
            self.prediction_ready.emit(data)