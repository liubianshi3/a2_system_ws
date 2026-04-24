#!/usr/bin/env python3

import math
from dataclasses import dataclass

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from tf2_ros import TransformBroadcaster


@dataclass
class PlanarPose:
    x: float
    y: float
    yaw: float


def normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def quaternion_to_yaw(orientation) -> float:
    siny_cosp = 2.0 * (orientation.w * orientation.z + orientation.x * orientation.y)
    cosy_cosp = 1.0 - 2.0 * (orientation.y * orientation.y + orientation.z * orientation.z)
    return math.atan2(siny_cosp, cosy_cosp)


def yaw_to_quaternion(yaw: float) -> tuple[float, float, float, float]:
    half_yaw = yaw * 0.5
    return (0.0, 0.0, math.sin(half_yaw), math.cos(half_yaw))


def inverse_pose(pose: PlanarPose) -> PlanarPose:
    cos_yaw = math.cos(pose.yaw)
    sin_yaw = math.sin(pose.yaw)
    return PlanarPose(
        x=-cos_yaw * pose.x - sin_yaw * pose.y,
        y=sin_yaw * pose.x - cos_yaw * pose.y,
        yaw=normalize_angle(-pose.yaw),
    )


def compose_pose(lhs: PlanarPose, rhs: PlanarPose) -> PlanarPose:
    cos_yaw = math.cos(lhs.yaw)
    sin_yaw = math.sin(lhs.yaw)
    return PlanarPose(
        x=lhs.x + cos_yaw * rhs.x - sin_yaw * rhs.y,
        y=lhs.y + sin_yaw * rhs.x + cos_yaw * rhs.y,
        yaw=normalize_angle(lhs.yaw + rhs.yaw),
    )


def odom_to_planar_pose(msg: Odometry) -> PlanarPose:
    pose = msg.pose.pose
    return PlanarPose(
        x=float(pose.position.x),
        y=float(pose.position.y),
        yaw=quaternion_to_yaw(pose.orientation),
    )


def initialpose_to_planar_pose(msg: PoseWithCovarianceStamped) -> PlanarPose:
    pose = msg.pose.pose
    return PlanarPose(
        x=float(pose.position.x),
        y=float(pose.position.y),
        yaw=quaternion_to_yaw(pose.orientation),
    )


class ManualLocalizationPublisher(Node):
    def __init__(self):
        super().__init__("manual_localization_publisher")
        self.odom_topic = self.declare_parameter("odom_topic", "/odom").value
        self.initial_pose_topic = self.declare_parameter("initial_pose_topic", "/initialpose").value
        self.pose_topic = self.declare_parameter("pose_topic", "/amcl_pose").value
        self.map_frame = self.declare_parameter("map_frame", "map").value
        self.odom_frame = self.declare_parameter("odom_frame", "odom").value
        self.base_frame = self.declare_parameter("base_frame", "base_link").value
        self.xy_variance = float(self.declare_parameter("xy_variance", 0.02).value)
        self.yaw_variance = float(self.declare_parameter("yaw_variance", 0.02).value)
        self.publish_tf = bool(self.declare_parameter("publish_tf", True).value)

        pose_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.pose_publisher = self.create_publisher(
            PoseWithCovarianceStamped,
            self.pose_topic,
            pose_qos,
        )
        self.tf_broadcaster = TransformBroadcaster(self)

        self.last_odom_msg: Odometry | None = None
        self.odom_reference: PlanarPose | None = None
        self.map_reference: PlanarPose | None = None
        self.pending_initial_pose: PoseWithCovarianceStamped | None = None

        self.create_subscription(Odometry, self.odom_topic, self.on_odom, 20)
        self.create_subscription(PoseWithCovarianceStamped, self.initial_pose_topic, self.on_initial_pose, 10)

    def on_initial_pose(self, msg: PoseWithCovarianceStamped) -> None:
        if self.last_odom_msg is None:
            self.pending_initial_pose = msg
            self.get_logger().warning(
                "Received initial pose before odom. Waiting for odom to anchor map->odom."
            )
            return

        self.apply_initial_pose(msg, self.last_odom_msg)

    def on_odom(self, msg: Odometry) -> None:
        self.last_odom_msg = msg
        if self.pending_initial_pose is not None and self.odom_reference is None:
            self.apply_initial_pose(self.pending_initial_pose, msg)
            self.pending_initial_pose = None

        if self.odom_reference is None or self.map_reference is None:
            return

        current_odom = odom_to_planar_pose(msg)
        odom_delta = compose_pose(inverse_pose(self.odom_reference), current_odom)
        current_map_pose = compose_pose(self.map_reference, odom_delta)
        map_to_odom = compose_pose(current_map_pose, inverse_pose(current_odom))

        self.publish_pose(msg, current_map_pose)
        if self.publish_tf:
            self.publish_transform(msg, map_to_odom)

    def apply_initial_pose(self, pose_msg: PoseWithCovarianceStamped, odom_msg: Odometry) -> None:
        self.odom_reference = odom_to_planar_pose(odom_msg)
        self.map_reference = initialpose_to_planar_pose(pose_msg)
        self.get_logger().info(
            "Anchored manual localization at "
            f"map=({self.map_reference.x:.2f}, {self.map_reference.y:.2f}, {self.map_reference.yaw:.2f}) "
            f"odom=({self.odom_reference.x:.2f}, {self.odom_reference.y:.2f}, {self.odom_reference.yaw:.2f})"
        )

    def publish_pose(self, odom_msg: Odometry, pose: PlanarPose) -> None:
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = odom_msg.header.stamp
        msg.header.frame_id = self.map_frame
        msg.pose.pose.position.x = pose.x
        msg.pose.pose.position.y = pose.y
        msg.pose.pose.position.z = 0.0
        _, _, qz, qw = yaw_to_quaternion(pose.yaw)
        msg.pose.pose.orientation.z = qz
        msg.pose.pose.orientation.w = qw
        msg.pose.covariance[0] = self.xy_variance
        msg.pose.covariance[7] = self.xy_variance
        msg.pose.covariance[35] = self.yaw_variance
        self.pose_publisher.publish(msg)

    def publish_transform(self, odom_msg: Odometry, pose: PlanarPose) -> None:
        tf_msg = TransformStamped()
        tf_msg.header.stamp = odom_msg.header.stamp
        tf_msg.header.frame_id = self.map_frame
        tf_msg.child_frame_id = self.odom_frame
        tf_msg.transform.translation.x = pose.x
        tf_msg.transform.translation.y = pose.y
        tf_msg.transform.translation.z = 0.0
        _, _, qz, qw = yaw_to_quaternion(pose.yaw)
        tf_msg.transform.rotation.z = qz
        tf_msg.transform.rotation.w = qw
        self.tf_broadcaster.sendTransform(tf_msg)


def main():
    rclpy.init()
    node = ManualLocalizationPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
