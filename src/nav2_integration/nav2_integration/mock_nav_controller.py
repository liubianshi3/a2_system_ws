#!/usr/bin/env python3

import math

import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String


class MockNavController(Node):
    def __init__(self):
        super().__init__("mock_nav_controller")
        self.use_mock = bool(self.declare_parameter("use_mock", True).value)
        self.runtime_mode = self.declare_parameter(
            "runtime_mode", "mock" if self.use_mock else "real"
        ).value
        self.goal_topic = self.declare_parameter("goal_topic", "/a2/exploration/goal").value
        self.odom_topic = self.declare_parameter("odom_topic", "/odom").value
        self.cmd_topic = self.declare_parameter("cmd_topic", "/cmd_vel").value
        self.goal_tolerance = float(self.declare_parameter("goal_tolerance", 0.2).value)
        self.max_linear = float(self.declare_parameter("max_linear", 0.25).value)
        self.max_yaw = float(self.declare_parameter("max_yaw", 0.45).value)
        self.current_goal = None
        self.current_odom = None

        self.cmd_pub = self.create_publisher(Twist, self.cmd_topic, 10)
        self.status_pub = self.create_publisher(String, "/a2/nav2/status", 10)
        self.legacy_status_pub = self.create_publisher(String, "/a2/mock_nav/status", 10)
        self.create_subscription(PoseStamped, self.goal_topic, self.on_goal, 10)
        self.create_subscription(Odometry, self.odom_topic, self.on_odom, 20)
        self.create_timer(0.1, self.tick)

    def on_goal(self, msg):
        self.current_goal = msg
        self.publish_status(True, "goal_received", "mock_goal_received")

    def on_odom(self, msg):
        self.current_odom = msg

    def tick(self):
        cmd = Twist()
        if self.current_goal is None or self.current_odom is None:
          self.cmd_pub.publish(cmd)
          return

        x = self.current_odom.pose.pose.position.x
        y = self.current_odom.pose.pose.position.y
        q = self.current_odom.pose.pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        dx = self.current_goal.pose.position.x - x
        dy = self.current_goal.pose.position.y - y
        distance = math.hypot(dx, dy)
        target_yaw = math.atan2(dy, dx)
        yaw_error = math.atan2(math.sin(target_yaw - yaw), math.cos(target_yaw - yaw))

        if distance < self.goal_tolerance:
            self.publish_status(True, "goal_completed", "mock_goal_reached")
            self.current_goal = None
            self.cmd_pub.publish(cmd)
            return

        cmd.angular.z = max(-self.max_yaw, min(self.max_yaw, yaw_error))
        if abs(yaw_error) < 0.6:
            cmd.linear.x = max(0.0, min(self.max_linear, distance * 0.5))
        self.cmd_pub.publish(cmd)
        self.publish_status(True, "goal_executing", "mock_tracking_goal")

    def publish_status(self, ready, state, reason):
        mode = self.runtime_mode
        status = f"mode={mode};state={state};ready={str(bool(ready)).lower()};reason={reason}"
        self.status_pub.publish(String(data=status))
        self.legacy_status_pub.publish(String(data=status))


def main():
    rclpy.init()
    node = MockNavController()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
