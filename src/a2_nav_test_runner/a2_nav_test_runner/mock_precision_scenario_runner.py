from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from pathlib import Path

import rclpy
from rclpy.node import Node

from .utils import load_yaml_file, write_markdown


class MockPrecisionScenarioRunner(Node):
    def __init__(self) -> None:
        super().__init__("mock_precision_scenario_runner")
        self.declare_parameter("scenario", "all")
        self.declare_parameter("scenarios_yaml", "src/a2_nav_test_runner/config/mock_precision_scenarios.yaml")
        self.declare_parameter("results_root", "src/a2_nav_test_runner/results/mock_precision")
        self.declare_parameter("data_source", "mock_navigation_test")
        self.scenario = str(self.get_parameter("scenario").value)
        self.scenarios_yaml = str(self.get_parameter("scenarios_yaml").value)
        self.results_root = Path(str(self.get_parameter("results_root").value))
        self.data_source = str(self.get_parameter("data_source").value)
        self.scenarios = load_yaml_file(self.scenarios_yaml).get("scenarios", [])

    def run(self):
        target_scenarios = self.scenarios if self.scenario in {"", "all"} else [self.get_scenario(self.scenario)]
        rows = []
        for scenario in target_scenarios:
            rows.append(self.run_scenario(scenario))
        report_path = self.results_root / "mock_precision_validation_report.md"
        lines = [
            "# Mock Precision Validation Report",
            "",
            "- THIS_IS_MOCK_DATA",
            "- data_source: `mock_navigation_test`",
            "",
            "| 场景 | 注入问题 | 期望根因 | Analyzer 输出 | 是否匹配 | 备注 |",
            "|---|---|---|---|---|---|",
        ]
        for row in rows:
            lines.append(
                f"| `{row['scenario']}` | {row['injected_issue']} | `{row['expected_root_cause']}` | `{row['actual_root_cause']}` | {row['matched']} | {row['note']} |"
            )
        write_markdown(str(report_path), lines)
        self.get_logger().info(f"Mock precision validation report written: {report_path}")
        return str(report_path)

    def get_scenario(self, name):
        for scenario in self.scenarios:
            if scenario.get("name") == name:
                return scenario
        raise RuntimeError(f"Scenario not found: {name}")

    def run_scenario(self, scenario):
        scenario_name = scenario["name"]
        scenario_dir = self.results_root / scenario_name
        scenario_dir.mkdir(parents=True, exist_ok=True)
        procs = []
        try:
            procs.append(self.spawn("mock_pose_tf_publisher", scenario_name))
            procs.append(self.spawn("mock_nav2_action_server", scenario_name))
            procs.append(self.spawn("mock_navcommand_service", scenario_name))
            time.sleep(2.0)
            self.run_tool("nav_runtime_diagnosis", scenario_dir)
            self.run_tool("runtime_param_dumper", scenario_dir)
            self.run_tool("tf_diagnosis", scenario_dir, extra=["-p", "duration_sec:=2.0", "-p", "sample_hz:=5.0"])
            self.run_tool("pose_accuracy_recorder", scenario_dir, extra=["-p", "duration_sec:=2.0", "-p", "sample_hz:=5.0"])
            self.run_tool(
                "single_goal_accuracy_test",
                scenario_dir,
                extra=[
                    "-p", "goal_x:=1.0",
                    "-p", "goal_y:=0.5",
                    "-p", "goal_yaw:=0.0",
                    "-p", "repeats:=5",
                    "-p", f"arrival_tolerance:={float(scenario.get('runner_arrival_tolerance', 0.20))}",
                ],
            )
            self.run_tool("navigation_precision_analyzer", scenario_dir, param_name="results_dir")
            analyzer_report = latest_file(scenario_dir, "navigation_precision_root_cause_report_*.md")
            actual_root = parse_primary_root_cause(analyzer_report)
            actual_conclusion = parse_conclusion(analyzer_report)
            expected_root = scenario.get("expected_root_cause")
            expected_result = scenario.get("expected_result")
            if expected_result:
                matched = str(actual_conclusion == expected_result)
                compare_label = actual_conclusion
                expected_label = expected_result
            else:
                matched = str(actual_root == expected_root)
                compare_label = actual_root
                expected_label = expected_root
            return {
                "scenario": scenario_name,
                "injected_issue": scenario.get("description", ""),
                "expected_root_cause": expected_label,
                "actual_root_cause": compare_label,
                "matched": matched,
                "note": "" if matched == "True" else "Mock signal or analyzer logic should be reviewed.",
            }
        finally:
            for proc in procs:
                terminate_process(proc)

    def spawn(self, executable, scenario_name):
        exe_path = installed_executable(executable)
        cmd = [
            str(exe_path), "--ros-args",
            "-p", f"scenarios_yaml:={self.scenarios_yaml}",
            "-p", f"scenario:={scenario_name}",
            "-p", f"data_source:={self.data_source}",
        ]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            env=os.environ.copy(),
            start_new_session=True,
        )

    def run_tool(self, executable, scenario_dir, extra=None, param_name="results_root"):
        exe_path = installed_executable(executable)
        cmd = [
            str(exe_path), "--ros-args",
            "-p", f"{param_name}:={scenario_dir}",
            "-p", f"data_source:={self.data_source}",
        ]
        if extra:
            cmd.extend(extra)
        completed = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy())
        if completed.returncode != 0:
            raise RuntimeError(f"{executable} failed for {scenario_dir.name}: {completed.stderr or completed.stdout}")


def latest_file(directory: Path, pattern: str):
    matches = sorted(directory.glob(pattern))
    return matches[-1] if matches else None


def parse_primary_root_cause(path):
    if not path or not path.exists():
        return "missing_report"
    match = re.search(r"Primary root cause:\s*`([^`]+)`", path.read_text(encoding="utf-8"))
    return match.group(1) if match else "unknown"


def parse_conclusion(path):
    if not path or not path.exists():
        return "missing_report"
    match = re.search(r"Conclusion:\s*`([^`]+)`", path.read_text(encoding="utf-8"))
    return match.group(1) if match else "unknown"


def installed_executable(executable: str) -> Path:
    root = Path.cwd()
    candidate = root / "install" / "a2_nav_test_runner" / "lib" / "a2_nav_test_runner" / executable
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Installed executable not found: {candidate}")


def terminate_process(proc):
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        proc.terminate()
    try:
        proc.wait(timeout=3.0)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()
        proc.wait(timeout=3.0)


def main(args=None):
    rclpy.init(args=args)
    node = MockPrecisionScenarioRunner()
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
