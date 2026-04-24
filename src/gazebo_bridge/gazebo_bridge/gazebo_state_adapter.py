#!/usr/bin/env python3

import math

import rclpy
from a2_interfaces.msg import RobotState
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Bool, String


class GazeboStateAdapter(Node):
    def __init__(self):
        super().__init__("gazebo_state_adapter")
        self.runtime_mode = self.declare_parameter("runtime_mode", "gazebo").value
        self.odom_topic = self.declare_parameter("odom_topic", "/gazebo/odom").value
        self.imu_topic = self.declare_parameter("imu_topic", "/gazebo/imu").value
        self.state_topic = self.declare_parameter("state_topic", "/a2/raw_state").value
        self.sdk_connected_topic = self.declare_parameter(
            "sdk_connected_topic", "/a2/sdk/connected"
        ).value
        self.sdk_status_topic = self.declare_parameter(
            "sdk_status_topic", "/a2/sdk/status"
        ).value
        self.base_frame = self.declare_parameter("base_frame", "base_link").value
        self.body_height = float(self.declare_parameter("body_height", 0.14).value)
        self.stale_timeout_sec = float(self.declare_parameter("stale_timeout_sec", 0.5).value)

        self.last_odom = None
        self.last_imu = None
        self.last_status = ""

        self.state_pub = self.create_publisher(RobotState, self.state_topic, 20)
        self.sdk_connected_pub = self.create_publisher(Bool, self.sdk_connected_topic, 10)
        self.sdk_status_pub = self.create_publisher(String, self.sdk_status_topic, 10)
        self.create_subscription(Odometry, self.odom_topic, self.on_odom, 20)
        self.create_subscription(Imu, self.imu_topic, self.on_imu, 20)
        self.create_timer(0.05, self.publish_state)

    def on_odom(self, msg):
        self.last_odom = msg

    def on_imu(self, msg):
        self.last_imu = msg

    def msg_age_sec(self, stamp):
        return (self.get_clock().now() - rclpy.time.Time.from_msg(stamp)).nanoseconds * 1e-9

    def publish_status(self, ready, state, reason):
        self.sdk_connected_pub.publish(Bool(data=bool(ready)))
        status = (
            f"mode={self.runtime_mode};state={state};ready={str(bool(ready)).lower()};"
            f"reason={reason};interface=gazebo"
        )
        self.sdk_status_pub.publish(String(data=status))
        if status != self.last_status:
            self.last_status = status
            self.get_logger().info(f"Gazebo state adapter status changed: {status}")

    def publish_state(self):
        if self.last_odom is None:
            self.publish_status(False, "waiting_odom", "waiting_for_odometry")
            return

        odom_age = self.msg_age_sec(self.last_odom.header.stamp)
        imu_ready = self.last_imu is not None and self.msg_age_sec(self.last_imu.header.stamp) <= self.stale_timeout_sec
        odom_ready = odom_age <= self.stale_timeout_sec

        if not odom_ready:
            self.publish_status(False, "stale", f"odometry_stale age={odom_age:.2f}s")
            return
        if not imu_ready:
            self.publish_status(False, "waiting_imu", "waiting_for_imu")
            return

        odom = self.last_odom
        imu = self.last_imu
        msg = RobotState()
        msg.stamp = odom.header.stamp
        msg.source_mode = self.runtime_mode
        msg.frame_id = self.base_frame
        msg.connected = True
        msg.imu_valid = True
        msg.odom_valid = True
        msg.position[0] = float(odom.pose.pose.position.x)
        msg.position[1] = float(odom.pose.pose.position.y)
        msg.position[2] = float(odom.pose.pose.position.z or self.body_height)
        msg.velocity[0] = float(odom.twist.twist.linear.x)
        msg.velocity[1] = float(odom.twist.twist.linear.y)
        msg.velocity[2] = float(odom.twist.twist.linear.z)
        msg.orientation_xyzw[0] = float(imu.orientation.x)
        msg.orientation_xyzw[1] = float(imu.orientation.y)
        msg.orientation_xyzw[2] = float(imu.orientation.z)
        msg.orientation_xyzw[3] = float(imu.orientation.w)
        msg.linear_acceleration[0] = float(imu.linear_acceleration.x)
        msg.linear_acceleration[1] = float(imu.linear_acceleration.y)
        msg.linear_acceleration[2] = float(imu.linear_acceleration.z)
        msg.angular_velocity[0] = float(imu.angular_velocity.x)
        msg.angular_velocity[1] = float(imu.angular_velocity.y)
        msg.angular_velocity[2] = float(imu.angular_velocity.z)
        msg.body_height = float(self.body_height)
        msg.yaw_speed = float(odom.twist.twist.angular.z)
        msg.motion_mode = 1
        msg.progress = 0.0
        msg.gait_type = 1

        qx = msg.orientation_xyzw[0]
        qy = msg.orientation_xyzw[1]
        qz = msg.orientation_xyzw[2]
        qw = msg.orientation_xyzw[3]
        sinr_cosp = 2.0 * (qw * qx + qy * qz)
        cosr_cosp = 1.0 - 2.0 * (qx * qx + qy * qy)
        sinp = 2.0 * (qw * qy - qz * qx)
        siny_cosp = 2.0 * (qw * qz + qx * qy)
        cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
        msg.rpy[0] = float(math.atan2(sinr_cosp, cosr_cosp))
        msg.rpy[1] = float(math.copysign(math.pi / 2.0, sinp) if abs(sinp) >= 1.0 else math.asin(sinp))
        msg.rpy[2] = float(math.atan2(siny_cosp, cosy_cosp))

        self.state_pub.publish(msg)
        self.publish_status(True, "ready", "gazebo_state_ok")


def main():
    rclpy.init()
    node = GazeboStateAdapter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
