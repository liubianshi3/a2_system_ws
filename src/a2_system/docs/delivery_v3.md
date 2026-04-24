# A2 Host-Side Delivery V3

This document is the engineering delivery companion for the ROS 2 workspace at `/home/dell/a2_system_ws`.

## 前置判断

### 1. 技术路线判断

- 宇树 A2 控制与状态主路线：`Unitree SDK2 + ROS 2 bridge`
  原因：A2 真机控制优先走 SDK2，ROS 2 层保持稳定接口，Nav2、SLAM、地图管理不直接依赖厂商 DDS 细节。
- `unitree_ros2` 的定位：作为话题协议、示例和调试参考，不作为本工程唯一主入口。
- MID360 接入主路线：`mid360_wrapper + livox_ros_driver2`
  原因：当前阶段没有真机，先用 wrapper 统一接口，真机阶段再切到官方/可用驱动，避免后续替雷达时大改上层代码。
- 点云 ROS 消息：`sensor_msgs/PointCloud2`
- SLAM 主路线：`FAST_LIO(MID360 CustomMsg) + A2 IMU`，同时为 Nav2 生成 2D/2.5D 可消费地图
  原因：办公室场景、四足姿态扰动、人流动态环境下，纯 3D LiDAR 对抗抖动能力不如 LiDAR+IMU 融合稳。
- Nav2 接入主路线：`3D 感知 / 3D 建图 / 2D-Nav2 平面导航`
  原因：Nav2 原生仍是 2D 导航栈，工程上最稳的折中是用 3D 感知保证避障与地图质量，再对外提供 2D 地图和定位。
- `cmd_vel` 适配：`Nav2 -> /cmd_vel -> a2_control_bridge -> Unitree SportClient.Move()`
  其中 `a2_control_bridge` 负责限速、超时停车、定位门控、地图门控、急停。

### 2. “3D 导航”的工程定义

- 真正 3D 路径规划 / 3D 空间导航：
  适合无人机、机械臂末端或多层自由空间机器人，不适合作为办公室四足首版交付主路线。
- 基于 3D 感知、3D 地图，但主要在地面平面导航：
  最适合 A2 办公室场景首版落地。
- 3D 建图 + 2D Nav2 导航：
  当前主推荐方案。
- 3D 局部感知 + 2.5D/2D 全局规划：
  作为进阶增强路线，适合后续引入高差地面、台阶、坡面语义。

### 3. 主推荐方案与进阶方案

- 主推荐方案：
  `MID360 + IMU -> 3D LiDAR/IMU SLAM -> 投影/导出 2D Occupancy Map -> Nav2 -> A2 Control Bridge`
- 进阶方案：
  `3D LiDAR/IMU SLAM + Elevation/Voxel Layer + 2.5D traversability -> Nav2 costmap augmentation`
- 当前阶段判断：
  阶段 A 优先完成工程架构、接口抽象、mock/stub、工具链和 bringup。
  阶段 B 再替换为真机数据源、完成实测联调与调参。

## 第 1 部分：总体架构设计

### 1.1 模块分层

- 配置管理层：`a2_system/config/*.yaml`
- 网络接入与设备发现层：`a2_system/tools/setup_unitree_dds.sh`、`mid360_link_check.py`
- 宇树 A2 SDK 接入层：`a2_sdk_bridge`
- 机器人状态桥接层：`a2_state_publisher`
- MID360 驱动接入层：`mid360_wrapper`
- TF 坐标管理层：`tf_manager`
- IMU / 点云时间同步层：`sensor_sync`
- SLAM 层：`slam_manager`
- 地图管理层：`map_manager`
- 定位层：`localization_manager`
- Nav2 导航层：`nav2_integration`
- 导航控制桥接层：`a2_control_bridge`
- 自动建图任务层：`exploration_manager`
- 安全控制层：`safety_manager`

### 1.2 主机全跑架构

- 主机统一承担：
  A2 DDS 接入、MID360 驱动、状态桥接、SLAM、地图管理、Nav2、探索状态机、安全监督。
- 主要瓶颈：
  CPU 被点云预处理和 SLAM 占满；DDS 和点云吞吐导致时延波动；RViz2 与录包会进一步拉高负载。
- 推荐隔离：
  `a2_sdk_bridge`、`a2_control_bridge`、`mid360` 驱动、SLAM、Nav2、RViz2 至少独立进程。
- 推荐 mock 优先：
  所有上层模块都先消费稳定 ROS 2 接口，不直接耦合真实 DDS/UDP 细节。

### 1.3 推荐进程划分

- `a2_sdk_bridge_node`：
  负责网卡选择、SDK2 初始化、A2 高层状态读取、mock/real 切换。
- `a2_state_publisher_node`：
  负责 `/a2/raw_state -> /imu/data /odom /robot_state`。
- `a2_control_bridge_node`：
  负责 `/cmd_vel -> A2 Move()`，带门控与急停。
- `mock_mid360_publisher` 或 `livox_ros_driver2_node`：
  负责 MID360 点云源。
- `livox_custom_to_pointcloud`：
  负责 `livox_ros_driver2/msg/CustomMsg -> /mid360/points`，让 FAST_LIO 和上层感知/安全同时成立。
- `static_tf_manager`：
  负责 `base_footprint -> base_link -> trunk` 和各传感器静态外参。
- `sync_monitor`：
  负责 IMU / 点云新鲜度和时延告警。
- `slam_orchestrator`：
  负责 SLAM 模式、状态与 mock `map->odom`。
- `map_manager_node`：
  负责地图版本目录、保存/加载/提升。
- `localization_gate`：
  负责定位质量门控。
- `goal_bridge` / `mock_nav_controller`：
  负责 Nav2 目标桥和 mock 导航。
- `exploration_manager_node`：
  负责探索状态机、覆盖率、卡住重规划。
- `safety_supervisor`：
  负责传感器失联、地图/定位门控、急停。

### 1.4 坐标系设计

- `map -> odom`：
  由 SLAM / 定位层发布。当前 mock 模式由 `slam_orchestrator` 发布单位变换。
- `odom -> base_link`：
  由 `a2_state_publisher` 发布。
- `base_footprint -> base_link`：
  由 `static_tf_manager` 发布，表示四足机体离地高度语义。
- `base_link -> trunk`：
  由 `static_tf_manager` 发布，表达机身语义层。
- `base_link -> lidar_link`：
  静态外参，由 `static_tf_manager` 根据 `extrinsics.yaml` 发布。
- `base_link -> imu_link`：
  静态外参，由 `static_tf_manager` 根据 `extrinsics.yaml` 发布。

避免 TF 重复发布原则：

- `map->odom` 只由 SLAM/定位层发布。
- `odom->base_link` 只由状态桥接层发布。
- 所有静态外参只由 `tf_manager` 发布。

## 第 2 部分：分阶段实施路线

### 阶段 A：未接真机阶段

目标：

- 完成工作空间与多包结构
- 固化 ROS 接口和配置模板
- 补齐 mock 状态、mock IMU、mock 点云、mock 地图、mock 定位、mock 导航
- 跑通自动探索闭环

已落地代码：

- `a2_system_ws/src/*`
- `ros2 launch a2_bringup bringup.launch.py use_mock:=true auto_start_explore:=true`

通过标准：

- `/a2/localization_ok = true`
- `/a2/allow_motion = true`
- `/a2/exploration/goal` 有输出
- `/a2/command_limited` 有输出
- `/robot_state`、`/odom`、`/imu/data` 连续输出

### 阶段 B：接入真机阶段

顺序：

1. 选择 A2 网卡并设置 DDS 环境  
   输入：A2 接上主机  
   命令：`source install/a2_system/share/a2_system/setup_unitree_dds.sh <iface>`  
   输出：`RMW_IMPLEMENTATION`、`A2_NETWORK_INTERFACE`、`A2_CYCLONEDDS_BIND_STATUS`、`CYCLONEDDS_URI`  
   通过：A2 DDS 话题可见  
   排查：网卡无载波时脚本会进入 diagnostic mode，先修复有线链路再绑定 CycloneDDS

2. 验证 A2 状态读取  
   命令：`ros2 launch a2_bringup bringup.launch.py use_mock:=false`  
   通过：`/robot_state`、`/imu/data`、`/odom` 连续更新  
   排查：SDK2 库路径、DDS 接口、A2 是否处于可通讯模式

3. 验证 MID360 点云  
   命令：`python3 src/mid360_wrapper/mid360_wrapper/mid360_link_check.py --target-ip 192.168.124.20`  
   通过：雷达可达、驱动起后 `/mid360/points` 有数据  
   排查：PC2 网段、雷达供电、UDP 数据口、驱动配置

4. RViz2 验证点云和 TF  
   通过：`map / odom / base_link / lidar_link / imu_link` 完整可视

5. 接入真实 SLAM 与地图管理  
   通过：地图可保存、可加载、可复用

6. 接入真实定位与 Nav2  
   通过：地图基础上可以下发目标并生成稳定 `cmd_vel`

## 第 3 部分：技术路线比较与最终推荐

### 3.1 A2 接入层比较

- 纯 SDK2：
  最适合真机控制，但不利于上层 ROS 模块化。
- `unitree_ros2`：
  适合快速看话题、抓协议，不适合作为唯一工程主入口。
- `SDK2 + ROS2 bridge`：
  最适合主机全跑、最利于 Nav2 对接、最利于后续维护。

最终选择：

- `SDK2 + ROS2 bridge`

### 3.2 MID360 接入层

- ROS2 接入方式：
  wrapper 固定接口，real 模式切到 `livox_ros_driver2` 或同类可用驱动。
- 当前 real 落地方式：
  `livox_ros_driver2(xfer_format=1)` 输出 `/livox/lidar`，`mid360_wrapper/livox_custom_to_pointcloud` 转成 `/mid360/points`
- 推荐话题：
  `/mid360/points`
- 网络检查：
  `mid360_link_check.py`
- 数据连通检查：
  `ros2 topic hz /mid360/points`
- 驱动包装原则：
  上层只认 `PointCloud2` 和固定 `frame_id=lidar_link`，不直接依赖具体驱动包名。

### 3.3 SLAM 路线

- 主路线：
  `3D LiDAR + IMU SLAM`，再投影/导出 2D 地图给 Nav2。
- 最稳原因：
  办公室几百平、动态行人多、四足抖动明显，IMU 融合必须保留。
- 进阶路线：
  后续引入体素地图或 elevation map，把 3D traversability 注入 Nav2 costmap。

### 3.4 Nav2 接入路线

- Nav2 地图输入：
  `map_manager` 导出的 `map.pgm + map.yaml`
- Nav2 定位输入：
  `/amcl_pose` 或外部定位结果
- Nav2 输出：
  `/cmd_vel`
- 四足控制桥：
  `a2_control_bridge`
- 动态环境调参方向：
  降低最大线速度、增大控制频率、提升障碍膨胀与恢复行为权重。

## 第 4 部分：最终主推荐方案

- 机器人控制：`Unitree SDK2 SportClient`
- 机器人状态桥接：`a2_sdk_bridge + a2_state_publisher`
- IMU 接入：默认从 A2 sport state 读取 IMU
- MID360 驱动：`mid360_wrapper`，real 模式接 `livox_ros_driver2`
- SLAM：`FAST_LIO + A2 IMU` 为主接入口，由 `slam_manager` 承接运行模式和状态
- 地图表示：3D SLAM 主地图 + Nav2 用 2D 占据栅格
- 定位：外部定位结果经 `localization_gate` 门控
- Nav2 接入方式：`goal_bridge + /cmd_vel`
- 四足控制桥接：`a2_control_bridge`
- 自动建图方式：`exploration_manager + frontier`
- 安全机制：`safety_supervisor + control gate + estop`
- 为什么这样选：
  这是最符合 A2 真机控制、Nav2 对接、办公室动态环境和主机全跑的现实折中。
- 升级到更强 3D：
  引入 2.5D traversability、局部体素层、复杂地形语义。

## 第 5 部分：工程目录结构

### 目录矩阵

| 目录 | 作用 | 关键源码 | 发布 | 订阅 | 依赖 | 需真机 | 可 mock |
|---|---|---|---|---|---|---|---|
| `a2_system/` | 配置、脚本、文档 | `network_utils.hpp` | - | - | SDK2 环境 | 否 | 是 |
| `a2_bringup/` | launch 入口 | `bringup.launch.py` | - | - | launch | 否 | 是 |
| `a2_sdk_bridge/` | A2 SDK 状态源 | `a2_sdk_bridge_node.cpp` | `/a2/raw_state` | `/cmd_vel`(mock) | SDK2 | real 模式需 | 是 |
| `a2_state_publisher/` | 状态桥接 | `a2_state_publisher_node.cpp` | `/imu/data` `/odom` `/robot_state` | `/a2/raw_state` | ROS2 msgs | 否 | 是 |
| `a2_control_bridge/` | 控制桥 | `a2_control_bridge_node.cpp` | `/a2/command_limited` | `/cmd_vel` | SDK2 | real 模式需 | 是 |
| `mid360_wrapper/` | 雷达 wrapper | `mock_mid360_publisher.py` | `/mid360/points` | - | driver/mock | real 模式需 | 是 |
| `sensor_sync/` | 时延监控 | `sync_monitor.py` | `/a2/sensor_sync/ok` | `/imu/data` `/mid360/points` | ROS2 | 否 | 是 |
| `tf_manager/` | TF 管理 | `static_tf_manager.py` | `/tf_static` | - | tf2 | 否 | 是 |
| `slam_manager/` | SLAM 模式 | `slam_orchestrator.py` | `/a2/slam/*` `/tf` | - | tf2 | real 模式需外部 SLAM | 是 |
| `map_manager/` | 地图保存/加载 | `map_manager_node.py` | `/a2/map_manager/active_map` `/a2/system_mode` | `/map` | a2_interfaces | 否 | 是 |
| `localization_manager/` | 定位门控 | `localization_gate.py` | `/a2/localization_ok` | `/amcl_pose` | ROS2 | real 定位需 | 是 |
| `nav2_integration/` | Nav2 对接 | `goal_bridge.py` `mock_nav_controller.py` | `/a2/nav2/status` `/cmd_vel` | `/a2/exploration/goal` `/odom` | nav2_msgs | Nav2 时需 | 是 |
| `exploration_manager/` | 自动探索 | `exploration_manager_node.py` | `/a2/exploration/*` | `/map` `/odom` `/a2/command_limited` | a2_interfaces | 否 | 是 |
| `safety_manager/` | 安全监督 | `safety_supervisor.py` | `/a2/allow_motion` `/a2/estop` | `/mid360/points` `/robot_state` `/map` | ROS2 | 否 | 是 |

## 第 6 部分：核心代码骨架

已落地的核心代码位置：

- A2 SDK 接入节点：
  [a2_sdk_bridge_node.cpp](/home/dell/a2_system_ws/src/a2_sdk_bridge/src/a2_sdk_bridge_node.cpp)
- 机器人状态桥接节点：
  [a2_state_publisher_node.cpp](/home/dell/a2_system_ws/src/a2_state_publisher/src/a2_state_publisher_node.cpp)
- 导航控制桥接节点：
  [a2_control_bridge_node.cpp](/home/dell/a2_system_ws/src/a2_control_bridge/src/a2_control_bridge_node.cpp)
- MID360 联通检查：
  [mid360_link_check.py](/home/dell/a2_system_ws/src/mid360_wrapper/mid360_wrapper/mid360_link_check.py)
- 启动前自检：
  [preflight_check.py](/home/dell/a2_system_ws/src/a2_system/scripts/preflight_check.py)
- 地图管理：
  [map_manager_node.py](/home/dell/a2_system_ws/src/map_manager/map_manager/map_manager_node.py)
- 自动建图任务：
  [exploration_manager_node.py](/home/dell/a2_system_ws/src/exploration_manager/exploration_manager/exploration_manager_node.py)

## 第 7 部分：配置文件模板

关键配置文件：

- 主系统：`config/system.yaml`
- 网卡：`config/network.yaml`
- A2 SDK：`config/a2_sdk.yaml`
- 状态桥：`config/state_bridge.yaml`
- MID360：`config/mid360.yaml`
- Livox MID360 real 驱动：`config/livox_mid360_driver.yaml`
- 时延同步：`config/sensor_sync.yaml`
- 外参：`config/extrinsics.yaml`
- TF：`config/tf.yaml`
- SLAM：`config/slam.yaml` 与 `config/slam_manager.yaml`
- 地图管理：`config/map_manager.yaml`
- 定位：`config/localization.yaml`
- Nav2：`config/nav2.yaml` 与 `config/nav2_stack.yaml`
- 运动约束：`config/motion_limits.yaml`
- 安全：`config/safety.yaml`
- 自动建图：`config/exploration.yaml`

参数解释原则：

- `network_interface`：
  真机阶段推荐显式填写；mock 阶段允许为空并走 `lo`
- `use_mock`：
  所有核心数据源都支持
- `max_linear_x / max_yaw_rate`：
  办公室建议保守，先低速验证
- `coverage_target`：
  办公室动态环境建议 0.8 左右，不要盲目追满图
- `lidar_timeout_sec / state_timeout_sec`：
  直接决定是否停车

## 第 8 部分：未接真机阶段的 Mock / Stub 设计

已实现：

- 机器人状态 mock：`a2_sdk_bridge` mock 模式
- IMU mock：由 mock `RobotState -> /imu/data`
- 点云输入抽象：`mid360_wrapper`
- 假雷达数据源：`mock_mid360_publisher`
- Livox real 数据转换：`livox_custom_to_pointcloud`
- Nav2 预对接：`goal_bridge`
- mock 导航：`mock_nav_controller`
- 地图保存/加载空跑：`map_manager`
- cmd_vel 到 A2 控制桥空跑：`a2_control_bridge` mock 模式
- 启动流程空跑检查：`preflight_check.py`

必须等真机的部分：

- A2 DDS 真连通
- IMU 真值验证
- MID360 真数据流
- 外参标定
- 真实 SLAM 参数

## 第 9 部分：自动建图策略设计

- 启动前检查：
  先看网卡、雷达、定位、地图门控
- 初始姿态：
  机器人静止站立后再启动探索
- 覆盖策略：
  frontier-based，覆盖率到阈值自动保存
- 走廊策略：
  优先推进长走廊，再回收房间边界
- 开放区域策略：
  用较大半径 frontier 聚类，减少来回震荡
- 转弯策略：
  先转向后前进，减小四足横摆误差
- 速度策略：
  办公室建议低速
- 动态行人避让：
  依赖局部感知和安全门控，不在高密人流时强行扩图
- 卡住恢复：
  `exploration_manager` 检测长时间有命令无位移后重规划 frontier
- 丢定位恢复：
  `localization_gate` 变 false 时禁止继续探索
- 地图质量指标：
  覆盖率、重复回环稳定性、动态污染程度、导航可用性
- 保存触发：
  覆盖率达标且定位/地图状态稳定
- 失败重建：
  地图污染严重、Nav2 无法使用、闭环明显漂移时重建

## 第 10 部分：地图保存、加载、定位、导航闭环

- 保存内容：
  `map.pgm`、`map.yaml`、`metadata.yaml`
- 地图格式：
  Nav2 原生占据栅格
- 3D 建图到 Nav2：
  由 3D SLAM 结果投影/导出成 2D 占据栅格
- 加载方式：
  `/map_manager/manage_map` service
- 已有地图定位：
  定位结果输入 `/amcl_pose`，经 `localization_gate` 放行
- Nav2 使用方式：
  读取 `map.yaml`，规划后输出 `/cmd_vel`
- 验证导航确实基于该地图：
  比对 `active_map_id`、定位一致性和目标点路径
- 地图版本管理：
  候选、测试、正式三类可由目录命名约束

## 第 11 部分：部署步骤

1. 安装依赖  
   `sudo apt install ros-humble-rmw-cyclonedds-cpp ros-humble-tf2-ros ros-humble-nav2-msgs`

2. 构建工作空间  
   `cd /home/dell/a2_system_ws && source /opt/ros/humble/setup.bash && colcon build --symlink-install`

3. 未接真机启动 mock  
   `source install/setup.bash && ros2 launch a2_bringup bringup.launch.py use_mock:=true auto_start_explore:=true`

4. 真机前设置 DDS  
   `source install/a2_system/share/a2_system/setup_unitree_dds.sh <iface>`
   如果输出 `A2_CYCLONEDDS_BIND_STATUS=diagnostic`，说明当前网卡未 ready，栈会以 real 诊断模式启动但不会真正上线 A2/MID360 数据。

4.1 生成的 real 运行时配置  
   `runtime/generated/MID360_config.json`  
   `runtime/generated/fastlio_mid360.yaml`

5. 切 real 模式  
   把 `a2_sdk.yaml`、`motion_limits.yaml` 里的 `use_mock` 改为 `false`

6. 启动顺序  
   网络 / DDS -> A2 状态 -> 雷达 -> TF -> SLAM -> 地图 -> 定位 -> Nav2 -> 探索

7. 停机顺序  
   探索 -> Nav2 -> SLAM -> 雷达 -> 控制桥 -> 状态桥

8. 一键脚本  
   `start_mock_stack.sh`  
   `start_real_stack.sh`  
   `stop_stack.sh`  
   `record_bag.sh`  
   `collect_logs.sh`

## 第 12 部分：调试与排障手册

- 未接真机可验证：
  全部 mock 链、地图保存/加载、探索闭环、控制门控
- 真机无法连接 A2：
  检查 DDS 网卡、A2 网段、SDK2 库和 `CYCLONEDDS_URI`
- 找不到正确网卡：
  先 `python3 src/a2_system/scripts/preflight_check.py --mode real`，再显式传给 `setup_unitree_dds.sh`
- 读不到 IMU：
  先确认 A2 sport state 是否更新
- 能 ping MID360 无点云：
  检查驱动参数、UDP 端口、PC2 网段
- RViz 有点云但 SLAM 不出图：
  检查 IMU 时间、TF、点云 `frame_id`
- SLAM 漂移严重：
  优先检查外参和 IMU 时间同步
- 地图保存后 Nav2 不能用：
  检查 `map.yaml`、分辨率和 origin
- Nav2 出 `cmd_vel` 但 A2 不动：
  看 `/a2/allow_motion`、`/a2/localization_ok`、`/a2/map_ready`
- CPU 打满：
  关闭 RViz2、降点云频率、录包与 SLAM 分机或分时运行

## 第 13 部分：安全机制

- 急停：`/a2/estop`
- 限速：`motion_limits.yaml`
- 启动前安全检查：`preflight_check.py`
- 无地图禁止导航：`a2_control_bridge`
- 无定位禁止移动：`a2_control_bridge`
- 雷达失联停车：`safety_supervisor`
- IMU 异常降级：停止 SLAM/导航，保留监控
- Nav2 异常停车：控制桥超时停车
- `cmd_vel` 超时停车：`cmd_timeout_sec`
- 网络中断停车：状态新鲜度检测触发
- 办公室动态人流边界：
  低速、扩大障碍膨胀层、必要时人工接管

## 第 14 部分：验收标准

- A2 接入：
  测试方法：`/robot_state` 连续更新  
  通过：10 分钟内无断流  
  失败：状态间歇消失或反复重连
- IMU 接入：
  通过：`/imu/data` 姿态与机身变化一致
- MID360 点云：
  通过：`/mid360/points` 稳定输出
- SLAM 建图：
  通过：办公室单层场景可形成闭环一致地图
- 地图保存：
  通过：生成 `map.pgm + map.yaml + metadata.yaml`
- 地图加载：
  通过：可正确切换 `active_map_id`
- 定位：
  通过：`/a2/localization_ok = true`
- Nav2 接入：
  通过：目标点触发 `cmd_vel`
- 自动建图：
  通过：探索到阈值自动保存地图
- 安全停车：
  通过：雷达断开、定位丢失、超时都能停车
- 主机全跑稳定性：
  通过：核心链路连续运行 30 分钟无崩溃

## 第 15 部分：分阶段里程碑计划

- M0：工程骨架完成  
  输出：多包工作空间、基础 build/launch/config
- M1：未接真机阶段 mock 跑通  
  输出：mock 探索闭环、地图保存/加载、门控链路
- M2：真机网络接入完成  
  输出：DDS 环境和网卡确定
- M3：A2 状态与 IMU 接入完成  
  输出：`/robot_state /imu/data /odom`
- M4：MID360 点云接入完成  
  输出：`/mid360/points`
- M5：SLAM 建图完成  
  输出：真实地图
- M6：地图保存/加载完成  
  输出：地图版本目录
- M7：定位完成  
  输出：稳定 `localization_ok`
- M8：Nav2 闭环完成  
  输出：目标点导航闭环
- M9：自动建图闭环完成  
  输出：自动探索和自动保存
- M10：安全与稳定性验收完成  
  输出：验收记录和日志包

## 现阶段交付结论

- 已交付：
  完整 ROS 2 工作空间、15 个包、mock/real 双模式接口、配置模板、launch、脚本、自检工具、运维脚本和正式交付文档。
- 尚需真机验证：
  A2 实机 DDS、MID360 真驱动、真实 3D SLAM 外部栈、Nav2 参数调优。
- 这不是“空洞方案文档”：
  代码、配置、launch、脚本和文档已经在同一工作空间内对齐，可直接继续进入真机阶段。
