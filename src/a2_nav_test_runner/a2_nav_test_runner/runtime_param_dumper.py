from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import rclpy
import yaml
from rclpy.node import Node

from .utils import discover_nodes, ensure_dir, get_node_parameters, list_node_parameters, timestamp_compact, write_markdown


KEYWORDS = [
    "controller",
    "nav",
    "planner",
    "bt_navigator",
    "behavior",
    "smoother",
    "waypoint",
    "pose",
    "goal",
    "localization",
    "amcl",
    "slam",
]

SUMMARY_KEYWORDS = [
    "tolerance",
    "goal_tolerance",
    "xy_goal_tolerance",
    "yaw_goal_tolerance",
    "goal_checker",
    "progress_checker",
    "controller_plugins",
    "planner_plugins",
    "robot_base_frame",
    "global_frame",
    "odom_frame",
    "base_link",
    "base_footprint",
    "transform_tolerance",
    "inflation_radius",
    "footprint",
    "robot_radius",
    "max_vel_x",
    "max_vel_theta",
    "min_speed_xy",
]


class RuntimeParamDumper(Node):
    def __init__(self) -> None:
        super().__init__("runtime_param_dumper")
        self.declare_parameter("results_root", "src/a2_nav_test_runner/results")
        self.declare_parameter("data_source", "")
        self.results_root = self.get_parameter("results_root").value
        self.data_source = str(self.get_parameter("data_source").value).strip()

    def run(self) -> str:
        output_dir = ensure_dir(str(Path(self.results_root) / f"runtime_params_{timestamp_compact()}"))
        summary_rows = []
        lines = [
            "# Runtime Parameter Summary",
            "",
            "Runtime values take precedence over static YAML when diagnosing navigation precision.",
        ]
        if self.data_source:
            lines.append(f"- data_source: `{self.data_source}`")
            if "mock" in self.data_source.lower():
                lines.append("- THIS_IS_MOCK_DATA")
        lines.extend(["", "| Node | Parameter name | Runtime value | Possible impact |", "|---|---|---:|---|"])

        for _, _, full_name in discover_nodes(self):
            if not any(keyword in full_name.lower() for keyword in KEYWORDS):
                continue
            parameter_names, error = list_node_parameters(self, full_name)
            if error:
                summary_rows.append({"node": full_name, "parameter": "(error)", "value": error, "impact": "parameter dump failed"})
                continue
            param_map, error = get_node_parameters(self, full_name, parameter_names)
            if error:
                summary_rows.append({"node": full_name, "parameter": "(error)", "value": error, "impact": "parameter retrieval failed"})
                continue
            dump_path = (output_dir / full_name.strip("/").replace("/", "__")).with_suffix(".yaml")
            dump_path.write_text(yaml.safe_dump(param_map, sort_keys=True, allow_unicode=False), encoding="utf-8")
            for param_name, value in sorted(param_map.items()):
                if any(keyword in param_name for keyword in SUMMARY_KEYWORDS):
                    summary_rows.append(
                        {
                            "node": full_name,
                            "parameter": param_name,
                            "value": value,
                            "impact": possible_impact(param_name),
                        }
                    )

        if not summary_rows:
            lines.append("| (none) | (none) | (none) | No matching navigation-related nodes were found. |")
        else:
            for row in summary_rows:
                lines.append(f"| `{row['node']}` | `{row['parameter']}` | `{row['value']}` | {row['impact']} |")

        summary_path = write_markdown(str(output_dir / "runtime_param_summary.md"), lines)
        self.get_logger().info(f"Runtime parameter summary written: {summary_path}")
        return summary_path


def possible_impact(param_name: str) -> str:
    lowered = param_name.lower()
    if "xy_goal_tolerance" in lowered or "yaw_goal_tolerance" in lowered or "goal_tolerance" in lowered:
        return "Directly affects when navigation is considered close enough to goal."
    if "goal_checker" in lowered:
        return "Determines which goal checker plugin actually decides arrival."
    if "progress_checker" in lowered:
        return "Can trigger failure or timeout before robot settles at goal."
    if "transform_tolerance" in lowered:
        return "Too-loose or too-tight TF tolerance can affect controller timing and pose validity."
    if "robot_base_frame" in lowered or "global_frame" in lowered or "odom_frame" in lowered:
        return "Frame mismatch here can create systematic pose comparison errors."
    if "base_link" in lowered or "base_footprint" in lowered:
        return "Reference frame choice affects which physical point is treated as robot position."
    if "robot_radius" in lowered or "inflation_radius" in lowered or "footprint" in lowered:
        return "Safety geometry can influence stopping behavior near the goal."
    if "max_vel" in lowered or "min_speed" in lowered:
        return "Velocity limits affect stopping distance and final approach smoothness."
    if "planner_plugins" in lowered or "controller_plugins" in lowered:
        return "Shows which planning and control stack is actually active at runtime."
    return "Potentially relevant to navigation precision."


def collect_runtime_tolerance_snapshot(node) -> Dict[str, Any]:
    snapshot = {
        "controller_node_used": None,
        "controller_goal_checker_plugin": None,
        "xy_goal_tolerance_runtime": None,
        "yaw_goal_tolerance_runtime": None,
        "pose_goal_controller_tolerance_runtime": None,
        "map_frame": None,
        "odom_frame": None,
        "base_frame": None,
    }
    node_names = [full_name for _, _, full_name in discover_nodes(node)]

    for candidate in ["/controller_server", "/controller_server_rclcpp_node"]:
        if candidate not in node_names:
            continue
        names, error = list_node_parameters(node, candidate)
        if error:
            continue
        wanted = [
            "goal_checker_plugins",
            "general_goal_checker.plugin",
            "general_goal_checker.xy_goal_tolerance",
            "general_goal_checker.yaw_goal_tolerance",
            "FollowPath.xy_goal_tolerance",
            "global_costmap.global_costmap.robot_base_frame",
            "local_costmap.local_costmap.robot_base_frame",
        ]
        param_map, error = get_node_parameters(node, candidate, [name for name in wanted if name in names])
        if error:
            continue
        snapshot["controller_node_used"] = candidate
        snapshot["controller_goal_checker_plugin"] = param_map.get("general_goal_checker.plugin")
        snapshot["xy_goal_tolerance_runtime"] = param_map.get("general_goal_checker.xy_goal_tolerance") or param_map.get("FollowPath.xy_goal_tolerance")
        snapshot["yaw_goal_tolerance_runtime"] = param_map.get("general_goal_checker.yaw_goal_tolerance")
        snapshot["base_frame"] = param_map.get("global_costmap.global_costmap.robot_base_frame") or param_map.get("local_costmap.local_costmap.robot_base_frame")
        break

    if "/pose_goal_controller_3d" in node_names:
        names, error = list_node_parameters(node, "/pose_goal_controller_3d")
        if not error:
            wanted = ["goal_tolerance_xy", "goal_tolerance_yaw", "map_frame", "pose_topic", "goal_topic"]
            param_map, error = get_node_parameters(node, "/pose_goal_controller_3d", [name for name in wanted if name in names])
            if not error:
                snapshot["pose_goal_controller_tolerance_runtime"] = param_map.get("goal_tolerance_xy")
                snapshot["map_frame"] = param_map.get("map_frame") or snapshot["map_frame"]

    if "/amcl" in node_names:
        names, error = list_node_parameters(node, "/amcl")
        if not error:
            param_map, error = get_node_parameters(node, "/amcl", [name for name in ["global_frame_id", "odom_frame_id", "base_frame_id"] if name in names])
            if not error:
                snapshot["map_frame"] = param_map.get("global_frame_id") or snapshot["map_frame"]
                snapshot["odom_frame"] = param_map.get("odom_frame_id") or snapshot["odom_frame"]
                snapshot["base_frame"] = param_map.get("base_frame_id") or snapshot["base_frame"]

    return snapshot


def main(args=None):
    rclpy.init(args=args)
    node = RuntimeParamDumper()
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
