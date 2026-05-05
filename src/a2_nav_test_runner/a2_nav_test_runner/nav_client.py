from .a2_navcommand_backend import A2NavCommandBackend
from .nav2_action_backend import Nav2ActionBackend
from .pose_monitor import PoseMonitor
from .runtime_checker import A2RuntimeChecker
from .utils import normalize_name, parse_bool


class NavClientUnavailable(RuntimeError):
    pass


class A2NavClient:
    def __init__(self, node, config, backend_type="auto"):
        self.node = node
        self.config = config or {}
        self.backend_type = backend_type or self.config.get("backend_type", "auto")
        self.allow_fallback = parse_bool(self.config.get("allow_backend_fallback", False))
        self.runtime_checker = A2RuntimeChecker(node, self.config)
        self.runtime_report = self.runtime_checker.build_report()
        self.pose_monitor = None
        if parse_bool(self.config.get("use_pose_feedback", True)):
            self.pose_monitor = PoseMonitor(
                node,
                self.config.get("pose_topic_candidates", ["/amcl_pose", "/odom"]),
            )
        self.backend = self._select_backend()

    def _select_backend(self):
        requested = self.backend_type
        available = self.runtime_checker.get_available_backend(self.runtime_report)
        if requested == "auto":
            if available == "nav2_action":
                return Nav2ActionBackend(
                    self.node,
                    self.config.get("nav2_action_name", "/navigate_to_pose"),
                )
            if available == "a2_navcommand":
                return A2NavCommandBackend(
                    self.node,
                    self._first_available_navcommand_service(required=True),
                    pose_monitor=self.pose_monitor,
                )
            raise NavClientUnavailable("No navigation backend is available in current ROS graph.")

        if requested == "nav2_action":
            action_name = normalize_name(self.config.get("nav2_action_name", "/navigate_to_pose"))
            if not self.runtime_report["actions"].get(action_name, {}).get("available"):
                if self.allow_fallback and available:
                    self.backend_type = available
                    return self._select_backend()
                raise NavClientUnavailable(f"Requested Nav2 action backend is not available: {action_name}")
            return Nav2ActionBackend(self.node, action_name)

        if requested == "a2_navcommand":
            service_name = self._first_available_navcommand_service(required=True)
            if service_name is None:
                if self.allow_fallback and available:
                    self.backend_type = available
                    return self._select_backend()
                raise NavClientUnavailable("Requested A2 NavCommand backend is not available.")
            return A2NavCommandBackend(self.node, service_name, pose_monitor=self.pose_monitor)

        raise NavClientUnavailable(f"Unsupported backend_type: {requested}")

    def _first_available_navcommand_service(self, required=False):
        for name, item in self.runtime_report.get("services", {}).items():
            if item.get("available"):
                return name
        if required:
            return None
        candidates = self.config.get("navcommand_service_candidates", [])
        return normalize_name(candidates[0]) if candidates else None

    def wait_until_ready(self, timeout_sec=10.0):
        if self.backend is None:
            raise NavClientUnavailable("Navigation backend is not initialized.")
        if not self.backend.wait_until_ready(timeout_sec=timeout_sec):
            raise NavClientUnavailable(f"Navigation backend did not become ready in {timeout_sec}s.")
        return True

    def send_goal(self, goal, frame_id=None, timeout_sec=None):
        frame = frame_id or goal.get("frame_id") or self.config.get("frame_id", "map")
        timeout = float(timeout_sec or self.config.get("navigation_timeout", 120.0))
        if isinstance(self.backend, A2NavCommandBackend):
            return self.backend.send_goal(
                goal.get("id", goal.get("goal_id")),
                goal["x"],
                goal["y"],
                goal["yaw"],
                frame_id=frame,
                timeout_sec=timeout,
                arrival_tolerance=float(self.config.get("arrival_tolerance", 0.35)),
            )
        return self.backend.send_goal(
            goal.get("id", goal.get("goal_id")),
            goal["x"],
            goal["y"],
            goal["yaw"],
            frame_id=frame,
            timeout_sec=timeout,
        )


# Backward-compatible alias for older imports in this package.
NavClient = A2NavClient
