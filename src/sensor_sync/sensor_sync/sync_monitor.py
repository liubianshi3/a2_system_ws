#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu, PointCloud2
from std_msgs.msg import Bool, String


class SyncMonitor(Node):
    def __init__(self):
        super().__init__("sync_monitor")
        self.use_mock = bool(self.declare_parameter("use_mock", True).value)
        self.runtime_mode = self.declare_parameter(
            "runtime_mode", "mock" if self.use_mock else "real"
        ).value
        imu_topic = self.declare_parameter("imu_topic", "/imu/data").value
        pointcloud_topic = self.declare_parameter("pointcloud_topic", "/mid360/points").value
        self.status_report_topic = self.declare_parameter(
            "status_report_topic", "/a2/sensor_sync/status"
        ).value
        self.max_age_sec = float(self.declare_parameter("max_age_sec", 0.25).value)
        self.warn_skew_sec = float(self.declare_parameter("warn_skew_sec", 0.05).value)
        self.ignore_skew_in_mock = bool(self.declare_parameter("ignore_skew_in_mock", True).value)
        self.ignore_skew_in_simulated = bool(
            self.declare_parameter("ignore_skew_in_simulated", self.ignore_skew_in_mock).value
        )

        self.last_imu_stamp = None
        self.last_cloud_stamp = None
        self.status_pub = self.create_publisher(Bool, "/a2/sensor_sync/ok", 10)
        self.status_report_pub = self.create_publisher(String, self.status_report_topic, 10)
        self.last_status_text = ""

        self.create_subscription(Imu, imu_topic, self.on_imu, 20)
        self.create_subscription(PointCloud2, pointcloud_topic, self.on_cloud, 10)
        self.create_timer(0.5, self.check_status)

    def on_imu(self, msg):
        self.last_imu_stamp = rclpy.time.Time.from_msg(msg.header.stamp)

    def on_cloud(self, msg):
        self.last_cloud_stamp = rclpy.time.Time.from_msg(msg.header.stamp)

    def check_status(self):
        now = self.get_clock().now()
        imu_ok = self.last_imu_stamp is not None and (now - self.last_imu_stamp).nanoseconds * 1e-9 <= self.max_age_sec
        cloud_ok = self.last_cloud_stamp is not None and (now - self.last_cloud_stamp).nanoseconds * 1e-9 <= self.max_age_sec
        skew_ok = True
        skew = 0.0
        if self.last_imu_stamp is not None and self.last_cloud_stamp is not None:
            skew = abs((self.last_imu_stamp - self.last_cloud_stamp).nanoseconds) * 1e-9
            if self.runtime_mode == "mock" and self.ignore_skew_in_mock:
                skew_ok = True
            elif self.runtime_mode != "real" and self.ignore_skew_in_simulated:
                skew_ok = True
            else:
                skew_ok = skew <= self.warn_skew_sec
            if not skew_ok:
                self.get_logger().warn(f"IMU / point cloud skew too large: {skew:.3f}s")
        ready = imu_ok and cloud_ok and skew_ok
        self.status_pub.publish(Bool(data=ready))

        reason = "ok"
        state = "ready"
        if not imu_ok and not cloud_ok:
            state = "waiting_inputs"
            reason = "imu_stale,pointcloud_stale"
        elif not imu_ok:
            state = "imu_stale"
            reason = "imu_stale"
        elif not cloud_ok:
            state = "pointcloud_stale"
            reason = "pointcloud_stale"
        elif not skew_ok:
            state = "skew_too_large"
            reason = f"skew={skew:.3f}s"
        self.publish_status(ready, state, reason)

    def publish_status(self, ready, state, reason):
        mode = self.runtime_mode
        status = f"mode={mode};state={state};ready={str(bool(ready)).lower()};reason={reason}"
        self.status_report_pub.publish(String(data=status))
        if status != self.last_status_text:
            self.get_logger().info(f"Sensor sync status changed: {status}")
            self.last_status_text = status


def main():
    rclpy.init()
    node = SyncMonitor()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
