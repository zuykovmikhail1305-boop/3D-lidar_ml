from . import test_detector
import numpy as np
import rclpy
from rclpy.qos import qos_profile_sensor_data, qos_profile_services_default
from std_msgs.msg import Float32
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py.point_cloud2 import read_points_numpy

class Node:
    def __init__(self):
        node = rclpy.create_node('model')
        self.node = node
        self.logger = node.get_logger()
        self.publisher = node.create_publisher(Float32, 'obstacle_distance', qos_profile_services_default)
        node.create_subscription(PointCloud2, 'lidar_points', self.callback, qos_profile_sensor_data)
        self.detector = test_detector.Detector()
    def callback(self, msg):
        self.logger.info('New message from lidar')
        # read_points() возвращает генератор кортежей, а api.analyze требует
        # numpy-массив (TypeError в check_points) — конвертируем сразу в массив.
        try:
            points = read_points_numpy(msg, field_names=('x', 'y', 'z', 'intensity'))
        except ValueError:
            # Редкий случай: в облаке нет поля intensity — добираем его нулями.
            full = read_points_numpy(msg)
            cols = []
            for name in ('x', 'y', 'z', 'intensity'):
                if name in full.dtype.names:
                    cols.append(full[name].astype(np.float32))
                else:
                    cols.append(np.zeros(len(full), dtype=np.float32))
            points = np.column_stack(cols)
        result = api.analyze_json(points)
        if not result is None:
            self.logger.info(f'An obstacle in {result} m')
            msg = Float32()
            msg.data = result
            self.publisher.publish(msg)

def main():
    rclpy.init()
    node_object = Node()
    rclpy.spin(node_object.node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
