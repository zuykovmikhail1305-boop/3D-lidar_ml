"""Extract frame sequences for the 3D viewer, so the page can play them back.

The bags are streams of sweeps at 10 Hz, so each scene ships as a run of
consecutive frames rather than a single snapshot. Start frames were picked by
scanning every bag for the window with the most structural change — see
`scan_activity()`.

Each scene is one JSON file holding a base64 payload (only standard web media
types are servable alongside a published page, so the buffer travels inside
JSON rather than as .bin). All frames sit back to back in one buffer; the
`counts` array says how many points each frame contributes, and the viewer
draws frame k with a single drawArrays call at the right offset.

Layout per point, 8 bytes, little-endian, interleaved:
    int16 x, int16 y, int16 z   (metres / SCALE, so 5 mm steps)
    uint8 intensity             (0-255, as recorded)
    uint8 ring                  (0-127)
"""
import base64
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rosbag_pc2 import open_bag  # noqa: E402

ROOT = r'D:\hack\extracted'
FIRST = 'for_hackathon'       # первая поставка: шесть коротких записей
SECOND = 'new_data'           # вторая поставка: один 20-минутный проезд
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'data')
SCALE = 0.005          # metres per quantisation step

def old(bag, **kw):
    kw.setdefault('frames', 50)
    kw.setdefault('points', 12000)
    kw.setdefault('far', 45)
    return dict(dir=os.path.join(FIRST, bag), bag=bag, delivery='первая поставка', **kw)


def new(**kw):
    kw.setdefault('frames', 50)
    kw.setdefault('points', 12000)
    kw.setdefault('far', 45)
    return dict(dir=SECOND, bag=SECOND, delivery='20-минутный проезд', **kw)


SCENES = [
    old('squareT_platform_squareT_switch', key='platform', start=95,
        title='Платформа и стрелка',
        note='Самый подвижный участок первой поставки: прямоугольное сечение, '
             'край платформы, справа уходит боковой проход.'),
    old('doubleT_platform', key='doubleT', start=100,
        title='Двухпутный тоннель',
        note='Широкий ход около 9.5 м. Сечение заметно меняется от кадра к кадру.'),
    old('roundT_doubleT', key='roundT', start=85,
        title='Круглый ствол',
        note='Обделка радиусом около 2.5 м, дальше — переход в двухпутный участок.'),
    old('roundT_pressureGate_roundT', key='gate', start=5,
        title='Гермозатвор',
        note='Ниша затвора: сечение раскрывается с 3 до 5.2 м на дистанции 10–16 м.'),
    old('doubleT_obstacle', key='wide360', start=100, frames=1,
        points=90000, far=70,
        title='Обзор 360°',
        note='Единственная запись с полным круговым обзором. Сенсор здесь почти '
             'неподвижен, поэтому это один кадр в высокой детализации.'),

    # Кадры выбраны по скану всего проезда (timeline): самое широкое место,
    # второе крупное раскрытие и самый резкий переход в узкий высокий ход.
    new(key='hall', start=2760, far=55,
        title='Зал на 4.6 минуте',
        note='Самое широкое место всего проезда: узкий ход шириной 4 м идёт '
             'внутри зала со стенами на 7.5 м слева и 11.5 м справа.'),
    new(key='opening', start=5730, far=55,
        title='Раскрытие на 9.6 минуте',
        note='Второе крупное раскрытие, около 16 м в поперечнике. Характер '
             'другой: свод выше, боковые проёмы короче.'),
    new(key='narrows', start=9810, far=50,
        title='Сужение на 16.9 минуте',
        note='Самый резкий переход записи: ширина падает до 6 м, а высота '
             'наоборот растёт до 6.6 м — узкий высокий ход.'),

    # Весь проезд прореженно: 225 кадров с шагом 50 покрывают все 11 271.
    # Точек на кадр меньше — иначе сцена не уложилась бы в лимит страницы.
    new(key='traverse', start=0, frames=225, stride=50, points=5000, far=55,
        title='Весь проезд, каждый 50-й кадр',
        note='Все 20 минут за один проход. Между соседними кадрами около 5 секунд '
             'реального времени, поэтому сцена идёт скачками.'),
]


def pack_frame(pts, max_points, far, rng):
    """One sweep -> the 8-byte-per-point record array, subsampled and clipped."""
    v = np.stack([pts['x'], pts['y'], pts['z']], axis=-1).astype(np.float32)
    keep = np.isfinite(v).all(1) & (np.abs(v).sum(1) > 1e-6)
    keep &= np.linalg.norm(v, axis=1) < far
    v, inten, ring = v[keep], pts['intensity'][keep], pts['ring'][keep]

    if len(v) > max_points:
        pick = rng.choice(len(v), max_points, replace=False)
        pick.sort()
        v, inten, ring = v[pick], inten[pick], ring[pick]

    rec = np.empty(len(v), dtype=[('x', '<i2'), ('y', '<i2'), ('z', '<i2'),
                                  ('i', 'u1'), ('r', 'u1')])
    rec['x'] = np.round(v[:, 0] / SCALE).astype(np.int16)
    rec['y'] = np.round(v[:, 1] / SCALE).astype(np.int16)
    rec['z'] = np.round(v[:, 2] / SCALE).astype(np.int16)
    rec['i'] = np.clip(inten, 0, 255).astype(np.uint8)
    rec['r'] = ring.astype(np.uint8)
    return rec


def build_scene(scene):
    """Extract one scene and return its manifest entry."""
    rng = np.random.default_rng(0)
    stride = scene.get('stride', 1)
    bag = open_bag(os.path.join(ROOT, scene['dir']))
    span_needed = (scene['frames'] - 1) * stride
    first = max(0, min(scene['start'], len(bag) - 1 - span_needed))

    blocks, counts = [], []
    for k in range(scene['frames']):
        meta, pts = bag.read(first + k * stride)
        rec = pack_frame(pts, scene['points'], scene['far'], rng)
        blocks.append(rec.tobytes())
        counts.append(len(rec))

    raw = b''.join(blocks)
    name = 'data/%s.json' % scene['key']
    with open(os.path.join(OUT, scene['key'] + '.json'), 'w', encoding='utf-8') as fh:
        json.dump({'counts': counts,
                   'b64': base64.b64encode(raw).decode('ascii')}, fh)

    span = (bag.timestamps[first + span_needed] - bag.timestamps[first]) / 1e9
    entry = dict(
        key=scene['key'], title=scene['title'], note=scene['note'],
        file=name, bag=scene['bag'], delivery=scene['delivery'],
        start=first, frames=scene['frames'], stride=stride,
        scale=SCALE, far=scene['far'], frameId=meta['frame_id'],
        rawPoints=int(meta['n_points']), seconds=round(float(span), 1),
    )
    print('%-9s %3d кадров (шаг %d) x %5d точек -> %s (%.1f МБ base64)'
          % (scene['key'], scene['frames'], stride, scene['points'], name,
             len(raw) * 4 / 3 / 1e6))
    bag.close()
    return entry


def main(only=None):
    """Rebuild every scene, or just the keys named on the command line."""
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, 'manifest.json')
    previous = {}
    if only and os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            previous = {e['key']: e for e in json.load(fh)}

    manifest = []
    for scene in SCENES:
        if only and scene['key'] not in only:
            if scene['key'] in previous:
                manifest.append(previous[scene['key']])
                print('%-9s без изменений' % scene['key'])
            continue
        manifest.append(build_scene(scene))

    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    print('wrote', path)


if __name__ == '__main__':
    main(set(sys.argv[1:]) or None)
