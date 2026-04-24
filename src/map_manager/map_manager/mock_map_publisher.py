#!/usr/bin/env python3

import math

import rclpy
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.node import Node


class MockMapPublisher(Node):
    def __init__(self):
        super().__init__("mock_map_publisher")
        self.topic = self.declare_parameter("map_topic", "/map").value
        self.frame_id = self.declare_parameter("frame_id", "map").value
        self.width = int(self.declare_parameter("width", 120).value)
        self.height = int(self.declare_parameter("height", 120).value)
        self.resolution = float(self.declare_parameter("resolution", 0.1).value)
        self.publish_rate_hz = float(self.declare_parameter("publish_rate_hz", 1.0).value)
        self.reveal_radius_m = float(self.declare_parameter("reveal_radius_m", 1.1).value)
        self.odom_topic = self.declare_parameter("odom_topic", "/odom").value
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.publisher = self.create_publisher(OccupancyGrid, self.topic, 5)
        self.create_subscription(Odometry, self.odom_topic, self.on_odom, 20)
        self.create_timer(1.0 / max(self.publish_rate_hz, 1.0), self.publish_map)

    def on_odom(self, msg):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y

    def cell_index(self, x, y):
        return y * self.width + x

    def cell_world(self, x, y):
        origin_x = -self.width * self.resolution / 2.0
        origin_y = -self.height * self.resolution / 2.0
        return (
            origin_x + (x + 0.5) * self.resolution,
            origin_y + (y + 0.5) * self.resolution,
        )

    def is_wall(self, x, y):
        return x in (0, self.width - 1) or y in (0, self.height - 1)

    def is_obstacle(self, x, y):
        wx, wy = self.cell_world(x, y)
        boxes = [
            (-1.0, -0.4, 1.0, 0.4),
            (1.8, 2.8, -2.2, -1.0),
            (-3.0, -2.0, 2.0, 3.2),
        ]
        for min_x, max_x, min_y, max_y in boxes:
            if min_x <= wx <= max_x and min_y <= wy <= max_y:
                return True
        corridor = abs(wx) < 0.15 and wy > -4.5 and wy < 4.5
        return corridor and abs(wy) > 0.9

    def publish_map(self):
        grid = OccupancyGrid()
        grid.header.stamp = self.get_clock().now().to_msg()
        grid.header.frame_id = self.frame_id
        grid.info.resolution = self.resolution
        grid.info.width = self.width
        grid.info.height = self.height
        grid.info.origin.position.x = -self.width * self.resolution / 2.0
        grid.info.origin.position.y = -self.height * self.resolution / 2.0
        grid.info.origin.orientation.w = 1.0
        data = [-1] * (self.width * self.height)

        for y in range(self.height):
            for x in range(self.width):
                index = self.cell_index(x, y)
                if self.is_wall(x, y) or self.is_obstacle(x, y):
                    data[index] = 100

                wx, wy = self.cell_world(x, y)
                distance = math.hypot(wx - self.robot_x, wy - self.robot_y)
                if distance <= self.reveal_radius_m and data[index] != 100:
                    data[index] = 0

        start_cx = self.width // 2
        start_cy = self.height // 2
        for y in range(start_cy - 4, start_cy + 5):
            for x in range(start_cx - 4, start_cx + 5):
                index = self.cell_index(x, y)
                if 0 <= x < self.width and 0 <= y < self.height and data[index] != 100:
                    data[index] = 0

        grid.data = data
        self.publisher.publish(grid)


def main():
    rclpy.init()
    node = MockMapPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
