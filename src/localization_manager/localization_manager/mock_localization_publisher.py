#!/usr/bin/env python3

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node


class MockLocalizationPublisher(Node):
    def __init__(self):
        super().__init__("mock_localization_publisher")
        self.odom_topic = self.declare_parameter("odom_topic", "/odom").value
        self.pose_topic = self.declare_parameter("pose_topic", "/amcl_pose").value
        self.xy_variance = float(self.declare_parameter("xy_variance", 0.02).value)
        self.yaw_variance = float(self.declare_parameter("yaw_variance", 0.02).value)
        self.publisher = self.create_publisher(PoseWithCovarianceStamped, self.pose_topic, 10)
        self.create_subscription(Odometry, self.odom_topic, self.on_odom, 20)

    def on_odom(self, msg):
        pose = PoseWithCovarianceStamped()
        pose.header = msg.header
        pose.header.frame_id = "map"
        pose.pose.pose = msg.pose.pose
        pose.pose.covariance[0] = self.xy_variance
        pose.pose.covariance[7] = self.xy_variance
        pose.pose.covariance[35] = self.yaw_variance
        self.publisher.publish(pose)


def main():
    rclpy.init()
    node = MockLocalizationPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
