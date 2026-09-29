"""
Развёртка облака лидара в картинку и обратно.

Hesai на этих записях - 128 лучей, шаг по азимуту 0.1 градуса. Облако ложится
в таблицу естественным образом: строка - номер луча (ring), столбец - азимут,
значение - дальность. Каждая точка занимает свой пиксель, и задачи «достроить»
и «убрать отклонение» становятся обычной обработкой изображения.

    строки     128 - по одному на луч, ring 0 сверху (+14.4 град),
               ring 127 снизу (-25.1 град)
    столбцы    1024 - азимут от -141.2 до -38.8 град с шагом 0.1

Сектор выбран по данным: шесть записей из семи пишут ровно -140..-40 град,
то есть смотрят вперёд вдоль тоннеля. 1000 столбцов округлены до 1024, чтобы
картинка делилась на 16 и проходила четыре понижения U-Net без обрезки.
doubleT_obstacle пишет полный круг - из неё берётся тот же передний сектор.

Если в пиксель попадает несколько точек (два эха одного луча), остаётся
ближняя - это первое отражение, как у самого сенсора.

Зависимости: numpy.
"""

import numpy as np

H = 128                   # лучей
W = 1024                  # столбцов
AZ_STEP = 0.1             # град на столбец
AZ_MIN = -141.2           # левый край сектора, град
AZ_MAX = AZ_MIN + W * AZ_STEP

# угол места каждого луча, град - нужен для обратного перевода в точки.
# Заполняется по данным (estimate_elevations); ниже - приближение по трём
# замеренным лучам, на случай если таблицы ещё нет.
DEFAULT_ELEVATION = np.interp(np.arange(H), [0, 64, 127], [14.40, -3.02, -25.12])

# Рабочий сектор. Лидар пишет азимут -140..-40 град, то есть по 50 град в
# каждую сторону от «вперёд» (-90). С краёв срезается по 17 град: модель не
# видит эти точки ни при обучении, ни при прогоне, и скопления там не ищутся.
# Лево - сторона +x лидара (азимут ближе к -40), право - сторона -x.
FORWARD_AZ = -90.0
HALF_FOV = 50.0
CUT_LEFT = 17.0
CUT_RIGHT = 17.0


def sector_columns(cut_left=CUT_LEFT, cut_right=CUT_RIGHT):
    """bool (W,): столбцы, чей азимут (по центру пикселя) внутри рабочего сектора."""
    az = AZ_MIN + (np.arange(W) + 0.5) * AZ_STEP
    return (az >= FORWARD_AZ - HALF_FOV + cut_right) & (az <= FORWARD_AZ + HALF_FOV - cut_left)


def apply_sector(*images, cut_left=CUT_LEFT, cut_right=CUT_RIGHT):
    """Обнулить всё вне рабочего сектора. Картинки (..., H, W) - numpy или torch; возвращаются копии."""
    keep = sector_columns(cut_left, cut_right)
    out = []
    for img in images:
        if hasattr(img, "clone"):                              # torch.Tensor
            import torch
            m = torch.as_tensor(keep, device=img.device)
            out.append(torch.where(m, img, torch.zeros_like(img)))
        else:
            out.append(np.where(keep, img, np.zeros((), np.asarray(img).dtype)))
    return out[0] if len(out) == 1 else out


def points_to_range(x, y, z, intensity, ring):
    """Точки -> (дальность м float32, интенсивность uint8, занятость bool), (H, W).

    Нулевые точки (луч не вернулся) пропускаются. Точки вне сектора и с
    номером луча за пределами 0..H-1 тоже.
    """
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    z = np.asarray(z, np.float64)
    r = np.sqrt(x * x + y * y + z * z)
    ok = r > 0
    az = np.degrees(np.arctan2(y, x))
    col = np.floor((az - AZ_MIN) / AZ_STEP).astype(np.int64)
    row = np.asarray(ring, np.int64)
    ok &= (col >= 0) & (col < W) & (row >= 0) & (row < H)

    rng = np.zeros((H, W), np.float32)
    inten = np.zeros((H, W), np.uint8)
    if not ok.any():
        return rng, inten, rng > 0

    r, row, col = r[ok], row[ok], col[ok]
    it = np.clip(np.asarray(intensity)[ok], 0, 255).astype(np.uint8)
    # несколько точек в пикселе: оставляем ближнюю. Сортируем по убыванию
    # дальности, тогда при записи по индексам последней ляжет ближняя
    order = np.argsort(-r, kind="stable")
    rng[row[order], col[order]] = r[order]
    inten[row[order], col[order]] = it[order]
    return rng, inten, rng > 0


def range_to_points(rng, intensity=None, valid=None, elevation=None):
    """Картинка -> точки (N, 4): x, y, z, интенсивность.

    Направление берётся из центра пикселя: азимут столбца и угол места луча.
    Это ровно та геометрия, в которой сенсор снимал, так что для
    непотревоженных пикселей точка восстанавливается с точностью до
    половины шага сетки по углу (0.05 град, около 2 см на 20 м).
    """
    if valid is None:
        valid = rng > 0
    if elevation is None:
        elevation = DEFAULT_ELEVATION
    rows, cols = np.nonzero(valid)
    r = rng[rows, cols].astype(np.float64)
    az = np.radians(AZ_MIN + (cols + 0.5) * AZ_STEP)
    el = np.radians(np.asarray(elevation)[rows])
    out = np.empty((len(r), 4), np.float32)
    out[:, 0] = r * np.cos(el) * np.cos(az)
    out[:, 1] = r * np.cos(el) * np.sin(az)
    out[:, 2] = r * np.sin(el)
    out[:, 3] = intensity[rows, cols] if intensity is not None else 0
    return out


def ring_from_elevation(x, y, z, elevation):
    """Номер луча по углу места - для записей без поля ring.

    Сенсор считает координаты по фиксированному углу своего луча, поэтому
    настоящая точка лежит на угле луча с точностью до округления float32.
    Проверено на трёх записях с ring: совпадение 100%. Точка, которая ни на
    один угол не попадает (вставлена в облако позже), уходит к ближайшему лучу.
    """
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    z = np.asarray(z, np.float64)
    r = np.sqrt(x * x + y * y + z * z)
    el = np.degrees(np.arcsin(np.clip(z / np.maximum(r, 1e-9), -1, 1)))
    order = np.argsort(elevation)
    srt = np.asarray(elevation)[order]
    pos = np.searchsorted(srt, el).clip(1, len(srt) - 1)
    nearer_lo = np.abs(el - srt[pos - 1]) <= np.abs(el - srt[pos])
    return order[np.where(nearer_lo, pos - 1, pos)]


def estimate_elevations(x, y, z, ring):
    """Медианный угол места каждого луча по одному или нескольким кадрам, град."""
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    z = np.asarray(z, np.float64)
    r = np.sqrt(x * x + y * y + z * z)
    ok = r > 0
    el = np.degrees(np.arcsin(np.clip(z[ok] / r[ok], -1, 1)))
    ring = np.asarray(ring)[ok]
    out = DEFAULT_ELEVATION.copy()
    for k in range(H):
        m = ring == k
        if m.any():
            out[k] = float(np.median(el[m]))
    return out
