import time
from typing import Dict

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient

from .utils import now_time, yaw_to_quaternion


class Nav2ActionBackend:
    def __init__(self, node, action_name="/navigate_to_pose"):
        self.node = node
        self.action_name = action_name
        self.client = ActionClient(self.node, NavigateToPose, self.action_name)

    def wait_until_ready(self, timeout_sec=10.0) -> bool:
        return bool(self.client.wait_for_server(timeout_sec=float(timeout_sec)))

    def send_goal(self, goal_id, x, y, yaw, frame_id="map", timeout_sec=120.0) -> Dict:
        send_time = now_time()
        result = base_result("nav2_action", goal_id, send_time)
        self.node.get_logger().info(
            f"Sending Nav2 goal {goal_id}: x={float(x):.3f}, y={float(y):.3f}, yaw={float(yaw):.3f}, frame={frame_id}"
        )
        if not self.wait_until_ready(timeout_sec=5.0):
            result.update(
                {
                    "duration": now_time() - send_time,
                    "status": "action_server_unavailable",
                    "error_message": f"NavigateToPose action server not available: {self.action_name}",
                }
            )
            return result

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = make_pose(self.node, x, y, yaw, frame_id)
        goal_future = self.client.send_goal_async(goal_msg)
        if not wait_future(self.node, goal_future, timeout_sec=min(10.0, float(timeout_sec))):
            result.update(
                {
                    "timeout": True,
                    "duration": now_time() - send_time,
                    "status": "goal_response_timeout",
                    "error_message": "Timed out waiting for Nav2 goal response.",
                }
            )
            return result

        goal_handle = goal_future.result()
        if goal_handle is None or not goal_handle.accepted:
            result.update(
                {
                    "duration": now_time() - send_time,
                    "status": "goal_rejected",
                    "error_message": "Nav2 action goal was rejected.",
                }
            )
            return result

        result_future = goal_handle.get_result_async()
        remaining = max(0.0, float(timeout_sec) - (now_time() - send_time))
        if not wait_future(self.node, result_future, timeout_sec=remaining):
            try:
                cancel_future = goal_handle.cancel_goal_async()
                wait_future(self.node, cancel_future, timeout_sec=2.0)
            except Exception as exc:
                self.node.get_logger().warn(f"Cancel request failed after timeout: {exc}")
            result.update(
                {
                    "timeout": True,
                    "duration": now_time() - send_time,
                    "status": "navigation_timeout",
                    "error_message": f"Navigation timed out after {float(timeout_sec):.1f}s.",
                }
            )
            return result

        action_result = result_future.result()
        status_code = getattr(action_result, "status", None)
        arrival_time = now_time()
        success = status_code == GoalStatus.STATUS_SUCCEEDED
        result.update(
            {
                "backend_success": success,
                "success": success,
                "arrival_time": arrival_time if success else None,
                "duration": arrival_time - send_time,
                "status": goal_status_text(status_code),
                "error_message": "" if success else f"Nav2 action status={status_code}",
            }
        )
        return result


def make_pose(node, x, y, yaw, frame_id):
    pose = PoseStamped()
    pose.header.frame_id = frame_id
    pose.header.stamp = node.get_clock().now().to_msg()
    pose.pose.position.x = float(x)
    pose.pose.position.y = float(y)
    pose.pose.position.z = 0.0
    quat = yaw_to_quaternion(float(yaw))
    pose.pose.orientation.x = quat["x"]
    pose.pose.orientation.y = quat["y"]
    pose.pose.orientation.z = quat["z"]
    pose.pose.orientation.w = quat["w"]
    return pose


def wait_future(node, future, timeout_sec) -> bool:
    timeout_sec = max(0.0, float(timeout_sec))
    rclpy.spin_until_future_complete(node, future, timeout_sec=timeout_sec)
    return future.done()


def goal_status_text(status_code):
    mapping = {
        GoalStatus.STATUS_UNKNOWN: "unknown",
        GoalStatus.STATUS_ACCEPTED: "accepted",
        GoalStatus.STATUS_EXECUTING: "executing",
        GoalStatus.STATUS_CANCELING: "canceling",
        GoalStatus.STATUS_SUCCEEDED: "succeeded",
        GoalStatus.STATUS_CANCELED: "canceled",
        GoalStatus.STATUS_ABORTED: "aborted",
    }
    return mapping.get(status_code, f"status_{status_code}")


def base_result(backend, goal_id, send_time):
    return {
        "backend": backend,
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
