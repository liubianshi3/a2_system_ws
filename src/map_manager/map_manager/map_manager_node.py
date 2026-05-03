#!/usr/bin/env python3

import math
import os
import struct
import time
from datetime import datetime
from pathlib import Path

import rclpy
import yaml
from a2_interfaces.srv import ManageMap, SetMode
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String


class MapManagerNode(Node):
    def __init__(self):
        super().__init__("map_manager")
        self.runtime_mode = self.declare_parameter("runtime_mode", "real").value
        raw_map_root = self.declare_parameter("map_root", "/tmp/a2_maps").value
        self.map_root = Path(os.path.expandvars(os.path.expanduser(raw_map_root)))
        self.occupancy_topic = self.declare_parameter("occupancy_topic", "/map").value
        self.map_representation = self.declare_parameter(
            "map_representation", "occupancy_grid_2d"
        ).value
        self.pointcloud_topic_3d = self.declare_parameter(
            "pointcloud_topic_3d", "/grid_clouds"
        ).value
        self.pointcloud_fallback_topic_3d = self.declare_parameter(
            "pointcloud_fallback_topic_3d", "/jt128/front/points"
        ).value
        self.pointcloud_primary_stale_sec = float(
            self.declare_parameter("pointcloud_primary_stale_sec", 2.0).value
        )
        self.pointcloud_snapshot_enabled = bool(
            self.declare_parameter("pointcloud_snapshot_enabled", True).value
        )
        self.pointcloud_max_points = int(
            self.declare_parameter("pointcloud_max_points", 200000).value
        )
        self.active_map_topic = self.declare_parameter(
            "active_map_topic", "/a2/map_manager/active_map"
        ).value
        self.mode_topic = self.declare_parameter("mode_topic", "/a2/system_mode").value
        self.status_topic = self.declare_parameter(
            "status_topic", "/a2/map_manager/status"
        ).value
        self.current_mode = self.declare_parameter("default_mode", "mapping").value
        self.map_transient_local = bool(
            self.declare_parameter("map_transient_local", False).value
        )
        self.latest_map = None
        self.latest_pointcloud_primary = None
        self.latest_pointcloud_primary_monotonic = 0.0
        self.latest_pointcloud_fallback = None
        self.latest_pointcloud_fallback_monotonic = 0.0
        self.active_map_id = ""
        self.last_status = ""

        self.map_root.mkdir(parents=True, exist_ok=True)
        self.active_pub = self.create_publisher(String, self.active_map_topic, 10)
        self.mode_pub = self.create_publisher(String, self.mode_topic, 10)
        self.status_pub = self.create_publisher(String, self.status_topic, 10)
        map_qos = (
            QoSProfile(
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            )
            if self.map_transient_local
            else 10
        )
        self.create_subscription(
            OccupancyGrid, self.occupancy_topic, self.on_map, map_qos
        )
        if self.pointcloud_snapshot_enabled:
            self.create_subscription(
                PointCloud2, self.pointcloud_topic_3d, self.on_primary_pointcloud, 10
            )
            if (
                self.pointcloud_fallback_topic_3d
                and self.pointcloud_fallback_topic_3d != self.pointcloud_topic_3d
            ):
                self.create_subscription(
                    PointCloud2,
                    self.pointcloud_fallback_topic_3d,
                    self.on_fallback_pointcloud,
                    10,
                )
        self.create_service(
            ManageMap, "/map_manager/manage_map", self.handle_manage_map
        )
        self.create_service(SetMode, "/map_manager/set_mode", self.handle_set_mode)
        self.publish_mode()
        self.publish_status("idle", "startup")

    def on_map(self, msg):
        first_map = self.latest_map is None
        self.latest_map = msg
        if first_map:
            self.publish_status("ready", "map_received")

    def on_primary_pointcloud(self, msg):
        first_cloud = self.latest_pointcloud_primary is None
        self.latest_pointcloud_primary = msg
        self.latest_pointcloud_primary_monotonic = time.monotonic()
        if first_cloud and self.latest_map is None:
            self.publish_status("ready", "pointcloud_primary_received")

    def on_fallback_pointcloud(self, msg):
        first_cloud = self.latest_pointcloud_fallback is None
        self.latest_pointcloud_fallback = msg
        self.latest_pointcloud_fallback_monotonic = time.monotonic()
        if first_cloud and self.latest_map is None and self.latest_pointcloud_primary is None:
            self.publish_status("ready", "pointcloud_fallback_received")

    def selected_pointcloud(self):
        now = time.monotonic()
        if (
            self.latest_pointcloud_primary is not None
            and now - self.latest_pointcloud_primary_monotonic
            <= self.pointcloud_primary_stale_sec
        ):
            return self.latest_pointcloud_primary, self.pointcloud_topic_3d
        if self.pointcloud_fallback_topic_3d and self.latest_pointcloud_fallback is not None:
            return self.latest_pointcloud_fallback, self.pointcloud_fallback_topic_3d
        if self.latest_pointcloud_primary is not None:
            return self.latest_pointcloud_primary, self.pointcloud_topic_3d
        return None, None

    def publish_active(self):
        self.active_pub.publish(String(data=self.active_map_id))

    def publish_mode(self):
        self.mode_pub.publish(String(data=self.current_mode))

    def list_maps(self):
        return sorted([item.name for item in self.map_root.iterdir() if item.is_dir()])

    def handle_set_mode(self, request, response):
        allowed = {"mapping", "localization", "navigation", "idle"}
        if request.mode not in allowed:
            response.success = False
            response.message = f"unsupported mode: {request.mode}"
            self.publish_status("error", f"unsupported_mode:{request.mode}")
            return response
        self.current_mode = request.mode
        self.publish_mode()
        self.publish_status("mode_changed", f"mode={self.current_mode}")
        response.success = True
        response.message = f"mode set to {self.current_mode}"
        return response

    def handle_manage_map(self, request, response):
        command = request.command.lower().strip()
        if command == "list":
            response.success = True
            response.message = "listed maps"
            response.map_ids = self.list_maps()
            self.publish_status("listed", f"count={len(response.map_ids)}")
            return response
        if command == "save":
            selected_pointcloud, _ = self.selected_pointcloud()
            if self.latest_map is None and selected_pointcloud is None:
                response.success = False
                response.message = "no map or pointcloud received yet"
                self.publish_status("error", "no_map_or_pointcloud")
                return response
            try:
                map_id = self.save_map_bundle(request.map_id)
            except Exception as exc:
                response.success = False
                response.message = f"save failed: {exc}"
                self.publish_status("error", "save_failed")
                self.get_logger().error(f"Failed to save map bundle: {exc}")
                return response
            self.active_map_id = map_id
            self.publish_active()
            self.publish_status("saved", f"map_id={map_id}")
            response.success = True
            response.message = f"saved map {map_id}"
            response.map_ids = self.list_maps()
            return response
        if command == "load":
            map_id = request.map_id
            if not map_id or not (self.map_root / map_id).exists():
                response.success = False
                response.message = f"map not found: {map_id}"
                self.publish_status("error", f"map_not_found:{map_id}")
                return response
            self.active_map_id = map_id
            self.publish_active()
            self.publish_status("loaded", f"map_id={map_id}")
            response.success = True
            response.message = f"loaded map {map_id}"
            response.map_ids = self.list_maps()
            return response
        if command == "promote":
            map_id = request.map_id
            if not map_id or not (self.map_root / map_id).exists():
                response.success = False
                response.message = f"map not found: {map_id}"
                self.publish_status("error", f"map_not_found:{map_id}")
                return response
            with (self.map_root / "current_map.txt").open("w", encoding="utf-8") as handle:
                handle.write(map_id + "\n")
            self.active_map_id = map_id
            self.publish_active()
            self.publish_status("promoted", f"map_id={map_id}")
            response.success = True
            response.message = f"promoted map {map_id}"
            response.map_ids = self.list_maps()
            return response
        response.success = False
        response.message = f"unsupported command: {request.command}"
        self.publish_status("error", f"unsupported_command:{request.command}")
        return response

    def save_map_bundle(self, requested_map_id: str) -> str:
        map_id = requested_map_id or datetime.now().strftime("map_%Y%m%d_%H%M%S")
        map_dir = self.map_root / map_id
        map_dir.mkdir(parents=True, exist_ok=True)

        artifacts = []
        selected_pointcloud, selected_topic = self.selected_pointcloud()
        if self.latest_map is not None:
            self.write_nav2_map(self.latest_map, map_dir)
            artifacts.append(
                {
                    "kind": "occupancy_grid_2d",
                    "topic": self.occupancy_topic,
                    "path": "map.yaml",
                    "resolution": float(self.latest_map.info.resolution),
                }
            )
        if self.pointcloud_snapshot_enabled and selected_pointcloud is not None:
            artifacts.append(
                self.write_pointcloud_snapshot(selected_pointcloud, map_dir, selected_topic)
            )

        metadata = {
            "created_at": datetime.now().isoformat(),
            "mode": self.current_mode,
            "representation": self.map_representation,
            "source_topic": self.occupancy_topic if self.latest_map is not None else None,
            "width": self.latest_map.info.width if self.latest_map is not None else None,
            "height": self.latest_map.info.height if self.latest_map is not None else None,
            "resolution": self.latest_map.info.resolution
            if self.latest_map is not None
            else None,
            "pointcloud_topic_3d": selected_topic,
            "artifacts": artifacts,
        }
        with (map_dir / "metadata.yaml").open("w", encoding="utf-8") as handle:
            yaml.safe_dump(metadata, handle, sort_keys=False)
        with (map_dir / "media_index.yaml").open("w", encoding="utf-8") as handle:
            yaml.safe_dump(
                {
                    "entries": [
                        {
                            "path": artifact["path"],
                            "kind": "pointcloud"
                            if artifact["kind"] in {"pointcloud_snapshot_3d", "native_pointcloud_map_3d"}
                            else "occupancy"
                            if artifact["kind"] == "occupancy_grid_2d"
                            else "other",
                            "group": "root",
                        }
                        for artifact in artifacts
                    ]
                },
                handle,
                sort_keys=False,
            )
        return map_id

    def publish_status(self, state, reason):
        mode = self.runtime_mode
        _, selected_topic = self.selected_pointcloud()
        ready = self.latest_map is not None or selected_topic is not None
        status = (
            f"mode={mode};state={state};ready={str(bool(ready)).lower()};reason={reason};"
            f"system_mode={self.current_mode};active_map={self.active_map_id or 'none'};"
            f"representation={self.map_representation};source_topic={self.occupancy_topic};"
            f"pointcloud_topic_3d={selected_topic or self.pointcloud_topic_3d};"
            f"pointcloud_fallback_topic_3d={self.pointcloud_fallback_topic_3d}"
        )
        self.status_pub.publish(String(data=status))
        if status != self.last_status:
            self.get_logger().info(f"Map manager status changed: {status}")
            self.last_status = status

    def write_nav2_map(self, msg, map_dir: Path):
        width = msg.info.width
        height = msg.info.height
        data = list(msg.data)
        image_path = map_dir / "map.pgm"
        yaml_path = map_dir / "map.yaml"

        with image_path.open("wb") as handle:
            handle.write(f"P5\n{width} {height}\n255\n".encode("ascii"))
            for row in range(height - 1, -1, -1):
                for col in range(width):
                    value = data[row * width + col]
                    if value < 0:
                        pixel = 205
                    elif value >= 65:
                        pixel = 0
                    else:
                        pixel = 254
                    handle.write(bytes([pixel]))

        yaml_data = {
            "image": "map.pgm",
            "resolution": float(msg.info.resolution),
            "origin": [
                float(msg.info.origin.position.x),
                float(msg.info.origin.position.y),
                0.0,
            ],
            "negate": 0,
            "occupied_thresh": 0.65,
            "free_thresh": 0.25,
            "mode": "trinary",
        }
        with yaml_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(yaml_data, handle, sort_keys=False)

    def write_pointcloud_snapshot(
        self, msg: PointCloud2, map_dir: Path, topic_name: str | None
    ) -> dict:
        pcd_path = map_dir / "pointcloud_map_3d.pcd"
        x_field = next((field for field in msg.fields if field.name == "x"), None)
        y_field = next((field for field in msg.fields if field.name == "y"), None)
        z_field = next((field for field in msg.fields if field.name == "z"), None)
        if x_field is None or y_field is None or z_field is None:
            raise RuntimeError("pointcloud missing x/y/z fields")
        if x_field.datatype != 7 or y_field.datatype != 7 or z_field.datatype != 7:
            raise RuntimeError(
                "only FLOAT32 x/y/z pointclouds are supported for snapshot export"
            )

        total_points = int(msg.width) * int(msg.height)
        if total_points <= 0:
            raise RuntimeError("pointcloud contains no points")

        sample_stride = max(
            1, int(math.ceil(total_points / max(1, self.pointcloud_max_points)))
        )
        endian = ">" if msg.is_bigendian else "<"
        unpack_float = struct.Struct(f"{endian}f").unpack_from
        valid_points = []
        raw = memoryview(msg.data)

        for point_index in range(0, total_points, sample_stride):
            base = point_index * msg.point_step
            x = unpack_float(raw, base + x_field.offset)[0]
            y = unpack_float(raw, base + y_field.offset)[0]
            z = unpack_float(raw, base + z_field.offset)[0]
            if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
                continue
            valid_points.append((x, y, z))

        with pcd_path.open("w", encoding="ascii") as handle:
            handle.write("# .PCD v0.7 - Point Cloud Data file format\n")
            handle.write("VERSION 0.7\n")
            handle.write("FIELDS x y z\n")
            handle.write("SIZE 4 4 4\n")
            handle.write("TYPE F F F\n")
            handle.write("COUNT 1 1 1\n")
            handle.write(f"WIDTH {len(valid_points)}\n")
            handle.write("HEIGHT 1\n")
            handle.write("VIEWPOINT 0 0 0 1 0 0 0\n")
            handle.write(f"POINTS {len(valid_points)}\n")
            handle.write("DATA ascii\n")
            for x, y, z in valid_points:
                handle.write(f"{x:.6f} {y:.6f} {z:.6f}\n")

        stamp = msg.header.stamp
        return {
            "kind": "pointcloud_snapshot_3d",
            "topic": topic_name,
            "path": pcd_path.name,
            "frame_id": msg.header.frame_id,
            "stamp_sec": int(stamp.sec),
            "stamp_nanosec": int(stamp.nanosec),
            "points_total": total_points,
            "points_saved": len(valid_points),
            "sample_stride": sample_stride,
        }


def main():
    rclpy.init()
    node = MapManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
