#!/usr/bin/env python3

from __future__ import annotations

import math
import os
import struct
from pathlib import Path

import numpy as np
import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from std_msgs.msg import String
from tf2_ros import TransformBroadcaster

try:
    from scipy.spatial import cKDTree
except Exception:  # pragma: no cover - exercised on robots without scipy.
    cKDTree = None


def normalize_quaternion(q: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(q))
    if not math.isfinite(norm) or norm < 1e-9:
        return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    return q / norm


def quaternion_to_matrix(x: float, y: float, z: float, w: float) -> np.ndarray:
    x, y, z, w = normalize_quaternion(np.array([x, y, z, w], dtype=np.float64))
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float64,
    )


def matrix_to_quaternion(rotation: np.ndarray) -> tuple[float, float, float, float]:
    trace = float(np.trace(rotation))
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (rotation[2, 1] - rotation[1, 2]) / s
        y = (rotation[0, 2] - rotation[2, 0]) / s
        z = (rotation[1, 0] - rotation[0, 1]) / s
    else:
        axis = int(np.argmax(np.diag(rotation)))
        if axis == 0:
            s = math.sqrt(1.0 + rotation[0, 0] - rotation[1, 1] - rotation[2, 2]) * 2.0
            w = (rotation[2, 1] - rotation[1, 2]) / s
            x = 0.25 * s
            y = (rotation[0, 1] + rotation[1, 0]) / s
            z = (rotation[0, 2] + rotation[2, 0]) / s
        elif axis == 1:
            s = math.sqrt(1.0 + rotation[1, 1] - rotation[0, 0] - rotation[2, 2]) * 2.0
            w = (rotation[0, 2] - rotation[2, 0]) / s
            x = (rotation[0, 1] + rotation[1, 0]) / s
            y = 0.25 * s
            z = (rotation[1, 2] + rotation[2, 1]) / s
        else:
            s = math.sqrt(1.0 + rotation[2, 2] - rotation[0, 0] - rotation[1, 1]) * 2.0
            w = (rotation[1, 0] - rotation[0, 1]) / s
            x = (rotation[0, 2] + rotation[2, 0]) / s
            y = (rotation[1, 2] + rotation[2, 1]) / s
            z = 0.25 * s
    q = normalize_quaternion(np.array([x, y, z, w], dtype=np.float64))
    return float(q[0]), float(q[1]), float(q[2]), float(q[3])


def pose_to_matrix(position, orientation) -> np.ndarray:
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = quaternion_to_matrix(
        float(orientation.x),
        float(orientation.y),
        float(orientation.z),
        float(orientation.w),
    )
    matrix[:3, 3] = [float(position.x), float(position.y), float(position.z)]
    return matrix


def xyz_rpy_to_matrix(xyz: list[float], rpy: list[float]) -> np.ndarray:
    roll, pitch, yaw = [float(value) for value in rpy]
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]], dtype=np.float64)
    ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]], dtype=np.float64)
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rz @ ry @ rx
    matrix[:3, 3] = np.array(xyz, dtype=np.float64)
    return matrix


def xyz_rotation_matrix_to_matrix(xyz: list[float], rotation_matrix: list[float]) -> np.ndarray:
    if len(rotation_matrix) != 9:
        raise ValueError("rotation_matrix must contain 9 values")
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = np.array(rotation_matrix, dtype=np.float64).reshape((3, 3))
    matrix[:3, 3] = np.array(xyz, dtype=np.float64)
    return matrix


def transform_points(transform: np.ndarray, points: np.ndarray) -> np.ndarray:
    return points @ transform[:3, :3].T + transform[:3, 3]


def rotation_angle(rotation: np.ndarray) -> float:
    value = (float(np.trace(rotation)) - 1.0) * 0.5
    return math.acos(max(-1.0, min(1.0, value)))


def estimate_rigid_transform(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    source_centroid = source.mean(axis=0)
    target_centroid = target.mean(axis=0)
    source_centered = source - source_centroid
    target_centered = target - target_centroid
    covariance = source_centered.T @ target_centered
    u, _, vt = np.linalg.svd(covariance)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0:
        vt[2, :] *= -1
        rotation = vt.T @ u.T
    translation = target_centroid - rotation @ source_centroid
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = rotation
    transform[:3, 3] = translation
    return transform


def voxel_downsample(points: np.ndarray, leaf_size: float, max_points: int) -> np.ndarray:
    if points.size == 0:
        return points
    if leaf_size > 0.0:
        keys = np.floor(points / leaf_size).astype(np.int64)
        _, indices = np.unique(keys, axis=0, return_index=True)
        points = points[np.sort(indices)]
    if max_points > 0 and len(points) > max_points:
        step = max(1, len(points) // max_points)
        points = points[::step][:max_points]
    return points.astype(np.float64, copy=False)


class NearestMap:
    def __init__(self, points: np.ndarray):
        self.points = points
        self.tree = cKDTree(points) if cKDTree is not None else None

    def query(self, source: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.tree is not None:
            distances, indices = self.tree.query(source, k=1, workers=-1)
            return distances.astype(np.float64), self.points[indices]
        distances = np.empty((len(source),), dtype=np.float64)
        targets = np.empty_like(source)
        for start in range(0, len(source), 256):
            chunk = source[start : start + 256]
            diff = chunk[:, None, :] - self.points[None, :, :]
            squared = np.einsum("ijk,ijk->ij", diff, diff)
            indices = np.argmin(squared, axis=1)
            distances[start : start + len(chunk)] = np.sqrt(squared[np.arange(len(chunk)), indices])
            targets[start : start + len(chunk)] = self.points[indices]
        return distances, targets


class PcdRelocalizer3D(Node):
    def __init__(self) -> None:
        super().__init__("pcd_relocalizer_3d")
        raw_map_root = self.declare_parameter("map_root", "${A2_WORKSPACE}/runtime/maps").value
        self.map_root = Path(os.path.expandvars(os.path.expanduser(raw_map_root)))
        self.map_id = self.declare_parameter("map_id", "").value
        self.pcd_path = self.declare_parameter("pcd_path", "").value
        self.live_cloud_topic = self.declare_parameter("live_cloud_topic", "/jt128/front/points").value
        self.odom_topic = self.declare_parameter("odom_topic", "/jt128/dlio/odom").value
        self.initial_pose_topic = self.declare_parameter("initial_pose_topic", "/initialpose").value
        self.pose_topic = self.declare_parameter("pose_topic", "/a2/relocalization/pose").value
        self.status_topic = self.declare_parameter("status_topic", "/a2/relocalization/status").value
        self.map_frame = self.declare_parameter("map_frame", "map").value
        self.odom_frame = self.declare_parameter("odom_frame", "odom").value
        self.base_frame = self.declare_parameter("base_frame", "base_link").value
        self.lidar_xyz = list(
            self.declare_parameter("base_to_lidar_xyz", [0.33767, 0.0, 0.08134]).value
        )
        self.use_lidar_rotation_matrix = bool(
            self.declare_parameter("base_to_lidar_use_rotation_matrix", False).value
        )
        self.lidar_rotation_matrix = list(
            self.declare_parameter(
                "base_to_lidar_rotation_matrix",
                [1.0, 0.0, 0.0,
                 0.0, 1.0, 0.0,
                 0.0, 0.0, 1.0],
            ).value
        )
        self.lidar_rpy = list(self.declare_parameter("base_to_lidar_rpy", [0.0, 0.0, 0.0]).value)
        self.publish_tf = bool(self.declare_parameter("publish_tf", True).value)
        self.auto_seed_identity = bool(self.declare_parameter("auto_seed_identity", True).value)
        self.icp_interval_sec = max(0.2, float(self.declare_parameter("icp_interval_sec", 1.0).value))
        self.voxel_leaf_size = max(0.0, float(self.declare_parameter("voxel_leaf_size", 0.25).value))
        self.max_map_points = int(self.declare_parameter("max_map_points", 80000).value)
        self.max_scan_points = int(self.declare_parameter("max_scan_points", 2500).value)
        self.min_correspondences = int(self.declare_parameter("min_correspondences", 120).value)
        self.max_correspondence_distance = float(
            self.declare_parameter("max_correspondence_distance", 0.8).value
        )
        self.max_iterations = int(self.declare_parameter("max_iterations", 8).value)
        self.max_translation_correction = float(
            self.declare_parameter("max_translation_correction", 0.35).value
        )
        self.max_rotation_correction = math.radians(
            float(self.declare_parameter("max_rotation_correction_deg", 8.0).value)
        )
        self.max_map_to_odom_translation = float(
            self.declare_parameter("max_map_to_odom_translation", 20.0).value
        )
        self.max_base_distance_from_origin = float(
            self.declare_parameter("max_base_distance_from_origin", 120.0).value
        )
        self.ready_fitness_threshold = float(
            self.declare_parameter("ready_fitness_threshold", 0.35).value
        )
        self.xy_variance = float(self.declare_parameter("xy_variance", 0.04).value)
        self.z_variance = float(self.declare_parameter("z_variance", 0.08).value)
        self.rot_variance = float(self.declare_parameter("rot_variance", 0.04).value)

        if self.use_lidar_rotation_matrix:
            self.base_to_lidar = xyz_rotation_matrix_to_matrix(
                self.lidar_xyz, self.lidar_rotation_matrix
            )
        else:
            self.base_to_lidar = xyz_rpy_to_matrix(self.lidar_xyz, self.lidar_rpy)
        self.map_to_odom = np.eye(4, dtype=np.float64)
        self.has_seed = bool(self.auto_seed_identity)
        self.last_odom: Odometry | None = None
        self.last_scan: np.ndarray | None = None
        self.last_status = ""
        self.last_logged_state = ""
        self.last_log_time = self.get_clock().now()
        self.last_fitness: float | None = None
        self.last_cloud_parse_time = None
        self.cloud_sub = None

        map_points = self._load_pcd()
        map_points = voxel_downsample(map_points, self.voxel_leaf_size, self.max_map_points)
        self.nearest_map = NearestMap(map_points)
        self.get_logger().info(
            f"Loaded 3D relocalization map points={len(map_points)} source={self._resolve_pcd_path()}"
        )

        self.pose_pub = self.create_publisher(PoseWithCovarianceStamped, self.pose_topic, 10)
        self.status_pub = self.create_publisher(String, self.status_topic, 10)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.create_subscription(Odometry, self.odom_topic, self.on_odom, 20)
        self.create_subscription(PoseWithCovarianceStamped, self.initial_pose_topic, self.on_initial_pose, 10)
        if self.has_seed:
            self.ensure_cloud_subscription()
        self.create_timer(self.icp_interval_sec, self.run_icp)

    def ensure_cloud_subscription(self) -> None:
        if self.cloud_sub is not None:
            return
        self.cloud_sub = self.create_subscription(PointCloud2, self.live_cloud_topic, self.on_cloud, 2)
        self.get_logger().info(f"Subscribed to live 3D cloud for relocalization: {self.live_cloud_topic}")

    def _resolve_pcd_path(self) -> Path:
        if self.pcd_path:
            return Path(os.path.expandvars(os.path.expanduser(self.pcd_path)))
        map_id = self.map_id
        if not map_id:
            current_file = self.map_root / "current_map.txt"
            if current_file.exists():
                map_id = current_file.read_text(encoding="utf-8").strip()
        if not map_id:
            raise RuntimeError("map_id or pcd_path is required")
        return self.map_root / map_id / "pointcloud_map_3d.pcd"

    def _load_pcd(self) -> np.ndarray:
        path = self._resolve_pcd_path()
        if not path.exists():
            raise RuntimeError(f"PCD not found: {path}")
        points: list[tuple[float, float, float]] = []
        fields: list[str] = []
        data_started = False
        with path.open("r", encoding="ascii", errors="strict") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if data_started:
                    parts = line.split()
                    if len(parts) < 3:
                        continue
                    try:
                        if fields and {"x", "y", "z"}.issubset(set(fields)):
                            points.append(
                                (
                                    float(parts[fields.index("x")]),
                                    float(parts[fields.index("y")]),
                                    float(parts[fields.index("z")]),
                                )
                            )
                        else:
                            points.append((float(parts[0]), float(parts[1]), float(parts[2])))
                    except (ValueError, IndexError):
                        continue
                    continue
                key, _, value = line.partition(" ")
                if key.upper() == "FIELDS":
                    fields = value.split()
                if key.upper() == "DATA":
                    if value.strip().lower() != "ascii":
                        raise RuntimeError("pcd_relocalizer_3d currently supports ASCII PCD only")
                    data_started = True
        if not points:
            raise RuntimeError(f"PCD has no readable XYZ points: {path}")
        return np.array(points, dtype=np.float64)

    def on_cloud(self, msg: PointCloud2) -> None:
        if not self.has_seed:
            return
        now = self.get_clock().now()
        if self.last_cloud_parse_time is not None:
            age = (now - self.last_cloud_parse_time).nanoseconds * 1e-9
            if age < self.icp_interval_sec:
                return
        self.last_cloud_parse_time = now
        points = []
        try:
            for point in point_cloud2.read_points(msg, field_names=("x", "y", "z"), skip_nans=True):
                x, y, z = float(point[0]), float(point[1]), float(point[2])
                if math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
                    points.append((x, y, z))
        except Exception as exc:
            self.publish_status(False, "cloud_error", f"read_points_failed:{exc}")
            return
        if not points:
            self.publish_status(False, "waiting_scan", "empty_cloud")
            return
        self.last_scan = voxel_downsample(
            np.array(points, dtype=np.float64),
            self.voxel_leaf_size,
            self.max_scan_points,
        )

    def on_odom(self, msg: Odometry) -> None:
        self.last_odom = msg
        if self.has_seed:
            self.publish_pose_and_tf(msg, ready=self.last_fitness is not None)

    def on_initial_pose(self, msg: PoseWithCovarianceStamped) -> None:
        if self.last_odom is None:
            self.publish_status(False, "waiting_odom", "initialpose_without_odom")
            return
        map_to_base = pose_to_matrix(msg.pose.pose.position, msg.pose.pose.orientation)
        odom_to_base = pose_to_matrix(
            self.last_odom.pose.pose.position,
            self.last_odom.pose.pose.orientation,
        )
        self.map_to_odom = map_to_base @ np.linalg.inv(odom_to_base)
        self.has_seed = True
        self.last_fitness = None
        self.last_scan = None
        self.last_cloud_parse_time = None
        self.ensure_cloud_subscription()
        if self.auto_seed_identity:
            self.get_logger().warning(
                "auto_seed_identity is enabled. This is only safe when the loaded PCD map "
                "was built in the same odom origin as the live DLIO session."
            )
        self.publish_pose_and_tf(self.last_odom, ready=False)
        self.publish_status(True, "seeded", "initialpose_anchor_set")

    def run_icp(self) -> None:
        if not self.has_seed:
            self.publish_status(False, "waiting_seed", "send_initialpose_or_enable_auto_seed")
            return
        if self.last_odom is None:
            self.publish_status(False, "waiting_odom", "no_dlio_odom")
            return
        if self.last_scan is None or len(self.last_scan) < self.min_correspondences:
            count = 0 if self.last_scan is None else len(self.last_scan)
            self.publish_status(False, "waiting_scan", f"scan_points={count}")
            return

        odom_to_base = pose_to_matrix(
            self.last_odom.pose.pose.position,
            self.last_odom.pose.pose.orientation,
        )
        source = transform_points(self.map_to_odom @ odom_to_base @ self.base_to_lidar, self.last_scan)
        correction = np.eye(4, dtype=np.float64)
        fitness = float("inf")
        correspondences = 0
        for _ in range(max(1, self.max_iterations)):
            moved = transform_points(correction, source)
            distances, targets = self.nearest_map.query(moved)
            mask = distances < self.max_correspondence_distance
            correspondences = int(np.count_nonzero(mask))
            if correspondences < self.min_correspondences:
                self.publish_status(
                    False,
                    "icp_rejected",
                    f"few_correspondences={correspondences}",
                )
                return
            step = estimate_rigid_transform(moved[mask], targets[mask])
            correction = step @ correction
            fitness = float(np.mean(distances[mask]))
            if np.linalg.norm(step[:3, 3]) < 0.01 and rotation_angle(step[:3, :3]) < math.radians(0.2):
                break

        translation = float(np.linalg.norm(correction[:3, 3]))
        angle = rotation_angle(correction[:3, :3])
        if translation > self.max_translation_correction or angle > self.max_rotation_correction:
            self.publish_status(
                False,
                "icp_rejected",
                f"correction_too_large:translation={translation:.3f},rotation_deg={math.degrees(angle):.2f}",
            )
            return

        candidate_map_to_odom = correction @ self.map_to_odom
        candidate_map_to_base = candidate_map_to_odom @ odom_to_base
        if np.linalg.norm(candidate_map_to_odom[:3, 3]) > self.max_map_to_odom_translation:
            self.publish_status(
                False,
                "icp_rejected",
                (
                    "map_to_odom_out_of_bounds:"
                    f"norm={np.linalg.norm(candidate_map_to_odom[:3, 3]):.3f},"
                    f"limit={self.max_map_to_odom_translation:.3f}"
                ),
            )
            return
        if np.linalg.norm(candidate_map_to_base[:3, 3]) > self.max_base_distance_from_origin:
            self.publish_status(
                False,
                "icp_rejected",
                (
                    "base_pose_out_of_bounds:"
                    f"norm={np.linalg.norm(candidate_map_to_base[:3, 3]):.3f},"
                    f"limit={self.max_base_distance_from_origin:.3f}"
                ),
            )
            return

        self.map_to_odom = candidate_map_to_odom
        self.last_fitness = fitness
        ready = fitness <= self.ready_fitness_threshold
        self.publish_pose_and_tf(self.last_odom, ready=ready)
        self.publish_status(
            ready,
            "ready" if ready else "icp_converging",
            f"fitness={fitness:.3f};correspondences={correspondences};translation={translation:.3f};rotation_deg={math.degrees(angle):.2f}",
        )

    def publish_pose_and_tf(self, odom_msg: Odometry, *, ready: bool) -> None:
        odom_to_base = pose_to_matrix(odom_msg.pose.pose.position, odom_msg.pose.pose.orientation)
        map_to_base = self.map_to_odom @ odom_to_base
        pose = PoseWithCovarianceStamped()
        pose.header.stamp = odom_msg.header.stamp
        pose.header.frame_id = self.map_frame
        pose.pose.pose.position.x = float(map_to_base[0, 3])
        pose.pose.pose.position.y = float(map_to_base[1, 3])
        pose.pose.pose.position.z = float(map_to_base[2, 3])
        qx, qy, qz, qw = matrix_to_quaternion(map_to_base[:3, :3])
        pose.pose.pose.orientation.x = qx
        pose.pose.pose.orientation.y = qy
        pose.pose.pose.orientation.z = qz
        pose.pose.pose.orientation.w = qw
        covariance_scale = 1.0 if ready else 10.0
        pose.pose.covariance[0] = self.xy_variance * covariance_scale
        pose.pose.covariance[7] = self.xy_variance * covariance_scale
        pose.pose.covariance[14] = self.z_variance * covariance_scale
        pose.pose.covariance[21] = self.rot_variance * covariance_scale
        pose.pose.covariance[28] = self.rot_variance * covariance_scale
        pose.pose.covariance[35] = self.rot_variance * covariance_scale
        self.pose_pub.publish(pose)

        if not self.publish_tf:
            return
        tf_msg = TransformStamped()
        tf_msg.header.stamp = odom_msg.header.stamp
        tf_msg.header.frame_id = self.map_frame
        tf_msg.child_frame_id = self.odom_frame
        tf_msg.transform.translation.x = float(self.map_to_odom[0, 3])
        tf_msg.transform.translation.y = float(self.map_to_odom[1, 3])
        tf_msg.transform.translation.z = float(self.map_to_odom[2, 3])
        qx, qy, qz, qw = matrix_to_quaternion(self.map_to_odom[:3, :3])
        tf_msg.transform.rotation.x = qx
        tf_msg.transform.rotation.y = qy
        tf_msg.transform.rotation.z = qz
        tf_msg.transform.rotation.w = qw
        self.tf_broadcaster.sendTransform(tf_msg)

    def publish_status(self, ready: bool, state: str, reason: str) -> None:
        status = (
            f"state={state};ready={str(bool(ready)).lower()};reason={reason};"
            f"map_id={self.map_id or 'current'};live_cloud_topic={self.live_cloud_topic};odom_topic={self.odom_topic}"
        )
        self.status_pub.publish(String(data=status))
        now = self.get_clock().now()
        log_age = (now - self.last_log_time).nanoseconds * 1e-9
        should_log = state != self.last_logged_state or log_age >= 5.0
        if should_log:
            self.get_logger().info(f"3D relocalization status changed: {status}")
            self.last_logged_state = state
            self.last_log_time = now
        self.last_status = status


def main() -> None:
    rclpy.init()
    node = PcdRelocalizer3D()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
