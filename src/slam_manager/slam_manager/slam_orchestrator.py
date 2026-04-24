#!/usr/bin/env python3

import rclpy
from a2_interfaces.srv import SetMode
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Bool, String
from tf2_ros import TransformBroadcaster


class SlamOrchestrator(Node):
    def __init__(self):
        super().__init__("slam_orchestrator")
        self.use_mock = bool(self.declare_parameter("use_mock", True).value)
        self.runtime_mode = self.declare_parameter(
            "runtime_mode", "mock" if self.use_mock else "real"
        ).value
        self.default_mode = self.declare_parameter("default_mode", "mapping").value
        self.publish_identity_map_odom = bool(
            self.declare_parameter("publish_identity_map_odom", True).value
        )
        self.stack_profile = self.declare_parameter("stack_profile", "fast_lio").value
        self.stack_available = bool(self.declare_parameter("stack_available", False).value)
        self.stack_blocked_reason = self.declare_parameter("stack_blocked_reason", "").value
        self.status_timeout_sec = float(
            self.declare_parameter("status_timeout_sec", 1.0).value
        )
        self.external_odom_topics = list(
            self.declare_parameter("external_odom_topics", ["/Odometry"]).value
        )
        self.mode = self.default_mode
        self.last_external_odom_time = None
        self.last_external_odom_topic = ""

        self.status_pub = self.create_publisher(String, "/a2/slam/status", 10)
        self.mode_pub = self.create_publisher(String, "/a2/slam/mode", 10)
        self.mapping_pub = self.create_publisher(Bool, "/a2/slam/mapping_active", 10)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.create_service(SetMode, "/slam_manager/set_mode", self.handle_set_mode)
        self.odom_subscriptions = []
        if self.runtime_mode == "real":
            for topic in self.external_odom_topics:
                if not topic:
                    continue
                self.odom_subscriptions.append(
                    self.create_subscription(
                        Odometry,
                        topic,
                        lambda msg, topic_name=topic: self.on_external_odom(msg, topic_name),
                        10,
                    )
                )
        self.create_timer(0.2, self.tick)

    def handle_set_mode(self, request, response):
        allowed = {"mapping", "localization", "navigation", "idle"}
        if request.mode not in allowed:
            response.success = False
            response.message = f"unsupported slam mode: {request.mode}"
            return response
        self.mode = request.mode
        response.success = True
        response.message = f"slam mode set to {self.mode}"
        return response

    def on_external_odom(self, msg, topic_name):
        del msg
        self.last_external_odom_time = self.get_clock().now()
        self.last_external_odom_topic = topic_name

    def tick(self):
        self.mode_pub.publish(String(data=self.mode))
        self.mapping_pub.publish(Bool(data=self.mode == "mapping"))
        self.status_pub.publish(String(data=self.build_status()))
        if self.runtime_mode in {"mock", "gazebo"} and self.publish_identity_map_odom:
            self.publish_identity_tf()

    def build_status(self):
        if self.runtime_mode == "mock":
            return (
                f"mode=mock;state=ready;ready=true;reason=mock_mode;"
                f"slam_mode={self.mode};profile={self.stack_profile}"
            )
        if self.runtime_mode == "gazebo":
            return (
                f"mode=gazebo;state=ready;ready=true;reason=gazebo_sim;"
                f"slam_mode={self.mode};profile={self.stack_profile}"
            )
        if self.stack_blocked_reason:
            return (
                f"mode=real;state=blocked;ready=false;reason={self.stack_blocked_reason};"
                f"slam_mode={self.mode};profile={self.stack_profile}"
            )
        if not self.stack_available:
            return (
                f"mode=real;state=waiting_stack;ready=false;reason=external_stack_missing;"
                f"slam_mode={self.mode};profile={self.stack_profile}"
            )
        if self.last_external_odom_time is None:
            return (
                f"mode=real;state=waiting_odometry;ready=false;reason=external_stack_waiting_for_odometry;"
                f"slam_mode={self.mode};profile={self.stack_profile}"
            )

        age = (self.get_clock().now() - self.last_external_odom_time).nanoseconds / 1e9
        if age > self.status_timeout_sec:
            return (
                f"mode=real;state=stale;ready=false;reason=external_odometry_stale;"
                f"slam_mode={self.mode};profile={self.stack_profile};"
                f"topic={self.last_external_odom_topic};age_sec={age:.2f}"
            )
        return (
            f"mode=real;state=ready;ready=true;reason=external_stack_ready;"
            f"slam_mode={self.mode};profile={self.stack_profile};topic={self.last_external_odom_topic}"
        )

    def publish_identity_tf(self):
        tf_msg = TransformStamped()
        tf_msg.header.stamp = self.get_clock().now().to_msg()
        tf_msg.header.frame_id = "map"
        tf_msg.child_frame_id = "odom"
        tf_msg.transform.rotation.w = 1.0
        self.tf_broadcaster.sendTransform(tf_msg)


def main():
    rclpy.init()
    node = SlamOrchestrator()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
