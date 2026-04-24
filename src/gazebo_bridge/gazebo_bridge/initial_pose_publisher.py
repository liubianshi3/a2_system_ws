#!/usr/bin/env python3

import math

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node


class InitialPosePublisher(Node):
    def __init__(self):
        super().__init__("initial_pose_publisher")
        self.topic = self.declare_parameter("topic", "/initialpose").value
        self.frame_id = self.declare_parameter("frame_id", "map").value
        self.publish_count = int(self.declare_parameter("publish_count", 5).value)
        self.publish_period_sec = float(self.declare_parameter("publish_period_sec", 0.5).value)
        self.wait_for_odom = bool(self.declare_parameter("wait_for_odom", True).value)
        self.use_latest_odom_stamp = bool(
            self.declare_parameter("use_latest_odom_stamp", False).value
        )
        self.use_zero_stamp = bool(self.declare_parameter("use_zero_stamp", True).value)
        self.odom_topic = self.declare_parameter("odom_topic", "/odom").value
        self.pose_x = float(self.declare_parameter("x", 0.0).value)
        self.pose_y = float(self.declare_parameter("y", 0.0).value)
        self.pose_yaw = float(self.declare_parameter("yaw", 0.0).value)
        self.xy_variance = float(self.declare_parameter("xy_variance", 0.05).value)
        self.yaw_variance = float(self.declare_parameter("yaw_variance", 0.1).value)

        self.publisher = self.create_publisher(PoseWithCovarianceStamped, self.topic, 10)
        self.latest_odom_stamp = None
        self.remaining = self.publish_count
        self.create_subscription(Odometry, self.odom_topic, self.on_odom, 10)
        self.timer = self.create_timer(self.publish_period_sec, self.publish_pose)

    def on_odom(self, msg):
        self.latest_odom_stamp = msg.header.stamp

    def publish_pose(self):
        if self.remaining <= 0:
            self.timer.cancel()
            return
        if self.wait_for_odom and self.latest_odom_stamp is None:
            return
        msg = PoseWithCovarianceStamped()
        if self.use_zero_stamp:
            msg.header.stamp.sec = 0
            msg.header.stamp.nanosec = 0
        elif self.use_latest_odom_stamp and self.latest_odom_stamp is not None:
            msg.header.stamp = self.latest_odom_stamp
        else:
            msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        msg.pose.pose.position.x = self.pose_x
        msg.pose.pose.position.y = self.pose_y
        msg.pose.pose.orientation.z = math.sin(self.pose_yaw * 0.5)
        msg.pose.pose.orientation.w = math.cos(self.pose_yaw * 0.5)
        msg.pose.covariance[0] = self.xy_variance
        msg.pose.covariance[7] = self.xy_variance
        msg.pose.covariance[35] = self.yaw_variance
        self.publisher.publish(msg)
        self.remaining -= 1


def main():
    rclpy.init()
    node = InitialPosePublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
