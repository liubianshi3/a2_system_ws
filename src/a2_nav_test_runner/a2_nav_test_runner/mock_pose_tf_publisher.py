from __future__ import annotations

import math
import random

import rclpy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, TransformStamped
from nav_msgs.msg import OccupancyGrid, MapMetaData, Odometry
from rclpy.node import Node
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster

from .utils import load_yaml_file, yaw_to_quaternion


class MockPoseTfPublisher(Node):
    def __init__(self) -> None:
        super().__init__("amcl")
        self.declare_parameter("scenarios_yaml", "src/a2_nav_test_runner/config/mock_precision_scenarios.yaml")
        self.declare_parameter("scenario", "clean_nav")
        self.declare_parameter("publish_hz", 10.0)
        self.declare_parameter("data_source", "mock_navigation_test")
        self.scenario = load_scenario(self.get_parameter("scenarios_yaml").value, self.get_parameter("scenario").value)
        self.publish_hz = float(self.get_parameter("publish_hz").value)
        self.declare_parameter("global_frame_id", "map")
        self.declare_parameter("odom_frame_id", "odom")
        self.declare_parameter("base_frame_id", "base_link")
        self.amcl_pub = self.create_publisher(PoseWithCovarianceStamped, "/amcl_pose", 10)
        self.odom_pub = self.create_publisher(Odometry, "/odom", 10)
        self.map_pub = self.create_publisher(OccupancyGrid, "/map", 10)
        self.goal_sub = self.create_subscription(PoseStamped, "/mock_nav/goal", self.on_goal, 10)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.static_broadcaster = StaticTransformBroadcaster(self)
        self.true_x = 0.0
        self.true_y = 0.0
        self.true_yaw = 0.0
        self.target_x = 0.0
        self.target_y = 0.0
        self.target_yaw = 0.0
        self.publish_static_transforms()
        self.timer = self.create_timer(1.0 / max(1.0, self.publish_hz), self.on_timer)

    def publish_static_transforms(self):
        stamp = self.get_clock().now().to_msg()
        transforms = []
        fixed_offset_x = float(self.scenario.get("fixed_offset_x", 0.0))
        fixed_offset_y = float(self.scenario.get("fixed_offset_y", 0.0))
        for child, x, y in [
            ("base_footprint", -fixed_offset_x, -fixed_offset_y),
            ("lidar", 0.10, 0.00),
            ("imu_link", 0.00, 0.00),
        ]:
            tf = TransformStamped()
            tf.header.stamp = stamp
            tf.header.frame_id = "base_link"
            tf.child_frame_id = child
            tf.transform.translation.x = float(x)
            tf.transform.translation.y = float(y)
            tf.transform.translation.z = 0.0
            quat = yaw_to_quaternion(0.0)
            tf.transform.rotation.x = quat["x"]
            tf.transform.rotation.y = quat["y"]
            tf.transform.rotation.z = quat["z"]
            tf.transform.rotation.w = quat["w"]
            transforms.append(tf)
        self.static_broadcaster.sendTransform(transforms)

    def on_goal(self, msg: PoseStamped):
        self.target_x = float(msg.pose.position.x)
        self.target_y = float(msg.pose.position.y)
        self.target_yaw = 0.0
        final_error = float(self.scenario.get("final_error", 0.0))
        self.true_x = self.target_x + final_error
        self.true_y = self.target_y
        self.true_yaw = self.target_yaw

    def on_timer(self):
        noise = float(self.scenario.get("pose_noise_std", 0.0))
        map_noise_x = random.gauss(0.0, noise)
        map_noise_y = random.gauss(0.0, noise)
        map_noise_yaw = random.gauss(0.0, noise * 0.2)
        self.publish_map()
        self.publish_amcl(self.true_x + map_noise_x, self.true_y + map_noise_y, self.true_yaw + map_noise_yaw)
        self.publish_odom(self.true_x, self.true_y, self.true_yaw)
        self.publish_dynamic_tf(map_noise_x, map_noise_y, map_noise_yaw)

    def publish_map(self):
        msg = OccupancyGrid()
        msg.header.frame_id = "map"
        meta = MapMetaData()
        meta.resolution = 0.1
        meta.width = 10
        meta.height = 10
        msg.info = meta
        msg.data = [0] * (meta.width * meta.height)
        self.map_pub.publish(msg)

    def publish_amcl(self, x, y, yaw):
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = "map"
        msg.pose.pose.position.x = float(x)
        msg.pose.pose.position.y = float(y)
        quat = yaw_to_quaternion(yaw)
        msg.pose.pose.orientation.x = quat["x"]
        msg.pose.pose.orientation.y = quat["y"]
        msg.pose.pose.orientation.z = quat["z"]
        msg.pose.pose.orientation.w = quat["w"]
        self.amcl_pub.publish(msg)

    def publish_odom(self, x, y, yaw):
        msg = Odometry()
        msg.header.frame_id = "odom"
        msg.child_frame_id = "base_link"
        msg.pose.pose.position.x = float(x)
        msg.pose.pose.position.y = float(y)
        quat = yaw_to_quaternion(yaw)
        msg.pose.pose.orientation.x = quat["x"]
        msg.pose.pose.orientation.y = quat["y"]
        msg.pose.pose.orientation.z = quat["z"]
        msg.pose.pose.orientation.w = quat["w"]
        self.odom_pub.publish(msg)

    def publish_dynamic_tf(self, map_noise_x, map_noise_y, map_noise_yaw):
        map_to_odom = TransformStamped()
        now = self.get_clock().now().to_msg()
        map_to_odom.header.stamp = now
        map_to_odom.header.frame_id = "map"
        map_to_odom.child_frame_id = "odom"
        if bool(self.scenario.get("tf_jump_enabled", False)):
            map_to_odom.transform.translation.x = map_noise_x * 2.0
            map_to_odom.transform.translation.y = map_noise_y * 2.0
        else:
            map_to_odom.transform.translation.x = map_noise_x
            map_to_odom.transform.translation.y = map_noise_y
        map_to_odom.transform.translation.z = 0.0
        quat = yaw_to_quaternion(map_noise_yaw)
        map_to_odom.transform.rotation.x = quat["x"]
        map_to_odom.transform.rotation.y = quat["y"]
        map_to_odom.transform.rotation.z = quat["z"]
        map_to_odom.transform.rotation.w = quat["w"]

        odom_to_base = TransformStamped()
        odom_to_base.header.stamp = now
        odom_to_base.header.frame_id = "odom"
        odom_to_base.child_frame_id = "base_link"
        odom_to_base.transform.translation.x = self.true_x
        odom_to_base.transform.translation.y = self.true_y
        odom_to_base.transform.translation.z = 0.0
        quat2 = yaw_to_quaternion(self.true_yaw)
        odom_to_base.transform.rotation.x = quat2["x"]
        odom_to_base.transform.rotation.y = quat2["y"]
        odom_to_base.transform.rotation.z = quat2["z"]
        odom_to_base.transform.rotation.w = quat2["w"]
        self.tf_broadcaster.sendTransform([map_to_odom, odom_to_base])


def load_scenario(path, scenario_name):
    data = load_yaml_file(path)
    for item in data.get("scenarios", []):
        if item.get("name") == scenario_name:
            return item
    raise RuntimeError(f"Scenario not found: {scenario_name}")


def main(args=None):
    rclpy.init(args=args)
    node = MockPoseTfPublisher()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
