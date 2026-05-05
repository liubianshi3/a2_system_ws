import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .utils import normalize_name


class A2RuntimeChecker:
    def __init__(self, node, config: Dict[str, Any]):
        self.node = node
        self.config = config or {}
        self.required_topics = self.config.get(
            "required_topics", ["/map", "/tf", "/odom", "/amcl_pose"]
        )
        self.required_actions = [self.config.get("nav2_action_name", "/navigate_to_pose")]
        self.service_candidates = self.config.get(
            "navcommand_service_candidates",
            ["/nav_command", "/a2/nav_command", "/a2_nav_command", "/NavCommand"],
        )
        self.report = None

    def _topic_map(self) -> Dict[str, List[str]]:
        return {name: types for name, types in self.node.get_topic_names_and_types()}

    def _service_map(self) -> Dict[str, List[str]]:
        return {name: types for name, types in self.node.get_service_names_and_types()}

    def _action_map(self) -> Dict[str, List[str]]:
        if hasattr(self.node, "get_action_names_and_types"):
            return {name: types for name, types in self.node.get_action_names_and_types()}
        return {}

    def check_topics(self) -> Dict[str, Dict[str, Any]]:
        topics = self._topic_map()
        result = {}
        for topic in self.required_topics:
            name = normalize_name(topic)
            result[name] = {
                "available": name in topics,
                "types": topics.get(name, []),
            }
        return result

    def check_actions(self) -> Dict[str, Dict[str, Any]]:
        actions = self._action_map()
        services = self._service_map()
        topics = self._topic_map()
        result = {}
        for action in self.required_actions:
            name = normalize_name(action)
            alt_name = name[1:] if name.startswith("/") else name
            types = actions.get(name) or actions.get(alt_name) or []
            if not types:
                send_goal = f"{name}/_action/send_goal"
                get_result = f"{name}/_action/get_result"
                status_topic = f"{name}/_action/status"
                if send_goal in services or get_result in services or status_topic in topics:
                    types = ["mock_or_discovered_via_action_endpoints"]
            result[name] = {
                "available": bool(types),
                "types": types,
            }
        return result

    def check_services(self) -> Dict[str, Dict[str, Any]]:
        services = self._service_map()
        result = {}
        for service in self.service_candidates:
            name = normalize_name(service)
            result[name] = {
                "available": name in services,
                "types": services.get(name, []),
            }
        return result

    def get_available_backend(self, report: Dict[str, Any] = None):
        report = report or self.report or self.build_report()
        nav2_action_name = normalize_name(self.config.get("nav2_action_name", "/navigate_to_pose"))
        if report["actions"].get(nav2_action_name, {}).get("available"):
            return "nav2_action"
        if any(item.get("available") for item in report["services"].values()):
            return "a2_navcommand"
        return None

    def build_report(self) -> Dict[str, Any]:
        topic_report = self.check_topics()
        action_report = self.check_actions()
        service_report = self.check_services()
        warnings = []
        if not any(item.get("available") for item in action_report.values()):
            warnings.append("NavigateToPose action was not detected.")
        if not any(item.get("available") for item in service_report.values()):
            warnings.append("No A2 NavCommand candidate service was detected.")
        if not any(item.get("available") for item in topic_report.values()):
            warnings.append("ROS graph appears empty or navigation stack is not running.")
        if not topic_report.get("/map", {}).get("available"):
            warnings.append("/map is not available; map server or SLAM output must be checked on robot.")
        if not topic_report.get("/tf", {}).get("available"):
            warnings.append("/tf is not available; transforms must be checked before navigation.")
        if not (
            topic_report.get("/amcl_pose", {}).get("available")
            or topic_report.get("/odom", {}).get("available")
        ):
            warnings.append("No pose feedback topic detected; final_error and NavCommand arrival checks may be unavailable.")
        self.report = {
            "topics": topic_report,
            "actions": action_report,
            "services": service_report,
            "available_backend": None,
            "warnings": warnings,
        }
        self.report["available_backend"] = self.get_available_backend(self.report)
        return self.report

    def wait_and_check(self, wait_sec: float = 1.0) -> Dict[str, Any]:
        end_time = time.time() + max(0.0, float(wait_sec))
        while time.time() < end_time:
            time.sleep(0.1)
        return self.build_report()

    def print_report(self, report: Dict[str, Any] = None) -> None:
        report = report or self.report or self.build_report()
        self.node.get_logger().info("A2 runtime interface report:")
        self.node.get_logger().info(json.dumps(report, ensure_ascii=False, indent=2))

    def write_report(self, path: str, report: Dict[str, Any] = None) -> str:
        report = report or self.report or self.build_report()
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# A2 Runtime Check Report",
            "",
            "This report is an interface availability check only. It is not a navigation experiment result.",
            "",
            f"- Available backend: `{report.get('available_backend')}`",
            "",
            "## Topics",
            "",
        ]
        for name, item in report.get("topics", {}).items():
            lines.append(f"- `{name}`: available={item.get('available')}, types={item.get('types')}")
        lines.extend(["", "## Actions", ""])
        for name, item in report.get("actions", {}).items():
            lines.append(f"- `{name}`: available={item.get('available')}, types={item.get('types')}")
        lines.extend(["", "## Services", ""])
        for name, item in report.get("services", {}).items():
            lines.append(f"- `{name}`: available={item.get('available')}, types={item.get('types')}")
        lines.extend(["", "## Warnings", ""])
        warnings = report.get("warnings", [])
        if warnings:
            lines.extend([f"- {warning}" for warning in warnings])
        else:
            lines.append("- None")
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(output_path)
