"""
Детектор: кадр лидара -> восстановленная моделью развёртка -> скопления добавленных точек.

    from lidar_detector import Detector

    det = Detector()                              # веса и таблицы из inference/artifacts
    res = det.process_points(points)              # (N, 4) x y z intensity или (N, 5) + ring
    for c in res.clusters:
        print(c["center"], c["extent_m"], c["points"])

    det.detect(points)                            # только ответ: 1 - в кадре есть скопление, 0 - нет

Что происходит с кадром:

  1. Облако -> развёртка 128 x 1024 (строка - луч, столбец - азимут с шагом
     0.1 град, значение - дальность). Если в облаке нет номера луча (ring),
     он восстанавливается по углу места точки (artifacts/elevation.npy).
  2. Всё вне рабочего сектора обнуляется: по 17 град с каждого края
     (range_image.CUT_LEFT / CUT_RIGHT) модель не видит.
  3. U-Net восстанавливает развёртку: достраивает дыры, поправляет дальности,
     убирает мусор.
  4. В объёме ищутся скопления точек, которые модель добавила (clusters.py),
     с порогами по зонам дальности из artifacts/cluster_zones_3d.json.

Зависимости: numpy, torch.
"""

import glob
import json
import os
import sqlite3

import numpy as np

from . import clusters as cl
from .model import load_model, restore
from .range_image import AZ_MIN, AZ_STEP, apply_sector, points_to_range, ring_from_elevation, sector_columns
from .rosbag import POINTCLOUD2_TYPE, list_topics, parse_pointcloud2

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ARTIFACTS = os.path.join(os.path.dirname(HERE), "artifacts")


# --------------------------------------------------------------------------- #
# результат одного кадра
# --------------------------------------------------------------------------- #

class Result:
    """Всё, что известно о кадре после прогона. Картинки - numpy (128, 1024)."""

    def __init__(self, range_in, intensity_in, range_out, occupancy, junk, labels, clusters, added, elevation):
        self.range_in = range_in            # вход модели, м (0 - пусто), уже обрезан по сектору
        self.intensity_in = intensity_in    # интенсивность входа, 0..255
        self.range_out = range_out          # ответ модели, м (0 - точки нет)
        self.occupancy = occupancy          # вероятность «здесь есть точка»
        self.junk = junk                    # вероятность «входная точка - мусор»
        self.labels = labels                # int32: 0 - не скопление, k - скопление с id k
        self.clusters = clusters            # список dict, см. README
        self.added = added                  # bool: добавленные моделью пиксели, где шёл поиск
        self._elevation = elevation

    @property
    def detected(self):
        """1 - в кадре найдено хотя бы одно скопление, 0 - нет."""
        return int(len(self.clusters) > 0)

    def _points(self, rng, mask, extra):
        rows, cols = np.nonzero(mask)
        r = rng[rows, cols].astype(np.float64)
        az = np.radians(AZ_MIN + (cols + 0.5) * AZ_STEP)
        el = np.radians(self._elevation[rows])
        out = np.empty((len(r), 3 + len(extra)), np.float32)
        out[:, 0] = r * np.cos(el) * np.cos(az)
        out[:, 1] = r * np.cos(el) * np.sin(az)
        out[:, 2] = r * np.sin(el)
        for j, img in enumerate(extra):
            out[:, 3 + j] = img[rows, cols]
        return out

    def points_in(self):
        """Вход модели точками: (N, 4) x y z intensity."""
        return self._points(self.range_in, self.range_in > 0, [self.intensity_in])

    def points_out(self):
        """Ответ модели точками: (N, 5) x y z added cluster_id.

        added - 1, если точку добавила модель (во входе на этом месте пусто);
        cluster_id - номер скопления или 0.
        """
        vo = self.range_out > 0
        added_any = (vo & (self.range_in <= 0)).astype(np.float32)
        return self._points(self.range_out, vo, [added_any, self.labels.astype(np.float32)])


# --------------------------------------------------------------------------- #
# детектор
# --------------------------------------------------------------------------- #

class Detector:
    """Загружает веса и таблицы один раз, потом обрабатывает кадры по одному.

    artifacts - папка с model.pt, elevation.npy, structural_empty.npy,
    added_rate.npy (необязательно), cluster_zones_3d.json (необязательно).
    device - "cuda", "cpu" или None (сам выберет cuda, если есть).
    """

    def __init__(self, artifacts=DEFAULT_ARTIFACTS, device=None, weights=None, zones=None):
        self.artifacts = artifacts
        path = lambda name: os.path.join(artifacts, name)
        self.model, self.device, self.weights_meta = load_model(weights or path("model.pt"), device)
        self.elevation = np.load(path("elevation.npy")).astype(np.float64)
        self.struct = np.load(path("structural_empty.npy")).astype(bool)
        self.rate = np.load(path("added_rate.npy")) if os.path.exists(path("added_rate.npy")) else None
        self.zones_file = path("cluster_zones_3d.json")
        self.zones = cl.check_zones(zones) if zones else cl.load_zones(self.zones_file)
        self.sector = sector_columns()

    # --- вход ---------------------------------------------------------------

    def to_range(self, points):
        """Облако -> (дальность м, интенсивность 0..255) развёртки, уже обрезанные по сектору.

        points - numpy structured array с полями x, y, z, intensity (и, если есть, ring)
        или обычный массив (N, 4) x y z intensity / (N, 5) x y z intensity ring.
        Нулевые точки (луч не вернулся) пропускаются сами.
        """
        if points.dtype.names:
            x, y, z, it = (points[k] for k in ("x", "y", "z", "intensity"))
            ring = points["ring"] if "ring" in points.dtype.names else None
        else:
            p = np.asarray(points)
            x, y, z, it = p[:, 0], p[:, 1], p[:, 2], p[:, 3]
            ring = p[:, 4].astype(np.int64) if p.shape[1] > 4 else None
        if ring is None:
            ring = ring_from_elevation(x, y, z, self.elevation)
        rng, inten, _ = points_to_range(x, y, z, it, ring)
        rng, inten = apply_sector(rng, inten)
        return rng, inten

    # --- обработка ------------------------------------------------------------

    def process_images(self, range_in, intensity_in, zones=None):
        """Развёртка входа -> Result. range_in, intensity_in - (128, 1024)."""
        r_in, i_in = apply_sector(np.asarray(range_in, np.float32), np.asarray(intensity_in, np.float32))
        r_out, occ, junk = restore(self.model, self.device, r_in, i_in)
        r_out, occ, junk = apply_sector(r_out, occ, junk)
        labels, found, added = cl.find_clusters(r_in, r_out, self.struct, self.elevation,
                                                zones or self.zones, self.rate)
        return Result(r_in, i_in, r_out, occ, junk, labels, found, added, self.elevation)

    def process_points(self, points, zones=None):
        """Облако точек одного кадра -> Result."""
        return self.process_images(*self.to_range(points), zones=zones)

    def process_message(self, blob, zones=None):
        """Сырое сообщение sensor_msgs/PointCloud2 (CDR-байты, как в rosbag2) -> Result."""
        return self.process_points(parse_pointcloud2(blob)["points"], zones=zones)

    def detect(self, points, zones=None):
        """Облако точек (или сырое сообщение PointCloud2 в байтах) -> 1, если в кадре есть скопление, иначе 0."""
        if isinstance(points, (bytes, bytearray, memoryview)):
            return self.process_message(bytes(points), zones=zones).detected
        return self.process_points(points, zones=zones).detected


# --------------------------------------------------------------------------- #
# запись rosbag2 с доступом к кадру по номеру
# --------------------------------------------------------------------------- #

class Bag:
    """Кадры PointCloud2 из записи rosbag2 (папка с .db3 или один .db3), по времени."""

    def __init__(self, path, topic=None):
        files = sorted(glob.glob(os.path.join(path, "*.db3"))) if os.path.isdir(path) else [path]
        if not files:
            raise FileNotFoundError("в %s нет файлов .db3" % path)
        if topic is None:
            pcs = sorted({name for _i, name, t in list_topics(files[0]) if t == POINTCLOUD2_TYPE})
            if len(pcs) != 1:
                raise ValueError("топиков PointCloud2: %s - укажите topic" % (pcs or "нет"))
            topic = pcs[0]
        self.topic, self.files = topic, files
        self.name = os.path.basename(os.path.normpath(path if os.path.isdir(path) else os.path.dirname(path)))
        self.items = []
        for f in files:
            con = sqlite3.connect("file:%s?mode=ro" % f, uri=True)
            try:
                for mid, ts in con.execute("SELECT m.id, m.timestamp FROM messages m JOIN topics t ON t.id = m.topic_id "
                                           "WHERE t.name = ?", (topic,)):
                    self.items.append((ts, f, mid))
            finally:
                con.close()
        self.items.sort()
        self._cons = {}

    def __len__(self):
        return len(self.items)

    def read(self, i):
        """-> (метка времени, нс; CDR-байты сообщения)."""
        ts, f, mid = self.items[i]
        con = self._cons.get(f)
        if con is None:
            con = self._cons[f] = sqlite3.connect("file:%s?mode=ro" % f, uri=True, check_same_thread=False)
        return ts, con.execute("SELECT data FROM messages WHERE id = ?", (mid,)).fetchone()[0]
