"""
Поиск скоплений добавленных моделью точек - в объёме, по расстояниям в метрах.

Та же логика, что find_clusters_3d.py в корне репозитория:

  1. Добавленная точка - пиксель, где во входе пусто, а у модели есть
     дальность. Не рассматриваются: пиксели вне рабочего сектора, места, где
     лидар пуст всегда (structural_empty.npy), выключенные зоны и «привычки»
     модели - пиксели, куда она добавляет точки чаще, чем habit зоны
     (added_rate.npy).
  2. Точки переводятся в x, y, z и прореживаются кубиками 5 см; кубик помнит,
     сколько точек в него попало.
  3. Соседи - точки ближе радиуса max(radius зоны, 0.01 * дальность).
  4. Скопление - связная группа соседей, у которой хватает точек (порог
     min_points задан для начала зоны и падает как 1/r^2, не ниже 6), размер
     (самая длинная сторона рамки) от min_size до max_size и толщина (самая
     короткая сторона) не меньше min_thickness.

Точка относится к зоне по своей дальности; соседи ищутся внутри зоны.

Зависимости: numpy.
"""

import json
import os

import numpy as np

from .range_image import AZ_MIN, AZ_STEP, H, W, sector_columns

DEFAULT_EDGES = [0, 50, 100, 150, 200, 250, 300]    # м - границы зон по дальности


def zone_index(r, zones):
    """Дальность -> номер зоны; -1, если ни в одну не попала."""
    edges = np.array([z["from"] for z in zones] + [zones[-1]["to"]])
    k = np.searchsorted(edges, r, side="right") - 1
    return np.where((k >= 0) & (k < len(zones)), k, -1)


DEFAULTS = {
    "voxel": 0.05,            # м - кубик прореживания
    "radius_per_m": 0.01,     # радиус соседства растёт на 1 см на каждый метр дальности
    "min_range": 0.5,         # м - ближе лежит сама платформа лидара
    "ref_range": 2.0,         # м - ближе этого порог точек не растёт
    "min_points_floor": 6,    # меньше шести точек - не скопление ни на какой дальности
}
ZONE_DEFAULTS = {"enabled": True, "radius": 0.15, "min_points": 10, "min_size": 0.1, "max_size": 6.0,
                 "min_thickness": 0.1, "habit": 0.2}
# min_points - сколько точек нужно в начале зоны; дальше порог падает как 1/r^2
ZONE_MIN_POINTS = {0: 200, 50: 6}
ZONE_FIELDS = ("enabled", "radius", "min_points", "min_size", "max_size", "min_thickness", "habit")


# --------------------------------------------------------------------------- #
# зоны
# --------------------------------------------------------------------------- #

def default_zones(edges=DEFAULT_EDGES):
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        z = {"from": float(a), "to": float(b), **ZONE_DEFAULTS}
        z["min_points"] = ZONE_MIN_POINTS.get(int(a), DEFAULTS["min_points_floor"])
        out.append(z)
    return out


def check_zones(zones):
    if not zones:
        raise ValueError("нет ни одной зоны")
    out = []
    for i, z in enumerate(sorted(zones, key=lambda z: float(z["from"]))):
        a, b = float(z["from"]), float(z["to"])
        if b <= a:
            raise ValueError("зона %d: to (%.1f) должно быть больше from (%.1f)" % (i, b, a))
        if out and abs(out[-1]["to"] - a) > 1e-6:
            raise ValueError("зоны должны идти встык: %.1f и %.1f" % (out[-1]["to"], a))
        q = {"from": a, "to": b, "enabled": bool(z.get("enabled", True)),
             "radius": max(0.01, float(z.get("radius", ZONE_DEFAULTS["radius"]))),
             "min_points": max(1, int(z.get("min_points", ZONE_DEFAULTS["min_points"]))),
             "min_size": max(0.0, float(z.get("min_size", ZONE_DEFAULTS["min_size"]))),
             "max_size": float(z.get("max_size", ZONE_DEFAULTS["max_size"])),
             "min_thickness": max(0.0, float(z.get("min_thickness", ZONE_DEFAULTS["min_thickness"]))),
             "habit": float(z.get("habit", ZONE_DEFAULTS["habit"]))}
        if q["max_size"] <= q["min_size"]:
            raise ValueError("зона %.0f-%.0f: max_size должен быть больше min_size" % (a, b))
        out.append(q)
    return out


def load_zones(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return check_zones(json.load(fh)["zones"])
    return default_zones()


def save_zones(zones, path):
    zones = check_zones(zones)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"note": "пороги объёмного поиска скоплений по зонам дальности, м; см. lidar_detector/clusters.py",
                   "zones": zones}, fh, indent=2, ensure_ascii=False)
    return zones


# --------------------------------------------------------------------------- #
# геометрия
# --------------------------------------------------------------------------- #

def required_points(r, zone, cfg=None):
    """Сколько точек нужно скоплению на дальности r в этой зоне.

    min_points зоны - порог в её начале. На одном и том же предмете точек в
    (r0 / r)^2 раз меньше, чем на дальности r0, - так же падает и порог, но не
    ниже min_points_floor.
    """
    cfg = {**DEFAULTS, **(cfg or {})}
    r0 = max(zone["from"], cfg["ref_range"])
    r = np.maximum(np.asarray(r, np.float64), r0)
    return np.maximum(cfg["min_points_floor"], np.ceil(zone["min_points"] * (r0 / r) ** 2)).astype(int)


def pixels_to_xyz(rows, cols, r, elevation):
    az = np.radians(AZ_MIN + (cols + 0.5) * AZ_STEP)
    el = np.radians(np.asarray(elevation, np.float64)[rows])
    return np.stack([r * np.cos(el) * np.cos(az), r * np.cos(el) * np.sin(az), r * np.sin(el)], axis=1)


def _key(c):
    """Целые координаты кубика (n, 3) -> один int64-ключ."""
    c = c + (1 << 20)
    return (c[:, 0] << 42) | (c[:, 1] << 21) | c[:, 2]


OFFSETS27 = np.array([(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)], np.int64)


def neighbor_pairs(p, eps, cell):
    """Пары (i, j), i < j, с расстоянием меньше max(eps_i, eps_j). Сетка с шагом cell >= max(eps)."""
    n = len(p)
    if n < 2:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    c = np.floor(p / cell).astype(np.int64)
    key = _key(c)
    order = np.argsort(key, kind="stable")
    ks = key[order]
    us, vs = [], []
    for off in OFFSETS27:
        nk = _key(c + off)
        s = np.searchsorted(ks, nk, "left")
        e = np.searchsorted(ks, nk, "right")
        cnt = e - s
        tot = int(cnt.sum())
        if tot == 0:
            continue
        i = np.repeat(np.arange(n), cnt)
        start = np.repeat(s - np.concatenate([[0], np.cumsum(cnt)[:-1]]), cnt)
        j = order[start + np.arange(tot)]
        keep = i < j
        i, j = i[keep], j[keep]
        d2 = ((p[i] - p[j]) ** 2).sum(axis=1)
        lim = np.maximum(eps[i], eps[j])
        near = d2 < lim * lim
        us.append(i[near])
        vs.append(j[near])
    if not us:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    return np.concatenate(us), np.concatenate(vs)


def _components(n, u, v):
    """Вершины 0..n-1, рёбра (u, v) -> метка компоненты у каждой вершины."""
    lab = np.arange(n)
    if len(u) == 0:
        return lab
    while True:
        lu, lv = lab[u], lab[v]
        m = np.minimum(lu, lv)
        new = lab.copy()
        np.minimum.at(new, lu, m)                # корень цепляется к меньшему корню
        np.minimum.at(new, lv, m)
        while True:                              # сжатие путей: каждый смотрит сразу на корень
            nxt = new[new]
            if np.array_equal(nxt, new):
                break
            new = nxt
        if np.array_equal(new, lab):
            return lab
        lab = new


# --------------------------------------------------------------------------- #
# поиск
# --------------------------------------------------------------------------- #

def added_mask(r_in, r_out, struct, zones, rate=None, cfg=None):
    """Добавленные моделью пиксели, где ищем, и номер зоны каждого пикселя."""
    cfg = {**DEFAULTS, **(cfg or {})}
    zi = zone_index(r_out, zones)
    enabled = np.array([z["enabled"] for z in zones] + [False])
    habit = np.array([z["habit"] for z in zones] + [0.0])
    ignore = struct | ~enabled[zi]
    if rate is not None:
        h = habit[zi]
        ignore |= (h > 0) & (rate > h)
    added = (r_out > cfg["min_range"]) & (r_in <= 0) & ~ignore & sector_columns()   # вне сектора не ищем
    return added, zi


def find_clusters(r_in, r_out, struct, elevation, zones, rate=None, cfg=None):
    """Одна пара картинок -> (метки H x W: 0 - нет, k - скопление k; список скоплений; маска добавленных в поиске)."""
    cfg = {**DEFAULTS, **(cfg or {})}
    r_in = np.asarray(r_in, np.float32)
    r_out = np.asarray(r_out, np.float32)
    added, zi = added_mask(r_in, r_out, struct, zones, rate, cfg)
    labels = np.zeros((H, W), np.int32)
    clusters = []
    rows, cols = np.nonzero(added)
    if len(rows) == 0:
        return labels, clusters, added
    rng = r_out[rows, cols].astype(np.float64)
    xyz = pixels_to_xyz(rows, cols, rng, elevation)
    pzone = zi[rows, cols]

    v = cfg["voxel"]
    k = 0
    for z_id, z in enumerate(zones):
        sel = np.flatnonzero(pzone == z_id)
        if not z["enabled"] or len(sel) < cfg["min_points_floor"]:
            continue
        # 2. кубики: центр - среднее точек, вес - сколько точек попало
        vk = _key(np.floor(xyz[sel] / v).astype(np.int64))
        _, inv, cnt = np.unique(vk, return_inverse=True, return_counts=True)
        inv = inv.ravel()
        nv = len(cnt)
        cen = np.stack([np.bincount(inv, weights=xyz[sel, a], minlength=nv) for a in range(3)], axis=1) / cnt[:, None]
        vr = np.linalg.norm(cen, axis=1)
        # 3. соседи: радиус растёт с дальностью
        eps = np.maximum(z["radius"], cfg["radius_per_m"] * vr)
        u, w = neighbor_pairs(cen, eps, max(float(eps.max()), v))
        lab = _components(nv, u, w)
        _, comp = np.unique(lab, return_inverse=True)
        comp = comp.ravel()
        # 4. пороги зоны
        n_pts = np.bincount(comp, weights=cnt)
        cand = np.flatnonzero(n_pts >= cfg["min_points_floor"])
        for c in cand[np.argsort(-n_pts[cand])]:
            m = comp == c
            # порог точек - по дальности скопления (медиана по кубикам с весом точек)
            if n_pts[c] < required_points(float(np.median(np.repeat(vr[m], cnt[m]))), z, cfg):
                continue
            lo = cen[m].min(axis=0) - v / 2
            hi = cen[m].max(axis=0) + v / 2
            size = float((hi - lo).max())
            if size < z["min_size"] or size > z["max_size"]:
                continue
            # толщина - самая короткая сторона рамки по точкам, без полукубиков по краям:
            # плоский кусок стены или пола её почти не имеет
            if float((cen[m].max(axis=0) - cen[m].min(axis=0)).min()) < z["min_thickness"]:
                continue
            k += 1
            pts = sel[m[inv]]                      # исходные точки этого скопления
            labels[rows[pts], cols[pts]] = k
            p = xyz[pts]
            lo, hi = p.min(axis=0), p.max(axis=0)
            clusters.append({
                "id": k, "zone": z_id, "points": int(len(pts)), "voxels": int(m.sum()),
                "size_m": round(float((hi - lo).max()), 3), "extent_m": np.round(hi - lo, 3).tolist(),
                "range_m": round(float(np.median(rng[pts])), 2), "center": np.round((lo + hi) / 2, 3).tolist(),
                "min": np.round(lo, 3).tolist(), "max": np.round(hi, 3).tolist(),
            })
    return labels, clusters, added
