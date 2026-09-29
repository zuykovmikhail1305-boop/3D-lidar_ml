from .lidar_api import api
import sys
import rclpy
from rclpy.qos import qos_profile_sensor_data, qos_profile_services_default
from std_msgs.msg import Float32
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py.point_cloud2 import read_points

class Node:
    def __init__(self):
        node = rclpy.create_node('model')
        self.node = node
        self.logger = node.get_logger()
        self.publisher = node.create_publisher(Float32, 'obstacle_distance', qos_profile_services_default)
        node.create_subscription(PointCloud2, 'lidar_points', self.callback, qos_profile_sensor_data)
    def callback(self, msg):
        self.logger.info('New message from lidar')
        points = read_points(msg)
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
