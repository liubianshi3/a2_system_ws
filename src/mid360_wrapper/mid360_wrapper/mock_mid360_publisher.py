#!/usr/bin/env python3

import math

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Header


class MockMid360Publisher(Node):
    def __init__(self):
        super().__init__("mock_mid360_publisher")
        self.frame_id = self.declare_parameter("frame_id", "lidar_link").value
        self.topic = self.declare_parameter("pointcloud_topic", "/mid360/points").value
        self.odom_topic = self.declare_parameter("odom_topic", "/odom").value
        self.publish_rate_hz = float(self.declare_parameter("publish_rate_hz", 10.0).value)
        self.range_m = float(self.declare_parameter("range_m", 14.0).value)
        self.wall_size = float(self.declare_parameter("wall_size", 22.0).value)
        self.lidar_offset_xyz = [
            float(value)
            for value in self.declare_parameter("lidar_offset_xyz", [0.32, 0.0, 0.24]).value
        ]
        self.base_pose = (0.0, 0.0, 0.0)
        self.world_points = self.build_world()
        self.publisher = self.create_publisher(PointCloud2, self.topic, 10)
        self.create_subscription(Odometry, self.odom_topic, self.on_odom, 20)
        self.timer = self.create_timer(1.0 / max(self.publish_rate_hz, 1.0), self.publish_cloud)

    def build_world(self):
        points = []
        half = self.wall_size * 0.5
        wall_step = 0.4
        z_levels = [z * 0.25 for z in range(-1, 9)]

        x = -half
        while x <= half:
            for z in z_levels:
                points.append((x, -half, z))
                points.append((x, half, z))
            x += wall_step

        y = -half
        while y <= half:
            for z in z_levels:
                points.append((-half, y, z))
                points.append((half, y, z))
            y += wall_step

        pillars = [(-4.0, -2.0), (3.0, 5.0), (2.0, -5.0), (-5.0, 4.0)]
        pillar_radius = 0.45
        for center_x, center_y in pillars:
            for degree in range(0, 360, 10):
                angle = math.radians(degree)
                point_x = center_x + pillar_radius * math.cos(angle)
                point_y = center_y + pillar_radius * math.sin(angle)
                for z in [0.0, 0.4, 0.8, 1.2, 1.6]:
                    points.append((point_x, point_y, z))

        for index in range(35):
            points.append((-2.5 + index * 0.2, -7.0 + index * 0.15, index * 0.03))

        return points

    def on_odom(self, msg):
        x = float(msg.pose.pose.position.x)
        y = float(msg.pose.pose.position.y)
        q = msg.pose.pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        self.base_pose = (x, y, yaw)

    def publish_cloud(self):
        stamp = self.get_clock().now().to_msg()
        points = []

        base_x, base_y, base_yaw = self.base_pose
        offset_x, offset_y, offset_z = self.lidar_offset_xyz
        cos_yaw = math.cos(base_yaw)
        sin_yaw = math.sin(base_yaw)
        lidar_x = base_x + cos_yaw * offset_x - sin_yaw * offset_y
        lidar_y = base_y + sin_yaw * offset_x + cos_yaw * offset_y
        lidar_z = offset_z

        for world_x, world_y, world_z in self.world_points:
            dx = world_x - lidar_x
            dy = world_y - lidar_y
            local_x = cos_yaw * dx + sin_yaw * dy
            local_y = -sin_yaw * dx + cos_yaw * dy
            local_z = world_z - lidar_z
            distance = math.sqrt(local_x * local_x + local_y * local_y + local_z * local_z)
            if distance > self.range_m or distance < 0.3:
                continue
            points.append((local_x, local_y, local_z))

        cloud = point_cloud2.create_cloud_xyz32(
            header=Header(stamp=stamp, frame_id=self.frame_id),
            points=points,
        )
        self.publisher.publish(cloud)


def main():
    rclpy.init()
    node = MockMid360Publisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
