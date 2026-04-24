# Gazebo 模式改造执行 Prompt

## 目标

把当前 `a2_system_ws` 中的二元运行模式：

- `mock`
- `real`

扩展为三元运行模式：

- `mock`
- `gazebo`
- `real`

其中 `gazebo` 模式用于替代当前纯假数据 `mock`，目标不是仿真 A2 本体，而是仿真导航系统的数据流。

## 约束

- 保留现有上层导航架构不动
- 不强依赖 A2 机器狗本体模型
- 用一个小车底盘替代 A2 作为 Gazebo 中的移动载体
- Gazebo 负责提供：
  - LiDAR
  - Camera
  - IMU
  - Odom
- 写适配层，把 Gazebo 输出转换为当前系统吃的接口
- 尽量保持 topic、service、状态格式和日志风格不变
- 上层模块如 `map_manager`、`safety_manager`、`slam_manager`、`nav2_integration`、`exploration_manager` 尽量不改业务语义

## 数据接口目标

Gazebo 模式最终应保证上层继续看到这些核心输入：

- `/a2/raw_state`
- `/robot_state`
- `/imu/data`
- `/odom`
- `/mid360/points`
- `/camera/image_raw`
- `/camera/camera_info`
- `/amcl_pose`

以及继续复用这些控制/状态接口：

- `/cmd_vel`
- `/a2/command_limited`
- `/a2/sdk/status`
- `/a2/control/status`
- `/a2/slam/status`
- `/a2/nav2/status`
- `/a2/mid360/status`
- `/a2/real/report`

## 实现原则

1. `gazebo` 模式视为“仿真但非 fake 数据”
2. `mock` 仍保留纯软件生成数据的能力
3. `real` 继续保留真实 A2 + MID360 链路
4. 所有状态类节点从二元 `use_mock` 逐步收口到三元 `runtime_mode`
5. `gazebo` 模式必须使用 `use_sim_time`
6. `gazebo` 模式下不启动真实 `a2_sdk_bridge`，改用仿真状态适配器
7. `gazebo` 模式下控制桥继续承担门控与限速，只是不再向 SDK 发命令，而是向 Gazebo 底盘发控制

## 推荐拆分

### 1. 启动层

- 在 `a2_bringup` 中新增 `runtime_mode`
- top-level bringup 根据 `runtime_mode` 选择：
  - `mock`: 纯假数据链
  - `gazebo`: Gazebo world + 仿真适配器
  - `real`: 真机 DDS + Livox + SDK

### 2. Gazebo 资产层

新增 `gazebo_bridge` 包，包含：

- 小车模型 URDF
- world 文件
- Gazebo 状态适配器节点

### 3. 适配层

Gazebo -> 当前系统：

- `/gazebo/odom` + `/gazebo/imu` -> `/a2/raw_state`
- Gazebo ray sensor -> `/mid360/points`
- Gazebo camera -> `/camera/image_raw` `/camera/camera_info`
- `/odom` -> `/amcl_pose` 可复用当前 mock localization publisher

### 4. 控制层

- 上层仍输出 `/cmd_vel`
- `a2_control_bridge` 在 `gazebo` 模式下完成：
  - 限速
  - 门控
  - 状态输出
  - 将最终命令转发到 `/gazebo/cmd_vel`

### 5. 状态层

以下节点统一支持 `runtime_mode`：

- `localization_gate`
- `sync_monitor`
- `mid360_driver_guard`
- `safety_supervisor`
- `real_readiness_monitor`
- `map_manager`
- `slam_orchestrator`
- `mock_nav_controller`
- `goal_bridge`
- `a2_control_bridge`

状态格式继续保持：

```text
mode=...;state=...;ready=...;reason=...
```

## 验收标准

### 功能验收

- `runtime_mode:=gazebo` 时整套 bringup 能启动
- Gazebo 中小车可响应导航命令移动
- `/mid360/points`、`/imu/data`、`/odom` 持续输出
- `/a2/raw_state`、`/robot_state` 持续输出
- `/a2/sdk/status` 在 Gazebo 模式下可读且不再依赖真机 SDK
- `/a2/control/status`、`/a2/slam/status`、`/a2/real/report` 反映 Gazebo 模式
- exploration / map / localization / safety 链路不需要为 Gazebo 单独重写上层逻辑

### 工程验收

- `colcon build --symlink-install` 通过
- Python 节点 `py_compile` 通过
- shell 脚本 `bash -n` 通过
- README 中有 Gazebo 启动说明

## 当前实现方向

当前代码实现采用：

- Gazebo Classic + `gazebo_ros`
- `libgazebo_ros_planar_move.so` 驱动小车底盘
- `libgazebo_ros_ray_sensor.so` 输出 `/mid360/points`
- `libgazebo_ros_imu_sensor.so` 输出 `/gazebo/imu`
- `libgazebo_ros_camera.so` 输出相机图像
- `gazebo_state_adapter` 把仿真 odom/imu 组合为 `/a2/raw_state`

这条路线的目标是：

**先让导航系统的数据流在 Gazebo 中跑起来，再考虑是否进一步接 Nav2/3D SLAM 的更高保真仿真。**
