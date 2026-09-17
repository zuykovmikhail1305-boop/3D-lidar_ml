import rclpy

class ModelNode():
    def __init__(self):
        self.node = rclpy.create_node('model')
        self.node.create_timer(1, self.callback)
    def callback(self):
        self.node.get_logger().info('Timer!')

def main():
    rclpy.init()
    model = ModelNode()
    rclpy.spin(model.node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
