#!/usr/bin/env python3

import argparse
import math
import os
import sys
import time
from pathlib import Path

import rclpy
from a2_interfaces.srv import ManageMap
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Bool, String


def parse_status_fields(payload: str):
    fields = {}
    for item in payload.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        fields[key] = value
    return fields


class OutdoorPipelineHelper(Node):
    def __init__(self):
        super().__init__("gazebo_outdoor_pipeline_helper")
        self.goal_pub = self.create_publisher(PoseStamped, "/a2/exploration/goal", 10)
        self.map_ready = False
        self.localization_ok = False
        self.current_odom = None
        self.real_report = ""
        self.nav_status = ""
        self.create_subscription(Bool, "/a2/map_ready", self.on_map_ready, 10)
        self.create_subscription(Bool, "/a2/localization_ok", self.on_localization_ok, 10)
        self.create_subscription(Odometry, "/odom", self.on_odom, 20)
        self.create_subscription(String, "/a2/real/report", self.on_real_report, 10)
        self.create_subscription(String, "/a2/nav2/status", self.on_nav_status, 10)
        self.map_client = self.create_client(ManageMap, "/map_manager/manage_map")

    def on_map_ready(self, msg):
        self.map_ready = msg.data

    def on_localization_ok(self, msg):
        self.localization_ok = msg.data

    def on_odom(self, msg):
        self.current_odom = msg

    def on_real_report(self, msg):
        self.real_report = msg.data

    def on_nav_status(self, msg):
        self.nav_status = msg.data

    def spin_until(self, predicate, timeout_sec, description):
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if predicate():
                return True
        self.get_logger().error(f"Timeout while waiting for {description}.")
        return False

    def current_xy(self):
        if self.current_odom is None:
            return None
        pose = self.current_odom.pose.pose.position
        return (float(pose.x), float(pose.y))

    def distance_to(self, x, y):
        current = self.current_xy()
        if current is None:
            return math.inf
        return math.hypot(current[0] - x, current[1] - y)

    def publish_goal(self, x, y, yaw=0.0):
        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.pose.position.x = float(x)
        msg.pose.position.y = float(y)
        msg.pose.orientation.z = math.sin(yaw * 0.5)
        msg.pose.orientation.w = math.cos(yaw * 0.5)
        self.goal_pub.publish(msg)

    def run_patrol(self, waypoints, tolerance, timeout_per_goal):
        if not self.spin_until(
            lambda: self.map_ready and self.localization_ok and self.current_odom is not None,
            40.0,
            "map_ready + localization + odom",
        ):
            return False

        for index, waypoint in enumerate(waypoints, start=1):
            x, y = waypoint
            self.get_logger().info(f"Patrol waypoint {index}/{len(waypoints)} -> ({x:.2f}, {y:.2f})")
            reached = self.drive_to_goal(x, y, tolerance, timeout_per_goal, use_nav_report=False)
            if not reached:
                self.get_logger().error(f"Failed to reach patrol waypoint {index}.")
                return False
        return True

    def drive_to_goal(self, x, y, tolerance, timeout_sec, use_nav_report):
        deadline = time.monotonic() + timeout_sec
        republish_period = 5.0 if use_nav_report else 2.0
        republish_at = 0.0
        reached_since = None
        initial_distance = None
        start_xy = None

        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            current_xy = self.current_xy()
            if current_xy is not None and initial_distance is None:
                start_xy = current_xy
                initial_distance = self.distance_to(x, y)

            now = time.monotonic()
            if now >= republish_at:
                nav_state = parse_status_fields(self.nav_status).get("state", "")
                should_publish = True
                if use_nav_report and nav_state in {"goal_sent", "goal_accepted", "goal_active"}:
                    should_publish = False
                if should_publish:
                    self.publish_goal(x, y)
                republish_at = now + republish_period

            distance = self.distance_to(x, y)
            if distance <= tolerance:
                if reached_since is None:
                    reached_since = now
                elif now - reached_since >= 1.0:
                    return True
            else:
                reached_since = None

            if use_nav_report and start_xy is not None:
                moved = math.hypot(current_xy[0] - start_xy[0], current_xy[1] - start_xy[1])
                distance_reduction = max(0.0, initial_distance - distance)
                nav_fields = parse_status_fields(self.nav_status)
                if (
                    nav_fields.get("state") in {
                        "goal_completed",
                        "goal_accepted",
                        "goal_sent",
                        "goal_active",
                    }
                    and (distance <= tolerance or (moved >= 0.8 and distance_reduction >= 0.8))
                ):
                    return True

        return False

    def save_map(self, map_id):
        if not self.map_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error("Map manager service is unavailable.")
            return False
        request = ManageMap.Request()
        request.command = "save"
        request.map_id = map_id
        future = self.map_client.call_async(request)
        if not self.spin_until(lambda: future.done(), 20.0, "map save response"):
            return False
        response = future.result()
        if response is None or not response.success:
            self.get_logger().error(
                f"Map save failed: {getattr(response, 'message', 'no response')}"
            )
            return False
        self.get_logger().info(response.message)
        return True

    def wait_ready_report(self):
        return self.spin_until(
            lambda: parse_status_fields(self.real_report).get("ready") == "true",
            50.0,
            "ready real report",
        )


def parse_waypoints(values):
    waypoints = []
    for value in values:
        if ":" not in value:
            raise ValueError(f"invalid waypoint `{value}`")
        x_text, y_text = value.split(":", 1)
        waypoints.append((float(x_text), float(y_text)))
    return waypoints


def main():
    parser = argparse.ArgumentParser(description="Outdoor Gazebo mapping/navigation helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    patrol_parser = subparsers.add_parser("patrol-save")
    patrol_parser.add_argument("--map-id", required=True)
    patrol_parser.add_argument(
        "--waypoint",
        action="append",
        dest="waypoints",
        default=[],
        help="Waypoint in x:y format",
    )
    patrol_parser.add_argument("--tolerance", type=float, default=0.9)
    patrol_parser.add_argument("--timeout-per-goal", type=float, default=80.0)

    nav_parser = subparsers.add_parser("nav-goal")
    nav_parser.add_argument("--x", type=float, required=True)
    nav_parser.add_argument("--y", type=float, required=True)
    nav_parser.add_argument("--tolerance", type=float, default=0.8)
    nav_parser.add_argument("--timeout", type=float, default=70.0)

    args = parser.parse_args()

    rclpy.init()
    node = OutdoorPipelineHelper()

    try:
        if args.command == "patrol-save":
            waypoints = parse_waypoints(args.waypoints)
            if not waypoints:
                waypoints = [
                    (-7.2, 3.4),
                    (-2.5, 3.4),
                    (2.5, 3.4),
                    (6.4, 3.0),
                    (6.4, -2.8),
                    (2.2, -2.8),
                    (-2.2, -2.8),
                    (-7.2, -2.8),
                    (-7.2, 0.0),
                ]
            if not node.run_patrol(waypoints, args.tolerance, args.timeout_per_goal):
                return 1
            if not node.save_map(args.map_id):
                return 1
            map_yaml = Path.home() / "a2_system_ws" / "runtime" / "maps" / args.map_id / "map.yaml"
            if not map_yaml.exists():
                node.get_logger().error(f"Saved map yaml not found: {map_yaml}")
                return 1
            print(str(map_yaml))
            return 0

        if args.command == "nav-goal":
            if not node.wait_ready_report():
                return 1
            if node.current_odom is None and not node.spin_until(lambda: node.current_odom is not None, 10.0, "odom"):
                return 1
            if not node.drive_to_goal(args.x, args.y, args.tolerance, args.timeout, use_nav_report=True):
                node.get_logger().error("Nav2 failed to move toward the requested goal in time.")
                return 1
            return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()

    return 1


if __name__ == "__main__":
    sys.exit(main())
