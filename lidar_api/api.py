r"""
Поиск скоплений на одном кадре лидара: numpy-массив точек на входе, JSON на выходе.

    from api import analyze, analyze_json

    info = analyze(points)                   # numpy-массив (N, 4) x y z intensity -> dict
    text = analyze_json(points)              # то же, сразу строкой JSON

points - облако одного кадра, уже в памяти:
    (N, 4) x y z intensity, (N, 5) x y z intensity ring
    или structured array с полями x, y, z, intensity (и, если есть, ring).
Файлы функция не читает.

Для проверки из командной строки (файл .npy читается здесь же и передаётся массивом):

    python api.py D:\dataset_numpy\doubleT_obstacle\points\000000.npy

Модель грузится один раз при первом вызове и дальше переиспользуется.

Ответ (dict, все значения - обычные типы Python, json.dumps работает сразу):

    {
      "detected": 1,                         1 - хотя бы в одном блоке есть скопление, 0 - нигде
      "blocks": [                            блоки по дальности от лидара
        {"block": "0-100", "from_m": 0, "to_m": 100,
         "detected": 1,                      1 - в этом блоке есть скопление, 0 - нет
         "clusters": 1,                      сколько скоплений в блоке
         "nearest_m": 72.35},                расстояние до ближайшего скопления блока, м (null, если нет)
        {"block": "100-200", ..., "detected": 0, "clusters": 0, "nearest_m": null},
        {"block": "200-300", ...}
      ],
      "clusters": [                          все скопления, от ближнего к дальнему
        {"id": 1, "block": "0-100",
         "distance_m": 72.35,                расстояние от лидара до скопления (медиана по его точкам), м
         "distance_min_m": 71.9,             до ближайшей точки скопления, м
         "center": [x, y, z], "min": [..], "max": [..],   рамка, м, система координат лидара
         "size_m": 1.11, "extent_m": [dx, dy, dz], "points": 6}
      ],
      "frame": {"points_in": 62694, "points_out": 62885, "added": 230},
      "time_ms": 85.3
    }

Система координат - лидара, м: z вверх, вперёд по тоннелю - -y.

Зависимости: numpy, torch.
"""

import json
import os
import sys
import threading
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from lidar_detector import Detector  # noqa: E402

BLOCKS = [(0, 100), (100, 200), (200, 300)]      # м - блоки ответа по дальности от лидара

_detector = None
_lock = threading.Lock()


def get_detector(device=None):
    """Детектор (модель + пороги из artifacts/), один на процесс. device - "cuda", "cpu" или None (сам)."""
    global _detector
    with _lock:
        if _detector is None:
            _detector = Detector(os.path.join(HERE, "artifacts"), device=device)
    return _detector


def check_points(arr):
    """numpy-массив кадра -> облако точек для детектора; неподходящий массив - ошибка.

    Облако - (N, 4) x y z intensity, (N, 5) + ring, или structured array с полями x, y, z, intensity (и ring).
    """
    if not isinstance(arr, np.ndarray):
        raise TypeError("ожидается numpy-массив точек, а пришёл %s" % type(arr).__name__)
    if arr.dtype.names:
        missing = [k for k in ("x", "y", "z", "intensity") if k not in arr.dtype.names]
        if missing:
            raise ValueError("в массиве нет полей %s" % ", ".join(missing))
        return arr.reshape(-1)
    if arr.ndim != 2 or arr.shape[1] < 4:
        raise ValueError("ожидается массив (N, 4) x y z intensity или (N, 5) + ring, а пришёл %s" % (arr.shape,))
    arr = arr[:, :5].astype(np.float32, copy=False)
    return arr[np.isfinite(arr[:, :3]).all(axis=1)]


def _block_name(a, b):
    return "%d-%d" % (a, b)


def analyze(points, device=None):
    """numpy-массив точек кадра -> dict со скоплениями по блокам 0-100, 100-200, 200-300 м."""
    points = check_points(points)
    det = get_detector(device)                       # первый вызов грузит модель - в time_ms не входит
    t0 = time.perf_counter()
    with _lock:                                      # модель одна на процесс - кадры по очереди
        res = det.process_points(points)

    clusters = []
    for c in res.clusters:
        mask = res.labels == c["id"]
        dist = float(c["range_m"])
        block = next((_block_name(a, b) for a, b in BLOCKS if a <= dist < b), None)
        clusters.append({
            "id": int(c["id"]), "block": block,
            "distance_m": round(dist, 2),
            "distance_min_m": round(float(res.range_out[mask].min()), 2) if mask.any() else round(dist, 2),
            "center": c["center"], "min": c["min"], "max": c["max"],
            "size_m": c["size_m"], "extent_m": c["extent_m"], "points": int(c["points"]),
        })
    clusters.sort(key=lambda c: c["distance_m"])

    blocks = []
    for a, b in BLOCKS:
        inside = [c for c in clusters if c["block"] == _block_name(a, b)]
        blocks.append({"block": _block_name(a, b), "from_m": a, "to_m": b,
                       "detected": int(bool(inside)), "clusters": len(inside),
                       "nearest_m": inside[0]["distance_m"] if inside else None})

    return {
        "detected": int(any(bl["detected"] for bl in blocks)),
        "blocks": blocks,
        "clusters": clusters,
        "frame": {"points_in": int((res.range_in > 0).sum()), "points_out": int((res.range_out > 0).sum()),
                  "added": int(res.added.sum())},
        "time_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


def analyze_json(points, device=None, indent=None):
    """То же, что analyze, но сразу строкой JSON."""
    return json.dumps(analyze(points, device), ensure_ascii=False, indent=indent)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("python api.py <кадр.npy> [ещё.npy ...]")
    for path in sys.argv[1:]:
        print(analyze_json(np.load(path), indent=2))
