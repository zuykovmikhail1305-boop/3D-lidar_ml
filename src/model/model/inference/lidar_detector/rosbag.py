"""
Чтение sensor_msgs/msg/PointCloud2 из rosbag2 (.db3, sqlite3) без ROS.

Единственная зависимость - numpy. Сообщение лежит в базе как CDR-блоб,
здесь он разбирается вручную: заголовок читается по полям, а сам массив
точек накрывается structured dtype и читается через np.frombuffer,
то есть без копирования и без цикла по точкам.
"""

import sqlite3
import struct
import numpy as np

# sensor_msgs/msg/PointField.datatype -> numpy
_PF_TO_NP = {
    1: "i1", 2: "u1", 3: "i2", 4: "u2",
    5: "i4", 6: "u4", 7: "f4", 8: "f8",
}

POINTCLOUD2_TYPE = "sensor_msgs/msg/PointCloud2"


class _CdrReader:
    """Минимальный десериализатор CDR (little/big endian, XCDR1)."""

    def __init__(self, buf):
        self.buf = buf
        # 4 байта encapsulation: [0x00, 0x00=BE / 0x01=LE, options(2)]
        self.little = buf[1] & 1 == 1
        self.e = "<" if self.little else ">"
        self.off = 4

    def align(self, n):
        # выравнивание считается от начала тела, т.е. от смещения 4
        rem = (self.off - 4) % n
        if rem:
            self.off += n - rem

    def _unpack(self, fmt, size):
        v = struct.unpack_from(self.e + fmt, self.buf, self.off)[0]
        self.off += size
        return v

    def u8(self):
        v = self.buf[self.off]
        self.off += 1
        return v

    def i32(self):
        self.align(4)
        return self._unpack("i", 4)

    def u32(self):
        self.align(4)
        return self._unpack("I", 4)

    def string(self):
        n = self.u32()                     # длина вместе с '\0'
        s = self.buf[self.off:self.off + n - 1].decode("utf-8", "replace")
        self.off += n
        return s


def parse_pointcloud2(blob):
    """Разбирает один CDR-блоб PointCloud2.

    Возвращает dict с полями заголовка и `points` - numpy structured array
    длиной height*width. Массив является view на исходный буфер.
    """
    r = _CdrReader(blob)

    sec = r.i32()
    nanosec = r.u32()
    frame_id = r.string()

    height = r.u32()
    width = r.u32()

    n_fields = r.u32()
    names, formats, offsets = [], [], []
    for _ in range(n_fields):
        name = r.string()
        offset = r.u32()
        datatype = r.u8()
        count = r.u32()
        np_type = _PF_TO_NP.get(datatype)
        if np_type is None:
            raise ValueError(f"неизвестный PointField.datatype={datatype} у поля {name!r}")
        names.append(name)
        formats.append(np_type if count == 1 else (np_type, count))
        offsets.append(offset)

    is_bigendian = bool(r.u8())
    point_step = r.u32()
    row_step = r.u32()
    data_len = r.u32()
    data_off = r.off
    r.off += data_len
    is_dense = bool(r.u8())

    endian = ">" if is_bigendian else "<"
    formats = [endian + f if isinstance(f, str) else (endian + f[0], f[1]) for f in formats]
    dtype = np.dtype({
        "names": names,
        "formats": formats,
        "offsets": offsets,
        "itemsize": point_step,
    })

    n_points = data_len // point_step
    points = np.frombuffer(blob, dtype=dtype, count=n_points, offset=data_off)

    return {
        "stamp_sec": sec,
        "stamp_nanosec": nanosec,
        "stamp": sec + nanosec * 1e-9,
        "frame_id": frame_id,
        "height": height,
        "width": width,
        "point_step": point_step,
        "row_step": row_step,
        "is_dense": is_dense,
        "is_bigendian": is_bigendian,
        "field_names": names,
        "points": points,
    }


def list_topics(db3_path):
    """[(topic_id, name, type), ...] из одного файла бага."""
    con = sqlite3.connect(f"file:{db3_path}?mode=ro", uri=True)
    try:
        return con.execute("SELECT id, name, type FROM topics").fetchall()
    finally:
        con.close()


def iter_messages(db3_path, topic_name=None):
    """Итератор (timestamp_ns, blob) по сообщениям одного .db3, по времени."""
    con = sqlite3.connect(f"file:{db3_path}?mode=ro", uri=True)
    try:
        if topic_name is None:
            sql = "SELECT timestamp, data FROM messages ORDER BY timestamp"
            args = ()
        else:
            sql = ("SELECT m.timestamp, m.data FROM messages m "
                   "JOIN topics t ON t.id = m.topic_id "
                   "WHERE t.name = ? ORDER BY m.timestamp")
            args = (topic_name,)
        cur = con.execute(sql, args)
        while True:
            rows = cur.fetchmany(4)
            if not rows:
                break
            for ts, blob in rows:
                yield ts, blob
    finally:
        con.close()


def count_messages(db3_path, topic_name=None):
    con = sqlite3.connect(f"file:{db3_path}?mode=ro", uri=True)
    try:
        if topic_name is None:
            return con.execute("SELECT count(*) FROM messages").fetchone()[0]
        return con.execute(
            "SELECT count(*) FROM messages m JOIN topics t ON t.id = m.topic_id WHERE t.name = ?",
            (topic_name,),
        ).fetchone()[0]
    finally:
        con.close()
