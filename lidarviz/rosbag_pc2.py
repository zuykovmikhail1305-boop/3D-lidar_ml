"""Minimal reader for rosbag2 (sqlite3) bags holding PointCloud2.

Handles both layouts in this dataset: a bag stored as a single .db3, and a bag
rosbag2 split across many .db3 parts listed in metadata.yaml.
"""
import glob
import os
import re
import sqlite3
import struct
import numpy as np

_DT = {1: np.int8, 2: np.uint8, 3: np.int16, 4: np.uint16,
       5: np.int32, 6: np.uint32, 7: np.float32, 8: np.float64}


class _CDR:
    def __init__(self, buf):
        self.b = buf
        self.le = buf[1] == 1
        self.p = 4
        self.base = 4

    def _align(self, n):
        off = (self.p - self.base) % n
        if off:
            self.p += n - off

    def _u(self, fmt, size):
        self._align(size)
        v = struct.unpack_from(('<' if self.le else '>') + fmt, self.b, self.p)[0]
        self.p += size
        return v

    def u32(self):
        return self._u('I', 4)

    def i32(self):
        return self._u('i', 4)

    def u8(self):
        return self._u('B', 1)

    def string(self):
        n = self.u32()
        s = self.b[self.p:self.p + n - 1].decode('utf-8', 'replace')
        self.p += n
        return s


def decode_pointcloud2(blob):
    """Decode a CDR-serialised sensor_msgs/msg/PointCloud2 into (meta, structured array)."""
    c = _CDR(blob)
    sec, nsec = c.i32(), c.u32()
    frame_id = c.string()
    height, width = c.u32(), c.u32()
    fields = []
    for _ in range(c.u32()):
        name = c.string()
        offset = c.u32()
        datatype = c.u8()
        count = c.u32()
        fields.append((name, offset, datatype, count))
    is_bigendian = c.u8()
    point_step, row_step = c.u32(), c.u32()
    data_len = c.u32()
    c._align(1)

    names = [f[0] for f in fields]
    formats = [_DT[f[2]] if f[3] == 1 else (_DT[f[2]], f[3]) for f in fields]
    offsets = [f[1] for f in fields]
    dtype = np.dtype({'names': names, 'formats': formats,
                      'offsets': offsets, 'itemsize': point_step})
    if is_bigendian:
        dtype = dtype.newbyteorder('>')

    n_points = data_len // point_step
    pts = np.frombuffer(blob, dtype=dtype, count=n_points, offset=c.p)

    meta = dict(stamp=sec + nsec * 1e-9, frame_id=frame_id, height=height,
                width=width, point_step=point_step, row_step=row_step,
                n_points=n_points, field_names=names)
    return meta, pts


class BagReader:
    """Iterate PointCloud2 messages of a rosbag2 .db3 file without loading it all."""

    def __init__(self, db3_path):
        self.path = str(db3_path)
        self.con = sqlite3.connect('file:%s?mode=ro' % self.path.replace('\\', '/'),
                                   uri=True)
        self.topics = {r[0]: (r[1], r[2]) for r in
                       self.con.execute('SELECT id, name, type FROM topics')}
        # Keep the id/timestamp index in memory so a frame fetch is a primary-key
        # lookup; OFFSET would rescan the (multi-GB) table on every read.
        rows = self.con.execute(
            'SELECT id, timestamp FROM messages ORDER BY timestamp').fetchall()
        self.ids = np.array([r[0] for r in rows], dtype=np.int64)
        self.timestamps = np.array([r[1] for r in rows], dtype=np.int64)

    def __len__(self):
        return len(self.timestamps)

    def read(self, index):
        """Decode a single message by its chronological index."""
        row = self.con.execute('SELECT data FROM messages WHERE id = ?',
                               (int(self.ids[index]),)).fetchone()
        return decode_pointcloud2(row[0])

    def iter_messages(self, start=0, stop=None, step=1):
        stop = len(self) if stop is None else stop
        for i in range(start, stop, step):
            yield i, self.read(i)

    def close(self):
        self.con.close()


def _part_paths(bag_dir):
    """Ordered .db3 parts of a split bag: metadata.yaml order, else numeric glob."""
    meta = os.path.join(bag_dir, 'metadata.yaml')
    if os.path.exists(meta):
        try:
            import yaml
            with open(meta, encoding='utf-8') as fh:
                info = yaml.safe_load(fh)['rosbag2_bagfile_information']
            paths = [os.path.join(bag_dir, p) for p in info['relative_file_paths']]
            if all(os.path.exists(p) for p in paths):
                return paths
        except Exception:
            pass
    parts = glob.glob(os.path.join(bag_dir, '*.db3'))

    def order(p):
        m = re.search(r'_(\d+)\.db3$', p)
        return int(m.group(1)) if m else 0

    return sorted(parts, key=order)


class SplitBagReader:
    """A bag split across many .db3 parts, addressed as one frame sequence.

    Each part is indexed once (id + timestamp only, so the point blobs are never
    touched), then parts are opened lazily and the most recent few kept open.
    """

    KEEP_OPEN = 4

    def __init__(self, bag_dir):
        self.path = str(bag_dir)
        self.parts = _part_paths(self.path)
        if not self.parts:
            raise ValueError('no .db3 parts under %s' % bag_dir)

        part_of, row_of, stamps = [], [], []
        for i, part in enumerate(self.parts):
            con = sqlite3.connect('file:%s?mode=ro' % part.replace('\\', '/'), uri=True)
            rows = con.execute(
                'SELECT id, timestamp FROM messages ORDER BY timestamp').fetchall()
            con.close()
            for rid, ts in rows:
                part_of.append(i)
                row_of.append(rid)
                stamps.append(ts)

        order = np.argsort(np.array(stamps, dtype=np.int64), kind='stable')
        self.part_of = np.array(part_of, dtype=np.int32)[order]
        self.ids = np.array(row_of, dtype=np.int64)[order]
        self.timestamps = np.array(stamps, dtype=np.int64)[order]
        self._open = {}

    def _con(self, part_index):
        con = self._open.get(part_index)
        if con is None:
            if len(self._open) >= self.KEEP_OPEN:
                self._open.pop(next(iter(self._open))).close()
            con = sqlite3.connect(
                'file:%s?mode=ro' % self.parts[part_index].replace('\\', '/'), uri=True)
            self._open[part_index] = con
        return con

    def __len__(self):
        return len(self.timestamps)

    def read(self, index):
        i = int(index)
        row = self._con(int(self.part_of[i])).execute(
            'SELECT data FROM messages WHERE id = ?', (int(self.ids[i]),)).fetchone()
        return decode_pointcloud2(row[0])

    def iter_messages(self, start=0, stop=None, step=1):
        stop = len(self) if stop is None else stop
        for i in range(start, stop, step):
            yield i, self.read(i)

    def close(self):
        for con in self._open.values():
            con.close()
        self._open.clear()


def open_bag(path):
    """Open a .db3 file or a bag directory, whichever the path points at."""
    path = str(path)
    if os.path.isdir(path):
        parts = _part_paths(path)
        return BagReader(parts[0]) if len(parts) == 1 else SplitBagReader(path)
    return BagReader(path)


def xyz(points, drop_invalid=True):
    """Structured array -> (N,3) float32 xyz, optionally dropping NaN/zero returns."""
    arr = np.stack([points['x'], points['y'], points['z']], axis=-1).astype(np.float32)
    if drop_invalid:
        finite = np.isfinite(arr).all(axis=1)
        nonzero = np.abs(arr).sum(axis=1) > 1e-6
        arr = arr[finite & nonzero]
    return arr
