# A2 Host-Side Delivery V3

This document is the engineering delivery companion for the ROS 2 workspace at `/home/dell/a2_system_ws`.

## Current Baseline

- Real robot only
- Front-LiDAR-first
- AMCL is the default real localization mode for Nav2
- JT128 plus DLIO is the current 3D mapping path
- PCD save/load plus 3D relocalization is the current 3D navigation path
- Gazebo, mock, and MID360 legacy workflows are no longer part of the active runtime surface

## Current Module Split

- `a2_sdk_bridge`: A2 SDK state ingress
- `a2_state_publisher`: normalized robot state, odom, and body TF
- `sensor_sync`: IMU and pointcloud freshness checks plus pointcloud projection helpers
- `tf_manager`: static TF publication
- `slam_manager`: SLAM readiness and backend orchestration
- `map_manager`: 2D and 3D map artifact save/load/list/promote boundary
- `localization_manager`: AMCL gate and 3D relocalization gate
- `nav2_integration`: Nav2 action bridge and 3D goal bridge
- `a2_control_bridge`: `/cmd_vel` to robot motion
- `safety_manager`: readiness gating, estop, and aggregate status
- `exploration_manager`: exploration goal production

## Current Entrypoints

- `bringup.launch.py`: real stack bringup
- `dlio_mapping.launch.py`: JT128 plus DLIO mapping
- `jt128_3d_navigation.launch.py`: PCD load plus 3D relocalization plus local pose control
- `scan_mission.launch.py`: route-based scan mission

## Canonical Docs

For current operation and contracts, use these files as the source of truth:

- `architecture.md`
- `interface_contracts.md`
- `operations_runbook.md`
- `scan_mission.md`
