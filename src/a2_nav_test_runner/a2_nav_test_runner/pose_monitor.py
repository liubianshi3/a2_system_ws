import math
import time
from typing import Any, Dict, Optional

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.duration import Duration
from tf2_ros import Buffer, TransformException, TransformListener

from .utils import normalize_angle, normalize_name, yaw_from_quaternion


class PoseMonitor:
    def __init__(self, node, topic_candidates=None):
        self.node = node
        self.topic_candidates = topic_candidates or ["/amcl_pose", "/odom"]
        self.latest = {}
        self.subscriptions = []
        self.selected_topic = None
        self.tf_buffer = Buffer(cache_time=Duration(seconds=30.0))
        self.tf_listener = TransformListener(self.tf_buffer, self.node, spin_thread=False)
        self.map_frame = "map"
        self.odom_frame = "odom"
        self.base_frame = "base_link"
        self.footprint_frame = "base_footprint"
        for topic in self.topic_candidates:
            name = normalize_name(topic)
            if name == "/amcl_pose":
                self.subscriptions.append(
                    self.node.create_subscription(
                        PoseWithCovarianceStamped,
                        name,
                        lambda msg, topic_name=name: self._on_amcl(msg, topic_name),
                        10,
                    )
                )
            elif name == "/odom":
                self.subscriptions.append(
                    self.node.create_subscription(
                        Odometry,
                        name,
                        lambda msg, topic_name=name: self._on_odom(msg, topic_name),
                        10,
                    )
                )

    def _store_pose(self, topic_name: str, x: float, y: float, yaw: float, frame_id: str):
        self.latest[topic_name] = {
            "topic": topic_name,
            "frame_id": frame_id,
            "x": float(x),
            "y": float(y),
            "yaw": float(yaw),
            "stamp": time.time(),
        }
        if self.selected_topic is None or topic_name == "/amcl_pose":
            self.selected_topic = topic_name

    def _on_amcl(self, msg, topic_name: str):
        pose = msg.pose.pose
        self._store_pose(
            topic_name,
            pose.position.x,
            pose.position.y,
            yaw_from_quaternion(pose.orientation),
            msg.header.frame_id or self.map_frame,
        )

    def _on_odom(self, msg, topic_name: str):
        pose = msg.pose.pose
        self._store_pose(
            topic_name,
            pose.position.x,
            pose.position.y,
            yaw_from_quaternion(pose.orientation),
            msg.header.frame_id or self.odom_frame,
        )

    def available_topics(self):
        graph_topics = {name for name, _ in self.node.get_topic_names_and_types()}
        return [topic for topic in self.topic_candidates if normalize_name(topic) in graph_topics]

    def get_current_pose(self) -> Optional[Dict[str, Any]]:
        if self.selected_topic and self.selected_topic in self.latest:
            return dict(self.latest[self.selected_topic])
        if "/amcl_pose" in self.latest:
            self.selected_topic = "/amcl_pose"
            return dict(self.latest["/amcl_pose"])
        if "/odom" in self.latest:
            self.selected_topic = "/odom"
            return dict(self.latest["/odom"])
        return None

    def get_pose_amcl(self):
        pose = self.latest.get("/amcl_pose")
        return dict(pose) if pose else None

    def get_pose_odom(self):
        pose = self.latest.get("/odom")
        return dict(pose) if pose else None

    def get_pose_tf_map_base_link(self):
        return self.lookup_pose(self.map_frame, self.base_frame)

    def get_pose_tf_map_base_footprint(self):
        return self.lookup_pose(self.map_frame, self.footprint_frame)

    def get_pose_tf_odom_base_link(self):
        return self.lookup_pose(self.odom_frame, self.base_frame)

    def lookup_pose(self, target_frame: str, source_frame: str):
        try:
            transform = self.tf_buffer.lookup_transform(
                target_frame,
                source_frame,
                rclpy.time.Time(),
                timeout=Duration(seconds=0.2),
            )
        except TransformException:
            return None
        translation = transform.transform.translation
        rotation = transform.transform.rotation
        return {
            "frame_id": target_frame,
            "child_frame_id": source_frame,
            "x": float(translation.x),
            "y": float(translation.y),
            "z": float(translation.z),
            "yaw": yaw_from_quaternion(rotation),
            "stamp": time.time(),
        }

    def transform_xy(self, x: float, y: float, from_frame: str, to_frame: str):
        try:
            transform = self.tf_buffer.lookup_transform(
                to_frame,
                from_frame,
                rclpy.time.Time(),
                timeout=Duration(seconds=0.2),
            )
        except TransformException:
            return None
        tx = transform.transform.translation.x
        ty = transform.transform.translation.y
        yaw = yaw_from_quaternion(transform.transform.rotation)
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        new_x = cos_yaw * float(x) - sin_yaw * float(y) + tx
        new_y = sin_yaw * float(x) + cos_yaw * float(y) + ty
        return {"x": new_x, "y": new_y, "yaw": yaw}

    def distance_to(self, x: float, y: float, goal_frame: str = "map"):
        distance_info = self._distance_from_available_sources(x, y, goal_frame=goal_frame)
        return None if distance_info is None else distance_info["distance"]

    def _distance_from_available_sources(self, x: float, y: float, goal_frame: str = "map"):
        goal_frame = goal_frame or self.map_frame
        candidates = []
        if goal_frame == self.map_frame:
            amcl = self.get_pose_amcl()
            if amcl and amcl.get("frame_id") == self.map_frame:
                candidates.append(("amcl", amcl["x"], amcl["y"]))
            tf_map = self.get_pose_tf_map_base_link()
            if tf_map:
                candidates.append(("tf_map_base_link", tf_map["x"], tf_map["y"]))
            tf_foot = self.get_pose_tf_map_base_footprint()
            if tf_foot:
                candidates.append(("tf_map_base_footprint", tf_foot["x"], tf_foot["y"]))
            odom = self.get_pose_odom()
            transformed_goal = self.transform_xy(x, y, self.map_frame, self.odom_frame)
            if odom and transformed_goal and odom.get("frame_id") == self.odom_frame:
                candidates.append(("odom", odom["x"], odom["y"], transformed_goal["x"], transformed_goal["y"]))
        elif goal_frame == self.odom_frame:
            odom = self.get_pose_odom()
            if odom and odom.get("frame_id") == self.odom_frame:
                candidates.append(("odom", odom["x"], odom["y"]))
            tf_pose = self.get_pose_tf_odom_base_link()
            if tf_pose:
                candidates.append(("tf_odom_base_link", tf_pose["x"], tf_pose["y"]))

        if not candidates:
            return None
        first = candidates[0]
        if len(first) == 5:
            source, px, py, gx, gy = first
            return {"source": source, "distance": math.hypot(gx - px, gy - py)}
        source, px, py = first
        return {"source": source, "distance": math.hypot(float(x) - px, float(y) - py)}

    def wait_until_close(self, x: float, y: float, tolerance: float, timeout_sec: float, goal_frame: str = "map"):
        end_time = time.time() + max(0.0, float(timeout_sec))
        last_distance = None
        last_source = None
        while time.time() < end_time:
            rclpy.spin_once(self.node, timeout_sec=0.1)
            distance_info = self._distance_from_available_sources(x, y, goal_frame=goal_frame)
            if distance_info is not None:
                last_distance = distance_info["distance"]
                last_source = distance_info["source"]
            if last_distance is not None and last_distance <= float(tolerance):
                return True, last_distance, last_source
        return False, last_distance, last_source

    def compute_errors(self, goal_x, goal_y, goal_yaw, goal_frame="map"):
        goal_frame = goal_frame or self.map_frame
        errors = {
            "final_error_amcl": None,
            "final_error_odom": None,
            "final_error_tf_map_base_link": None,
            "final_error_tf_map_base_footprint": None,
            "yaw_error_tf_map_base_link": None,
            "pose_source_available": [],
        }

        amcl = self.get_pose_amcl()
        if amcl and amcl.get("frame_id") == goal_frame:
            errors["final_error_amcl"] = math.hypot(float(goal_x) - amcl["x"], float(goal_y) - amcl["y"])
            errors["pose_source_available"].append("amcl")

        odom = self.get_pose_odom()
        if odom:
            if goal_frame == self.odom_frame:
                errors["final_error_odom"] = math.hypot(float(goal_x) - odom["x"], float(goal_y) - odom["y"])
                errors["pose_source_available"].append("odom")
            elif goal_frame == self.map_frame:
                transformed_goal = self.transform_xy(goal_x, goal_y, self.map_frame, self.odom_frame)
                if transformed_goal and odom.get("frame_id") == self.odom_frame:
                    errors["final_error_odom"] = math.hypot(
                        transformed_goal["x"] - odom["x"],
                        transformed_goal["y"] - odom["y"],
                    )
                    errors["pose_source_available"].append("odom_via_map_to_odom")

        tf_map_base_link = self.get_pose_tf_map_base_link()
        if tf_map_base_link and goal_frame == self.map_frame:
            errors["final_error_tf_map_base_link"] = math.hypot(
                float(goal_x) - tf_map_base_link["x"],
                float(goal_y) - tf_map_base_link["y"],
            )
            errors["yaw_error_tf_map_base_link"] = abs(
                normalize_angle(float(goal_yaw) - tf_map_base_link["yaw"])
            )
            errors["pose_source_available"].append("tf_map_base_link")

        tf_map_base_footprint = self.get_pose_tf_map_base_footprint()
        if tf_map_base_footprint and goal_frame == self.map_frame:
            errors["final_error_tf_map_base_footprint"] = math.hypot(
                float(goal_x) - tf_map_base_footprint["x"],
                float(goal_y) - tf_map_base_footprint["y"],
            )
            errors["pose_source_available"].append("tf_map_base_footprint")

        return errors
