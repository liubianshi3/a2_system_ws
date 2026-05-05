from __future__ import annotations

import csv
import re
from pathlib import Path

import rclpy
from rclpy.node import Node

from .utils import latest_matching_file, mean, stddev, timestamp_compact, write_markdown


class NavigationPrecisionAnalyzer(Node):
    def __init__(self) -> None:
        super().__init__("navigation_precision_analyzer")
        self.declare_parameter("results_dir", "src/a2_nav_test_runner/results")
        self.declare_parameter("data_source", "")
        self.results_dir = self.get_parameter("results_dir").value
        self.data_source = str(self.get_parameter("data_source").value).strip()

    def run(self) -> str:
        results_dir = Path(self.results_dir)
        files = {
            "static_scan": results_dir / "a2_navigation_precision_static_scan.md",
            "runtime_param_summary": latest_matching_file(str(results_dir), "runtime_params_*/runtime_param_summary.md"),
            "nav_runtime_diagnosis": latest_matching_file(str(results_dir), "nav_runtime_diagnosis_*.md"),
            "tf_diagnosis_csv": latest_matching_file(str(results_dir), "tf_diagnosis_*.csv"),
            "single_goal_csv": latest_matching_file(str(results_dir), "single_goal_accuracy_*.csv"),
            "static_pose_csv": latest_matching_file(str(results_dir), "static_pose_accuracy_*.csv"),
        }

        runtime_backend = parse_backend_candidate(files["nav_runtime_diagnosis"])
        runtime_tolerance_lines = extract_runtime_tolerance_lines(files["runtime_param_summary"])
        static_tolerance_lines = extract_static_tolerance_lines(files["static_scan"])
        single_goal_stats = summarize_single_goal(read_csv_rows(files["single_goal_csv"]))
        static_pose_stats = summarize_static_pose(read_csv_rows(files["static_pose_csv"]))
        tf_stats = summarize_tf(read_csv_rows(files["tf_diagnosis_csv"]))
        conclusion, root_cause, reasons = decide_conclusion(runtime_backend, single_goal_stats, static_pose_stats, tf_stats)

        output_path = results_dir / f"navigation_precision_root_cause_report_{timestamp_compact()}.md"
        lines = ["# Navigation Precision Root Cause Report", ""]
        if self.data_source:
            lines.append(f"- data_source: `{self.data_source}`")
            if "mock" in self.data_source.lower():
                lines.append("- THIS_IS_MOCK_DATA")
            lines.append("")
        lines.extend(
            [
                f"- Conclusion: `{conclusion}`",
                f"- Primary root cause: `{root_cause}`",
                "",
                "## 1. Runtime Navigation Chain",
                "",
                f"- backend_candidate: `{runtime_backend or 'unknown'}`",
                "",
                "## 2. Runtime Tolerance Parameters",
                "",
            ]
        )
        lines.extend(runtime_tolerance_lines or ["- No runtime parameter summary was available."])
        lines.extend(["", "## 3. Static Config vs Runtime", ""])
        lines.extend(static_tolerance_lines or ["- Static scan report was not available."])
        lines.extend(["", "## 4. Single Goal Repeat Statistics", ""])
        lines.extend(format_single_goal_stats(single_goal_stats))
        lines.extend(["", "## 5. Static Pose Stability", ""])
        lines.extend(format_static_pose_stats(static_pose_stats))
        lines.extend(["", "## 6. TF Stability", ""])
        lines.extend(format_tf_stats(tf_stats))
        lines.extend(["", "## 7. Top 5 Suspects", ""])
        lines.extend(top_suspects(root_cause, runtime_backend, tf_stats))
        lines.extend(["", "## 8. Evidence-Based Recommendations", ""])
        lines.extend(recommendations(root_cause))
        lines.extend(["", "## 9. Do Not Adjust Yet", ""])
        lines.extend(do_not_adjust(root_cause))
        lines.extend(["", "## 10. PADS Readiness", ""])
        lines.extend(pads_readiness(conclusion))
        lines.extend(["", "## 11. Conclusion Reasons", ""])
        lines.extend([f"- {reason}" for reason in reasons] or ["- No supporting reasons were available."])
        written = write_markdown(str(output_path), lines)
        self.get_logger().info(f"Navigation precision root-cause report written: {written}")
        return written


def read_csv_rows(path):
    if not path or not Path(path).exists():
        return []
    with Path(path).open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_backend_candidate(path):
    if not path or not Path(path).exists():
        return None
    match = re.search(r"backend_candidate:\s*`([^`]+)`", Path(path).read_text(encoding="utf-8"))
    return match.group(1) if match else None


def extract_runtime_tolerance_lines(path):
    if not path or not Path(path).exists():
        return []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [f"- {line.strip('| ')}" for line in lines if "|" in line and ("tolerance" in line.lower() or "goal_checker" in line.lower())]


def extract_static_tolerance_lines(path):
    if not path or not Path(path).exists():
        return []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [f"- {line.strip()}" for line in lines if "|" in line and any(token in line.lower() for token in ["xy_goal_tolerance", "yaw_goal_tolerance", "goal_tolerance_xy", "arrival_tolerance"])]


def numeric_values(rows, key):
    values = []
    for row in rows:
        value = row.get(key)
        if value in ("", None):
            continue
        try:
            values.append(float(value))
        except ValueError:
            continue
    return values


def truthy(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def summarize_single_goal(rows):
    if not rows:
        return {}
    tf_errors = numeric_values(rows, "final_error_tf_map_base_link")
    footprint_errors = numeric_values(rows, "final_error_tf_map_base_footprint")
    return {
        "count": len(rows),
        "backend_success_rate": sum(1 for row in rows if truthy(row.get("backend_success"))) / len(rows),
        "runner_arrival_success_rate": sum(1 for row in rows if truthy(row.get("runner_arrival_success"))) / len(rows),
        "mean_final_error_tf_map_base_link": mean(tf_errors) if tf_errors else None,
        "max_final_error_tf_map_base_link": max(tf_errors) if tf_errors else None,
        "std_final_error_tf_map_base_link": stddev(tf_errors) if tf_errors else None,
        "mean_final_error_tf_map_base_footprint": mean(footprint_errors) if footprint_errors else None,
        "mean_final_error_amcl": mean(numeric_values(rows, "final_error_amcl")) if numeric_values(rows, "final_error_amcl") else None,
        "mean_final_error_odom": mean(numeric_values(rows, "final_error_odom")) if numeric_values(rows, "final_error_odom") else None,
        "xy_goal_tolerance_runtime": mean(numeric_values(rows, "xy_goal_tolerance_runtime")) if numeric_values(rows, "xy_goal_tolerance_runtime") else None,
        "runner_arrival_tolerance": mean(numeric_values(rows, "runner_arrival_tolerance")) if numeric_values(rows, "runner_arrival_tolerance") else None,
    }


def summarize_static_pose(rows):
    if not rows:
        return {}
    return {
        "tf_map_base_x_std": stddev(numeric_values(rows, "tf_map_base_x")),
        "tf_map_base_y_std": stddev(numeric_values(rows, "tf_map_base_y")),
        "amcl_x_std": stddev(numeric_values(rows, "amcl_x")),
        "amcl_y_std": stddev(numeric_values(rows, "amcl_y")),
        "odom_x_std": stddev(numeric_values(rows, "odom_x")),
        "odom_y_std": stddev(numeric_values(rows, "odom_y")),
    }


def summarize_tf(rows):
    if not rows:
        return {}
    grouped = {}
    for row in rows:
        tf_name = f"{row.get('parent_frame')}->{row.get('child_frame')}"
        grouped.setdefault(tf_name, []).append(row)
    summary = {}
    for tf_name, tf_rows in grouped.items():
        summary[tf_name] = {
            "available_count": sum(1 for row in tf_rows if truthy(row.get("available"))),
            "error_count": sum(1 for row in tf_rows if row.get("error")),
        }
    return summary


def decide_conclusion(runtime_backend, single_goal_stats, static_pose_stats, tf_stats):
    reasons = []
    if not runtime_backend or runtime_backend == "unknown":
        reasons.append("Runtime backend is still unclear.")
        return "NEED_BACKEND_CLARIFICATION", "backend_clarification_needed", reasons
    if not single_goal_stats:
        reasons.append("No single-goal repeat data was available.")
        return "INSUFFICIENT_DATA", "insufficient_data", reasons

    tf_error = single_goal_stats.get("mean_final_error_tf_map_base_link")
    footprint_error = single_goal_stats.get("mean_final_error_tf_map_base_footprint")
    xy_tol = single_goal_stats.get("xy_goal_tolerance_runtime")
    pose_std_values = [value for value in [static_pose_stats.get("tf_map_base_x_std"), static_pose_stats.get("tf_map_base_y_std"), static_pose_stats.get("amcl_x_std"), static_pose_stats.get("amcl_y_std")] if value is not None]
    pose_std = max(pose_std_values) if pose_std_values else None

    if single_goal_stats.get("backend_success_rate", 0.0) < 0.5 and single_goal_stats.get("runner_arrival_success_rate", 0.0) > 0.5:
        reasons.append("Runner arrival success is high while backend success is low.")
        return "NEED_NAV_TUNING", "runner_arrival_tolerance", reasons
    if pose_std is not None and pose_std >= 0.08:
        reasons.append("Static pose jitter is already large enough to hurt final stop precision.")
        return "NEED_LOCALIZATION_FIX", "localization_instability", reasons
    if tf_error is not None and footprint_error is not None and abs(tf_error - footprint_error) >= 0.12:
        reasons.append("base_link and base_footprint final errors diverge strongly, suggesting frame or offset mismatch.")
        return "NEED_FRAME_FIX", "tf_or_base_frame_offset", reasons
    if tf_stats and any(is_serious_tf_issue(info) for info in tf_stats.values()):
        reasons.append("TF lookups showed missing edges or repeated errors.")
        return "NEED_FRAME_FIX", "tf_or_base_frame_offset", reasons
    if tf_error is not None and xy_tol is not None and xy_tol >= 0.20 and abs(tf_error - xy_tol) <= 0.05:
        reasons.append("Final stop error closely tracks a loose runtime goal tolerance.")
        return "NEED_NAV_TUNING", "goal_tolerance_too_large", reasons
    if tf_error is not None and xy_tol is not None and tf_error > max(0.20, xy_tol + 0.08):
        reasons.append("Final stop error is much larger than runtime goal tolerance.")
        return "NEED_NAV_TUNING", "controller_or_execution_stop_error", reasons
    if single_goal_stats.get("backend_success_rate", 0.0) >= 1.0 and single_goal_stats.get("runner_arrival_success_rate", 0.0) >= 1.0 and tf_error is not None and tf_error <= 0.20 and single_goal_stats.get("max_final_error_tf_map_base_link", 999.0) <= 0.35:
        reasons.append("Single-goal success and final-error bounds are already acceptable for PADS handoff.")
        return "PASS_NAV_FOR_PADS", "clean_navigation", reasons
    reasons.append("Collected data does not yet support a clean PADS handoff.")
    return "NEED_NAV_TUNING", "controller_or_execution_stop_error", reasons


def format_single_goal_stats(stats):
    if not stats:
        return ["- No single-goal accuracy CSV was available."]
    return [
        f"- count: `{stats.get('count')}`",
        f"- backend_success_rate: `{fmt(stats.get('backend_success_rate'))}`",
        f"- runner_arrival_success_rate: `{fmt(stats.get('runner_arrival_success_rate'))}`",
        f"- mean_final_error_tf_map_base_link: `{fmt(stats.get('mean_final_error_tf_map_base_link'))}`",
        f"- mean_final_error_tf_map_base_footprint: `{fmt(stats.get('mean_final_error_tf_map_base_footprint'))}`",
        f"- max_final_error_tf_map_base_link: `{fmt(stats.get('max_final_error_tf_map_base_link'))}`",
        f"- std_final_error_tf_map_base_link: `{fmt(stats.get('std_final_error_tf_map_base_link'))}`",
    ]


def format_static_pose_stats(stats):
    if not stats:
        return ["- No static pose accuracy CSV was available."]
    return [f"- {key}: `{fmt(value)}`" for key, value in stats.items()]


def format_tf_stats(stats):
    if not stats:
        return ["- No TF diagnosis CSV was available."]
    return [f"- `{name}` available_count={info.get('available_count')} error_count={info.get('error_count')}" for name, info in sorted(stats.items())]


def top_suspects(root_cause, runtime_backend, tf_stats):
    suspects = [f"- Primary suspect from current evidence: `{root_cause}`."]
    if runtime_backend == "pose_goal_controller_3d":
        suspects.append("- 3D controller tolerance or stop behavior may dominate final placement.")
    if tf_stats and any(is_serious_tf_issue(info) for info in tf_stats.values()):
        suspects.append("- TF chain inconsistency or missing transforms can distort final-error calculation.")
    return suspects


def recommendations(root_cause):
    mapping = {
        "goal_tolerance_too_large": ["- Tighten runtime goal tolerance gradually and retest.", "- Keep runner arrival tolerance distinct from backend goal tolerance."],
        "runner_arrival_tolerance": ["- Reduce runner arrival tolerance and keep backend success separate from runner success.", "- Do not treat runner arrival success as backend navigation success."],
        "localization_instability": ["- Improve localization stability before tuning controller stop behavior.", "- Repeat static pose recording after localization changes."],
        "tf_or_base_frame_offset": ["- Verify base_link vs base_footprint offset and goal comparison frame.", "- Recompute final error in the correct frame before controller tuning."],
        "controller_or_execution_stop_error": ["- Inspect controller stop behavior, velocity limits, and final approach logic.", "- Compare final error with runtime goal tolerance to confirm stop-layer miss."],
    }
    return mapping.get(root_cause, ["- Collect more runtime evidence."])


def do_not_adjust(root_cause):
    lines = ["- Do not blame PADS or task scheduling before navigation precision is understood.", "- Do not write mock or diagnosis-only outputs as real robot experiment results."]
    if root_cause != "runner_arrival_tolerance":
        lines.append("- Do not tune runner arrival tolerance alone and claim navigation improved.")
    return lines


def pads_readiness(conclusion):
    if conclusion == "PASS_NAV_FOR_PADS":
        return ["- Navigation precision looks acceptable for the first PADS handoff step."]
    return ["- Do not connect PADS yet.", "- Fix navigation precision first so scheduling results are not confounded by backend error."]


def is_serious_tf_issue(info):
    available = int(info.get("available_count", 0))
    errors = int(info.get("error_count", 0))
    if available == 0 and errors > 0:
        return True
    return errors > 1


def fmt(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def main(args=None):
    rclpy.init(args=args)
    node = NavigationPrecisionAnalyzer()
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
