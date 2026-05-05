import csv
from datetime import datetime
from pathlib import Path

from .metrics import compute_summary


LOG_FIELDS = [
    "timestamp",
    "run_id",
    "goal_id",
    "goal_x",
    "goal_y",
    "goal_yaw",
    "backend",
    "backend_success",
    "runner_arrival_success",
    "send_time",
    "arrival_time",
    "duration",
    "success",
    "timeout",
    "status",
    "final_error",
    "final_error_amcl",
    "final_error_odom",
    "final_error_tf_map_base_link",
    "final_error_tf_map_base_footprint",
    "yaw_error_tf_map_base_link",
    "pose_source_used",
    "xy_goal_tolerance_runtime",
    "yaw_goal_tolerance_runtime",
    "pose_goal_controller_tolerance_runtime",
    "runner_arrival_tolerance",
    "controller_node_used",
    "navigation_backend_candidate",
    "map_frame",
    "odom_frame",
    "base_frame",
    "failure_reason",
    "error_message",
]


SUMMARY_FIELDS = [
    "backend",
    "run_count",
    "total_goals",
    "success_count",
    "success_rate",
    "backend_success_rate",
    "runner_arrival_success_rate",
    "total_navigation_time",
    "average_navigation_time",
    "average_final_error",
    "mean_final_error_amcl",
    "mean_final_error_odom",
    "mean_final_error_tf_map_base_link",
    "mean_final_error_tf_map_base_footprint",
    "max_final_error_tf_map_base_link",
    "std_final_error_tf_map_base_link",
    "mean_yaw_error_tf_map_base_link",
    "failed_goals",
    "timeout_count",
]


class ResultLogger:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.rows = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def add(self, row):
        self.rows.append(row)

    def save_log_csv(self, filename=None):
        if filename is None:
            filename = f"a2_nav_test_log_{self.timestamp}.csv"
        path = self.output_dir / filename
        write_csv(path, LOG_FIELDS, self.rows)
        return str(path)

    def save_summary_csv(self, filename=None):
        summary = compute_summary(self.rows)
        if summary is None:
            return None
        if filename is None:
            filename = f"a2_nav_test_summary_{self.timestamp}.csv"
        path = self.output_dir / filename
        write_csv(path, SUMMARY_FIELDS, [summary])
        return str(path)

    def save_csv(self, filename="nav_test_results.csv"):
        return self.save_log_csv(filename=filename)

    def summary(self):
        return compute_summary(self.rows) or {}


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def runtime_report_path(output_dir, timestamp=None):
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return str(path / f"a2_runtime_check_{stamp}.md")
