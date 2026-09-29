r"""
Пересчёт карты «привычек» модели (artifacts/added_rate.npy) - после смены весов.

    python calibrate.py D:\hackaton_full_dataset\cloud_with_fake_obj
    python calibrate.py <запись> --frames 500

Каждая модель ошибается по-своему: в одних и тех же пикселях из кадра в кадр
добавляет точки, которых нет. Детектор не ищет скопления там, где модель
добавляет точки чаще, чем habit зоны (по умолчанию в 20% кадров). Эта карта -
доля кадров, в которых модель добавила точку в каждом пикселе. Её нужно
считать для тех весов, с которыми работает детектор, на записи, похожей на
рабочие данные. Старый файл сохраняется как added_rate.npy.bak.

Зависимости: numpy, torch.
"""

import argparse
import os
import shutil
import time

import numpy as np

from lidar_detector import Bag, Detector
from lidar_detector.clusters import DEFAULTS
from lidar_detector.model import restore
from lidar_detector.rosbag import parse_pointcloud2

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("bag", help="папка записи rosbag2 или файл .db3")
    p.add_argument("--topic")
    p.add_argument("--artifacts", default=os.path.join(HERE, "artifacts"))
    p.add_argument("--frames", type=int, default=300, help="сколько кадров взять, равномерно по записи")
    p.add_argument("--device")
    args = p.parse_args()

    bag = Bag(args.bag, args.topic)
    det = Detector(args.artifacts, device=args.device)
    idx = np.unique(np.linspace(0, len(bag) - 1, min(args.frames, len(bag))).astype(int))
    print("запись %s: %d кадров из %d, устройство %s" % (bag.name, len(idx), len(bag), det.device))
    acc = np.zeros(det.struct.shape)
    t0 = time.time()
    for n, i in enumerate(idx):
        r_in, i_in = det.to_range(parse_pointcloud2(bag.read(i)[1])["points"])
        r_out = restore(det.model, det.device, r_in, i_in)[0]
        acc += (r_out > DEFAULTS["min_range"]) & (r_in <= 0) & ~det.struct & det.sector
        if (n + 1) % 50 == 0:
            print("  %d / %d" % (n + 1, len(idx)))
    rate = (acc / len(idx)).astype(np.float32)
    path = os.path.join(args.artifacts, "added_rate.npy")
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    np.save(path, rate)
    print("готово за %.0f с -> %s" % (time.time() - t0, path))
    for t in (0.1, 0.2, 0.3):
        print("  пикселей, где модель добавляет точки чаще %d%% кадров: %.2f%%" % (100 * t, 100 * (rate > t).mean()))


if __name__ == "__main__":
    main()
