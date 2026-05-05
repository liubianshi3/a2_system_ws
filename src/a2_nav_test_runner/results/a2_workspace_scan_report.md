# A2 Workspace Scan Report

生成日期：2026-05-03

工作区：`/home/dell/a2_sys_ws`

说明：本报告是当前 ROS2 工作区的软件扫描记录，不是真机实验结果，不代表 A2 已经完成真实导航测试。

## 1. 当前 ROS2 包

`src/` 下检测到的 ROS2 包包括：

- `a2_bringup`
- `a2_control_bridge`
- `a2_interfaces`
- `a2_nav_test_runner`
- `a2_sdk_bridge`
- `a2_state_publisher`
- `a2_system`
- `exploration_manager`
- `inspection_task_allocator`
- `localization_manager`
- `map_manager`
- `nav2_integration`
- `safety_manager`
- `sensor_sync`
- `slam_manager`
- `tf_manager`
- `unitree_api`

## 2. a2_bringup launch 文件

`src/a2_bringup/launch/` 中存在：

- `bringup.launch.py`
- `dlio_mapping.launch.py`
- `explore.launch.py`
- `jt128_3d_navigation.launch.py`
- `jt128_driver.launch.py`
- `localization.launch.py`
- `mapping.launch.py`
- `nav2.launch.py`
- `scan_mission.launch.py`
- `sensors.launch.py`
- `slam.launch.py`

后续真机导航测试建议优先检查：

```bash
ros2 launch a2_bringup nav2.launch.py
```

或：

```bash
ros2 launch a2_bringup jt128_3d_navigation.launch.py
```

具体选择取决于当前真机传感器、地图和定位链路。

## 3. a2_system Nav2 配置

`src/a2_system/config/` 中存在 Nav2 相关配置：

- `nav2.yaml`
- `nav2_stack.yaml`
- `pose_goal_controller_3d.yaml`
- `motion_limits.yaml`
- `localization.yaml`
- `slam.yaml`
- `slam_toolbox_mapping.yaml`
- `native_map_relay.yaml`
- `occupancy_mapper.yaml`
- `map_manager.yaml`

扫描到的关键接口引用：

- `/navigate_to_pose`
- `/map`
- `/tf`
- `/odom`
- `/amcl_pose`

这些接口是否在运行态真实可用，必须在 A2 真机启动后通过 ROS2 graph 检查确认。

## 4. 地图文件

`runtime/maps/` 下检测到地图文件：

- `runtime/maps/outdoor_demo_map_v2/map.yaml`
- `runtime/maps/outdoor_demo_map_v2/map.pgm`
- `runtime/maps/outdoor_demo_map_v2/metadata.yaml`
- `runtime/maps/outdoor_demo_map_v3/map.yaml`
- `runtime/maps/outdoor_demo_map_v3/map.pgm`
- `runtime/maps/outdoor_demo_map_v3/metadata.yaml`
- `runtime/maps/outdoor_demo_map_v4/map.yaml`
- `runtime/maps/outdoor_demo_map_v4/map.pgm`
- `runtime/maps/outdoor_demo_map_v4/metadata.yaml`
- `runtime/maps/smoke_map/map.yaml`
- `runtime/maps/smoke_map/map.pgm`
- `runtime/maps/smoke_map/metadata.yaml`
- `runtime/maps/smoke_map_2/map.yaml`
- `runtime/maps/smoke_map_2/map.pgm`
- `runtime/maps/smoke_map_2/metadata.yaml`

这些地图是否适合 A2 真机测试，需要现场确认地图坐标、定位状态和可通行区域。

## 5. nav2_integration goal bridge

`src/nav2_integration/nav2_integration/goal_bridge.py` 存在。

扫描结果：

- 已使用 `nav2_msgs/action/NavigateToPose`
- 已包含 `ActionClient`
- 默认 action 名称参数为 `navigate_to_pose`
- 可将上层目标桥接到 Nav2 或 3D pose topic

这说明当前工作区已有 Nav2 goal bridge 相关实现，本轮 `a2_nav_test_runner` 不重复造底层导航，只作为测试 runner 调用运行态接口。

## 6. NavCommand.srv 真实字段

真实文件：`src/a2_interfaces/srv/NavCommand.srv`

字段如下：

```text
string command
string map_id
string route_id
string mode
string mission_name
string route_yaml
string waypoints_file
bool dry_run
bool stop_on_failure
bool save_map_on_finish
bool save_map_on_failure
geometry_msgs/PoseStamped pose
---
bool success
string message
string active_map
string current_mode
string route_id
string route_path
string mission_state
string report_path
string[] items
string route_yaml
```

重要说明：

- request 中包含 `pose`，可承载目标点位姿；
- request 中包含 `command/mode/mission_name/route_id`，本轮后端使用 `command=navigate_to_pose`、`mode=navigation`；
- response 中 `success` 只能说明命令是否被服务端接受；
- response 没有明确的到达成功字段；
- 因此 `a2_navcommand_backend` 不能把 service 调用成功直接写成导航成功；
- 若需要判断到达，必须结合 `/amcl_pose` 或 `/odom` 位姿反馈。

## 7. a2_nav_test_runner 当前完整度

当前目标包：`src/a2_nav_test_runner/`

已补齐文件：

- `package.xml`
- `setup.py`
- `README.md`
- `PADS_INTEGRATION_PLAN.md`
- `resource/a2_nav_test_runner`
- `config/nav_test_goals.yaml`
- `config/nav_test_config.yaml`
- `launch/nav_test.launch.py`
- `results/.gitkeep`
- `results/a2_workspace_scan_report.md`
- `a2_nav_test_runner/__init__.py`
- `a2_nav_test_runner/goal_loader.py`
- `a2_nav_test_runner/runtime_checker.py`
- `a2_nav_test_runner/nav2_action_backend.py`
- `a2_nav_test_runner/a2_navcommand_backend.py`
- `a2_nav_test_runner/pose_monitor.py`
- `a2_nav_test_runner/nav_client.py`
- `a2_nav_test_runner/nav_test_node.py`
- `a2_nav_test_runner/logger.py`
- `a2_nav_test_runner/metrics.py`
- `a2_nav_test_runner/utils.py`

## 8. 缺失模块清单

本轮目标范围内的导航测试 runner 模块已经补齐。

尚未实现的是真机 PADS 调度执行模块，按照计划下一阶段再新增：

- `a2_pads_task_runner.py`
- `pads_task_loader.py`
- `pads_method_adapter.py`
- `pads_experiment_logger.py`

这些模块不能在没有真机数据时生成实验结果。

## 9. 当前是否可以构建

已完成本轮静态检查和构建检查：

```bash
python3 -m py_compile src/a2_nav_test_runner/a2_nav_test_runner/*.py
colcon list | grep a2_nav_test_runner
colcon build --packages-select a2_interfaces a2_nav_test_runner
```

检查结果：

- `py_compile`：通过；
- `colcon list`：可以识别 `a2_nav_test_runner`；
- `colcon build --packages-select a2_interfaces a2_nav_test_runner`：通过。

曾发现的问题：

- 初次 dry check 时，包缺少 `setup.cfg`，导致 ROS2 launch 找不到 `lib/a2_nav_test_runner` libexec 目录；
- 已补充 `setup.cfg` 并重建通过。

已执行 dry check：

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch a2_nav_test_runner nav_test.launch.py dry_check_only:=true
```

当前没有 A2 真机和导航栈在线，因此 dry check 报告显示 `/navigate_to_pose`、`/map`、`/tf`、`/odom`、`/amcl_pose` 和 NavCommand 候选 service 均未检测到。该报告只是接口检查，不是导航实验结果。

## 10. 后续真机运行需要先启动哪个 launch

建议顺序：

1. 构建并 source 工作区；
2. 启动 A2 bringup/Nav；
3. 执行 dry check；
4. 单点 P1 测试；
5. 多点固定序列测试；
6. 再接入 PADS。

可选启动命令：

```bash
ros2 launch a2_bringup nav2.launch.py
```

或：

```bash
ros2 launch a2_bringup jt128_3d_navigation.launch.py
```

## 11. 不确定项和必须真机确认的项

当前没有 A2 真机在线，因此以下接口必须现场确认：

- `/navigate_to_pose` action 是否存在；
- `/map` 是否发布；
- `/tf` 是否发布；
- `/odom` 是否发布；
- `/amcl_pose` 是否发布；
- NavCommand service 实际名称是 `/nav_command`、`/a2/nav_command`、`/a2_nav_command`、`/NavCommand` 还是 `/a2/task_manager/command`；
- 地图坐标系是否为 `map`；
- P1-P5 示例坐标是否在真实地图可达区域；
- NavCommand service 的 `success` 是否仅表示命令接受，还是系统另有任务完成状态 topic/service。

在这些项确认前，不能生成真实机器人导航实验结论。
