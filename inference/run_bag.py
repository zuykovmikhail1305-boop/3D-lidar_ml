r"""
Прогон записи rosbag2 через детектор: скопления по каждому кадру - в CSV и JSONL.

    python run_bag.py D:\hackaton_full_dataset\cloud_with_fake_obj
    python run_bag.py <запись> --out results\run1 --limit 100 --device cpu

Результат в папке --out (по умолчанию results/<имя записи>):

    clusters.csv    по строке на скопление: кадр, время, зона, точки, размеры, центр, рамка
    frames.csv      по строке на кадр: detected (1 - есть скопление, 0 - нет), точек во входе и в ответе, добавлено, скоплений
    clusters.jsonl  по строке JSON на кадр со списком скоплений - удобно читать построчно

Зависимости: numpy, torch.
"""

import argparse
import csv
import json
import os
import time

from lidar_detector import Bag, Detector

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("bag", help="папка записи rosbag2 или файл .db3")
    p.add_argument("--out", help="куда писать (по умолчанию results/<имя записи>)")
    p.add_argument("--topic", help="топик PointCloud2, если их несколько")
    p.add_argument("--artifacts", default=os.path.join(HERE, "artifacts"))
    p.add_argument("--zones", help="свой файл порогов зон (по умолчанию artifacts/cluster_zones_3d.json)")
    p.add_argument("--device", help="cuda или cpu (по умолчанию cuda, если есть)")
    p.add_argument("--stride", type=int, default=1, help="брать каждый N-й кадр")
    p.add_argument("--limit", type=int, default=0, help="не больше N кадров")
    args = p.parse_args()

    bag = Bag(args.bag, args.topic)
    det = Detector(args.artifacts, device=args.device)
    if args.zones:
        from lidar_detector.clusters import load_zones
        det.zones = load_zones(args.zones)
    frames = list(range(0, len(bag), args.stride))[: args.limit or None]
    out = args.out or os.path.join(HERE, "results", bag.name)
    os.makedirs(out, exist_ok=True)
    print("запись: %s (%s), кадров к обработке %d, устройство %s" % (bag.name, bag.topic, len(frames), det.device))

    c_fields = ["frame", "timestamp_ns", "cluster", "zone", "points", "size_m", "dx_m", "dy_m", "dz_m",
                "range_m", "x", "y", "z", "min_x", "min_y", "min_z", "max_x", "max_y", "max_z"]
    f_fields = ["frame", "timestamp_ns", "detected", "points_in", "points_out", "added_in_search", "clusters"]
    t0 = time.time()
    n_clusters = n_with = 0
    with open(os.path.join(out, "clusters.csv"), "w", newline="", encoding="utf-8") as fc, \
            open(os.path.join(out, "frames.csv"), "w", newline="", encoding="utf-8") as ff, \
            open(os.path.join(out, "clusters.jsonl"), "w", encoding="utf-8") as fj:
        wc, wf = csv.DictWriter(fc, fieldnames=c_fields), csv.DictWriter(ff, fieldnames=f_fields)
        wc.writeheader()
        wf.writeheader()
        for n, i in enumerate(frames):
            ts, blob = bag.read(i)
            res = det.process_message(blob)
            for c in res.clusters:
                z = det.zones[c["zone"]]
                wc.writerow({"frame": i, "timestamp_ns": ts, "cluster": c["id"],
                             "zone": "%.0f-%.0f" % (z["from"], z["to"]), "points": c["points"],
                             "size_m": c["size_m"], "dx_m": c["extent_m"][0], "dy_m": c["extent_m"][1],
                             "dz_m": c["extent_m"][2], "range_m": c["range_m"],
                             "x": c["center"][0], "y": c["center"][1], "z": c["center"][2],
                             "min_x": c["min"][0], "min_y": c["min"][1], "min_z": c["min"][2],
                             "max_x": c["max"][0], "max_y": c["max"][1], "max_z": c["max"][2]})
            wf.writerow({"frame": i, "timestamp_ns": ts, "detected": res.detected, "points_in": int((res.range_in > 0).sum()),
                         "points_out": int((res.range_out > 0).sum()), "added_in_search": int(res.added.sum()),
                         "clusters": len(res.clusters)})
            fj.write(json.dumps({"frame": i, "timestamp_ns": ts, "detected": res.detected, "clusters": res.clusters}, ensure_ascii=False) + "\n")
            n_clusters += len(res.clusters)
            n_with += bool(res.clusters)
            if (n + 1) % 100 == 0 or n + 1 == len(frames):
                el = time.time() - t0
                print("  %d / %d кадров, %.1f кадр/с, скоплений %d" % (n + 1, len(frames), (n + 1) / el, n_clusters))
    print("готово за %.1f с: скоплений %d в %d кадрах из %d -> %s"
          % (time.time() - t0, n_clusters, n_with, len(frames), out))


if __name__ == "__main__":
    main()
