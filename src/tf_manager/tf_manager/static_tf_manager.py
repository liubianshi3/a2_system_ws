#!/usr/bin/env python3

from pathlib import Path

import rclpy
import yaml
from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster


class StaticTfManager(Node):
    def __init__(self):
        super().__init__("static_tf_manager")
        self.extrinsics_file = self.declare_parameter("extrinsics_file", "").value
        self.tf_file = self.declare_parameter("tf_file", "").value
        self.base_height = float(self.declare_parameter("base_height", 0.28).value)
        self.broadcaster = StaticTransformBroadcaster(self)
        self.publish_once()

    def load_yaml(self, path):
        if not path:
            return {}
        file_path = Path(path)
        if not file_path.exists():
            self.get_logger().warn(f"YAML not found: {file_path}")
            return {}
        with file_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def make_transform(self, parent, child, xyz, rpy):
        msg = TransformStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = parent
        msg.child_frame_id = child
        msg.transform.translation.x = float(xyz[0])
        msg.transform.translation.y = float(xyz[1])
        msg.transform.translation.z = float(xyz[2])

        roll, pitch, yaw = [float(value) for value in rpy]
        import math

        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)
        msg.transform.rotation.w = cr * cp * cy + sr * sp * sy
        msg.transform.rotation.x = sr * cp * cy - cr * sp * sy
        msg.transform.rotation.y = cr * sp * cy + sr * cp * sy
        msg.transform.rotation.z = cr * cp * sy - sr * sp * cy
        return msg

    def publish_once(self):
        extrinsics = self.load_yaml(self.extrinsics_file).get("extrinsics", {})
        tf_tree = self.load_yaml(self.tf_file).get("tf_tree", {})
        base_frame = tf_tree.get("base_frame", "base_link")
        footprint_frame = tf_tree.get("footprint_frame", "base_footprint")
        trunk_frame = tf_tree.get("body_semantic_frame", "trunk")

        transforms = [
            self.make_transform(footprint_frame, base_frame, [0.0, 0.0, self.base_height], [0.0, 0.0, 0.0]),
            self.make_transform(base_frame, trunk_frame, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]),
        ]

        for sensor_name, spec in extrinsics.items():
            transforms.append(
                self.make_transform(
                    spec.get("parent", base_frame),
                    spec.get("child", sensor_name + "_link"),
                    spec.get("xyz", [0.0, 0.0, 0.0]),
                    spec.get("rpy", [0.0, 0.0, 0.0]),
                )
            )

        self.broadcaster.sendTransform(transforms)


def main():
    rclpy.init()
    node = StaticTfManager()
    rclpy.spin_once(node, timeout_sec=0.1)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
