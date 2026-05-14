#!/usr/bin/env python3
"""DLIO-synchronized cloud gate and OctoMap saver.

octomap_server owns the OcTree insertion. This node keeps the A2-specific policy:
only point clouds with a nearby DLIO odometry timestamp are forwarded, and the
running OctoMap is periodically persisted through octomap_saver_node.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque

import rclpy
from builtin_interfaces.msg import Time
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import PointCloud2


def _stamp_to_sec(stamp: Time) -> float:
    return float(stamp.sec) + float(stamp.nanosec) * 1.0e-9


class OctomapMappingNode(Node):
    def __init__(self) -> None:
        super().__init__("octomap_mapping_node")

        self.odom_topic = str(self.declare_parameter("odom_topic", "/jt128/dlio/odom").value)
        self.cloud_topic = str(self.declare_parameter("cloud_topic", "/jt128/front/points").value)
        self.filtered_cloud_topic = str(
            self.declare_parameter("filtered_cloud_topic", "/a2/octomap/cloud_in").value
        )
        self.max_stamp_delta_sec = float(self.declare_parameter("max_stamp_delta_sec", 0.010).value)
        self.odom_cache_sec = float(self.declare_parameter("odom_cache_sec", 2.0).value)
        self.save_path = str(self.declare_parameter("save_path", "").value)
        self.save_period_sec = float(self.declare_parameter("save_period_sec", 30.0).value)
        self.save_on_shutdown = bool(self.declare_parameter("save_on_shutdown", True).value)

        qos = QoSProfile(
            depth=20,
            history=HistoryPolicy.KEEP_LAST,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.odom_stamps: Deque[float] = deque()
        self.forwarded_clouds = 0
        self.dropped_clouds = 0
        self.last_save_time = 0.0
        self._saving = False
        self._lock = threading.Lock()

        self.cloud_pub = self.create_publisher(PointCloud2, self.filtered_cloud_topic, qos)
        self.create_subscription(Odometry, self.odom_topic, self._on_odom, qos)
        self.create_subscription(PointCloud2, self.cloud_topic, self._on_cloud, qos)

        if self.save_path and self.save_period_sec > 0.0:
            self.create_timer(self.save_period_sec, self._save_timer)

        self.create_timer(5.0, self._status_timer)
        self.get_logger().info(
            "OctoMap cloud gate: cloud=%s odom=%s out=%s max_delta=%.3fs save=%s"
            % (
                self.cloud_topic,
                self.odom_topic,
                self.filtered_cloud_topic,
                self.max_stamp_delta_sec,
                self.save_path or "disabled",
            )
        )

    def _on_odom(self, msg: Odometry) -> None:
        stamp = _stamp_to_sec(msg.header.stamp)
        self.odom_stamps.append(stamp)
        cutoff = stamp - self.odom_cache_sec
        while self.odom_stamps and self.odom_stamps[0] < cutoff:
            self.odom_stamps.popleft()

    def _nearest_odom_delta(self, stamp: float) -> float | None:
        if not self.odom_stamps:
            return None
        return min(abs(stamp - odom_stamp) for odom_stamp in self.odom_stamps)

    def _on_cloud(self, msg: PointCloud2) -> None:
        stamp = _stamp_to_sec(msg.header.stamp)
        delta = self._nearest_odom_delta(stamp)
        if delta is None or delta > self.max_stamp_delta_sec:
            self.dropped_clouds += 1
            if self.dropped_clouds <= 5 or self.dropped_clouds % 100 == 0:
                reason = "no_odom" if delta is None else f"delta={delta:.4f}s"
                self.get_logger().warn(f"Dropping OctoMap cloud: {reason}")
            return
        self.cloud_pub.publish(msg)
        self.forwarded_clouds += 1

    def _status_timer(self) -> None:
        self.get_logger().info(
            "OctoMap gate stats: forwarded=%d dropped=%d odom_cache=%d"
            % (self.forwarded_clouds, self.dropped_clouds, len(self.odom_stamps))
        )

    def _save_timer(self) -> None:
        self.save_octomap_async()

    def save_octomap_async(self) -> None:
        if not self.save_path:
            return
        with self._lock:
            if self._saving:
                return
            self._saving = True
        thread = threading.Thread(target=self._save_octomap, daemon=True)
        thread.start()

    def _save_octomap(self) -> None:
        try:
            save_path = Path(self.save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = save_path.with_name(save_path.stem + ".tmp" + save_path.suffix)
            cmd = [
                "ros2",
                "run",
                "octomap_server",
                "octomap_saver_node",
                "--ros-args",
                "-p",
                f"octomap_path:={tmp_path}",
            ]
            start = time.monotonic()
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=20)
            if result.returncode != 0:
                self.get_logger().warn(
                    "octomap_saver_node failed rc=%d output=%s"
                    % (result.returncode, result.stdout.strip())
                )
                return
            if not tmp_path.exists():
                self.get_logger().warn(
                    "octomap_saver_node did not create %s output=%s"
                    % (tmp_path, result.stdout.strip())
                )
                return
            os.replace(tmp_path, save_path)
            self.last_save_time = time.monotonic()
            self.get_logger().info(
                "Saved OctoMap to %s in %.1fs" % (save_path, time.monotonic() - start)
            )
        except subprocess.TimeoutExpired:
            self.get_logger().warn("Timed out while saving OctoMap")
        except Exception as exc:
            self.get_logger().warn(f"Failed to save OctoMap: {exc}")
        finally:
            with self._lock:
                self._saving = False

    def destroy_node(self) -> bool:
        if self.save_on_shutdown and self.save_path:
            self._save_octomap()
        return super().destroy_node()


def main() -> None:
    rclpy.init()
    node = OctomapMappingNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
