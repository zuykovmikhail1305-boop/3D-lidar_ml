r"""
Визуализация детектора: слева кадр до модели, справа - после, скопления в рамках.

    python viewer/server.py D:\hackaton_full_dataset\cloud_with_fake_obj
    python viewer/server.py <запись> --port 8790 --device cpu --no-browser

Кадры читаются прямо из записи rosbag2 и прогоняются через Detector на лету -
ровно то же, что делает бэкенд. Откроется страница в браузере:

    слева   вход модели (уже обрезанный по рабочему сектору)
    справа  ответ модели: серо-голубой - точка на месте входной, зелёный -
            добавлена, тёмно-серый - добавлена там, где скопления не ищутся,
            малиновый - скопление; рамки скоплений на обеих панелях
    зоны    пороги поиска по зонам дальности, «сохранить» пишет их в
            artifacts/cluster_zones_3d.json - этот файл читает Detector

Управление: ползунок и ← →, пробел - пуск, [ ] - к кадру со скоплением,
мышь вращает обе панели сразу.

Зависимости: numpy, torch.
"""

import argparse
import json
import os
import socket
import sys
import threading
import webbrowser
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))                  # чтобы найти lidar_detector рядом

from lidar_detector import Bag, Detector                    # noqa: E402
from lidar_detector import clusters as cl                   # noqa: E402
from lidar_detector.model import restore                    # noqa: E402
from lidar_detector.range_image import AZ_MIN, AZ_STEP      # noqa: E402
from lidar_detector.rosbag import parse_pointcloud2         # noqa: E402

PAGE = os.path.join(HERE, "index.html")
NORMAL, ADDED, CLUSTER, IGNORED = 0, 3, 4, 5


def to_points(rng, inten, mask, elevation, cat):
    """Пиксели mask -> float32 (N, 5): x y z интенсивность категория."""
    rows, cols = np.nonzero(mask)
    r = rng[rows, cols].astype(np.float64)
    az = np.radians(AZ_MIN + (cols + 0.5) * AZ_STEP)
    el = np.radians(elevation[rows])
    out = np.empty((len(r), 5), np.float32)
    out[:, 0] = r * np.cos(el) * np.cos(az)
    out[:, 1] = r * np.cos(el) * np.sin(az)
    out[:, 2] = r * np.sin(el)
    out[:, 3] = inten[rows, cols]
    out[:, 4] = cat[rows, cols]
    return out


class Frames:
    def __init__(self, bag, det):
        self.bag, self.det = bag, det
        self.cache = OrderedDict()            # кадр -> (вход, интенсивность, ответ модели): модель - самое дорогое
        self.lock = threading.Lock()          # модель и чтение записи - по одному кадру за раз

    def images(self, i):
        with self.lock:
            if i in self.cache:
                self.cache.move_to_end(i)
                return self.cache[i]
            r_in, i_in = self.det.to_range(parse_pointcloud2(self.bag.read(i)[1])["points"])
            r_out = restore(self.det.model, self.det.device, r_in, i_in)[0]
            r_out = np.where(self.det.sector, r_out, 0).astype(np.float32)
            self.cache[i] = (r_in, i_in.astype(np.float32), r_out)
            while len(self.cache) > 64:
                self.cache.popitem(last=False)
            return self.cache[i]

    def zones_from(self, q):
        return cl.check_zones(json.loads(q["zones"][0])) if "zones" in q else self.det.zones

    def frame(self, i, zones):
        r_in, i_in, r_out = self.images(i)
        det = self.det
        labels, clusters, added = cl.find_clusters(r_in, r_out, det.struct, det.elevation, zones, det.rate)
        vi, vo = r_in > 0, r_out > 0
        added_all = vo & ~vi & (r_out > cl.DEFAULTS["min_range"])
        cat = np.full(r_out.shape, NORMAL, np.float32)
        cat[added_all & ~added] = IGNORED
        cat[added] = ADDED
        cat[labels > 0] = CLUSTER
        # у добавленных точек своей интенсивности нет - ближайшая слева в том же луче
        idx = np.maximum.accumulate(np.where(vi, np.arange(r_in.shape[1])[None, :], 0), axis=1)
        i_out = np.where(vi, i_in, np.take_along_axis(i_in, idx, axis=1))
        before = to_points(r_in, i_in, vi, det.elevation, np.zeros_like(r_in))
        after = to_points(r_out, i_out, vo, det.elevation, cat)
        stats = {"frame": i, "n_in": int(vi.sum()), "n_out": int(vo.sum()), "added": int(added_all.sum()),
                 "added_search": int(added.sum()), "in_clusters": int((labels > 0).sum()), "clusters": clusters,
                 "detected": int(len(clusters) > 0)}
        return before.tobytes() + after.tobytes(), len(before), stats

    def seek(self, start, step, zones):
        i = start + step
        while 0 <= i < len(self.bag):
            r_in, _, r_out = self.images(i)
            if cl.find_clusters(r_in, r_out, self.det.struct, self.det.elevation, zones, self.det.rate)[1]:
                return i
            i += step
        return -1


def make_handler(fr):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path)
            path, q = unquote(u.path), parse_qs(u.query)
            try:
                if path in ("/", "/index.html"):
                    with open(PAGE, "rb") as fh:
                        self.send(200, fh.read(), "text/html; charset=utf-8")
                elif path == "/api/info":
                    body = {"name": fr.bag.name, "frames": len(fr.bag), "zones": fr.det.zones,
                            "default_zones": cl.default_zones(), "zones_file": fr.det.zones_file,
                            "zones_saved": os.path.exists(fr.det.zones_file), "common": cl.DEFAULTS}
                    self.send(200, json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                elif path.startswith("/api/frame/"):
                    i = int(path.rsplit("/", 1)[1])
                    if not 0 <= i < len(fr.bag):
                        self.send(404, b"no such frame", "text/plain")
                        return
                    body, n_before, stats = fr.frame(i, fr.zones_from(q))
                    self.send(200, body, "application/octet-stream",
                              {"X-N-Before": str(n_before), "X-Stats": json.dumps(stats, ensure_ascii=True)})
                elif path == "/api/seek":
                    i = fr.seek(int(q["from"][0]), 1 if int(q["dir"][0]) > 0 else -1, fr.zones_from(q))
                    self.send(200, json.dumps({"frame": i}).encode(), "application/json")
                else:
                    self.send(404, b"not found", "text/plain")
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                try:
                    self.send(500, str(e).encode("utf-8"), "text/plain; charset=utf-8")
                except Exception:
                    pass

        def do_POST(self):
            """Сохранить пороги со страницы в artifacts/cluster_zones_3d.json - его читает Detector."""
            try:
                if urlparse(self.path).path != "/api/zones":
                    self.send(404, b"not found", "text/plain")
                    return
                n = int(self.headers.get("Content-Length", 0))
                zones = json.loads(self.rfile.read(n).decode("utf-8"))["zones"]
                fr.det.zones = cl.save_zones(zones, fr.det.zones_file)
                self.send(200, json.dumps({"saved": fr.det.zones_file, "zones": fr.det.zones}, ensure_ascii=False)
                          .encode("utf-8"), "application/json; charset=utf-8")
            except Exception as e:
                self.send(400, str(e).encode("utf-8"), "text/plain; charset=utf-8")

    return Handler


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("bag", help="папка записи rosbag2 или файл .db3")
    p.add_argument("--topic")
    p.add_argument("--artifacts", default=os.path.join(os.path.dirname(HERE), "artifacts"))
    p.add_argument("--device", help="cuda или cpu (по умолчанию cuda, если есть)")
    p.add_argument("--port", type=int, default=8790)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()

    bag = Bag(args.bag, args.topic)
    det = Detector(args.artifacts, device=args.device)
    fr = Frames(bag, det)
    print("запись: %s (%s), кадров %d, устройство %s" % (bag.name, bag.topic, len(bag), det.device))

    handler = make_handler(fr)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    try:                                                     # localhost в Windows сначала идёт на ::1
        class Server6(ThreadingHTTPServer):
            address_family = socket.AF_INET6
        server6 = Server6(("::1", args.port), handler)
        threading.Thread(target=server6.serve_forever, daemon=True).start()
    except OSError:
        pass
    url = "http://127.0.0.1:%d/" % args.port
    print("открыто: %s   (остановить - Ctrl+C)" % url)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")


if __name__ == "__main__":
    main()
