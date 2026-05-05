# A2 Navigation Precision Static Scan

This is a static code-and-config scan. It is not a runtime diagnosis result and it cannot prove which parameters are actually loaded on the robot.

## 1. Static tolerance parameters

| Parameter | Static value | Source |
|---|---:|---|
| `controller_server.general_goal_checker.xy_goal_tolerance` | `0.06` | `src/a2_system/config/nav2_stack.yaml:85` |
| `controller_server.general_goal_checker.yaw_goal_tolerance` | `0.08` | `src/a2_system/config/nav2_stack.yaml:86` |
| `controller_server.FollowPath.xy_goal_tolerance` | `0.06` | `src/a2_system/config/nav2_stack.yaml:111` |
| `planner_server.GridBased.tolerance` | `0.10` | `src/a2_system/config/nav2_stack.yaml:54` |
| `smoother_server.simple_smoother.tolerance` | `1.0e-10` | `src/a2_system/config/nav2_stack.yaml:64` |
| `amcl.transform_tolerance` | `0.5` | `src/a2_system/config/nav2_stack.yaml:33` |
| `controller_server.FollowPath.transform_tolerance` | `0.2` | `src/a2_system/config/nav2_stack.yaml:110` |
| `local_costmap.transform_tolerance` | `0.2` | `src/a2_system/config/nav2_stack.yaml:144` |
| `global_costmap` / `local_costmap` `robot_radius` | `0.24` | `src/a2_system/config/nav2_stack.yaml:274`, `src/a2_system/config/nav2_stack.yaml:298` |
| `global_costmap.inflation_layer.inflation_radius` | `0.35` | `src/a2_system/config/nav2_stack.yaml:283` |
| `local_costmap.inflation_layer.inflation_radius` | `0.32` | `src/a2_system/config/nav2_stack.yaml:317` |
| `pose_goal_controller_3d.goal_tolerance_xy` | `0.15` | `src/a2_system/config/pose_goal_controller_3d.yaml:21` |
| `pose_goal_controller_3d.goal_tolerance_yaw` | `0.18` | `src/a2_system/config/pose_goal_controller_3d.yaml:22` |
| `a2_nav_test_runner.arrival_tolerance` | `0.35` | `src/a2_nav_test_runner/config/nav_test_config.yaml:25` |

## 2. Frame-related static settings

| Parameter | Static value | Source |
|---|---|---|
| `goal_bridge.map_frame` | `map` | `src/a2_system/config/nav2.yaml:10` |
| `goal_bridge.require_map_frame` | `true` | `src/a2_system/config/nav2.yaml:11` |
| `pose_goal_controller_3d.map_frame` | `map` | `src/a2_system/config/pose_goal_controller_3d.yaml:9` |
| `amcl.base_frame_id` | `base_link` | `src/a2_system/config/nav2_stack.yaml:9` |
| `amcl.odom_frame_id` | `odom` | `src/a2_system/config/nav2_stack.yaml:23` |
| `global_costmap.robot_base_frame` | `base_link` | `src/a2_system/config/nav2_stack.yaml:272` |
| `local_costmap.robot_base_frame` | `base_link` | `src/a2_system/config/nav2_stack.yaml:293` |

## 3. Launch files and what they load

### 3.1 `src/a2_bringup/launch/nav2.launch.py`

- Always launches `goal_bridge` with `src/a2_system/config/nav2.yaml`:
  - `src/a2_bringup/launch/nav2.launch.py:51-59`
- Only launches the standard Nav2 stack if `enable_nav2_bringup` is true **and** `use_3d_navigation` is false:
  - `src/a2_bringup/launch/nav2.launch.py:62-63`
  - `src/a2_bringup/launch/nav2.launch.py:77-139`
- When Nav2 bringup is enabled, it passes `src/a2_system/config/nav2_stack.yaml` into either:
  - `navigation_launch.py`: `src/a2_bringup/launch/nav2.launch.py:114-123`
  - or `bringup_launch.py`: `src/a2_bringup/launch/nav2.launch.py:126-138`

### 3.2 `src/a2_bringup/launch/jt128_3d_navigation.launch.py`

- Launches `goal_bridge` with:
  - `navigation_backend: "pose_topic_3d"`
  - `pose_goal_topic: "/a2/nav3/goal_pose"`
  - `map_frame: "map"`
  - Source: `src/a2_bringup/launch/jt128_3d_navigation.launch.py:202-216`
- Launches `pose_goal_controller_3d` with `src/a2_system/config/pose_goal_controller_3d.yaml`:
  - Source: `src/a2_bringup/launch/jt128_3d_navigation.launch.py:218-229`

## 4. Possible navigation chains from static code

### Chain A: Standard Nav2 action chain

Likely path:

`exploration goal -> goal_bridge -> /navigate_to_pose -> controller_server / bt_navigator / planner_server`

Evidence:

- `goal_bridge` only creates a `NavigateToPose` action client when `navigation_backend == "nav2"`:
  - `src/nav2_integration/nav2_integration/goal_bridge.py:82-87`
- `goal_bridge` default backend in static config is **not** `nav2`; it is `pose_topic_3d`:
  - `src/a2_system/config/nav2.yaml:4`
  - `src/nav2_integration/nav2_integration/goal_bridge.py:57`

### Chain B: 3D pose-topic controller chain

Likely path:

`exploration goal -> goal_bridge -> /a2/nav3/goal_pose -> pose_goal_controller_3d -> /cmd_vel`

Evidence:

- `goal_bridge` default backend is `pose_topic_3d`:
  - `src/a2_system/config/nav2.yaml:4`
  - `src/nav2_integration/nav2_integration/goal_bridge.py:57`
- `jt128_3d_navigation.launch.py` explicitly forces `navigation_backend: "pose_topic_3d"`:
  - `src/a2_bringup/launch/jt128_3d_navigation.launch.py:209-213`
- `goal_bridge` publishes to `/a2/nav3/goal_pose` in that mode:
  - `src/nav2_integration/nav2_integration/goal_bridge.py:96-108`
- `pose_goal_controller_3d` subscribes to that goal topic:
  - `src/a2_system/config/pose_goal_controller_3d.yaml:3`

### Chain C: A2 task manager / NavCommand service chain

Likely path:

`NavCommand service -> task_manager -> (pose_topic_3d publish OR Nav2 action, depending on runtime backend)`

Evidence:

- `task_manager` exposes `NavCommand` service at `/a2/task_manager/command`:
  - `src/a2_system/scripts/task_manager.py:268-273`
- `task_manager` static default `navigation_backend` is `pose_topic_3d`:
  - `src/a2_system/scripts/task_manager.py:223`
- `task_manager` only creates a Nav2 action client if `navigation_backend == "nav2"`:
  - `src/a2_system/scripts/task_manager.py:284-292`

## 5. Static conclusions we can already make

1. The repository does **not** support the claim that the robot is simply using Nav2 default `xy_goal_tolerance = 0.25 m`.
2. The static Nav2 controller tolerance in this workspace is `0.06 m`, not `0.25 m`.
3. The static 3D local controller tolerance is looser at `0.15 m`.
4. The test runner `arrival_tolerance = 0.35 m` is only a **program-side arrival check**, not proof of backend stop precision.
5. The most likely real-world confusion is that multiple navigation paths exist, and the running robot may be using:
   - Nav2 action,
   - 3D pose-topic controller,
   - or `NavCommand -> task_manager -> pose_topic_3d`.

## 6. Still requires runtime confirmation

The following cannot be answered from static files alone:

1. Which launch file is actually running on the robot.
2. Whether `enable_nav2_bringup` is true at runtime.
3. Whether `goal_bridge` is currently in `nav2` mode or `pose_topic_3d` mode.
4. Which node is actually deciding “goal reached” at runtime.
5. The real runtime values of:
   - `controller_server.general_goal_checker.xy_goal_tolerance`
   - `controller_server.general_goal_checker.yaw_goal_tolerance`
   - `pose_goal_controller_3d.goal_tolerance_xy`
   - `goal_checker` plugin name
   - active map / odom / base frame parameters
6. Whether the final error is being measured in the same frame as the goal.
7. Whether the observed 20–25 cm error comes from:
   - runtime goal tolerance,
   - localization jitter,
   - frame mismatch,
   - base_link vs base_footprint offset,
   - controller stopping behavior,
   - or the runner’s own arrival threshold.

## 7. Runtime tools that must be used next

- `ros2 run a2_nav_test_runner nav_runtime_diagnosis`
- `ros2 run a2_nav_test_runner runtime_param_dumper`
- `ros2 run a2_nav_test_runner pose_accuracy_recorder --ros-args -p duration_sec:=60`
- `ros2 run a2_nav_test_runner tf_diagnosis`
- `ros2 run a2_nav_test_runner single_goal_accuracy_test --ros-args -p goal_x:=... -p goal_y:=... -p repeats:=5`
- `ros2 run a2_nav_test_runner navigation_precision_analyzer`
