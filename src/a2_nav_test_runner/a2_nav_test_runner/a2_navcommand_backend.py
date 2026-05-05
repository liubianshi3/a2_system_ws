from typing import Dict

import rclpy
from a2_interfaces.srv import NavCommand

from .nav2_action_backend import make_pose, wait_future
from .utils import now_time


class A2NavCommandBackend:
    def __init__(self, node, service_name, pose_monitor=None):
        self.node = node
        self.service_name = service_name
        self.pose_monitor = pose_monitor
        self.client = self.node.create_client(NavCommand, self.service_name)

    def wait_until_ready(self, timeout_sec=10.0) -> bool:
        return bool(self.client.wait_for_service(timeout_sec=float(timeout_sec)))

    def send_goal(
        self,
        goal_id,
        x,
        y,
        yaw,
        frame_id="map",
        timeout_sec=120.0,
        arrival_tolerance=0.35,
    ) -> Dict:
        send_time = now_time()
        result = {
            "backend": "a2_navcommand",
            "goal_id": goal_id,
            "backend_success": False,
            "success": False,
            "timeout": False,
            "send_time": send_time,
            "arrival_time": None,
            "duration": 0.0,
            "status": "not_started",
            "error_message": "",
        }
        self.node.get_logger().info(
            f"Sending A2 NavCommand goal {goal_id}: x={float(x):.3f}, y={float(y):.3f}, yaw={float(yaw):.3f}, frame={frame_id}"
        )
        if not self.wait_until_ready(timeout_sec=5.0):
            result.update(
                {
                    "duration": now_time() - send_time,
                    "status": "service_unavailable",
                    "error_message": f"NavCommand service not available: {self.service_name}",
                }
            )
            return result

        request = NavCommand.Request()
        request.command = "navigate_to_pose"
        request.map_id = ""
        request.route_id = str(goal_id)
        request.mode = "navigation"
        request.mission_name = f"a2_nav_test_{goal_id}"
        request.route_yaml = ""
        request.waypoints_file = ""
        request.dry_run = False
        request.stop_on_failure = True
        request.save_map_on_finish = False
        request.save_map_on_failure = False
        request.pose = make_pose(self.node, x, y, yaw, frame_id)

        future = self.client.call_async(request)
        if not wait_future(self.node, future, timeout_sec=min(10.0, float(timeout_sec))):
            result.update(
                {
                    "timeout": True,
                    "duration": now_time() - send_time,
                    "status": "service_call_timeout",
                    "error_message": "Timed out waiting for NavCommand service response.",
                }
            )
            return result

        try:
            response = future.result()
        except Exception as exc:
            result.update(
                {
                    "duration": now_time() - send_time,
                    "status": "service_call_exception",
                    "error_message": str(exc),
                }
            )
            return result

        service_success = bool(getattr(response, "success", False))
        message = getattr(response, "message", "")
        result["service_success"] = service_success
        result["service_message"] = message
        if not service_success:
            result.update(
                {
                    "duration": now_time() - send_time,
                    "status": "command_rejected",
                    "error_message": message or "NavCommand service returned success=false.",
                }
            )
            return result

        if self.pose_monitor is None:
            result.update(
                {
                    "backend_success": True,
                    "duration": now_time() - send_time,
                    "status": "command_sent_no_arrival_feedback",
                    "error_message": "NavCommand service does not provide arrival feedback.",
                }
            )
            return result

        arrived, final_error, pose_source = self.pose_monitor.wait_until_close(
            x,
            y,
            arrival_tolerance,
            max(0.0, float(timeout_sec) - (now_time() - send_time)),
            goal_frame=frame_id,
        )
        arrival_time = now_time() if arrived else None
        result.update(
            {
                "backend_success": True,
                "success": bool(arrived),
                "timeout": not arrived,
                "arrival_time": arrival_time,
                "duration": now_time() - send_time,
                "status": "arrived_by_pose_feedback" if arrived else "arrival_not_confirmed",
                "final_error": final_error,
                "pose_source_used": pose_source,
                "error_message": "" if arrived else "NavCommand sent, but pose feedback did not confirm arrival.",
            }
        )
        return result
