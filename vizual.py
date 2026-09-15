from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

import pathlib
import numpy as np
import plotly.express as px

bag_path = pathlib.Path(r"D:\hack\extracted\for_hackathon\roundT_doubleT")
typestore = get_typestore(Stores.LATEST)

with Reader(bag_path) as reader:
    pc_connections = [
        conn for conn in reader.connections
        if "PointCloud2" in conn.msgtype
    ]

    if not pc_connections:
        raise SystemExit("PointCloud2 не найден. Проверьте вывод inspect_bag.py")

    conn = pc_connections[0]
    print(f"Читаем топик: {conn.topic}")

    for connection, timestamp, rawdata in reader.messages([conn]):
        msg = typestore.deserialize_cdr(rawdata, connection.msgtype)

        data = bytes(msg.data)

        fields = {field.name: field.offset for field in msg.fields}

        if not all(name in fields for name in ["x", "y", "z"]):
            raise SystemExit("В PointCloud2 не найдены поля x, y, z")

        dtype = np.dtype({
            "names": ["x", "y", "z"],
            "formats": ["<f4", "<f4", "<f4"],
            "offsets": [fields["x"], fields["y"], fields["z"]],
            "itemsize": msg.point_step,
        })

        points = np.frombuffer(data, dtype=dtype)

        xyz = np.vstack([
            points["x"],
            points["y"],
            points["z"]
        ]).T

        valid = np.isfinite(xyz).all(axis=1)
        xyz = xyz[valid]

        print(f"Точек в кадре: {len(xyz)}")

        # Прореживаем, если точек очень много
        max_points = 200_000
        if xyz.shape[0] > max_points:
            step = xyz.shape[0] // max_points
            xyz = xyz[::step]

        print(f"Рисуем {len(xyz)} точек")

        fig = px.scatter_3d(
            x=xyz[:, 0],
            y=xyz[:, 1],
            z=xyz[:, 2],
        )

        fig.update_traces(
            marker=dict(
                size=1,
                color="red",
            )
        )

        fig.update_layout(
            scene=dict(
                aspectmode="data",
            ),
            title=f"PointCloud2: {conn.topic}",
        )

        fig.show()

        break
