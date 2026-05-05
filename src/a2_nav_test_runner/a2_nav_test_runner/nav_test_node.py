import time
from pathlib import Path

import rclpy
from rclpy.node import Node

from .goal_loader import load_goals
from .logger import ResultLogger, runtime_report_path
from .nav_client import A2NavClient
from .runtime_checker import A2RuntimeChecker
from .runtime_param_dumper import collect_runtime_tolerance_snapshot
from .utils import load_yaml_file, now_time, parse_bool


class NavTestNode(Node):
    def __init__(self):
        super().__init__("a2_nav_test_node")
        self.declare_parameter("goals_yaml", "")
        self.declare_parameter("config_yaml", "")
        self.declare_parameter("backend_type", "")
        self.declare_parameter("runs", 0)
        self.declare_parameter("dry_check_only", True)
        self.declare_parameter("first_goal_only", True)

        self.config = self._load_config()
        self._apply_parameter_overrides()
        self.goals = load_goals(
            self.config["goals_yaml"],
            first_goal_only=parse_bool(self.config.get("first_goal_only", True)),
        )

    def _load_config(self):
        config_yaml = self.get_parameter("config_yaml").value
        if not config_yaml:
            raise RuntimeError("config_yaml parameter is required")
        config = load_yaml_file(config_yaml)
        config["config_yaml"] = config_yaml
        goals_yaml = self.get_parameter("goals_yaml").value
        if not goals_yaml:
            raise RuntimeError("goals_yaml parameter is required")
        config["goals_yaml"] = goals_yaml
        return config

    def _apply_parameter_overrides(self):
        backend_type = self.get_parameter("backend_type").value
        if backend_type:
            self.config["backend_type"] = backend_type

        runs_value = self.get_parameter("runs").value
        try:
            runs = int(runs_value)
            if runs > 0:
                self.config["runs"] = runs
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"runs must be an integer, got {runs_value!r}") from exc

        self.config["dry_check_only"] = parse_bool(self.get_parameter("dry_check_only").value)
        self.config["first_goal_only"] = parse_bool(self.get_parameter("first_goal_only").value)

    def run(self):
        log_dir = str(Path(self.config.get("log_dir", "src/a2_nav_test_runner/results")))
        checker = A2RuntimeChecker(self, self.config)
        report = checker.wait_and_check(wait_sec=float(self.config.get("runtime_graph_wait_sec", 1.0)))
        checker.print_report(report)

        if parse_bool(self.config.get("dry_check_only", True)):
            report_path = runtime_report_path(log_dir)
            written = checker.write_report(report_path, report)
            self.get_logger().warn("dry_check_only=true; no navigation goal will be sent.")
            self.get_logger().info(f"Runtime check report written: {written}")
            return 0

        client = A2NavClient(self, self.config, backend_type=self.config.get("backend_type", "auto"))
        client.wait_until_ready(timeout_sec=float(self.config.get("backend_wait_timeout", 10.0)))

        logger = ResultLogger(log_dir)
        runs = int(self.config.get("runs", 1))
        wait_between_goals = float(self.config.get("wait_between_goals", 2.0))
        stop_on_failure = parse_bool(self.config.get("stop_on_failure", False))
        frame_id = self.config.get("frame_id", "map")

        for run_index in range(1, runs + 1):
            self.get_logger().info(f"Starting navigation test run {run_index}/{runs}")
            for goal in self.goals:
                row = self._send_and_record(client, run_index, goal, frame_id)
                logger.add(row)
                if stop_on_failure and not row.get("success"):
                    self.get_logger().error(
                        f"Stopping run {run_index} after failed goal {row.get('goal_id')}: {row.get('failure_reason')}"
                    )
                    break
                if wait_between_goals > 0:
                    time.sleep(wait_between_goals)

        log_path = logger.save_log_csv()
        summary_path = logger.save_summary_csv()
        self.get_logger().info(f"Navigation log written: {log_path}")
        if summary_path:
            self.get_logger().info(f"Navigation summary written: {summary_path}")
        else:
            self.get_logger().warn("No navigation summary was generated because no goal rows were recorded.")
        return 0

    def _send_and_record(self, client, run_id, goal, frame_id):
        runtime_snapshot = collect_runtime_tolerance_snapshot(self)
        goal_frame = goal.get("frame_id", frame_id)
        result = client.send_goal(
            goal,
            frame_id=goal_frame,
            timeout_sec=float(self.config.get("navigation_timeout", 120.0)),
        )

        errors = {}
        if client.pose_monitor is not None:
            errors = client.pose_monitor.compute_errors(goal["x"], goal["y"], goal["yaw"], goal_frame=goal_frame)
        final_error = first_available_error(result.get("final_error"), errors)
        error_message = result.get("error_message", "")
        status = result.get("status", "")
        backend_success = bool(result.get("backend_success", result.get("success", False)))
        runner_arrival_success, pose_source_used = evaluate_runner_arrival(
            errors,
            float(self.config.get("arrival_tolerance", 0.35)),
            result.get("pose_source_used"),
        )
        pose_sources = errors.get("pose_source_available", []) if isinstance(errors, dict) else []

        return {
            "timestamp": now_time(),
            "run_id": run_id,
            "goal_id": goal.get("id", goal.get("goal_id")),
            "goal_x": goal["x"],
            "goal_y": goal["y"],
            "goal_yaw": goal["yaw"],
            "backend": result.get("backend", ""),
            "backend_success": backend_success,
            "runner_arrival_success": runner_arrival_success,
            "send_time": result.get("send_time", ""),
            "arrival_time": result.get("arrival_time", ""),
            "duration": result.get("duration", ""),
            "success": bool(result.get("success", False)),
            "timeout": bool(result.get("timeout", False)),
            "status": status,
            "final_error": "" if final_error is None else final_error,
            "final_error_amcl": errors.get("final_error_amcl"),
            "final_error_odom": errors.get("final_error_odom"),
            "final_error_tf_map_base_link": errors.get("final_error_tf_map_base_link"),
            "final_error_tf_map_base_footprint": errors.get("final_error_tf_map_base_footprint"),
            "yaw_error_tf_map_base_link": errors.get("yaw_error_tf_map_base_link"),
            "pose_source_used": pose_source_used or ",".join(pose_sources),
            "xy_goal_tolerance_runtime": runtime_snapshot.get("xy_goal_tolerance_runtime"),
            "yaw_goal_tolerance_runtime": runtime_snapshot.get("yaw_goal_tolerance_runtime"),
            "pose_goal_controller_tolerance_runtime": runtime_snapshot.get("pose_goal_controller_tolerance_runtime"),
            "runner_arrival_tolerance": float(self.config.get("arrival_tolerance", 0.35)),
            "controller_node_used": runtime_snapshot.get("controller_node_used"),
            "navigation_backend_candidate": client.runtime_report.get("available_backend"),
            "map_frame": runtime_snapshot.get("map_frame") or getattr(client.pose_monitor, "map_frame", "map"),
            "odom_frame": runtime_snapshot.get("odom_frame") or getattr(client.pose_monitor, "odom_frame", "odom"),
            "base_frame": runtime_snapshot.get("base_frame") or getattr(client.pose_monitor, "base_frame", "base_link"),
            "failure_reason": "" if result.get("success") else (error_message or status),
            "error_message": error_message,
        }


def first_available_error(backend_final_error, errors):
    if backend_final_error is not None:
        return backend_final_error
    if not isinstance(errors, dict):
        return None
    for key in [
        "final_error_tf_map_base_link",
        "final_error_tf_map_base_footprint",
        "final_error_amcl",
        "final_error_odom",
    ]:
        value = errors.get(key)
        if value is not None:
            return value
    return None


def evaluate_runner_arrival(errors, tolerance, backend_pose_source=None):
    if not isinstance(errors, dict):
        return None, backend_pose_source
    for key, source in [
        ("final_error_tf_map_base_link", "tf_map_base_link"),
        ("final_error_tf_map_base_footprint", "tf_map_base_footprint"),
        ("final_error_amcl", "amcl"),
        ("final_error_odom", "odom"),
    ]:
        value = errors.get(key)
        if value is not None:
            return bool(float(value) <= float(tolerance)), backend_pose_source or source
    return None, backend_pose_source


def main(args=None):
    rclpy.init(args=args)
    node = None
    exit_code = 0
    try:
        node = NavTestNode()
        exit_code = node.run()
    except Exception as exc:
        if node is not None:
            node.get_logger().error(str(exc))
        else:
            print(f"a2_nav_test_node failed during startup: {exc}")
        exit_code = 1
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
