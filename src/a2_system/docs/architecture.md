# A2 System Architecture

This workspace is organized around a host-only ROS 2 deployment for Unitree A2 with MID360, mock/real mode parity, and a Nav2-facing interface boundary.

## Main data path

1. `a2_sdk_bridge` resolves the network interface, subscribes to A2 sport state through SDK2, and publishes `/a2/raw_state`.
2. `a2_state_publisher` normalizes `/a2/raw_state` into `/imu/data`, `/odom`, `/robot_state`, and optional `/joint_states`.
3. `mid360_wrapper` publishes `/mid360/points` from a mock source or external Livox/MID360 driver.
4. `sensor_sync` and `safety_manager` watch sensor freshness and publish `/a2/allow_motion`, `/a2/map_ready`, and `/a2/estop`.
5. `slam_manager` and `localization_manager` feed mapping and localization outputs for Nav2.
6. `nav2_integration` consumes exploration goals and forwards them to Nav2.
7. `a2_control_bridge` converts `/cmd_vel` into Unitree A2 sport commands with saturation, timeout stop, and motion gating.

## Mode split

- `mock`: all sources are synthesized on the host so interfaces, launch flow, services, and safety gating can be debugged before the robot is connected.
- `real`: the same ROS topics stay stable while only the source adapters switch to SDK2 and the real MID360 driver.
