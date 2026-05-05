from __future__ import annotations

import time

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionServer
from rclpy.node import Node

from .utils import load_yaml_file


class MockNav2ActionServer(Node):
    def __init__(self) -> None:
        super().__init__("controller_server")
        self.declare_parameter("scenarios_yaml", "src/a2_nav_test_runner/config/mock_precision_scenarios.yaml")
        self.declare_parameter("scenario", "clean_nav")
        self.declare_parameter("data_source", "mock_navigation_test")
        self.scenario = load_scenario(self.get_parameter("scenarios_yaml").value, self.get_parameter("scenario").value)
        self.data_source = str(self.get_parameter("data_source").value)
        self.goal_pub = self.create_publisher(PoseStamped, "/mock_nav/goal", 10)
        self.declare_parameter("general_goal_checker.plugin", "nav2_controller::SimpleGoalChecker")
        self.declare_parameter("general_goal_checker.xy_goal_tolerance", float(self.scenario.get("runtime_xy_goal_tolerance", 0.06)))
        self.declare_parameter("general_goal_checker.yaw_goal_tolerance", 0.08)
        self.declare_parameter("FollowPath.xy_goal_tolerance", float(self.scenario.get("runtime_xy_goal_tolerance", 0.06)))
        self.declare_parameter("global_costmap.global_costmap.robot_base_frame", "base_link")
        self.declare_parameter("local_costmap.local_costmap.robot_base_frame", "base_link")
        self._server = ActionServer(self, NavigateToPose, "/navigate_to_pose", execute_callback=self.execute_callback)

    def execute_callback(self, goal_handle):
        pose = goal_handle.request.pose
        self.goal_pub.publish(pose)
        time.sleep(0.3)
        result = NavigateToPose.Result()
        backend_success = bool(self.scenario.get("backend_success", True))
        if backend_success:
            goal_handle.succeed()
        else:
            goal_handle.abort()
        return result


def load_scenario(path, scenario_name):
    data = load_yaml_file(path)
    for item in data.get("scenarios", []):
        if item.get("name") == scenario_name:
            return item
    raise RuntimeError(f"Scenario not found: {scenario_name}")


def main(args=None):
    rclpy.init(args=args)
    node = MockNav2ActionServer()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
