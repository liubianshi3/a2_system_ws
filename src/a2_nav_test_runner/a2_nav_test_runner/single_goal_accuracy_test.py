from __future__ import annotations

import csv
import time
from pathlib import Path

import rclpy
from rclpy.node import Node

from .nav_client import A2NavClient
from .runtime_param_dumper import collect_runtime_tolerance_snapshot
from .utils import mean, stddev, timestamp_compact, write_markdown


class SingleGoalAccuracyTest(Node):
    def __init__(self) -> None:
        super().__init__("single_goal_accuracy_test")
        self.declare_parameter("goal_x", 1.0)
        self.declare_parameter("goal_y", 0.5)
        self.declare_parameter("goal_yaw", 0.0)
        self.declare_parameter("goal_frame", "map")
        self.declare_parameter("repeats", 5)
        self.declare_parameter("backend_type", "auto")
        self.declare_parameter("results_root", "src/a2_nav_test_runner/results")
        self.declare_parameter("navigation_timeout", 120.0)
        self.declare_parameter("arrival_tolerance", 0.35)
        self.declare_parameter("wait_between_repeats", 2.0)
        self.declare_parameter("data_source", "")

        self.results_root = self.get_parameter("results_root").value
        self.data_source = str(self.get_parameter("data_source").value).strip()
        self.goal = {
            "id": "single_goal_accuracy",
            "x": float(self.get_parameter("goal_x").value),
            "y": float(self.get_parameter("goal_y").value),
            "yaw": float(self.get_parameter("goal_yaw").value),
            "frame_id": str(self.get_parameter("goal_frame").value),
        }
        self.repeats = int(self.get_parameter("repeats").value)
        self.backend_type = str(self.get_parameter("backend_type").value)
        self.navigation_timeout = float(self.get_parameter("navigation_timeout").value)
        self.arrival_tolerance = float(self.get_parameter("arrival_tolerance").value)
        self.wait_between_repeats = float(self.get_parameter("wait_between_repeats").value)
        self.config = {
            "backend_type": self.backend_type,
            "nav2_action_name": "/navigate_to_pose",
            "navcommand_service_candidates": ["/nav_command", "/a2/nav_command", "/a2_nav_command", "/NavCommand", "/a2/task_manager/command"],
            "required_topics": ["/map", "/tf", "/odom", "/amcl_pose"],
            "pose_topic_candidates": ["/amcl_pose", "/odom"],
            "use_pose_feedback": True,
            "arrival_tolerance": self.arrival_tolerance,
            "navigation_timeout": self.navigation_timeout,
            "allow_backend_fallback": False,
        }

    def run(self) -> tuple[str, str]:
        client = A2NavClient(self, self.config, backend_type=self.backend_type)
        client.wait_until_ready(timeout_sec=10.0)
        csv_path = Path(self.results_root) / f"single_goal_accuracy_{timestamp_compact()}.csv"
        md_path = Path(self.results_root) / f"single_goal_accuracy_summary_{timestamp_compact()}.md"
        rows = []
        for repeat_id in range(1, self.repeats + 1):
            runtime_snapshot = collect_runtime_tolerance_snapshot(self)
            start_pose = client.pose_monitor.get_current_pose() if client.pose_monitor is not None else None
            result = client.send_goal(self.goal, frame_id=self.goal["frame_id"], timeout_sec=self.navigation_timeout)
            errors = client.pose_monitor.compute_errors(self.goal["x"], self.goal["y"], self.goal["yaw"], goal_frame=self.goal["frame_id"]) if client.pose_monitor is not None else {}
            runner_arrival_success, pose_source_used = evaluate_runner_arrival(errors, self.arrival_tolerance, result.get("pose_source_used"))
            rows.append(
                {
                    "repeat_id": repeat_id,
                    "data_source": self.data_source,
                    "goal_x": self.goal["x"],
                    "goal_y": self.goal["y"],
                    "goal_yaw": self.goal["yaw"],
                    "backend": result.get("backend", ""),
                    "backend_success": bool(result.get("backend_success", result.get("success", False))),
                    "runner_arrival_success": runner_arrival_success,
                    "send_time": result.get("send_time", ""),
                    "arrival_time": result.get("arrival_time", ""),
                    "duration": result.get("duration", ""),
                    "timeout": bool(result.get("timeout", False)),
                    "status": result.get("status", ""),
                    "final_error_amcl": errors.get("final_error_amcl"),
                    "final_error_odom": errors.get("final_error_odom"),
                    "final_error_tf_map_base_link": errors.get("final_error_tf_map_base_link"),
                    "final_error_tf_map_base_footprint": errors.get("final_error_tf_map_base_footprint"),
                    "yaw_error_tf_map_base_link": errors.get("yaw_error_tf_map_base_link"),
                    "pose_source_used": pose_source_used or ",".join(errors.get("pose_source_available", [])),
                    "xy_goal_tolerance_runtime": runtime_snapshot.get("xy_goal_tolerance_runtime"),
                    "yaw_goal_tolerance_runtime": runtime_snapshot.get("yaw_goal_tolerance_runtime"),
                    "pose_goal_controller_tolerance_runtime": runtime_snapshot.get("pose_goal_controller_tolerance_runtime"),
                    "runner_arrival_tolerance": self.arrival_tolerance,
                    "failure_reason": "" if result.get("success") else (result.get("error_message") or result.get("status", "")),
                    "start_pose_source": start_pose.get("topic") if isinstance(start_pose, dict) else "",
                }
            )
            if self.wait_between_repeats > 0 and repeat_id < self.repeats:
                time.sleep(self.wait_between_repeats)
        write_accuracy_csv(csv_path, rows)
        summary_lines = build_summary_lines(rows, self.goal, self.arrival_tolerance, self.data_source)
        write_markdown(str(md_path), summary_lines)
        self.get_logger().info(f"Single-goal accuracy CSV written: {csv_path}")
        self.get_logger().info(f"Single-goal accuracy summary written: {md_path}")
        return str(csv_path), str(md_path)


def evaluate_runner_arrival(errors, tolerance, backend_pose_source=None):
    if not isinstance(errors, dict):
        return None, backend_pose_source
    for key, source in [("final_error_tf_map_base_link", "tf_map_base_link"), ("final_error_tf_map_base_footprint", "tf_map_base_footprint"), ("final_error_amcl", "amcl"), ("final_error_odom", "odom")]:
        value = errors.get(key)
        if value is not None:
            return bool(float(value) <= float(tolerance)), backend_pose_source or source
    return None, backend_pose_source


def write_accuracy_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["repeat_id", "data_source", "goal_x", "goal_y", "goal_yaw", "backend", "backend_success", "runner_arrival_success", "send_time", "arrival_time", "duration", "timeout", "status", "final_error_amcl", "final_error_odom", "final_error_tf_map_base_link", "final_error_tf_map_base_footprint", "yaw_error_tf_map_base_link", "pose_source_used", "xy_goal_tolerance_runtime", "yaw_goal_tolerance_runtime", "pose_goal_controller_tolerance_runtime", "runner_arrival_tolerance", "failure_reason", "start_pose_source"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def numeric_values(rows, key):
    values = []
    for row in rows:
        value = row.get(key)
        if value in ("", None):
            continue
        values.append(float(value))
    return values


def build_summary_lines(rows, goal, runner_arrival_tolerance, data_source=""):
    backend_success_count = sum(1 for row in rows if row.get("backend_success") is True)
    runner_success_count = sum(1 for row in rows if row.get("runner_arrival_success") is True)
    timeout_count = sum(1 for row in rows if row.get("timeout") is True)
    tf_errors = numeric_values(rows, "final_error_tf_map_base_link")
    amcl_errors = numeric_values(rows, "final_error_amcl")
    odom_errors = numeric_values(rows, "final_error_odom")
    footprint_errors = numeric_values(rows, "final_error_tf_map_base_footprint")
    xy_runtime_values = numeric_values(rows, "xy_goal_tolerance_runtime")
    yaw_runtime_values = numeric_values(rows, "yaw_goal_tolerance_runtime")
    pose_goal_runtime_values = numeric_values(rows, "pose_goal_controller_tolerance_runtime")
    lines = ["# Single Goal Accuracy Summary", ""]
    if data_source:
        lines.append(f"- data_source: `{data_source}`")
        if "mock" in data_source.lower():
            lines.append("- THIS_IS_MOCK_DATA")
        lines.append("")
    lines.extend(
        [
            f"Goal: `({goal['x']:.3f}, {goal['y']:.3f}, yaw={goal['yaw']:.3f})` in frame `{goal['frame_id']}`",
            "",
            f"- repeats: `{len(rows)}`",
            f"- backend_success_rate: `{backend_success_count}/{len(rows)}`",
            f"- runner_arrival_success_rate: `{runner_success_count}/{len(rows)}`",
            f"- timeout_count: `{timeout_count}`",
            "",
            "| Metric | mean | min | max | std |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for name, values in [("final_error_tf_map_base_link", tf_errors), ("final_error_tf_map_base_footprint", footprint_errors), ("final_error_amcl", amcl_errors), ("final_error_odom", odom_errors), ("yaw_error_tf_map_base_link", numeric_values(rows, "yaw_error_tf_map_base_link"))]:
        if values:
            lines.append(f"| `{name}` | {fmt(mean(values))} | {fmt(min(values))} | {fmt(max(values))} | {fmt(stddev(values))} |")
        else:
            lines.append(f"| `{name}` |  |  |  |  |")
    lines.extend(["", "## Runtime Tolerances", ""])
    lines.extend(
        [
            f"- controller_server.xy_goal_tolerance(runtime): `{fmt(mean(xy_runtime_values)) if xy_runtime_values else ''}`",
            f"- controller_server.yaw_goal_tolerance(runtime): `{fmt(mean(yaw_runtime_values)) if yaw_runtime_values else ''}`",
            f"- pose_goal_controller_3d.goal_tolerance_xy(runtime): `{fmt(mean(pose_goal_runtime_values)) if pose_goal_runtime_values else ''}`",
            f"- runner_arrival_tolerance: `{runner_arrival_tolerance:.3f}`",
        ]
    )
    return lines


def fmt(value):
    if value is None:
        return ""
    return f"{float(value):.4f}"


def main(args=None):
    rclpy.init(args=args)
    node = SingleGoalAccuracyTest()
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
