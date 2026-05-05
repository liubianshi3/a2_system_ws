from __future__ import annotations

import csv
import time
from pathlib import Path

import rclpy
from rclpy.node import Node

from .pose_monitor import PoseMonitor
from .utils import stddev, timestamp_compact, write_markdown


class PoseAccuracyRecorder(Node):
    def __init__(self) -> None:
        super().__init__("pose_accuracy_recorder")
        self.declare_parameter("results_root", "src/a2_nav_test_runner/results")
        self.declare_parameter("duration_sec", 60.0)
        self.declare_parameter("sample_hz", 10.0)
        self.declare_parameter("data_source", "")
        self.results_root = self.get_parameter("results_root").value
        self.duration_sec = float(self.get_parameter("duration_sec").value)
        self.sample_hz = max(1.0, float(self.get_parameter("sample_hz").value))
        self.data_source = str(self.get_parameter("data_source").value).strip()
        self.pose_monitor = PoseMonitor(self)

    def run(self):
        csv_path = Path(self.results_root) / f"static_pose_accuracy_{timestamp_compact()}.csv"
        md_path = Path(self.results_root) / f"static_pose_accuracy_summary_{timestamp_compact()}.md"
        rows = []
        start = time.time()
        interval = 1.0 / self.sample_hz
        while time.time() - start < self.duration_sec:
            rclpy.spin_once(self, timeout_sec=0.1)
            amcl = self.pose_monitor.get_pose_amcl() or {}
            odom = self.pose_monitor.get_pose_odom() or {}
            tf_map_base = self.pose_monitor.get_pose_tf_map_base_link() or {}
            tf_odom_base = self.pose_monitor.get_pose_tf_odom_base_link() or {}
            rows.append(
                {
                    "timestamp": time.time(),
                    "data_source": self.data_source,
                    "amcl_x": amcl.get("x", ""),
                    "amcl_y": amcl.get("y", ""),
                    "amcl_yaw": amcl.get("yaw", ""),
                    "odom_x": odom.get("x", ""),
                    "odom_y": odom.get("y", ""),
                    "odom_yaw": odom.get("yaw", ""),
                    "tf_map_base_x": tf_map_base.get("x", ""),
                    "tf_map_base_y": tf_map_base.get("y", ""),
                    "tf_map_base_yaw": tf_map_base.get("yaw", ""),
                    "tf_odom_base_x": tf_odom_base.get("x", ""),
                    "tf_odom_base_y": tf_odom_base.get("y", ""),
                    "tf_odom_base_yaw": tf_odom_base.get("yaw", ""),
                }
            )
            time.sleep(interval)
        write_pose_csv(csv_path, rows)
        written = write_markdown(str(md_path), build_summary_lines(rows, self.duration_sec, self.sample_hz, self.data_source))
        self.get_logger().info(f"Static pose accuracy CSV written: {csv_path}")
        self.get_logger().info(f"Static pose accuracy summary written: {written}")
        return str(csv_path), written


def build_summary_lines(rows, duration_sec, sample_hz, data_source=""):
    lines = ["# Static Pose Accuracy Summary", ""]
    if data_source:
        lines.append(f"- data_source: `{data_source}`")
        if "mock" in data_source.lower():
            lines.append("- THIS_IS_MOCK_DATA")
        lines.append("")
    lines.extend(
        [
            f"Sampling window: `{duration_sec}` sec at `{sample_hz}` Hz",
            "",
            "| Source | x_std | y_std | yaw_std | jump_detected |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for prefix in ["amcl", "odom", "tf_map_base", "tf_odom_base"]:
        x_vals = numeric_values(rows, f"{prefix}_x")
        y_vals = numeric_values(rows, f"{prefix}_y")
        yaw_vals = numeric_values(rows, f"{prefix}_yaw")
        lines.append(f"| `{prefix}` | {fmt(stddev(x_vals))} | {fmt(stddev(y_vals))} | {fmt(stddev(yaw_vals))} | {detect_jump_series(x_vals, y_vals, yaw_vals)} |")
    lines.extend(["", "## Interpretation", ""])
    lines.extend(
        [
            "- If `tf_map_base` or `amcl` standard deviation approaches 0.10 m, localization itself can explain large final error.",
            "- If `odom` is stable but `map`-based sources jump, suspect localization or frame correction rather than controller stopping.",
            "- If all pose sources are stable while final stop error is large, controller or execution layer becomes the stronger suspect.",
        ]
    )
    return lines


def write_pose_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["timestamp", "data_source", "amcl_x", "amcl_y", "amcl_yaw", "odom_x", "odom_y", "odom_yaw", "tf_map_base_x", "tf_map_base_y", "tf_map_base_yaw", "tf_odom_base_x", "tf_odom_base_y", "tf_odom_base_yaw"]
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


def detect_jump_series(x_vals, y_vals, yaw_vals):
    if len(x_vals) < 2 or len(y_vals) < 2 or len(yaw_vals) < 2:
        return False
    for idx in range(1, min(len(x_vals), len(y_vals), len(yaw_vals))):
        if abs(x_vals[idx] - x_vals[idx - 1]) > 0.08 or abs(y_vals[idx] - y_vals[idx - 1]) > 0.08 or abs(yaw_vals[idx] - yaw_vals[idx - 1]) > 0.20:
            return True
    return False


def fmt(value):
    if value is None:
        return ""
    return f"{float(value):.4f}"


def main(args=None):
    rclpy.init(args=args)
    node = PoseAccuracyRecorder()
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
