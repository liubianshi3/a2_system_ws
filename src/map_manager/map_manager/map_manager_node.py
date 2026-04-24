#!/usr/bin/env python3

import os
from datetime import datetime
from pathlib import Path

import rclpy
import yaml
from a2_interfaces.srv import ManageMap, SetMode
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String


class MapManagerNode(Node):
    def __init__(self):
        super().__init__("map_manager")
        self.use_mock = bool(self.declare_parameter("use_mock", True).value)
        self.runtime_mode = self.declare_parameter(
            "runtime_mode", "mock" if self.use_mock else "real"
        ).value
        raw_map_root = self.declare_parameter("map_root", "/tmp/a2_maps").value
        self.map_root = Path(os.path.expandvars(os.path.expanduser(raw_map_root)))
        self.occupancy_topic = self.declare_parameter("occupancy_topic", "/map").value
        self.active_map_topic = self.declare_parameter("active_map_topic", "/a2/map_manager/active_map").value
        self.mode_topic = self.declare_parameter("mode_topic", "/a2/system_mode").value
        self.status_topic = self.declare_parameter("status_topic", "/a2/map_manager/status").value
        self.current_mode = self.declare_parameter("default_mode", "mapping").value
        self.map_transient_local = bool(
            self.declare_parameter("map_transient_local", False).value
        )
        self.latest_map = None
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
        self.create_subscription(OccupancyGrid, self.occupancy_topic, self.on_map, map_qos)
        self.create_service(ManageMap, "/map_manager/manage_map", self.handle_manage_map)
        self.create_service(SetMode, "/map_manager/set_mode", self.handle_set_mode)
        self.publish_mode()
        self.publish_status("idle", "startup")

    def on_map(self, msg):
        first_map = self.latest_map is None
        self.latest_map = msg
        if first_map:
            self.publish_status("ready", "map_received")

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
            if self.latest_map is None:
                response.success = False
                response.message = "no occupancy grid received yet"
                self.publish_status("error", "no_occupancy_grid")
                return response
            map_id = request.map_id or datetime.now().strftime("map_%Y%m%d_%H%M%S")
            map_dir = self.map_root / map_id
            map_dir.mkdir(parents=True, exist_ok=True)
            self.write_nav2_map(self.latest_map, map_dir)
            metadata = {
                "created_at": datetime.now().isoformat(),
                "mode": self.current_mode,
                "width": self.latest_map.info.width,
                "height": self.latest_map.info.height,
                "resolution": self.latest_map.info.resolution,
            }
            with (map_dir / "metadata.yaml").open("w", encoding="utf-8") as handle:
                yaml.safe_dump(metadata, handle, sort_keys=False)
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

    def publish_status(self, state, reason):
        mode = self.runtime_mode
        ready = self.latest_map is not None
        status = (
            f"mode={mode};state={state};ready={str(bool(ready)).lower()};reason={reason};"
            f"system_mode={self.current_mode};active_map={self.active_map_id or 'none'}"
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


def main():
    rclpy.init()
    node = MapManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
