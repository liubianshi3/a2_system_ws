from __future__ import annotations

import time

import rclpy
from a2_interfaces.srv import NavCommand
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node

from .utils import load_yaml_file


class MockNavCommandService(Node):
    def __init__(self) -> None:
        super().__init__("task_manager")
        self.declare_parameter("scenarios_yaml", "src/a2_nav_test_runner/config/mock_precision_scenarios.yaml")
        self.declare_parameter("scenario", "clean_nav")
        self.scenario = load_scenario(self.get_parameter("scenarios_yaml").value, self.get_parameter("scenario").value)
        self.goal_pub = self.create_publisher(PoseStamped, "/mock_nav/goal", 10)
        self.declare_parameter("navigation_backend", "nav2")
        self._service = self.create_service(NavCommand, "/a2/task_manager/command", self.handle_command)

    def handle_command(self, request, response):
        self.goal_pub.publish(request.pose)
        time.sleep(0.1)
        response.success = bool(self.scenario.get("service_success", True))
        response.message = "mock_nav_command_service"
        response.current_mode = "mock"
        response.mission_state = "accepted" if response.success else "rejected"
        return response


def load_scenario(path, scenario_name):
    data = load_yaml_file(path)
    for item in data.get("scenarios", []):
        if item.get("name") == scenario_name:
            return item
    raise RuntimeError(f"Scenario not found: {scenario_name}")


def main(args=None):
    rclpy.init(args=args)
    node = MockNavCommandService()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
