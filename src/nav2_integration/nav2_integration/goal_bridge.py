#!/usr/bin/env python3

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String


class GoalBridge(Node):
    def __init__(self):
        super().__init__("goal_bridge")
        self.use_mock = bool(self.declare_parameter("use_mock", True).value)
        self.runtime_mode = self.declare_parameter(
            "runtime_mode", "mock" if self.use_mock else "real"
        ).value
        self.goal_topic = self.declare_parameter("exploration_goal_topic", "/a2/exploration/goal").value
        self.action_name = self.declare_parameter("navigate_action_name", "navigate_to_pose").value
        self.status_pub = self.create_publisher(String, "/a2/nav2/status", 10)
        self.action_client = None
        self.navigate_type = None
        self.active_goal_handle = None
        try:
            from nav2_msgs.action import NavigateToPose

            self.navigate_type = NavigateToPose
            self.action_client = ActionClient(self, NavigateToPose, self.action_name)
        except ImportError:
            self.get_logger().error("nav2_msgs is not available. Goal bridge will stay idle until Nav2 is installed.")

        self.create_subscription(PoseStamped, self.goal_topic, self.on_goal, 10)

    def on_goal(self, msg):
        if self.use_mock:
            return
        if self.action_client is None or self.navigate_type is None:
            self.publish_status(False, "bridge_unavailable", "nav2_msgs_missing")
            return
        if not self.action_client.server_is_ready():
            self.get_logger().warn("NavigateToPose action server is not ready.")
            self.publish_status(False, "waiting_server", "navigate_action_not_ready")
            return
        if self.active_goal_handle is not None:
            status = getattr(self.active_goal_handle, "status", None)
            if status in (0, 1, 2, 3):
                self.publish_status(True, "goal_active", "action_goal_already_running")
                return

        goal = self.navigate_type.Goal()
        goal.pose = msg
        future = self.action_client.send_goal_async(goal)
        future.add_done_callback(self.goal_response_callback)
        self.publish_status(True, "goal_sent", "action_goal_dispatched")

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.publish_status(False, "goal_rejected", "action_goal_rejected")
            return
        self.active_goal_handle = goal_handle
        self.publish_status(True, "goal_accepted", "action_goal_accepted")
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.result_callback)

    def result_callback(self, future):
        _ = future.result()
        self.active_goal_handle = None
        self.publish_status(True, "goal_completed", "action_goal_completed")

    def publish_status(self, ready, state, reason):
        status = (
            f"mode={self.runtime_mode};state={state};ready={str(bool(ready)).lower()};"
            f"reason={reason}"
        )
        self.status_pub.publish(String(data=status))


def main():
    rclpy.init()
    node = GoalBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
