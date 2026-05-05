from __future__ import annotations

from pathlib import Path

import rclpy
from rclpy.node import Node

from .runtime_checker import A2RuntimeChecker
from .utils import discover_nodes, write_markdown, timestamp_compact


class NavRuntimeDiagnosis(Node):
    def __init__(self) -> None:
        super().__init__("nav_runtime_diagnosis")
        self.declare_parameter("results_root", "src/a2_nav_test_runner/results")
        self.declare_parameter("data_source", "")
        self.results_root = self.get_parameter("results_root").value
        self.data_source = str(self.get_parameter("data_source").value).strip()
        self.config = {
            "nav2_action_name": "/navigate_to_pose",
            "navcommand_service_candidates": [
                "/nav_command",
                "/a2/nav_command",
                "/a2_nav_command",
                "/NavCommand",
                "/a2/task_manager/command",
            ],
            "required_topics": ["/map", "/tf", "/odom", "/amcl_pose"],
        }

    def run(self) -> str:
        output_path = Path(self.results_root) / f"nav_runtime_diagnosis_{timestamp_compact()}.md"
        checker = A2RuntimeChecker(self, self.config)
        report = checker.wait_and_check(wait_sec=1.0)
        node_names = [full_name for _, _, full_name in discover_nodes(self)]
        topic_names = sorted(name for name, _ in self.get_topic_names_and_types())
        action_names = sorted(name for name, _ in self.get_action_names_and_types()) if hasattr(self, "get_action_names_and_types") else []
        service_names = sorted(name for name, _ in self.get_service_names_and_types())

        pose_goal_controller_present = "/pose_goal_controller_3d" in node_names
        controller_server_present = any(name in node_names for name in ["/controller_server", "/controller_server_rclcpp_node"])
        bt_navigator_present = any(name in node_names for name in ["/bt_navigator", "/bt_navigator_navigate_to_pose_rclcpp_node"])
        planner_server_present = "/planner_server" in node_names
        goal_bridge_present = "/goal_bridge" in node_names
        task_manager_present = "/task_manager" in node_names

        backend_candidate, evidence = infer_backend(
            report,
            pose_goal_controller_present,
            controller_server_present,
            bt_navigator_present,
            goal_bridge_present,
            task_manager_present,
            topic_names,
        )

        lines = [
            "# Navigation Runtime Diagnosis",
            "",
            "This report is a runtime interface diagnosis. It is not a navigation experiment result.",
        ]
        if self.data_source:
            lines.append(f"- data_source: `{self.data_source}`")
            if "mock" in self.data_source.lower():
                lines.append("- THIS_IS_MOCK_DATA")
        lines.extend(
            [
                "",
                f"- backend_candidate: `{backend_candidate}`",
                "",
                "## Evidence",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in evidence] or ["- No decisive evidence was detected."])
        lines.extend(["", "## Nodes", ""])
        lines.extend([f"- `{name}`" for name in node_names] or ["- No ROS2 nodes were visible."])
        lines.extend(["", "## Topics", ""])
        lines.extend([f"- `{name}`" for name in topic_names] or ["- No ROS2 topics were visible."])
        lines.extend(["", "## Actions", ""])
        lines.extend([f"- `{name}`" for name in action_names] or ["- No ROS2 actions were visible."])
        lines.extend(["", "## Services", ""])
        lines.extend([f"- `{name}`" for name in service_names] or ["- No ROS2 services were visible."])
        lines.extend(["", "## Key Interface Presence", ""])
        lines.extend(
            [
                f"- `/navigate_to_pose` action: {report['actions'].get('/navigate_to_pose', {}).get('available')}",
                f"- `/map` topic: {report['topics'].get('/map', {}).get('available')}",
                f"- `/tf` topic: {report['topics'].get('/tf', {}).get('available')}",
                f"- `/odom` topic: {report['topics'].get('/odom', {}).get('available')}",
                f"- `/amcl_pose` topic: {report['topics'].get('/amcl_pose', {}).get('available')}",
                f"- `pose_goal_controller_3d` node: {pose_goal_controller_present}",
                f"- `controller_server` node: {controller_server_present}",
                f"- `bt_navigator` node: {bt_navigator_present}",
                f"- `planner_server` node: {planner_server_present}",
                f"- `goal_bridge` node: {goal_bridge_present}",
                f"- `task_manager` node: {task_manager_present}",
            ]
        )
        lines.extend(["", "## Missing Or Uncertain Pieces", ""])
        lines.extend([f"- {warning}" for warning in report["warnings"]] or ["- None"])
        lines.extend(["", "## Next Checks", ""])
        lines.extend(
            [
                "- Dump runtime parameters to confirm which tolerances are actually active.",
                "- Check TF chain stability before blaming goal tolerance.",
                "- Compare goal frame with final pose frame before interpreting final_error.",
                "- If NavCommand is present, verify whether it reports arrival or only command acceptance.",
            ]
        )
        written = write_markdown(str(output_path), lines)
        self.get_logger().info(f"Navigation runtime diagnosis written: {written}")
        return written


def infer_backend(report, pose_goal_controller_present, controller_server_present, bt_navigator_present, goal_bridge_present, task_manager_present, topic_names):
    evidence = []
    if report["actions"].get("/navigate_to_pose", {}).get("available") and controller_server_present:
        evidence.append("`/navigate_to_pose` action is available and `controller_server` is running.")
        if bt_navigator_present:
            evidence.append("`bt_navigator` is present, which strongly suggests Nav2 action chain is active.")
        return "nav2_action", evidence
    if pose_goal_controller_present:
        evidence.append("`pose_goal_controller_3d` node is running.")
        if "/a2/nav3/goal_pose" in topic_names:
            evidence.append("`/a2/nav3/goal_pose` topic exists, matching the 3D local goal controller path.")
        if goal_bridge_present:
            evidence.append("`goal_bridge` is running and can forward exploration goals into the 3D goal topic path.")
        return "pose_goal_controller_3d", evidence
    if any(item.get("available") for item in report["services"].values()):
        evidence.append("A NavCommand candidate service is available at runtime.")
        if task_manager_present:
            evidence.append("`task_manager` node is present and exposes `/a2/task_manager/command` in this stack.")
        return "a2_navcommand", evidence
    return "unknown", evidence


def main(args=None):
    rclpy.init(args=args)
    node = NavRuntimeDiagnosis()
    exit_code = 0
    try:
        node.run()
    except Exception as exc:
        node.get_logger().error(str(exc))
        exit_code = 1
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
