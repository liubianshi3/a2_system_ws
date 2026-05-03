#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import Bool, String


class PointCloudGuard(Node):
    def __init__(self):
        super().__init__("pointcloud_guard")
        self.pointcloud_topic = self.declare_parameter("pointcloud_topic", "/jt128/front/points").value
        self.stale_timeout_sec = float(self.declare_parameter("stale_timeout_sec", 1.0).value)
        self.connected_topic = self.declare_parameter("connected_topic", "/a2/lidar/connected").value
        self.status_topic = self.declare_parameter("status_topic", "/a2/lidar/status").value
        self.status_label = self.declare_parameter("status_label", "lidar").value
        self.last_cloud_time = None
        self.last_status_text = ""

        self.connected_pub = self.create_publisher(Bool, self.connected_topic, 10)
        self.status_pub = self.create_publisher(String, self.status_topic, 10)
        self.create_subscription(PointCloud2, self.pointcloud_topic, self.on_cloud, 10)
        self.create_timer(0.5, self.tick)

    def on_cloud(self, _msg):
        self.last_cloud_time = self.get_clock().now()

    def tick(self):
        if self.last_cloud_time is None:
            self.publish_status(False, "waiting_pointcloud", "waiting_for_pointcloud")
            return

        age = (self.get_clock().now() - self.last_cloud_time).nanoseconds * 1e-9
        connected = age <= self.stale_timeout_sec
        self.publish_status(
            connected,
            "ready" if connected else "pointcloud_stale",
            "pointcloud_ok" if connected else f"pointcloud_stale age={age:.2f}s",
        )

    def publish_status(self, ready, state, reason):
        self.connected_pub.publish(Bool(data=bool(ready)))
        status = f"mode=real;state={state};ready={str(bool(ready)).lower()};reason={reason}"
        self.status_pub.publish(String(data=status))
        if status != self.last_status_text:
            self.get_logger().info(f"{self.status_label} status changed: {status}")
            self.last_status_text = status


def main():
    rclpy.init()
    node = PointCloudGuard()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
