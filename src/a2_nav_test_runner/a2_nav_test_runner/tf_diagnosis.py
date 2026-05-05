from __future__ import annotations

import csv
import math
import time
from pathlib import Path

import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from tf2_ros import Buffer, TransformException, TransformListener

from .utils import mean, stddev, timestamp_compact, write_markdown, yaw_from_quaternion


TF_PAIRS = [
    ("map", "odom"),
    ("odom", "base_link"),
    ("map", "base_link"),
    ("map", "base_footprint"),
    ("base_link", "base_footprint"),
    ("base_link", "lidar"),
    ("base_link", "imu_link"),
]


class TfDiagnosis(Node):
    def __init__(self) -> None:
        super().__init__("tf_diagnosis")
        self.declare_parameter("results_root", "src/a2_nav_test_runner/results")
        self.declare_parameter("duration_sec", 10.0)
        self.declare_parameter("sample_hz", 10.0)
        self.declare_parameter("data_source", "")
        self.results_root = self.get_parameter("results_root").value
        self.duration_sec = float(self.get_parameter("duration_sec").value)
        self.sample_hz = max(1.0, float(self.get_parameter("sample_hz").value))
        self.data_source = str(self.get_parameter("data_source").value).strip()
        self.buffer = Buffer(cache_time=Duration(seconds=30.0))
        self.listener = TransformListener(self.buffer, self, spin_thread=False)

    def run(self):
        csv_path = Path(self.results_root) / f"tf_diagnosis_{timestamp_compact()}.csv"
        md_path = Path(self.results_root) / f"tf_diagnosis_{timestamp_compact()}.md"
        records = []
        per_pair_samples = {pair: [] for pair in TF_PAIRS}
        per_pair_errors = {pair: [] for pair in TF_PAIRS}
        interval = 1.0 / self.sample_hz
        start = time.time()

        while time.time() - start < self.duration_sec:
            rclpy.spin_once(self, timeout_sec=0.1)
            for parent, child in TF_PAIRS:
                try:
                    transform = self.buffer.lookup_transform(parent, child, rclpy.time.Time(), timeout=Duration(seconds=0.15))
                    translation = transform.transform.translation
                    rotation = transform.transform.rotation
                    sample = {
                        "parent_frame": parent,
                        "child_frame": child,
                        "timestamp": time.time(),
                        "data_source": self.data_source,
                        "x": float(translation.x),
                        "y": float(translation.y),
                        "z": float(translation.z),
                        "yaw": yaw_from_quaternion(rotation),
                        "available": True,
                        "error": "",
                    }
                    per_pair_samples[(parent, child)].append(sample)
                    records.append(sample)
                except TransformException as exc:
                    per_pair_errors[(parent, child)].append(str(exc))
                    records.append(
                        {
                            "parent_frame": parent,
                            "child_frame": child,
                            "timestamp": time.time(),
                            "data_source": self.data_source,
                            "x": "",
                            "y": "",
                            "z": "",
                            "yaw": "",
                            "available": False,
                            "error": str(exc),
                        }
                    )
            time.sleep(interval)

        write_tf_csv(csv_path, records)
        lines = ["# TF Diagnosis", ""]
        if self.data_source:
            lines.append(f"- data_source: `{self.data_source}`")
            if "mock" in self.data_source.lower():
                lines.append("- THIS_IS_MOCK_DATA")
            lines.append("")
        lines.extend(
            [
                f"Sampling window: `{self.duration_sec}` sec at `{self.sample_hz}` Hz",
                "",
                "| TF | available | translation_mean_xy | translation_std_xy | yaw_mean | yaw_std | jump_detected | extrapolation_error |",
                "|---|---|---:|---:|---:|---:|---|---|",
            ]
        )
        for parent, child in TF_PAIRS:
            samples = per_pair_samples[(parent, child)]
            errors = per_pair_errors[(parent, child)]
            if samples:
                radii = [math.hypot(item["x"], item["y"]) for item in samples]
                yaw_values = [item["yaw"] for item in samples]
                lines.append(
                    f"| `{parent} -> {child}` | True | {fmt(mean(radii))} | {fmt(stddev(radii))} | {fmt(mean(yaw_values))} | {fmt(stddev(yaw_values))} | {detect_jump(samples)} | {any('extrapolation' in item.lower() for item in errors)} |"
                )
            else:
                lines.append(f"| `{parent} -> {child}` | False |  |  |  |  | False | {any('extrapolation' in item.lower() for item in errors)} |")
        lines.extend(["", "## Interpretation", ""])
        lines.extend(
            [
                "- If `map -> base_link` jitters while robot is stationary, localization noise is a top suspect.",
                "- If `map -> odom` jumps but `odom -> base_link` is smooth, the issue is likely localization or relocalization correction.",
                "- If `base_link -> base_footprint` has a fixed offset, visual stop error may reflect reference point choice rather than controller miss.",
                "- Missing TF edges block trustworthy final-error comparison across frames.",
            ]
        )
        written = write_markdown(str(md_path), lines)
        self.get_logger().info(f"TF diagnosis CSV written: {csv_path}")
        self.get_logger().info(f"TF diagnosis report written: {written}")
        return str(csv_path), written


def write_tf_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["parent_frame", "child_frame", "timestamp", "data_source", "x", "y", "z", "yaw", "available", "error"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def detect_jump(samples):
    if len(samples) < 2:
        return False
    for current, nxt in zip(samples, samples[1:]):
        if math.hypot(nxt["x"] - current["x"], nxt["y"] - current["y"]) > 0.08:
            return True
        if abs(nxt["yaw"] - current["yaw"]) > 0.20:
            return True
    return False


def fmt(value):
    if value is None:
        return ""
    return f"{float(value):.4f}"


def main(args=None):
    rclpy.init(args=args)
    node = TfDiagnosis()
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
