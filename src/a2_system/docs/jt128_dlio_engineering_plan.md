# A2 JT128 + DLIO 3D Mapping and Navigation Migration Plan

## 0. Scope and Verified Facts

This document is the engineering plan for replacing the current A2 mapping and localization LiDAR chain with the front Hesai JT128. The first deliverable is not full autonomous 3D navigation. The first deliverable is:

```text
front JT128 -> official Hesai ROS2 driver -> JT128 point cloud + JT128 IMU -> DLIO -> 3D PCD map save
```

The plan supports only:

- Real A2 robot.
- Rosbag/offline playback.

It intentionally drops:

- Simulation mode.
- Mock LiDAR.
- MID360 as primary input.
- `pointcloud_to_laserscan`, `slam_toolbox`, `AMCL`, and 2D `OccupancyGrid` as the core truth path.

Verified on `unitree-a2-pc2` on 2026-04-29:

| Item | Value |
| --- | --- |
| ROS distro | Humble |
| Robot host | `unitree-a2-pc2` |
| Robot Wi-Fi IP | `192.168.31.49` |
| Control interface | `eth0`, `192.168.123.162/24` |
| JT128 sensor interface | `net1`, `192.168.124.162/24` |
| Front JT128 IP | `192.168.124.20` |
| Front JT128 UDP point port | `2368` |
| Front JT128 PTC port | `9347` |
| Current native point topic | `/unitree/slam_lidar/points1` |
| Current native IMU topic | `/unitree/slam_lidar/imu1` |
| Current point frame | `hesai_lidar` |
| Point fields | `x`, `y`, `z`, `intensity`, `ring`, `timestamp` |
| Rear LiDAR | not part of Phase 1 |
| Native service currently active | `unitree_slam.service` |
| Native driver package after graph workspace source | `hesai_ros_driver` |
| DLIO package | not installed |
| FAST-LIO2 source | present under `src/third_party/FAST_LIO` |

Important network correction:

```text
192.168.124.20 dev net1 src 192.168.124.162
```

The JT128 path is on `net1`, not `eth0`. `eth0` is still relevant for Unitree SDK/control traffic.

## 1. System Fusion Architecture

### 1.1 Current System to Preserve at the Robot-Control Layer

The following modules should remain because they are not the root cause of the mapping precision problem:

| Module | Keep? | Reason |
| --- | --- | --- |
| `a2_sdk_bridge` | yes | Unitree state ingress stays useful. |
| `a2_state_publisher` | partial | Keep `/robot_state`; remove or gate TF ownership once LIO owns odometry. |
| `a2_control_bridge` | yes | Still converts `/cmd_vel` or future command topic to Unitree motion commands. |
| `safety_manager` | yes | Must be upgraded to watch JT128/DLIO health. |
| `sensor_sync` | yes | Must be upgraded from MID360/2D assumptions to JT128 point+IMU timing. |
| `tf_manager` | yes | Must become the single owner of static extrinsics. |
| `map_manager` | yes | Must support PCD and 3D metadata as first-class map artifacts. |
| `task_manager` | yes | Must call 3D map/navigation contracts instead of Nav2-only assumptions. |
| Web backend/frontend | yes | Must switch from 2D map snapshot to 3D point cloud/map assets. |

### 1.2 Current Modules to Replace as Core Truth

These may remain only as rollback tools or derived compatibility products, not as the primary system:

| Module/path | Replacement direction |
| --- | --- |
| `mid360_wrapper` as primary source | Replace with `jt128_driver` or `jt128_wrapper`. |
| `pointcloud_to_laserscan` | Remove from main chain. |
| `slam_toolbox` | Replace with DLIO mapping first. |
| `AMCL` | Replace with 3D scan-to-map relocalization after PCD mapping. |
| `nav2_stack.yaml` `map_server/amcl` path | Not used as 3D truth path. |
| `occupancy_mapper` | Derived visualization/export only if needed. |
| `auto_scan_mission` map validation against `OccupancyGrid` | Replace with 3D coverage/reachability contracts. |
| Web `MapCanvas` 2D-only view | Replace with 3D point cloud viewer. |

### 1.3 Target Architecture

Mapping mode:

```text
JT128 Ethernet packets
  -> HesaiLidar_ROS_2.0
  -> /jt128/front/points        sensor_msgs/PointCloud2
  -> /jt128/front/imu           sensor_msgs/Imu
  -> tf_manager                 base_link -> jt128_front_link, base_link -> jt128_imu_link
  -> DLIO
  -> /jt128/dlio/odom           nav_msgs/Odometry
  -> /jt128/dlio/path           nav_msgs/Path
  -> /jt128/dlio/map_points     sensor_msgs/PointCloud2
  -> map_manager
  -> runtime/maps/<map_id>/pointcloud_map_3d.pcd
  -> runtime/maps/<map_id>/metadata.yaml
  -> Web 3D viewer
```

Navigation mode after mapping:

```text
saved PCD map
  -> 3D localization node, initially NDT/ICP scan-to-map
  -> map -> odom transform
  -> current JT128 points + LIO odom
  -> 3D local obstacle model
  -> 3D-first planner/controller or validated Unitree native goal bridge
  -> /cmd_vel or /goal_pose_
  -> a2_control_bridge / Unitree motion command
```

Compatibility exports allowed:

- `/map` as a derived 2D slice for temporary display or fallback only.
- `/scan` as a diagnostic projection only.
- Nav2 goal adapter only if explicitly marked as compatibility.

Compatibility exports not allowed as primary truth:

- `/scan -> slam_toolbox -> /map`
- `/map + /scan + /odom -> AMCL`
- Web-only 2D map as the authoritative map.

## 2. ROS2 Topic Unification

The new naming should be JT128-style, not MID360-style.

| Contract | Topic | Message | Owner |
| --- | --- | --- | --- |
| Raw front packets | `/jt128/front/packets` | driver packet msg | Hesai driver |
| Front point cloud | `/jt128/front/points` | `sensor_msgs/PointCloud2` | Hesai driver |
| Front LiDAR IMU | `/jt128/front/imu` | `sensor_msgs/Imu` | Hesai driver |
| LIO odometry | `/jt128/dlio/odom` | `nav_msgs/Odometry` | DLIO |
| LIO path | `/jt128/dlio/path` | `nav_msgs/Path` | DLIO |
| Live 3D map | `/jt128/dlio/map_points` | `sensor_msgs/PointCloud2` | DLIO or map publisher |
| Saved/managed 3D map preview | `/a2/map/pointcloud_3d` | `sensor_msgs/PointCloud2` | `map_manager` |
| Current robot pose | `/a2/localization/pose_3d` | `geometry_msgs/PoseWithCovarianceStamped` | 3D localization |
| Localization status | `/a2/localization/status` | `std_msgs/String` | localization gate |
| Mapping status | `/a2/mapping/status` | `std_msgs/String` | DLIO wrapper/map manager |
| Map manager status | `/a2/map_manager/status` | `std_msgs/String` | `map_manager` |
| Control command | `/cmd_vel` | `geometry_msgs/Twist` | planner/controller |
| 3D goal | `/a2/goal_pose_3d` | `geometry_msgs/PoseStamped` | Web/task manager |
| Unitree native goal adapter | `/goal_pose_` | `geometry_msgs/PoseStamped` | bridge only |
| Safety allow | `/a2/allow_motion` | `std_msgs/Bool` | safety manager |

Temporary aliases during transition:

| Current | New canonical |
| --- | --- |
| `/unitree/slam_lidar/points1` | `/jt128/front/points` |
| `/unitree/slam_lidar/imu1` | `/jt128/front/imu` |
| `/a2/pointcloud_map_3d` | `/a2/map/pointcloud_3d` |

The alias should be implemented in launch/remap first, then removed once the official driver is validated.

## 3. TF Design

### 3.1 Target Frames

| Frame | Meaning |
| --- | --- |
| `map` | Global map frame, fixed to saved PCD map in navigation mode. |
| `odom` | Continuous local odometry frame. |
| `base_link` | Robot body reference frame. |
| `base_footprint` | Optional planar footprint for compatibility. |
| `jt128_front_link` | Front JT128 point cloud frame. |
| `jt128_front_imu_link` | Front JT128 internal IMU frame if distinct. |
| `camera_link` | Optional camera frame. |

### 3.2 TF Ownership

| Transform | Owner | Notes |
| --- | --- | --- |
| `map -> odom` | 3D localization node | In mapping mode may be identity or absent. In navigation mode must be scan-to-map owner. |
| `odom -> base_link` | DLIO/LIO odometry | `a2_state_publisher` must not publish the same dynamic TF once DLIO owns it. |
| `base_link -> base_footprint` | `tf_manager` | Static or derived, no duplicate publisher. |
| `base_link -> jt128_front_link` | `tf_manager` | Must come from official/calibrated extrinsic. |
| `base_link -> jt128_front_imu_link` | `tf_manager` | Use official extrinsic or identity to LiDAR frame only if verified. |
| `base_link -> camera_link` | `tf_manager` | Optional. |

### 3.3 Current Risk

Current `tf_static` on A2 includes:

```text
base_link -> lidar_link: x=0.32, y=0.0, z=0.24, rpy=0,0,0
base_link -> imu_link:   x=0.0,  y=0.0, z=0.0,  rpy=0,0,0
```

This is enough for early visualization, but not enough to claim high-precision LIO. Before DLIO closed-loop testing, create a calibrated file:

```text
src/a2_system/config/jt128_extrinsics.yaml
```

with explicit:

```yaml
jt128_front:
  parent_frame: base_link
  lidar_frame: jt128_front_link
  imu_frame: jt128_front_imu_link
  xyz: [x, y, z]
  rpy: [roll, pitch, yaw]
  source: official_or_calibrated
  validated_at: ""
```

## 4. JT128 Driver Integration with HesaiLidar_ROS_2.0

### 4.1 Current Native Driver Reference

Unitree currently runs a packaged `hesai_ros_driver_node` through:

```text
/home/unitree/graph_pid_ws/bin/tools/service/launch_slam.sh
```

and config:

```text
/home/unitree/graph_pid_ws/config_files/hs_lidar_jt128/config.yaml
```

Relevant verified config:

```yaml
device_ip_address: 192.168.124.20
udp_port: 2368
is_use_ptc: true
ptc_port: 9347
multicast_ip_address: ""
ros_frame_id: hesai_lidar
ros_send_packet_topic: /lidar_packets1
ros_send_point_cloud_topic: /unitree/slam_lidar/points1
ros_send_imu_topic: /unitree/slam_lidar/imu1
send_packet_ros: true
send_point_cloud_ros: true
```

This is useful as a reference, but the target stack should not depend on `unitree_slam.service` because that service also starts:

- `navigation_mapping.py`
- `dwa_obstacle_avoidance.py`
- `point_cloud_fusion`
- `unitree_slam`

Those are interference for our final JT128 + DLIO chain.

### 4.2 Target Driver Config

Create a dedicated config:

```text
src/a2_system/config/jt128_front_hesai.yaml
```

Target output:

```yaml
lidar:
  - driver:
      source_type: 1
      device_ip_address: 192.168.124.20
      udp_port: 2368
      is_use_ptc: true
      ptc_port: 9347
      multicast_ip_address: ""
      use_timestamp_type: 0
      transform_flag: false
    ros:
      ros_frame_id: jt128_front_link
      ros_send_packet_topic: /jt128/front/packets
      ros_send_point_cloud_topic: /jt128/front/points
      ros_send_imu_topic: /jt128/front/imu
      send_packet_ros: true
      send_point_cloud_ros: true
      send_imu_ros: true
```

Driver launch requirements:

- Source `/home/unitree/graph_pid_ws/install/setup.bash` if using Unitree packaged driver initially.
- Later vendor or install official `HesaiLidar_ROS_2.0` explicitly under a controlled workspace.
- Bind runtime to `net1`, not `eth0`, for JT128 traffic.
- Increase socket buffer:

```bash
sudo sysctl -w net.core.rmem_max=2147483647
```

### 4.3 Driver Validation

Acceptance commands:

```bash
source /opt/ros/humble/setup.bash
source ~/a2_system_ws/install/setup.bash

ros2 topic info /jt128/front/points
ros2 topic info /jt128/front/imu
timeout 10s ros2 topic hz /jt128/front/points
timeout 10s ros2 topic hz /jt128/front/imu
timeout 5s ros2 topic echo --once /jt128/front/points
timeout 5s ros2 topic echo --once /jt128/front/imu
```

Pass criteria:

- `/jt128/front/points` has one publisher.
- `/jt128/front/imu` has one publisher.
- Point cloud frame is `jt128_front_link`.
- Fields include `x`, `y`, `z`, `intensity`, `ring`, `timestamp`.
- No native Unitree navigation helper is running.
- No duplicate Hesai node name.

## 5. DLIO Integration

### 5.1 Recommended Route

Use DLIO as the first LIO mapping implementation because the target is a 3D LiDAR + IMU mapping pipeline and JT128 point cloud already has per-point timing fields.

Add DLIO under one of:

```text
src/third_party/direct_lidar_inertial_odometry/
```

or as an external overlay:

```text
~/dlio_ws
```

For industrial maintainability, prefer vendored source or a pinned git submodule with commit hash recorded in:

```text
src/a2_system/docs/dependency_versions.md
```

### 5.2 DLIO Input Contract

| DLIO input | A2 topic |
| --- | --- |
| point cloud | `/jt128/front/points` |
| IMU | `/jt128/front/imu` |
| base frame | `base_link` |
| LiDAR frame | `jt128_front_link` |
| map frame | `map` |
| odom frame | `odom` |

Expected output:

| DLIO output | A2 topic |
| --- | --- |
| odometry | `/jt128/dlio/odom` |
| path | `/jt128/dlio/path` |
| map cloud | `/jt128/dlio/map_points` |
| TF | `odom -> base_link` |

### 5.3 DLIO Config Requirements

Create:

```text
src/a2_system/config/dlio_jt128.yaml
```

Must include:

- Point cloud topic.
- IMU topic.
- Frames.
- Extrinsics.
- Voxel/downsample settings.
- IMU noise parameters.
- Motion compensation enabled.
- PCD save path.
- Diagnostics status output.

Do not fake IMU parameters. If official JT128 IMU specs are unavailable, record values as provisional and validate drift on a short-loop dataset.

### 5.4 PCD Saving

DLIO PCD output must be wrapped by `map_manager`, not saved as an unmanaged file.

Required artifact layout:

```text
runtime/maps/<map_id>/
  metadata.yaml
  pointcloud_map_3d.pcd
  trajectory.csv
  dlio_config.yaml
  jt128_driver_config.yaml
  extrinsics.yaml
  validation_report.md
```

`metadata.yaml` minimum:

```yaml
map_id: <map_id>
representation: pointcloud_map_3d
sensor: hesai_jt128_front
pointcloud_topic: /jt128/dlio/map_points
pcd_file: pointcloud_map_3d.pcd
map_frame: map
odom_frame: odom
base_frame: base_link
created_at: ""
software:
  ros_distro: humble
  dlio_commit: ""
  hesai_driver_commit: ""
quality:
  duration_sec: null
  distance_m: null
  final_loop_error_m: null
  warnings: []
```

### 5.5 DLIO Validation

Pass criteria for Phase 2:

- Driver publishes points + IMU for at least 5 minutes.
- DLIO publishes odometry continuously.
- `odom -> base_link` is continuous and does not jump under stationary robot.
- PCD map grows when robot moves.
- PCD can be saved and reloaded.
- Web can display the saved/live 3D map.
- Rosbag recorded during run can replay the same DLIO mapping path offline.

## 6. FAST-LIO2 Backup Plan

FAST-LIO2 is the backup, not the first implementation, because the current local source is present but was originally prepared around Livox/MID360-style configs.

Switch to FAST-LIO2 if:

- DLIO fails to build cleanly on Humble.
- DLIO cannot consume JT128 timestamps/ring fields correctly.
- DLIO shows unacceptable drift with JT128 IMU.
- FAST-LIO2 produces a measurably better PCD on the same rosbag.

FAST-LIO2 JT128 adaptation must check:

| Requirement | JT128 status |
| --- | --- |
| `x/y/z` fields | verified |
| `intensity` | verified |
| `ring` | verified |
| per-point timestamp | verified |
| IMU topic | verified native topic, must validate content/rate |
| LiDAR type support | may need Pandar/JT128 preprocessing adapter |

Create:

```text
src/a2_system/config/fast_lio_jt128.yaml
```

FAST-LIO2 A/B test uses the same bag:

```text
rosbag2: jt128_short_loop_<date>
inputs:
  /jt128/front/points
  /jt128/front/imu
  /tf_static
outputs:
  DLIO PCD
  FAST-LIO2 PCD
metrics:
  visible wall sharpness
  floor/ceiling separation
  loop closure residual if available
  odom drift at end point
  CPU/memory
  dropped messages
```

## 7. Map and Navigation Fusion

### 7.1 Mapping Stage

The mapping stage ends with a 3D PCD and metadata. It does not require Nav2 or AMCL.

Inputs:

- `/jt128/front/points`
- `/jt128/front/imu`
- `base_link -> jt128_front_link`

Outputs:

- `/jt128/dlio/odom`
- `/jt128/dlio/map_points`
- `pointcloud_map_3d.pcd`

### 7.2 Navigation Stage

The target navigation stack must use the PCD map directly:

```text
saved PCD + live JT128 scan -> 3D relocalization -> map -> odom
live JT128 scan + robot pose -> local 3D obstacle model
goal pose -> 3D reachability/planning -> motion command
```

Recommended first 3D localization method:

- NDT or ICP scan-to-map against downsampled PCD.

Reason:

- It is easier to validate than jumping directly to a full 3D global planner.
- It gives a clean replacement for AMCL: a map-frame pose and covariance.

### 7.3 Existing Navigation Bridge During Transition

The current web/task path can temporarily send pose goals through a bridge to `/goal_pose_`, but only after:

- Goal frame is explicit.
- Pose feedback topic is explicit.
- Stop accuracy is measured.
- Failure feedback is captured.
- Safety manager can cancel/stop.

This is not full industrial 3D navigation. It is a transition execution backend.

### 7.4 Local Obstacle Input

For dynamic obstacle avoidance, use live JT128 point cloud directly:

```text
/jt128/front/points -> voxel obstacle layer / 3D local map
```

Do not convert it to `/scan` as the main obstacle source.

If a legacy 2D local costmap is temporarily needed, it must be documented as a derived compatibility layer.

## 8. Engineering Phases

### Phase 1: JT128 Driver Standalone

Goal:

- Run front JT128 official/packaged Hesai ROS2 driver without `unitree_slam.service`.

Inputs:

- `net1`
- JT128 `.20`

Outputs:

- `/jt128/front/points`
- `/jt128/front/imu`

Files:

- `src/a2_system/config/jt128_front_hesai.yaml`
- `src/a2_bringup/launch/jt128_driver.launch.py`
- `src/a2_system/tools/start_jt128_dlio_mapping.sh`

Validation:

- Point cloud and IMU rates stable.
- Correct fields and frames.
- Rosbag record works.
- No native Unitree SLAM/DWA helpers running.

Rollback:

- Stop new driver.
- Restart `unitree_slam.service` only for native debug, not as runtime fallback.

### Phase 2: JT128 + DLIO Mapping

Goal:

- DLIO consumes `/jt128/front/points` and `/jt128/front/imu` and publishes LIO odometry/map.

Outputs:

- `/jt128/dlio/odom`
- `/jt128/dlio/path`
- `/jt128/dlio/map_points`

Files:

- `src/a2_system/config/dlio_jt128.yaml`
- `src/a2_bringup/launch/dlio_mapping.launch.py`
- `src/a2_system/tools/start_jt128_dlio_mapping.sh`

Validation:

- Stationary robot odom does not drift rapidly.
- Slow straight motion creates stable map.
- Short loop returns near start.
- PCD saved through `map_manager`.

Rollback:

- Stop DLIO launch.
- Keep saved bag for replay.

### Phase 3: PCD Save and Map Validation

Goal:

- Make PCD maps managed artifacts.

Files:

- `src/map_manager/map_manager/map_manager_node.py`
- `src/a2_system/config/map_manager.yaml`
- Web backend map APIs.

Validation:

- Save map from Web.
- PCD file exists and has non-zero points.
- Metadata records topic/frame/config.
- Reload publishes `/a2/map/pointcloud_3d`.

Rollback:

- Keep old map directories untouched.

### Phase 4: Connect to Existing Navigation Without Closed-Loop Motion

Goal:

- Load PCD, run localization, show pose in Web, but do not move the robot.

Inputs:

- Saved PCD.
- Live JT128 scan.

Outputs:

- `/a2/localization/pose_3d`
- `map -> odom`
- Web robot marker.

Validation:

- Pose is stable when robot is stationary.
- Moving robot updates pose in correct direction.
- Covariance/status is visible.

Rollback:

- Stop localization node and leave robot motion disabled.

### Phase 5: Closed-Loop Motion

Goal:

- Send short goals in a clear test area.

Inputs:

- `/a2/goal_pose_3d`
- 3D localization pose.
- Safety allow.

Outputs:

- `/cmd_vel` or verified `/goal_pose_` adapter.

Validation:

- Goal result reports final position/yaw error.
- Stop/cancel works.
- `/cmd_vel` timeout zeroing works.
- Estop blocks motion.

Rollback:

- Stop controller.
- Clear `/cmd_vel`.
- Keep estop available.

### Phase 6: Safety, Fallback, and Offline Replay

Goal:

- Industrialize diagnostics and replay.

Validation:

- Point cloud loss stops motion.
- IMU loss stops mapping/localization.
- TF timeout blocks navigation.
- Localization drift blocks goal execution.
- Rosbag replay reproduces mapping.

Note:

- The user requested no legacy fallback in the runtime chain. Rollback here means operational rollback to a known previous startup path, not simultaneous fallback during autonomous operation.

## 9. Safety and Industrial Requirements

Required checks before any motion:

| Risk | Required protection |
| --- | --- |
| Emergency stop | `/a2/estop` must immediately block control bridge. |
| Point cloud loss | No `/jt128/front/points` within timeout -> zero command and unsafe. |
| IMU loss | No `/jt128/front/imu` within timeout -> stop DLIO and unsafe. |
| TF timeout | Missing `map -> odom` or `odom -> base_link` -> navigation blocked. |
| Localization drift | Pose jump/covariance threshold -> navigation blocked. |
| `/cmd_vel` stale | Control bridge zeros command after timeout. |
| Robot abnormal state | SDK fall/fault state -> unsafe. |
| Native interference | `unitree_slam.service`, `navigation_mapping.py`, `dwa_obstacle_avoidance.py`, old AMCL/Nav2 projection stack stopped before JT128 DLIO startup. |
| Logging | Runtime logs under `runtime/logs/`; map validation report under map directory. |
| Rosbag | Standard bag profile records points, IMU, TF, odom, status. |
| Parameter versioning | Save driver/DLIO/extrinsic config with every PCD. |

## 10. Recommended Directory Structure

```text
src/a2_bringup/launch/
  jt128_driver.launch.py
  dlio_mapping.launch.py
  jt128_3d_navigation.launch.py

src/a2_system/config/
  jt128_front_hesai.yaml
  jt128_extrinsics.yaml
  dlio_jt128.yaml
  fast_lio_jt128.yaml
  jt128_rosbag_topics.txt

src/a2_system/tools/
  start_jt128_dlio_mapping.sh
  stop_jt128_stack.sh
  record_jt128_bag.sh
  replay_jt128_bag_dlio.sh

src/map_manager/map_manager/
  pcd_map_manager.py
  pointcloud_map_loader.py

web_console/
  backend: add PCD map list/save/load APIs
  frontend: add 3D point cloud map viewer and robot marker

runtime/maps/<map_id>/
  pointcloud_map_3d.pcd
  metadata.yaml
  trajectory.csv
  validation_report.md
```

## 11. Launch Design

### `jt128_driver.launch.py`

Responsibilities:

- Source/configure Hesai driver.
- Publish `/jt128/front/points`.
- Publish `/jt128/front/imu`.
- Publish driver status.

Must not:

- Start Unitree native SLAM.
- Start DWA.
- Start pointcloud-to-scan.

### `dlio_mapping.launch.py`

Responsibilities:

- Start static TF for JT128 extrinsics.
- Start DLIO.
- Start map manager in `pointcloud_map_3d` mode.
- Start Web 3D live map backend.

### `jt128_3d_navigation.launch.py`

Responsibilities:

- Load saved PCD.
- Start 3D localization.
- Publish `map -> odom`.
- Start safety gates.
- Start goal/control adapter only after localization ready.

## 12. Node Graph

Phase 2 mapping:

```text
[Hesai JT128]
    |
[hesai_ros_driver_node]
    |-- /jt128/front/points
    |-- /jt128/front/imu
    |
[tf_manager] -- /tf_static
    |
[DLIO]
    |-- /jt128/dlio/odom
    |-- /jt128/dlio/path
    |-- /jt128/dlio/map_points
    |
[map_manager]
    |-- /a2/map_manager/status
    |-- runtime/maps/<map_id>/pointcloud_map_3d.pcd
    |
[web_console]
```

Phase 4 navigation without motion:

```text
[saved PCD] + [/jt128/front/points]
    |
[3D localization]
    |-- map -> odom
    |-- /a2/localization/pose_3d
    |
[web_console robot marker]
```

## 13. Test Checklist

Driver:

- `ros2 topic hz /jt128/front/points`
- `ros2 topic hz /jt128/front/imu`
- `ros2 topic echo --once /jt128/front/points`
- Confirm point cloud fields.
- Confirm frame is `jt128_front_link`.

TF:

- `ros2 run tf2_ros tf2_echo base_link jt128_front_link`
- `ros2 run tf2_ros tf2_echo odom base_link`
- No duplicate dynamic TF owners.

DLIO:

- `/jt128/dlio/odom` publisher exists.
- `/jt128/dlio/path` grows.
- `/jt128/dlio/map_points` grows.
- Stationary drift check passes.

Map save:

- PCD saved.
- Metadata saved.
- PCD reload visible in Web.

Offline:

- Record real bag.
- Replay bag.
- DLIO map is reproducible.

Motion later:

- Short goal in clear area.
- Stop/cancel works.
- Final error reported.

## 14. Real-Machine Debug Order

1. Stop interference:

```bash
sudo systemctl stop unitree_slam.service
pkill -f navigation_mapping.py || true
pkill -f dwa_obstacle_avoidance.py || true
pkill -f pointcloud_to_laserscan || true
pkill -f slam_toolbox || true
pkill -f amcl || true
```

2. Confirm JT128 network:

```bash
ip route get 192.168.124.20
ping -I net1 -c 3 192.168.124.20
```

3. Start dedicated JT128 driver.

4. Check `/jt128/front/points` and `/jt128/front/imu`.

5. Record first bag:

```bash
ros2 bag record \
  /jt128/front/points \
  /jt128/front/imu \
  /tf_static
```

6. Start DLIO mapping.

7. Save PCD through `map_manager`.

8. Replay bag offline and compare.

9. Only after mapping quality passes, start 3D localization.

10. Only after localization is stable, enable motion tests.

## 15. DLIO vs FAST-LIO2 A/B Table

| Dimension | DLIO | FAST-LIO2 |
| --- | --- | --- |
| First choice | yes | no |
| Reason | Clean LiDAR-inertial mapping target, good fit for JT128 point+IMU plan. | Already present locally, useful fallback and comparison. |
| IMU dependency | yes | yes |
| Per-point timestamp | preferred/important | important |
| Ring field | useful | often useful depending preprocess path |
| Loop closure | not the main feature | not the main feature |
| JT128 adaptation risk | medium | medium-high, may need preprocess changes |
| Humble build risk | must verify | already partially present but not validated for JT128 |
| Output PCD | yes | yes |
| Best use | Primary mapping pipeline | A/B validation fallback |

## 16. Immediate Next Implementation Tasks

1. Add `jt128_front_hesai.yaml` using verified `.20/net1/2368/9347` values.
2. Add `jt128_driver.launch.py` that starts only the Hesai driver.
3. Add `start_jt128_dlio_mapping.sh` that:
   - stops `unitree_slam.service`
   - kills native SLAM/DWA and old 2D nodes
   - checks `net1 -> 192.168.124.20`
   - starts JT128 driver
   - starts DLIO if installed, otherwise exits with a clear missing-DLIO error
   - starts Web
4. Vendor or install DLIO.
5. Add `dlio_jt128.yaml`.
6. Extend `map_manager` to save DLIO map PCD as a first-class map.
7. Extend Web to treat `pointcloud_map_3d` as the default map representation.

## 17. Key Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Official Hesai driver not yet tested standalone | Phase 1 may fail | Use Unitree packaged driver as reference, then isolate. |
| Wrong network interface | No packets | Bind JT128 path to `net1`; do not use `eth0` for `.20`. |
| Extrinsic inaccurate | DLIO drift and distorted map | Use official JT128 extrinsic or calibrate. |
| IMU frame mismatch | LIO instability | Validate axes with stationary/rotation tests. |
| Duplicate `odom -> base_link` | TF jumps | Disable `a2_state_publisher` dynamic TF when DLIO owns odom. |
| Native Unitree SLAM interference | Duplicate drivers/topics/goals | Startup script must stop native services and helpers. |
| Web performance | Large clouds lag browser | Downsample server-side and stream bounded previews. |
| No loop closure | Long map drift | Start with short-loop validation, consider loop-closure backend later. |

## 18. Conclusion

Do not rewrite every layer at once. The stable cut-in point is the sensor-to-map pipeline:

```text
JT128 official driver -> DLIO -> managed PCD -> Web 3D display
```

The three critical validations before navigation work are:

1. Standalone JT128 driver publishes correct point cloud and IMU on `net1`.
2. DLIO produces stable odometry and a usable PCD from the same data.
3. Saved PCD can be loaded and used for repeatable 3D scan-to-map localization.

Only after those pass should `/cmd_vel`, Unitree motion, automatic scan missions, and full 3D navigation be enabled.
# Historical Engineering Plan

This file records the earlier JT128 migration planning process. It is retained as engineering context, not as the current source of truth for active topic names, TF names, or startup paths.
