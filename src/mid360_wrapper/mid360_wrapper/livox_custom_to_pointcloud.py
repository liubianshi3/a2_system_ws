#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2, PointField
from sensor_msgs_py import point_cloud2


class LivoxCustomToPointCloud(Node):
    def __init__(self):
        super().__init__("livox_custom_to_pointcloud")
        input_topic = self.declare_parameter("input_topic", "/livox/lidar").value
        output_topic = self.declare_parameter("output_topic", "/mid360/points").value
        self.frame_id = self.declare_parameter("frame_id", "lidar_link").value

        try:
            from livox_ros_driver2.msg import CustomMsg
        except ImportError as exc:  # pragma: no cover - depends on optional external package
            raise RuntimeError(
                "livox_ros_driver2 Python messages are unavailable. Build/source livox_ros_driver2 "
                "before starting the Livox custom pointcloud relay."
            ) from exc

        self.publisher = self.create_publisher(PointCloud2, output_topic, 10)
        self.create_subscription(CustomMsg, input_topic, self.on_custom_msg, 10)
        self.get_logger().info(
            f"Converting Livox CustomMsg {input_topic} -> PointCloud2 {output_topic} frame={self.frame_id}"
        )

    def on_custom_msg(self, msg):
        header = msg.header
        header.frame_id = self.frame_id or header.frame_id or "lidar_link"
        fields = [
            PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name="intensity", offset=12, datatype=PointField.FLOAT32, count=1),
        ]
        points = [
            (
                float(point.x),
                float(point.y),
                float(point.z),
                float(point.reflectivity),
            )
            for point in msg.points
        ]
        cloud = point_cloud2.create_cloud(header, fields, points)
        self.publisher.publish(cloud)


def main():
    rclpy.init()
    node = LivoxCustomToPointCloud()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
