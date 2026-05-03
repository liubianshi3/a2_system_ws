# Agent Work Log

## Session metadata

- Date: 2026-04-27
- Repository: /home/dell/a2_system_ws
- Branch: master
- Agent: GPT-5 Codex
- Conversation/session: Unitree internal SLAM single-lidar hotfix preparation
- Log file: `agent-logs/2026-04-27-agent-session.md`

---

## Entry 1 — Initial request

### User request
用户要求先给出一个用于“把 Unitree 内部 `navigation_mapping_node` 改成直接吃 `/unitree/slam_lidar/points1`”的 prompt，然后开始实际修改。

### Plan
先基于已排查出的内部 SLAM 结论，准备一段清晰的热修复 prompt；随后优先做“第一种方案”的本地落地：新增一个可回退的热修复脚本，用于在 SSH 恢复后备份并修改机器人本体上的 `navigation_mapping.py`，把默认输入点云切到 `points1`，再重启 `unitree_slam.service` 并验证订阅是否切换成功。

### Reasoning
当前最短路径不是继续改融合链，而是直接把下游 `navigation_mapping_node` 从旧 `/rslidar_points` 切到当前唯一稳定在线的 `/unitree/slam_lidar/points1`。由于刚刚出现了机器人 SSH 链路中断，先把热修复动作固化为本地脚本，比继续口头描述更可靠。

---

## Entry 2 — Connectivity failure and fallback

### Time
2026-04-27 14:15 CST

### Action taken
尝试从本机再次连接 `a2` 抓取远端 `navigation_mapping.py` 并开始热修复，但连接失败。随后确认本机到 `192.168.31.49` 已经不通，因此切换为“先在本地准备热修复脚本”的方案。

### Tool or method used
- `ssh a2`
- `scp a2:/home/unitree/graph_pid_ws/bin/tools/py-planner/navigation_mapping.py ...`
- `ping -c 2 192.168.31.49`
- `ssh -G a2`
- `ip route`

### Why this approach
当前失败类型是网络层 `No route to host`，不是认证失败，也不是代码错误。在这种情况下继续硬试远端改动没有意义，最有效的做法是把热修复过程脚本化，等链路恢复后直接执行。

### Problems encountered
`ssh a2` 和 `scp a2:...` 都失败，错误为 `No route to host`。`ping 192.168.31.49` 也 100% 丢包，说明机器人当前从本机不可达。

### Fixes applied
放弃当前回合对远端文件的直接热改，转为在本地仓库中新增脚本 `scripts/hotfix_unitree_navigation_mapping_points1.sh`，把热修复流程固化下来。

### Current result
已确认：当前只能先准备本地脚本，不能直接修改机器人上的 `navigation_mapping.py`。

### Remaining risks or follow-ups
需要在网络恢复后实际运行脚本，验证 `navigation_mapping_node` 的订阅 topic 是否从 `/rslidar_points` 切换到 `/unitree/slam_lidar/points1`。

---

## Entry 3 — Local hotfix script creation

### Time
2026-04-27 14:20 CST

### Action taken
在仓库 `scripts/` 下新增热修复脚本，内容包括：
- 备份远端 `navigation_mapping.py`
- 下载到本地临时目录
- 自动打补丁，把点云输入改成参数化的 `pointcloud_topic`
- 默认值切到 `/unitree/slam_lidar/points1`
- 增加启动日志输出当前点云输入 topic
- 回传远端
- 可选重启 `unitree_slam.service`
- 输出运行后的 ROS2 订阅验证信息

### Tool or method used
使用 `apply_patch` 新增：
- `scripts/hotfix_unitree_navigation_mapping_points1.sh`
- 本日志文件

### Why this approach
相较于一次性手改远端文件，脚本化方案更适合当前状态：
- 可回退：先自动备份远端原文件
- 可重复：网络恢复后可直接重跑
- 可诊断：执行后会输出订阅验证信息
- 可扩展：后续如需切到别的 topic，只需传参数或继续改脚本

### Problems encountered
当前还不能对远端真实执行，因此暂时不能验证热修复后的运行效果。

### Fixes applied
先把脚本实现做到尽量稳健：
- `REMOTE_FILE`、`REMOTE_SERVICE`、`RESTART_SERVICE`、`SUDO_PASSWORD` 均支持环境变量覆盖
- 脚本对远端原文件先做时间戳备份
- 本地补丁逻辑具备锚点检测，避免静默改坏文件

### Current result
本地已经新增热修复脚本，待网络恢复后可直接执行。

### Remaining risks or follow-ups
需要本地做 shell 语法校验；随后在 SSH 恢复后真实跑脚本并验证。

---

## Entry 4 — Script validation

### Time
2026-04-27 14:25 CST

### Action taken
为热修复脚本添加可执行权限，并完成本地 shell 语法检查。

### Tool or method used
- `chmod +x scripts/hotfix_unitree_navigation_mapping_points1.sh`
- `bash -n scripts/hotfix_unitree_navigation_mapping_points1.sh`

### Why this approach
在远端暂时不可达的情况下，本地至少要确保脚本本身是可执行、可解析的，避免链路恢复后再因为语法错误浪费时间。

### Problems encountered
None

### Fixes applied
None

### Current result
脚本已具备执行权限，`bash -n` 返回 `syntax_ok`。

### Remaining risks or follow-ups
仍需等待 SSH 网络恢复后，对机器人本体真实执行并验证订阅链路切换效果。

---

## Entry 5 — Remote hotfix execution

### Time
2026-04-27 14:54 CST

### Action taken
在 `ssh a2` 恢复后，直接执行本地热修复脚本，把机器人本体 `/home/unitree/graph_pid_ws/bin/tools/py-planner/navigation_mapping.py` 的默认点云输入改为参数化的 `pointcloud_topic`，并将默认值设置为 `/unitree/slam_lidar/points1`。随后重启 `unitree_slam.service`，验证订阅是否切换成功。

### Tool or method used
- `ssh a2 'sudo -n true'`
- `ssh a2 'ros2 node info /navigation_mapping_node'`
- `./scripts/hotfix_unitree_navigation_mapping_points1.sh a2`
- `ssh a2 'grep -n "pointcloud_topic|points1|rslidar_points" .../navigation_mapping.py'`
- `ssh a2 'systemctl status unitree_slam.service'`
- `ssh a2 'ros2 node info /navigation_mapping_node'`
- `ssh a2 'ros2 topic info /rslidar_points'`
- `ssh a2 'ros2 topic info /unitree/slam_lidar/points1'`
- `ssh a2 'ros2 topic hz /unitree/slam_lidar/points1'`

### Why this approach
热修脚本已经本地准备完毕，当前远端 `sudo` 也确认免密，因此直接执行脚本比手动远端编辑更稳、更可回退。

### Problems encountered
热修脚本运行过程中返回了 SSH 级别退出码 `255`，但实际输出已经显示 `Patched navigation_mapping.py`。说明脚本后半段的某次 SSH 会话在服务重启窗口中断开了，但不影响补丁本体已经落地。

### Fixes applied
放弃依赖脚本尾部的自动验证，改为手动分步核查远端状态，包括：
- 文件内容
- `unitree_slam.service` 运行状态
- `navigation_mapping_node` 当前订阅
- 点云话题发布状态

### Current result
远端热修已成功落地：

- 远端原文件备份已生成：
  - `/home/unitree/graph_pid_ws/bin/tools/py-planner/navigation_mapping.py.bak-2026-04-27-145437`
- `navigation_mapping.py` 中已新增：
  - `self.declare_parameter('pointcloud_topic', '/unitree/slam_lidar/points1')`
  - `self.pointcloud_topic = self.get_parameter('pointcloud_topic').value`
  - 订阅器改为 `PointCloud2, self.pointcloud_topic, ...`
  - 启动日志新增 `点云输入 topic: /unitree/slam_lidar/points1`
- `unitree_slam.service` 当前状态为 `active (running)`
- `navigation_mapping_node` 已不再订阅 `/rslidar_points`
- `navigation_mapping_node` 现在明确订阅：
  - `/unitree/slam_lidar/points1`
- `/unitree/slam_lidar/points1` 当前仍有约 `10Hz` 的真实点云
- `/rslidar_points` 当前仍存在 topic 名，但 `Publisher count: 0`、`Subscription count: 2`

### Remaining risks or follow-ups
虽然输入点云已经切到单雷达 `points1`，但 `navigation_mapping_node` 仍报：

- `加载全局地图失败: /home/unitree/grid_nav/map_/map.yaml`

这说明“订阅错链”问题已经解决，但内部 SLAM/导航链仍有地图路径或地图模式配置问题，不能据此直接宣称整套建图导航完全恢复。

---

## Entry 6 — ROS1 Docker coexistence check

### Time
2026-04-27 15:00 CST

### User request
用户补充说明机器人当前还有一个 ROS1 Docker，希望先确认这件事与当前链路的关系。

### Action taken
检查了机器人上的 Docker 容器、Docker 网络、宿主进程和当前 ROS2 图，确认 ROS1 容器确实仍在运行，但宿主机当前主链路已经是单独的 ROS2 `unitree_slam.service`。

### Tool or method used
- `docker ps`
- `docker network ls`
- `ip addr show docker0`
- `ip addr show docker1`
- `ps -eo ... | grep -Ei "roscore|roslaunch|rosmaster|docker|ros1"`
- `ros2 node list`
- `ros2 topic list`

### Why this approach
需要区分“有一个叫 docker1 的网卡”与“有一个 ROS1 Docker 容器在跑”这两种不同情况，避免误判故障来源。

### Problems encountered
None

### Fixes applied
None

### Current result
当前状态为：

- 没有 `docker1` 网卡
- 存在 `docker0`
- 存在 Docker bridge 网络 `robot_default`
- 有一个 ROS1 容器在跑：
  - 容器名：`festive_johnson`
  - 镜像：`registry.cn-guangzhou.aliyuncs.com/z_nav/x_nav_mj_release:2.2`
- 宿主机可见 ROS1 相关进程：
  - `roslaunch x_nav_control run.launch`
  - `rosmaster --core -p 11311`
  - `foxglove_bridge`
  - `a2_ros1_sdk`
- 当前宿主 ROS2 主链仍在运行：
  - `/navigation_mapping_node`
  - `/point_cloud_fusion`
  - `/hesai_ros_driver_node`
  - `/new_dwa_controller`
- 当前 ROS2 图里同时可见：
  - `/rslidar_points`
  - `/unitree/slam_lidar/points1`

结论：

- 机器人上确实还有一个旧 ROS1 Docker 栈在并行运行
- 但我们刚完成的宿主 ROS2 热修复已经不再依赖 `/rslidar_points`
- 当前单雷达主链真正依赖的是 `/unitree/slam_lidar/points1`

### Remaining risks or follow-ups
ROS1 Docker 现在最大的风险不是“直接把宿主 ROS2 点云链抢走”，而是：

- 继续占 CPU / 内存
- 继续保留旧 `/rslidar_points` 语义，造成排障混淆
- 可能与后续端口、桥接或 Web 可视化形成干扰

如果后续要做运行环境收口，建议把 ROS1 Docker 单独停掉并重新核查宿主 ROS2 图，但这一步不应与当前单雷达热修复混在一起做。

---

## Entry 7 — ROS1 container codebase reuse analysis

### Time
2026-04-27 15:10 CST

### User request
用户要求分析 ROS1 容器内部代码，判断其中“扫图、建图、用图”的思路和代码，哪些对当前 `a2_system_ws` 有价值。

### Action taken
检查了 ROS1 容器 `festive_johnson` 的工作区结构、主 launch、Web 控制脚本、A2 SDK 桥接代码、`x_nav` 配置、地图资产目录和运行模式，区分“上层流程源码”和“底层闭源二进制”。

### Tool or method used
- `docker inspect festive_johnson`
- `find /catkin_ws/src/...`
- `sed -n` 查看：
  - `/catkin_ws/src/x_nav_control/launch/run.launch`
  - `/catkin_ws/src/x_nav_control/scripts/robot_web_controller.py`
  - `/catkin_ws/src/x_nav_control/scripts/extra.py`
  - `/catkin_ws/src/x_nav_control/scripts/nav_demo.py`
  - `/catkin_ws/src/x_nav_control/scripts/task.py`
  - `/catkin_ws/src/a2_ros1_sdk/src/a2_ros1_sdk.cpp`
  - `/catkin_ws/src/a2_ros1_sdk/include/a2_ros1_sdk.h`
  - `/nav_map/x_nav.yaml`
  - `/catkin_ws/src/x_nav/srv/nav_function.srv`
- `find /nav`

### Why this approach
用户不是要继续跑 ROS1，而是要判断哪些遗产值得迁移。为此必须先区分：
- 是否有算法源码
- 是否只是封装层/流程层
- 地图和导航点的存储格式是什么
- 机器人控制桥是否能提供现成经验

### Problems encountered
容器里的核心 `x_slam` / `x_planner` / `w_nav` 不是源码包，而是外部二进制，因此无法直接审计其内部算法实现。

### Fixes applied
通过 `x_nav.yaml` 中的运行模式参数和 `/nav` 目录内容交叉确认：

- `planner_run: false`
- `slam_run: false`
- `/nav/x_slam`
- `/nav/x_planner`
- `/nav/w_nav`

因此当前容器的核心 SLAM/Planner 实现属于闭源或至少非当前源码树内实现。

### Current result
结论如下。

1. **不能直接复用的部分**

- 真正的 SLAM / Planner 核心：
  - `/nav/x_slam`
  - `/nav/x_planner`
  - `/nav/w_nav`
- 这些是大体量二进制，不在 `catkin_ws/src` 中。
- 因此不能指望“直接读源码搬进 ROS2”。

2. **值得复用的思路和接口层**

- `x_nav_control/scripts/robot_web_controller.py`
  - 是一层进程编排器和 Web 控制器。
  - 负责按模式启动/停止 SLAM、Planner、SDK、Web、Foxglove 等进程。
  - 有清晰的 `start_slam()` / `start_planner()` / `auto_run()` 结构。

- `x_nav_control/scripts/extra.py`
  - 这部分很有价值。
  - 它已经把“建图/保存地图/保存导航点/读取地图数据/点选导航/多点导航/虚拟障碍物”整理成 HTTP API + service 调用。
  - 关键命令包括：
    - `save_map`
    - `save_nav_msgs`
    - `get_map`
    - `get_ground`
    - `get_obs_pc`
    - `get_navpoint`
    - `add_nav_point`
    - `add_virtual_obs`
    - `nav_point`
    - `nav_line`
    - `multi_nav`

- `x_nav/srv/nav_function.srv`
  - 这是一个很适合借鉴的“统一导航服务接口”。
  - 用一套 service 封装多种命令：
    - `cmd`
    - `set_value_string`
    - `set_value_float32`
    - `set_value_int32`
    - pose 参数
    - `no_align`
  - 对当前 ROS2 系统而言，这种“统一任务接口”比零散 topic 更适合做上层自动任务与 Web 控制。

- `x_nav_control/scripts/nav_demo.py`
  - 展示了旧系统如何做：
    - `initialpose`
    - `/topological_path`
    - `web_cmd` 的 stop / continue
  - 这里的代码不该原样迁移，但“多点任务过程中插入停靠任务/恢复导航”的流程值得借。

- `x_nav_control/scripts/task.py`
  - 这部分是任务调度器，支持任务列表、定时任务、地图切换、多点导航和异常回调。
  - 对你后面要做“自动导航 + 自动扫图 + 自动闭环验证”非常有参考价值。

- `a2_ros1_sdk`
  - 这部分不是建图算法，但很值得看。
  - 它已经把 Unitree SDK 状态桥成 ROS：
    - 发布 IMU
    - 发布 `dog_odom`
    - 发布电量
    - 处理 `web_cmd`
    - 接收 `cmd_vel`
    - 做 `Nav stop` / `Nav continue` 的运动门控
  - 这些“机器人控制门控”和“状态桥接”思路对你现在的 ROS2 `a2_control_bridge` / `a2_system` 有直接参考价值。

3. **值得复用的数据格式**

- `/home/unitree/nav_map/<map_name>/` 下保留了非常有价值的资产格式：
  - `global_map.pcd`
  - `global_ground_map.pcd`
  - `nav_points.txt`
  - `obs_points.txt`
  - `poses_lidar.txt`
  - `poses_localization.txt`
  - `imu_to_base.txt`
  - 以及下采样版本地图
- 这说明旧系统不是只保存一张 `map.yaml`，而是把：
  - 全局点云
  - 地面点云
  - 导航点
  - 障碍点
  - 轨迹/位姿
  一起保存。
- 这套“地图资产目录设计”非常值得在当前 ROS2 系统中借鉴。

4. **不值得直接继承的包袱**

- ROS1 `roscore` / `roslaunch` / `web_cmd` 字符串协议
- 旧 topic 假设：
  - `/rslidar_points`
  - `/livox/lidar`
  - `/livox/imu`
- `x_nav.yaml` 中仍有明显的旧传感器和旧机型耦合
- 当前 A2 真机实际主链已经是宿主 ROS2 + Hesai + 单雷达 `points1`，继续把这些 ROS1 topic 语义搬进新系统会制造更多历史债

### Remaining risks or follow-ups
最值得做的不是“整体复活 ROS1 容器”，而是选择性提取：

- 统一任务/服务接口设计
- 地图资产目录结构
- Web/API 行为模型
- A2 SDK 状态桥和安全门控思路

不建议把以下内容当成迁移目标：

- `x_slam` 算法本体
- `x_planner` 算法本体
- ROS1 运行时和旧 topic 语义

如果后续用户需要，我可以继续做一份“ROS1 容器遗产到 `a2_system_ws` 的迁移清单”，按：
- 可直接照搬
- 需要 ROS2 重写
- 只能参考思路
- 应明确放弃
四类列出来。

---

## Entry 8 — ROS2 task-layer design and scope lock

### Time
2026-04-27 16:05 CST

### User request
用户要求把 ROS1 容器里最有价值的几层迁移为 ROS2 可用并融入现有 `a2_system_ws`：

- `robot_web_controller.py`
- `extra.py`
- `nav_function.srv`
- `task.py`
- `a2_ros1_sdk`

### Action taken
对本地 ROS2 代码现状做对位，确认已有的骨架包括：

- `map_manager`：地图保存/加载/提升/模式切换
- `goal_bridge`：高层目标到 `NavigateToPose`
- `auto_scan_mission.py`：路点任务执行、验证和 Markdown/JSON/CSV 报告
- `web_console/backend/stack_control.py`：已有基础进程编排

据此决定不再复制一套“ROS1 风格总控”，而是在现有实现之上新增统一命令层和任务管理层。

### Tool or method used
- `sed -n` 检查：
  - `src/map_manager/map_manager/map_manager_node.py`
  - `src/nav2_integration/nav2_integration/goal_bridge.py`
  - `src/slam_manager/slam_manager/slam_orchestrator.py`
  - `src/a2_system/scripts/auto_scan_mission.py`
  - `web_console/backend/main.py`
  - `web_console/backend/ros_bridge.py`
  - `web_console/backend/stack_control.py`
- `rg -n` 检查现有接口、话题、动作、测试覆盖

### Why this approach
用户要的是“融合”，不是“并存两套系统”。当前 ROS2 里已经有：

- 地图服务
- 模式服务
- Nav2 动作桥
- Web 控制台
- 路点任务执行器

最小且正确的工业化路径，是补一层统一命令/任务入口，把这些已有模块收口，而不是另起一个平行系统。

### Problems encountered
None

### Fixes applied
None

### Current result
确定了这次迁移的核心边界：

1. 不碰闭源 `x_slam` / `x_planner`
2. 不恢复 ROS1 runtime
3. 不依赖当前会崩堆的 `a2_control_bridge`
4. 先落地：
   - 统一 ROS2 service
   - route 资产目录
   - 任务管理节点
   - bringup 集成
   - web 状态接入

### Remaining risks or follow-ups
- 暂未把 route CRUD / route run 能力直接接入现有 Web 按钮
- `a2_ros1_sdk` 中的运动门控思路只做了范围规避，未直接并入崩溃中的控制桥

---

## Entry 9 — Unified NavCommand service and task manager implementation

### Time
2026-04-27 16:35 CST

### Action taken
新增并接入了以下 ROS2 能力：

1. `a2_interfaces/srv/NavCommand.srv`
   - 作为 ROS2 版统一命令接口
   - 承载：
     - 地图命令
     - 单点导航
     - 取消导航
     - 初始位姿
     - route 资产 CRUD
     - route 任务启动/停止/状态

2. `src/a2_system/scripts/task_manager.py`
   - 新增 `task_manager` 节点
   - 暴露 `/a2/task_manager/command`
   - 暴露 `/a2/task_manager/status`
   - 暴露 `/a2/task_manager/report`
   - 直接包装：
     - `/map_manager/manage_map`
     - `/map_manager/set_mode`
     - `/navigate_to_pose`
     - `/initialpose`
   - 管理 `${A2_WORKSPACE}/runtime/routes`
   - 使用子进程复用 `auto_scan_mission.py`，而不是复制第二套路点任务逻辑

3. bringup 集成
   - 在 `a2_bringup/launch/bringup.launch.py` 中新增 `task_manager`
   - 新增 `src/a2_system/config/task_manager.yaml`

4. Web 状态接入
   - `web_console` 新增 `task_manager_status_topic`
   - `RobotStatus` 新增 `task_manager_status`
   - 前端状态侧栏显示 `task mgr`

5. 文档更新
   - `src/a2_system/docs/interface_contracts.md`
   - `src/a2_system/docs/task_manager.md`

### Tool or method used
- `apply_patch`
- 变更文件：
  - `src/a2_interfaces/srv/NavCommand.srv`
  - `src/a2_interfaces/CMakeLists.txt`
  - `src/a2_interfaces/package.xml`
  - `src/a2_system/scripts/task_manager.py`
  - `src/a2_system/config/task_manager.yaml`
  - `src/a2_system/CMakeLists.txt`
  - `src/a2_system/package.xml`
  - `src/a2_bringup/launch/bringup.launch.py`
  - `src/a2_system/docs/interface_contracts.md`
  - `src/a2_system/docs/task_manager.md`
  - `web_console/backend/config.py`
  - `web_console/backend/config.example.yaml`
  - `web_console/backend/config.docker.yaml`
  - `web_console/backend/models.py`
  - `web_console/backend/ros_bridge.py`
  - `web_console/frontend/src/types.ts`
  - `web_console/frontend/src/components/StatusSidebar.tsx`

### Why this approach
这是对 ROS1 `nav_function.srv + extra.py + task.py` 价值最高的迁移：

- 用统一 service 取代零散 topic 命令
- 用 route 目录取代临时 YAML 四处散落
- 用 `task_manager` 编排 `auto_scan_mission.py`
- 避免复制已有的任务执行、报告生成和地图验证逻辑

### Problems encountered
初版 `task_manager` 服务回调里同步等待 action/service 响应，存在死锁风险：

- 默认单线程 executor
- 默认 mutually-exclusive callback group
- 服务回调阻塞后，客户端 future 回调可能无法被调度

### Fixes applied
对 `task_manager.py` 做并发模型修正：

- 引入 `ReentrantCallbackGroup`
- 给 service/client/action client 显式绑定 reentrant callback group
- `main()` 改为 `MultiThreadedExecutor(num_threads=4)`

### Current result
新的任务管理层已经具备以下本地可用能力：

- 统一命令接口
- route YAML 解析与归一化
- route 文件存取
- 直接单点导航
- 取消导航
- 初始位姿发布
- 复用 `auto_scan_mission.py` 启停 route 任务
- Web 侧看到 task manager 状态

### Remaining risks or follow-ups
- `run_route` 目前还未接 Web 按钮，只完成了 ROS2 service 层和状态层
- route 子进程 stdout/stderr 当前未单独落日志文件
- 虚拟障碍物和旧 `nav_points.txt` 资产结构还未迁移

---

## Entry 10 — Verification, build, and test hardening

### Time
2026-04-27 17:05 CST

### Action taken
对新增改动执行了：

- Python 编译检查
- 选择性包构建
- 单元测试
- Web 合同测试
- 配置 schema 检查
- 导航合同检查

### Tool or method used
- `python3 -m py_compile ...`
- `colcon build --packages-select a2_interfaces a2_system a2_bringup --symlink-install`
- `python3 -m pytest ...`
- `ros2 run a2_system nav_contract_check.py`
- `python3 src/a2_system/scripts/config_schema_check.py`

### Why this approach
这次改动同时触及：

- ROS interface 生成
- Python 脚本安装
- launch 集成
- Web backend/frontend 类型

所以必须至少覆盖：
- 语法层
- 接口构建层
- 单元测试层
- 工程合同层

### Problems encountered
1. 本地 `pytest` 可执行文件不存在
2. 系统 pytest 与用户目录中的 `anyio` pytest 插件版本冲突，导致：

`ModuleNotFoundError: No module named '_pytest.scope'`

3. 在未 source 本地 `install/setup.bash` 前，测试导入不到新生成的 `a2_interfaces`

### Fixes applied
1. 改用 `python3 -m pytest`
2. 使用：

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`

禁用外部插件自动加载
3. 先执行 `colcon build`，再 source：

- `/opt/ros/humble/setup.bash`
- `/home/dell/a2_system_ws/install/setup.bash`

### Current result
验证结果如下：

- `python3 -m py_compile`：通过
- `colcon build --packages-select a2_interfaces a2_system a2_bringup --symlink-install`：通过
- `test_task_manager.py + test_auto_scan_mission.py`：`9 passed`
- `web_console/backend/test/test_web_contracts.py`：`2 passed`
- `config_schema_check.py`：`PASS`
- `nav_contract_check.py`：`PASS`

### Remaining risks or follow-ups
- 这些验证仍然是本地/离线级别，尚未覆盖真机下 `/a2/task_manager/command` 的现场调用
- `task_manager` 还没现场验证是否能在真机上成功拉起 `auto_scan_mission.py` 子进程并产生报告

---

## Final outcome

### Summary
今天这轮工作在保留前面 Unitree 本体单雷达热修的基础上，又把 ROS1 容器里最值得迁移的“统一命令层 + 任务编排层 + route 资产层”正式落进了当前 ROS2 架构。

现在本地代码新增了：

- ROS2 统一命令接口：`a2_interfaces/srv/NavCommand.srv`
- 任务管理节点：`task_manager.py`
- route 资产目录：`${A2_WORKSPACE}/runtime/routes`
- bringup 自动接入 `task_manager`
- Web 侧的 `task_manager` 状态展示

这意味着当前 `a2_system_ws` 已经不只是“能点导航、能扫图脚本单独跑”，而是开始具备一层更像工业系统的统一任务入口。

### Files changed
- `agent-logs/2026-04-27-agent-session.md`
- `scripts/hotfix_unitree_navigation_mapping_points1.sh`
- `src/a2_interfaces/CMakeLists.txt`
- `src/a2_interfaces/package.xml`
- `src/a2_interfaces/srv/NavCommand.srv`
- `src/a2_system/CMakeLists.txt`
- `src/a2_system/package.xml`
- `src/a2_system/config/task_manager.yaml`
- `src/a2_system/docs/interface_contracts.md`
- `src/a2_system/docs/task_manager.md`
- `src/a2_system/scripts/task_manager.py`
- `src/a2_system/test/test_task_manager.py`
- `src/a2_bringup/launch/bringup.launch.py`
- `web_console/backend/config.py`
- `web_console/backend/config.example.yaml`
- `web_console/backend/config.docker.yaml`
- `web_console/backend/models.py`
- `web_console/backend/ros_bridge.py`
- `web_console/frontend/src/components/StatusSidebar.tsx`
- `web_console/frontend/src/types.ts`

### Commands run
- `docker inspect festive_johnson`
- `find /catkin_ws/src ...`
- `sed -n ...`
- `rg -n ...`
- `python3 -m py_compile ...`
- `colcon build --packages-select a2_interfaces a2_system a2_bringup --symlink-install`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest ...`
- `python3 /home/dell/a2_system_ws/src/a2_system/scripts/config_schema_check.py`
- `ros2 run a2_system nav_contract_check.py`
- 以及此前的远端热修和 SSH 检查命令

### Verification
- 远端 Unitree 内部 SLAM 热修验证：已完成
  - `navigation_mapping_node` 已改吃 `/unitree/slam_lidar/points1`
- 本地 Python 编译检查：通过
- 本地选择性构建：
  - `a2_interfaces`
  - `a2_system`
  - `a2_bringup`
  全部通过
- 本地任务与 mission 单测：`9 passed`
- Web 合同测试：`2 passed`
- 配置 schema 检查：`PASS`
- 导航合同检查：`PASS`

### Known limitations
- 还没有在真机上实际调用 `/a2/task_manager/command` 做现场闭环
- `task_manager` 的 route 启停能力还没接到现有 Web 控制按钮
- route 子进程日志目前未单独归档
- 虚拟障碍物、导航点资产、旧 `nav_points.txt/obs_points.txt` 兼容层尚未实现
- `a2_control_bridge` 仍保持关闭，因为当前接 SDK 会触发堆内存崩溃
- Unitree 本体内部自带 SLAM 仍有地图路径问题：`/home/unitree/grid_nav/map_/map.yaml`

---

## Entry 8 — Real reproduction readiness audit

### Time
2026-04-27 15:45 CST

### Action taken
针对“现在开始真实复现”的要求，检查了当前 `a2_system_ws` 的实机入口链，重点覆盖：
- hardware assumption
- localization
- Nav2 planner/controller
- configuration
- web/bringup entrypoint

核查内容包括：
- `README_A2_Quickstart.md`
- `operations_runbook.md`
- `bringup.launch.py`
- `localization.launch.py`
- `nav2.launch.py`
- `sensors.launch.py`
- `preflight_check.py`
- `real_lidar.yaml`
- `pointcloud_to_scan.yaml`
- `nav2_stack.yaml`
- `start_real_stack.sh`

### Tool or method used
- `sed -n`
- `rg -n`
- `git status --short --branch`
- `readlink -f`

### Why this approach
真实复现第一步不是直接上机器人乱起栈，而是先确认当前仓库的默认入口是否还残留旧的 `manual_odom` 假设，以及前雷达单链、AMCL、Nav2 的合同是否一致。

### Problems encountered
发现一个会直接影响实机复现路径的入口级冲突：

- 运行手册和工程规则要求真实默认定位模式是 `amcl`
- 但 `src/a2_system/tools/start_real_stack.sh` 仍把 `A2_REAL_LOCALIZATION_MODE` 默认值写成了 `manual_odom`

同时发现 `README_A2_Quickstart.md` 中“启动成功后的预期进程”仍把 `manual_localization_publisher` 当成默认成功信号，容易把真实复现带回旧链路。

### Fixes applied
本步骤先完成审计与问题定位，下一步对真实启动脚本、合同检查和快启文档做最小修正。

### Current result
已确认当前真实链路本体是正确的：

- 实机点云入口：`/unitree/slam_lidar/points1`
- 中继输出：`/mid360/points`
- Nav2 激光输入：`/scan`
- 定位状态输入：`/amcl_pose`

问题集中在默认入口和值班文档，而不是 Nav2/AMCL 配置本体。

### Remaining risks or follow-ups
需要把默认入口修回 `amcl`，并把该约束加入离线合同检查，避免后续再次回退。

---

## Entry 9 — Real entrypoint hardening

### Time
2026-04-27 15:50 CST

### Action taken
执行了三类硬化修改：

- 把 `start_real_stack.sh` 的默认 `A2_REAL_LOCALIZATION_MODE` 从 `manual_odom` 改为 `amcl`
- 扩展 `nav_contract_check.py`，要求真实启动脚本默认必须是 `amcl`
- 修正 `README_A2_Quickstart.md` 的成功判据，改为默认应看到 `amcl`，并显式说明 `manual_localization_publisher` 只应出现在手动覆盖场景

### Tool or method used
- `apply_patch`
- 代码审阅对照：
  - `src/a2_system/tools/start_real_stack.sh`
  - `src/a2_system/scripts/nav_contract_check.py`
  - `readme/README_A2_Quickstart.md`

### Why this approach
这次目标是“开始真实复现”，因此优先修入口级默认值和合同约束，比先动底层导航参数更重要，也更小、更安全、可立即验证。

### Problems encountered
None

### Fixes applied
- 默认定位模式修正为 `amcl`
- 新增脚本级合同检查，防止未来被旧默认值回退
- 文档成功判据与当前工业规则对齐

### Current result
当前仓库的真实启动默认语义已与工程规则对齐：

- 默认真实定位：`amcl`
- 默认真实雷达：前雷达单链 `points1`
- 默认真实 Nav2 路径：`/scan` + `/amcl_pose` + `/map`

### Remaining risks or follow-ups
还需要跑离线合同检查，确认修改没有引入脚本级或文档级回归；随后再给出真实复现的最短执行顺序。

---

## Entry 10 — Offline verification for real reproduction path

### Time
2026-04-27 15:54 CST

### Action taken
对本轮实机入口硬化做了离线验证，确认脚本、合同检查和相关 launch 文件没有语法或合同回归。

### Tool or method used
- `python3 -m py_compile /home/dell/a2_system_ws/src/a2_system/scripts/nav_contract_check.py /home/dell/a2_system_ws/src/a2_bringup/launch/bringup.launch.py /home/dell/a2_system_ws/src/a2_bringup/launch/localization.launch.py /home/dell/a2_system_ws/src/a2_bringup/launch/nav2.launch.py`
- `bash -n /home/dell/a2_system_ws/src/a2_system/tools/start_real_stack.sh /home/dell/a2_system_ws/src/a2_system/tools/start_real1_suite.sh`
- `python3 /home/dell/a2_system_ws/src/a2_system/scripts/config_schema_check.py`
- `python3 /home/dell/a2_system_ws/src/a2_system/scripts/nav_contract_check.py`

### Why this approach
“开始真实复现”前，至少要先证明：

- 默认入口脚本可解析
- launch/检查脚本可解析
- 配置合同仍然成立
- 新增的“默认 AMCL”约束已经被检查脚本覆盖

### Problems encountered
None

### Fixes applied
None

### Current result
离线验证结果全部通过：

- `py_compile`：通过
- `bash -n`：通过
- `config_schema_check.py`：`PASS`
- `nav_contract_check.py`：`PASS`

### Remaining risks or follow-ups
这仍然只是本地/离线级验证，尚未实际在 A2 真机上执行：

- `deploy_to_a2.sh`
- `start_real_stack.sh`
- `/a2/real/report`
- `/a2/localization/status`
- `NavigateToPose`

---

## Final outcome update

### Summary
本轮围绕“现在开始真实复现”完成了入口级审计和最小硬化。当前仓库已经把真实默认路径重新固定为：

- 前雷达单链 `points1`
- `/mid360/points -> /scan`
- `AMCL -> /amcl_pose`
- Nav2 实机 bringup

同时，真实启动脚本不再默认回退到 `manual_odom`，对应合同检查也已补上。

### Files changed
- `agent-logs/2026-04-27-agent-session.md`
- `readme/README_A2_Quickstart.md`
- `src/a2_system/scripts/nav_contract_check.py`
- `src/a2_system/tools/start_real_stack.sh`

### Commands run
- `git -C /home/dell/a2_system_ws status --short --branch`
- `sed -n ...`
- `rg -n ...`
- `readlink -f /home/dell/a2_system_ws/install/a2_system/share/a2_system/start_real_stack.sh`
- `date '+%Y-%m-%d %H:%M %Z'`
- `python3 -m py_compile ...`
- `bash -n ...`
- `python3 /home/dell/a2_system_ws/src/a2_system/scripts/config_schema_check.py`
- `python3 /home/dell/a2_system_ws/src/a2_system/scripts/nav_contract_check.py`

### Verification
- `config_schema_check.py`：`PASS`
- `nav_contract_check.py`：`PASS`
- `py_compile`：通过
- `bash -n`：通过

### Known limitations
- 尚未在 A2 真机上实际启动 `real1`
- 尚未现场确认 `/scan`、`/map`、`/amcl_pose`、`/navigate_to_pose` 的在线状态
- `a2_control_bridge` 的真机稳定性风险仍需现场复核

---

## Entry 11 — A2 read-only readiness check

### Time
2026-04-27 15:58 CST

### Action taken
对别名 `a2` 的机器人做了只读检查，确认当前远端是否已经具备按新版 `real1` 路径启动的条件。

### Tool or method used
- `ssh -o BatchMode=yes -o ConnectTimeout=5 a2 'hostname; date; ...'`
- `ssh ... 'pgrep -af ...'`
- `ssh ... 'ros2 topic list ...'`
- `ssh ... 'grep -n \"A2_REAL_LOCALIZATION_MODE\" .../start_real_stack.sh'`
- `ssh ... 'systemctl is-active unitree_slam.service ...; docker ps ...'`
- `ssh ... 'ros2 node list ...'`

### Why this approach
在真正起栈前，必须先确认：

- 机器人当前是不是还在跑 Unitree 自带链路
- 远端工作区是不是已经拿到新版默认 `amcl`
- 是否已经有 `/map`、`/scan`、`/amcl_pose` 这类 `real1` 关键接口在线

### Problems encountered
发现三个实机复现阻塞项：

1. 远端 `/home/unitree/a2_system_ws/install/a2_system/share/a2_system/start_real_stack.sh` 仍是旧版本：
   - `A2_REAL_LOCALIZATION_MODE:-manual_odom`
2. `unitree_slam.service` 当前为 `active`
3. 当前在线节点仍是 Unitree 内建链：
   - `/navigation_mapping_node`
   - `/point_cloud_fusion`
   - `/hesai_ros_driver_node`

同时，`ros2 topic list` 未见：

- `/map`
- `/scan`
- `/amcl_pose`
- `/a2/real/report`
- `/a2/localization/status`
- `/navigate_to_pose`

### Fixes applied
本步骤未直接修改远端，只完成状态确认。避免在旧栈仍在线、远端脚本仍旧版时直接强起 `real1`。

### Current result
结论很明确：

- 本地仓库已经适合开始真实复现
- 远端 A2 还没有切到这套新版默认入口
- 现在直接在 A2 上起 `real1`，会混入旧 `manual_odom` 默认值和 Unitree 自带 SLAM 干扰

### Remaining risks or follow-ups
真实复现前至少还要完成三步：

1. 从本机把当前工作区部署到 A2
2. 在 A2 上停掉 `unitree_slam.service` 和旧干扰栈
3. 再用新版 `start_real_stack.sh` 起 `real1`

---

## Entry 12 — Remote real-entrypoint correction and interference cleanup

### Time
2026-04-27 15:50 CST

### User request
用户要求直接处理远端阻塞项：

- 把远端 `start_real_stack.sh` 的旧默认值 `manual_odom` 改掉
- 关掉所有会影响真实复现的旧进程

### Plan
先在远端确认 `start_real_stack.sh` 的真实落点并做备份，然后把本地已修正的脚本同步到 A2。之后依次停掉：

- `unitree_slam.service`
- ROS1 容器 `festive_johnson`
- Unitree 内建 ROS2 点云链及残留 ROS1 进程

最后复查当前进程、服务和关键 topic，确认环境已经清场。

### Reasoning
用户要求是远端实机收口，不是继续本地离线分析。当前最小、最稳的做法是：

1. 直接同步已验证过的脚本，而不是在远端手工改一行
2. 先停 service 和 container，再做残留 `pkill`
3. 用只读复查确认清场结果，避免“看起来停了”但仍有残留进程

---

## Entry 13 — Remote start_real_stack.sh correction

### Time
2026-04-27 15:50 CST

### Action taken
已在 A2 上备份并覆盖远端真实启动脚本，把默认 `A2_REAL_LOCALIZATION_MODE` 从 `manual_odom` 改为 `amcl`。

### Tool or method used
- `ssh a2 'cp ... start_real_stack.sh.bak-<timestamp>'`
- `scp /home/dell/a2_system_ws/src/a2_system/tools/start_real_stack.sh a2:/home/unitree/a2_system_ws/src/a2_system/tools/start_real_stack.sh`
- `ssh a2 'chmod +x ...; grep -n \"A2_REAL_LOCALIZATION_MODE\" ...'`

### Why this approach
远端 `install/.../start_real_stack.sh` 已确认是软链到 `src/a2_system/tools/start_real_stack.sh`，所以同步本地已验证脚本比远端临时手改更稳，也保留了时间戳备份。

### Problems encountered
None

### Fixes applied
None

### Current result
远端当前两处入口已一致：

- `/home/unitree/a2_system_ws/src/a2_system/tools/start_real_stack.sh`
- `/home/unitree/a2_system_ws/install/a2_system/share/a2_system/start_real_stack.sh`

都已变为：

- `A2_REAL_LOCALIZATION_MODE:-amcl`

并保留了备份：

- `/home/unitree/a2_system_ws/src/a2_system/tools/start_real_stack.sh.bak-20260427_155035`

### Remaining risks or follow-ups
还需要实际停掉所有旧链路，避免修完脚本后仍被 Unitree 自带进程和 ROS1 容器干扰。

---

## Entry 14 — Remote interference shutdown

### Time
2026-04-27 15:52 CST

### Action taken
在 A2 上停掉了会影响当前真实复现的旧链路：

- `unitree_slam.service`
- ROS1 容器 `festive_johnson`
- 相关残留 ROS1/ROS2 进程

### Tool or method used
- `ssh a2 'sudo -n systemctl stop unitree_slam.service'`
- `ssh a2 'docker update --restart=no festive_johnson; docker stop festive_johnson'`
- `ssh a2 'pkill -f ...'`
- `ssh a2 'systemctl is-active ...; docker ps ...; pgrep -af ...; ros2 topic list ...'`
- `ssh a2 'sudo systemctl reset-failed unitree_slam.service'`

### Why this approach
当前旧链路来自两个方向：

- Unitree 宿主 ROS2 `unitree_slam.service`
- ROS1 Docker `festive_johnson`

必须同时处理，单停其中一个仍会留下历史 topic 语义、桥接进程或点云链残留。

### Problems encountered
中间有两次组合式 SSH 命令没有顺利返回：

- 一次退出码 `255`
- 一次退出码 `127`

这更像是长串命令在远端会话/环境切换时被打断，而不是停栈动作本身失败。

### Fixes applied
改为分步执行并逐项复查：

- 先单独停 `unitree_slam.service`
- 再单独停 `festive_johnson`
- 最后补 `pkill`
- 用 `systemctl`、`docker ps`、`pgrep`、`ros2 topic list` 分别验证
- 把 `unitree_slam.service` 从 `failed` 重置到 `inactive`

### Current result
远端当前状态：

- `unitree_slam.service`: `inactive`
- `a2-web-console.service`: `inactive`
- `festive_johnson`: 已停止，不在 `docker ps`
- 关键干扰进程已清空：
  - `navigation_mapping_node`
  - `point_cloud_fusion`
  - `hesai_ros_driver_node`
  - `roslaunch x_nav_control`
  - `rosmaster`
  - `foxglove_bridge`
  - `a2_ros1_sdk`
- 关键 `real1` topic 当前为空：
  - `/map`
  - `/scan`
  - `/amcl_pose`
  - `/a2/real/report`
  - `/a2/localization/status`
  - `/navigate_to_pose`

仍在线但未处理的容器：

- `voice-camera`
- `hik-camera-service`

这两个不属于当前导航/定位/建图干扰链，因此本轮未停。

### Remaining risks or follow-ups
下一步就可以在 A2 上按新版默认 `AMCL` 路径启动 `real1`，并现场检查：

- `/scan`
- `/map`
- `/amcl_pose`
- `/a2/real/report`
- `/navigate_to_pose`

---

## Entry 15 — User requested runbook commands only

### Time
2026-04-27 16:02 CST

### Action taken
用户要求不再由 agent 代执行，而是直接提供一组可手动运行的 `real1` 启动与验收命令。

### Tool or method used
基于当前已完成的远端清场结果和已修正的 `start_real_stack.sh` 默认值，整理最短手动执行序列。

### Why this approach
当前远端环境已经清到可启动状态，用户明确要求自己执行，因此最合适的是给出一组顺序明确、可直接复制的命令，而不是继续远端代操作。

### Problems encountered
None

### Fixes applied
None

### Current result
已切换为“提供命令，由用户手动执行”的模式。

### Remaining risks or follow-ups
待用户执行后，还需要根据：

- `/a2/real/report`
- `/a2/localization/status`
- `/scan`
- `/amcl_pose`
- `/navigate_to_pose`

的实际输出判断 `real1` 是否真正在线。

---

## Entry 16 — Web frontend access address

### Time
2026-04-27 16:04 CST

### Action taken
用户要求直接给出 Web 前端访问地址，因此提供当前仓库约定的前端 URL 和访问前提。

### Tool or method used
基于现有运行手册与当前远端 IP 约定整理访问地址，不执行远端启动。

### Why this approach
这是一个轻量信息请求，不需要继续改代码或远端操作。

### Problems encountered
当前已知 `a2-web-console.service` 处于 `inactive`，所以地址只有在服务启动后才能访问。

### Fixes applied
None

### Current result
已提供前端访问 URL。

### Remaining risks or follow-ups
如果页面打不开，需要先启动 Web 后端服务并检查 8080 端口监听状态。

---

## Entry 17 — Real1 startup diagnosis after user-run start

### Time
2026-04-27 16:10 CST

### Action taken
根据用户贴出的 `preflight_check.py`、`start_real_stack.sh` 和 ROS topic/status 输出，分析当前 `real1` 为什么处于：

- `/a2/real/report`: `state=degraded; reason=lidar_down,localization_down`
- `/a2/localization/status`: `state=waiting_pose; reason=no_pose`
- `/a2/control/status`: `state=blocked; reason=estop`

### Tool or method used
- 阅读用户提供的远端终端输出
- 本地核对：
  - `src/a2_system/config/real_lidar.yaml`
  - `src/mid360_wrapper/mid360_wrapper/pointcloud_frame_relay.py`
  - `src/mid360_wrapper/mid360_wrapper/mid360_driver_guard.py`
  - `src/localization_manager/localization_manager/localization_gate.py`
  - `src/safety_manager/safety_manager/real_readiness_monitor.py`
  - `src/safety_manager/safety_manager/safety_supervisor.py`

### Why this approach
用户已经成功把 `real1` 拉起，当前需要的是精确解释运行态，而不是继续泛化排查。

### Problems encountered
发现一个关键系统耦合：

- 当前真实配置 `real_lidar.yaml` 不是直接起 `livox_ros_driver2`
- 而是依赖外部原生点云：
  - `input_topic: /unitree/slam_lidar/points1`
  - `output_topic: /mid360/points`

因此，前面停掉 `unitree_slam.service` / 原生点云链后，`real1` 虽然启动了，但没有可转发的输入点云，导致：

- `mid360_driver_guard` 判定 `lidar=false`
- `safety_supervisor` 触发 `estop`
- `localization_gate` 一直等不到有效 `/amcl_pose`

### Fixes applied
本步骤未直接执行远端修复，只完成根因定位并整理下一步恢复顺序。

### Current result
当前状态解释如下：

- `/scan` 有 publisher，不代表有稳定激光数据流
- `lidar=false` 才是上游点云是否真正在线的权威判定
- `localization waiting_pose` 说明当前还没有有效 AMCL 位姿
- `control blocked; reason=estop` 是因为安全门控要求激光 freshness，而当前 `/mid360/points` 不新鲜

### Remaining risks or follow-ups
要让 `real1` 真正 ready，下一步需要：

1. 恢复 `/unitree/slam_lidar/points1` 的原生发布
2. 确认 `/mid360/points` 和 `/scan` 真正在出数据
3. 给 AMCL 一个初始位姿
4. 再检查 `/navigate_to_pose`

---

## Entry 18 — unitree_slam restarted but native pointcloud still missing

### Time
2026-04-27 16:14 CST

### Action taken
用户在 A2 上执行了：

- `sudo systemctl start unitree_slam.service`
- `sleep 5`
- `ros2 topic hz /unitree/slam_lidar/points1`
- `ros2 topic hz /mid360/points`
- `ros2 topic hz /scan`
- `ros2 topic echo --once /a2/lidar/status`
- `ros2 topic echo --once /a2/real/report`

并反馈：

- `WARNING: topic [/unitree/slam_lidar/points1] does not appear to be published yet`

### Tool or method used
基于用户现场终端输出继续做链路诊断，不代执行远端命令。

### Why this approach
这一步已经证明问题不在 `real1` 启动脚本本身，而是在 `unitree_slam.service` 恢复后，原生点云话题仍未恢复。

### Problems encountered
`unitree_slam.service` 启动后，`/unitree/slam_lidar/points1` 仍未发布。当前可能性收敛为：

- service 未真正 healthy
- service 内点云驱动/融合进程未拉起
- topic 名称变化
- ROS 图可见性/环境不一致

### Fixes applied
本步骤未修改系统状态，转为要求进一步采集：

- `systemctl status`
- `journalctl`
- `ros2 node list`
- `ros2 topic list`
- `ps`

### Current result
根因已进一步收敛到 Unitree 原生点云源恢复失败，而不是 `real1` 自身逻辑错误。

### Remaining risks or follow-ups
需要读取 `unitree_slam.service` 日志和当前 ROS 图，判断是：

- 驱动未起
- topic 改名
- 进程崩溃
- DDS/ROS 环境隔离

---

## Entry 19 — unitree_slam active but Hesai data path still empty

### Time
2026-04-27 16:18 CST

### Action taken
根据用户回传的 `systemctl status` 和 `journalctl`，继续定位 `unitree_slam.service` 已运行但 `/unitree/slam_lidar/points1` 仍未发布的原因。

### Tool or method used
- 分析用户回传的：
  - `systemctl status unitree_slam.service --no-pager`
  - `journalctl -u unitree_slam.service -n 120 --no-pager`
- 本地对照：
  - `src/a2_system/config/network.yaml`
  - `readme/a2_system_ws开发日志.md`

### Why this approach
这一步已经不需要继续怀疑 `real1` 脚本。关键是要区分：

- service 是否 healthy
- 驱动是否真正收到雷达数据
- 网络或驱动参数是否错配

### Problems encountered
从日志可见：

- `unitree_slam.service` 当前 `active (running)`
- `hesai_ros_driver_node` 已启动
- `point_cloud_fusion` 已启动，但明确打印 `Waiting for data...`
- `navigation_mapping_node` 已启动，且确认订阅 `/unitree/slam_lidar/points1`
- `hesai_ros_driver_node` 打印：
  - `Multicast IP error, set correct multicast ip address or keep it empty`
  - `PtcClient::PtcClient() 192.168.124.20 9347`

这说明当前故障点不在上层节点，而在 Hesai 数据接收链。最可能方向是：

- 雷达网络链路异常
- 驱动 multicast 配置错误
- 雷达本体未实际推流

### Fixes applied
本步骤未修改远端配置，先把故障面压缩到“网络/驱动”层，再要求用户采集更有判别力的链路证据。

### Current result
当前最可信结论：

- `real1` 正常起了
- `unitree_slam.service` 也正常起了
- 但 `192.168.124.20` 这条 Hesai 实时点云链没有真正喂出 ROS 点云

### Remaining risks or follow-ups
下一步应优先检查：

1. A2 到 `192.168.124.20` 的网络连通性
2. `eth0` 上是否真的收到来自 `.20` 的 UDP 点云包
3. `graph_pid_ws` 内 Hesai 配置里的 multicast 字段是否错配

---

## Entry 20 — Sensor subnet/interface conflict identified

### Time
2026-04-27 16:24 CST

### Action taken
用户回传了更关键的现场证据：

- `graph_pid_ws` Hesai 配置中的 `multicast_ip_address: 192.168.124.162`
- ROS 图里 `/unitree/slam_lidar/points1`、`points2` 话题和 publisher 仍存在
- 但 `ping 192.168.124.20` 100% 丢包
- `ip neigh show dev eth0` 对 `.20` 为 `FAILED`
- `tcpdump -ni eth0 host 192.168.124.20 and udp` 没看到数据

### Tool or method used
基于用户提供的远端输出进行网络层诊断，并对照先前接口枚举结果：

- `net1 = 192.168.124.162/24`
- `eth0` 被 `configure_real_network.sh` 额外加上了 `192.168.124.10/24`

### Why this approach
这已经不是 ROS 层问题，而是传感器子网落在哪块 NIC 上的问题。只有先确认 `.124` 子网应该走 `net1` 还是 `eth0`，后续修驱动配置才有意义。

### Problems encountered
证据显示当前很可能存在 `.124` 子网接口冲突：

- Unitree 原生 Hesai 配置指向 `192.168.124.162`
- 这个地址正好对应之前枚举到的 `net1`
- 但我们为了 `real1` 又给 `eth0` 加了 `192.168.124.10/24`
- 结果现在对 `.20` 的探测走错接口或形成歧义，现场在 `eth0` 上既 ping 不通，也抓不到 UDP

同时还有第二个明确问题：

- Hesai 配置中的 `multicast_ip_address` 不是组播地址，而是宿主单播地址 `192.168.124.162`
- 驱动日志也明确报了 `Multicast IP error`

### Fixes applied
本步骤未直接改远端配置，先给出更安全的验证顺序：

1. 验证 `net1` 是否才是真实传感器口
2. 如果是，撤掉 `eth0` 上临时加的 `192.168.124.10/24`
3. 再把 Hesai 配置中的错误 multicast 字段清空并重启 service

### Current result
当前最可信结论变为：

- 真实激光链路大概率属于 `net1`
- `configure_real_network.sh` 给 `eth0` 加入 `.124` 地址后，制造了传感器子网冲突
- `graph_pid_ws` 的 Hesai multicast 配置也存在确定性错误

### Remaining risks or follow-ups
下一步必须先验证：

- `ip route get 192.168.124.20`
- `ping -I net1 192.168.124.20`
- `tcpdump -ni net1 host 192.168.124.20 and udp`

然后才能决定是否：

- 移除 `eth0` 上的 `192.168.124.10/24`
- 清空 `multicast_ip_address`

---

## Entry 21 — net1 confirmed as the real lidar interface

### Time
2026-04-27 16:30 CST

### Action taken
用户补充执行了：

- `ip route get 192.168.124.20`
- `ping -I net1 -c 4 192.168.124.20`
- `ping -I eth0 -c 4 192.168.124.20`
- `sudo tcpdump -ni net1 host 192.168.124.20 and udp -c 20`

并返回了完整结果。

### Tool or method used
基于用户现场网络探测结果继续定位，不代执行远端命令。

### Why this approach
这是区分“驱动配置错”与“接口绑错”的关键证据层。没有这一步，很难证明 `.124` 子网到底该归 `net1` 还是 `eth0`。

### Problems encountered
结果已经明确暴露了路由/接口错绑：

- `ip route get 192.168.124.20` 当前错误地走 `eth0 src 192.168.124.10`
- `ping -I net1 192.168.124.20` 正常
- `ping -I eth0 192.168.124.20` 100% 丢包
- `tcpdump -ni net1` 明确抓到 `.20 -> 192.168.124.162:2368` 的连续 UDP 点云流

### Fixes applied
本步骤完成了根因确认，建议后续修复顺序调整为：

1. 先撤掉 `eth0` 上人为加入的 `192.168.124.10/24`
2. 再修 Hesai 配置里的错误 `multicast_ip_address`
3. 最后重启 `unitree_slam.service` 验证 `points1`

### Current result
当前最可信结论已经坐实：

- 真正的 Hesai 传感器口是 `net1`
- `eth0` 上的 `.124` 地址是人为冲突项
- 原生点云 UDP 包实际存在，但在当前错配下没有被正确转成 ROS 点云

### Remaining risks or follow-ups
需要继续完成：

- `sudo ip addr del 192.168.124.10/24 dev eth0`
- 清空 `config.yaml` 和 `config_new.yaml` 中的 `multicast_ip_address`
- 重启 `unitree_slam.service`
- 重新验证 `/unitree/slam_lidar/points1`、`/mid360/points`、`/scan`

---

## Entry 22 — Native pointcloud restored after interface/config fix

### Time
2026-04-27 16:36 CST

### Action taken
用户在修正接口与 Hesai 配置后重新执行了：

- `ros2 topic hz /unitree/slam_lidar/points1`
- `ros2 topic hz /mid360/points`
- `ros2 topic hz /scan`
- `ros2 topic echo --once /a2/lidar/status`
- `ros2 topic echo --once /a2/real/report`

当前回传输出显示 `/unitree/slam_lidar/points1` 已恢复到稳定约 `10Hz`。

### Tool or method used
基于用户现场终端输出判断链路恢复状态，不代执行远端命令。

### Why this approach
相比 `topic list` 或 `topic info`，`ros2 topic hz` 能直接证明原生点云链已经真实恢复，而不是只有 publisher 名称存在。

### Problems encountered
用户当前只贴出了 `ros2 topic hz /unitree/slam_lidar/points1` 的持续输出，说明 shell 仍停留在第一条 `hz` 命令上，后续 `/mid360/points`、`/scan`、`/a2/lidar/status`、`/a2/real/report` 还没有真正执行。

### Fixes applied
下一步不再把多个 `ros2 topic hz/echo` 连续写在一起，而是要求用户：

1. 先 `Ctrl-C` 结束当前 `hz`
2. 再逐条执行剩余验证命令

### Current result
关键恢复信号已出现：

- `/unitree/slam_lidar/points1`: 约 `10Hz`

这说明：

- `net1` 路径正确
- Hesai 原生点云已重新进入 ROS 图
- `real1` 之前的 `lidar_down` 根因已经基本解除

### Remaining risks or follow-ups
还需要继续确认：

- `/mid360/points` 是否同样稳定
- `/scan` 是否稳定
- `/a2/lidar/status` 是否 `ready=true`
- `/a2/real/report` 是否去掉 `lidar_down`
- 然后再检查 `/amcl_pose` 和 `/a2/localization/status`

---

## Entry 23 — points1 restored but relay/scan chain still unverified

### Time
2026-04-27 16:42 CST

### Action taken
用户补充回传了：

- `unitree_slam.service` 在 16:04 左右发生一次 stop/start
- `/unitree/slam_lidar/points1` 稳定约 `10Hz`
- `/mid360/points` 查询提示 `does not appear to be published yet`
- `/scan` 查询也提示 `does not appear to be published yet`
- `/navigate_to_pose` 仍存在

### Tool or method used
基于用户现场控制台输出继续诊断，不代执行远端命令。

### Why this approach
当前不需要再怀疑 Hesai 原生点云恢复问题。关键是要确认 `a2_system_ws` 这边的中继链：

- `pointcloud_frame_relay`
- `pointcloud_to_laserscan`
- `amcl`

是否真正在线。

### Problems encountered
本轮用户的 `ros2` 命令有两个干扰因素：

1. `ros2 topic hz` 长时间占用前台，导致后续命令没有顺序执行完
2. 中间出现了输入错误：
   - `~ros2 topic hz /scanan`
   - `/a2/lidar/statusus`

不过可确认的有效信号仍然是：

- `points1` 已恢复
- `mid360/points` 与 `/scan` 当前还不能确认在线

### Fixes applied
后续建议改用 `timeout 5s ros2 topic hz ...`，避免反复 `Ctrl-C` 造成 CLI 噪声，并优先检查节点与最近 `bringup_real` 日志，而不是继续串行跑长时间 `hz`。

### Current result
当前最可信状态：

- `unitree_slam.service`：恢复后原生点云正常
- `real1`：Nav2 action 面存在，但点云中继链未确认接通

### Remaining risks or follow-ups
下一步应直接检查：

- `ros2 node list | egrep "pointcloud_frame_relay|pointcloud_to_laserscan|amcl|goal_bridge"`
- 最新 `bringup_real_*.log`
- `timeout 5s ros2 topic hz /mid360/points`
- `timeout 5s ros2 topic hz /scan`

---

## Entry 24 — Direct SSH repair of real1 path and startup script hardening

### Time
2026-04-27 16:08 CST

### Action taken
按用户要求，直接接管远端 A2 修复，并在现有启动脚本基础上做收口，而不是继续只给命令。

本轮完成了以下工作：

1. 本地修改 `a2_system_ws` 启动链，绕开 `pointcloud_frame_relay -> /mid360/points` 对真实 ready 判定的硬依赖。
2. 修改网络脚本，使 `unitree_native_fused/external_pointcloud` 模式下不再把 `.124` 传感器子网绑到 `eth0`。
3. 修改一键脚本 `start_real1_suite.sh`，让它在真实原生点云模式下：
   - 清理错误的 Hesai multicast 配置
   - 删除 `eth0` 上冲突的 `.124` 地址
   - 重启 `unitree_slam.service`
   - 等待 `/unitree/slam_lidar/points1`
4. 远端同步并重建：
   - `a2_bringup`
   - `a2_system`
   - `a2_interfaces`
5. 修复远端 `task_manager.py`/`task_manager.yaml` 缺失与 `task_manager.py` 缺执行位问题。
6. 远端重新启动 `real1` 并验证关键运行态。

### Tool or method used
- 本地代码修改：
  - `apply_patch`
- 远端同步：
  - `scp`
- 远端构建：
  - `colcon build --symlink-install --packages-select ...`
- 远端运行与核查：
  - `ssh a2`
  - `ros2 node list`
  - `ros2 topic hz`
  - `ros2 topic echo --once`
  - `tail -n ... bringup_real_*.log`

### Why this approach
前面的现场证据已经证明：

- 原生 Hesai 点云真实入口是 `net1 + /unitree/slam_lidar/points1`
- `real1` 失败的根因不再是单一 topic 问题，而是：
  - 传感器子网绑错
  - 启动脚本默认行为不适配原生点云模式
  - 远端源码/安装产物不完整

因此必须同时修：

- 入口网络逻辑
- launch 关键路径
- 远端安装完整性

### Problems encountered
本轮遇到的主要问题：

1. `pointcloud_frame_relay` 在节点存在的情况下仍未形成可靠关键路径，因此直接把真实关键消费路径切到 `/unitree/slam_lidar/points1`
2. 远端 `a2_system` 代码不同步：
   - 缺 `task_manager.py`
   - 缺 `task_manager.yaml`
3. 远端 `a2_system/CMakeLists.txt` 还是旧版，未安装 `task_manager`
4. 远端 `task_manager.py` 无执行权限
5. 最后 SSH 再次出现 `No route to host`，影响了最终追加只读检查

### Fixes applied
已完成的具体修复：

- `src/a2_bringup/launch/bringup.launch.py`
  - 真实原生点云模式下让 `safety_supervisor` 直接消费 `/unitree/slam_lidar/points1`
- `src/a2_bringup/launch/sensors.launch.py`
  - 真实原生点云模式下让 `mid360_driver_guard` 和 `sync_monitor` 直接盯 `/unitree/slam_lidar/points1`
- `src/a2_bringup/launch/nav2.launch.py`
  - 真实原生点云模式下让 `pointcloud_to_laserscan` 直接从 `/unitree/slam_lidar/points1` 出 `/scan`
- `src/a2_system/tools/configure_real_network.sh`
  - `unitree_native_fused/external_pointcloud` 模式下跳过 `MID360_HOST_IP` 绑到 `eth0`
- `src/a2_system/tools/start_real1_suite.sh`
  - 增加原生点云模式下的网络/配置清理与 `unitree_slam.service` 拉起逻辑
- 远端同步并重建：
  - `a2_bringup`
  - `a2_system`
  - `a2_interfaces`
- 远端源码补齐：
  - `src/a2_system/CMakeLists.txt`
  - `src/a2_system/config/task_manager.yaml`
  - `src/a2_system/scripts/task_manager.py`
- 远端权限修复：
  - `chmod +x /home/unitree/a2_system_ws/src/a2_system/scripts/task_manager.py`

### Current result
在 SSH 中断前，已经完成并验证到以下状态：

- 新版 `start_real_stack.sh` 启动输出明确包含：
  - `sensor_subnet_skipped=real_lidar_native_source profile=unitree_native_fused driver_mode=external_pointcloud`
- 新 `bringup_real_20260427_162607.log` 中可见：
  - `amcl`
  - `controller_server`
  - `planner_server`
  - `bt_navigator`
  - `pointcloud_to_laserscan`
  - `mid360_driver_guard`
  - `sync_monitor`
  - `safety_supervisor`
- `ros2 node list` 已确认这些节点在线：
  - `/amcl`
  - `/goal_bridge`
  - `/map_server`
  - `/controller_server`
  - `/planner_server`
  - `/bt_navigator`
  - `/pointcloud_to_laserscan`
  - `/mid360_driver_guard`
  - `/real_readiness_monitor`
  - `/safety_supervisor`
  - `/sync_monitor`
- `/unitree/slam_lidar/points1` 已恢复并稳定约 `10Hz`
- `/scan` 已恢复输出，实测约 `2.3Hz ~ 2.7Hz`
- `/a2/lidar/status` 已确认：
  - `mode=real;state=ready;ready=true;reason=pointcloud_ok`
- 日志显示 `estop=false`
- 当前剩余阻塞已经收敛为：
  - AMCL 还没有初始位姿
  - `sync_monitor` 报 IMU / pointcloud skew 约 `0.145s`

### Remaining risks or follow-ups
下一步现场只剩两类工作：

1. 发初始位姿，让 AMCL 发布 `/amcl_pose`，从而让 `/a2/localization/status` 和 `/a2/real/report` 进入 ready
2. 再评估 `sync_monitor` 的 `warn_skew_sec=0.05` 是否过严，需要不要针对当前原生点云模式单独放宽

---

## Entry 25 — Newcomer-oriented system walkthrough requested

### Time
2026-04-27 16:35 CST

### User request
用户要求在当前暂时 SSH 不进 A2 的窗口期，写一份“非常详细、让小白也能看懂并参与后续开发”的整套系统说明。

### Action taken
整理了当前工作区中的：

- 架构说明
- 接口合同
- 交付文档
- README
- 以及本轮真实链路修复结论

计划输出一份面向新人 onboarding 的系统讲解，覆盖：

- 系统目标
- 分层模块
- 真实/仿真/Mock 三种模式
- 数据流
- 启动方式
- 真实链路现状
- 后续开发建议

### Tool or method used
- `sed -n`
- 文档归纳
- 最近实机修复过程中的运行结论

### Why this approach
当前 SSH 不稳定，不适合继续做实机细调；此时把系统讲清楚，对后续多人协作和模块接手价值最高。

### Problems encountered
None

### Fixes applied
None

### Current result
已完成面向新人参与开发的系统级说明整理。

### Remaining risks or follow-ups
后续如果用户需要，可以继续把这份说明沉淀成正式文档，例如：

- `docs/newcomer_guide.md`
- `docs/real1_system_walkthrough.md`

---

## Entry 26 — Explained core bridge chain and sensor helper modules

### Time
2026-04-27 16:42 CST

### Action taken
用户继续追问：

- `mid360_wrapper`
- `sensor_sync`
- `tf_manager`

以及这条链：

- `Unitree SDK2 -> a2_sdk_bridge -> /a2/raw_state -> a2_state_publisher -> /odom + /imu/data + /robot_state`

本步骤以面向新人的方式解释这些模块和核心 ROS 概念，不改代码。

### Tool or method used
基于当前代码架构与既有接口合同做概念说明。

### Why this approach
这是理解后续导航、定位、网页和任务层的最基础前置知识。

### Problems encountered
None

### Fixes applied
None

### Current result
已补充说明：

- `a2_sdk_bridge`
- `/a2/raw_state`
- `a2_state_publisher`
- `/odom`
- `/imu/data`
- `/robot_state`
- `mid360_wrapper`
- `sensor_sync`
- `tf_manager`

### Remaining risks or follow-ups
如果用户继续追问，可以下一步单独解释：

- TF 是什么
- `map / odom / base_link` 的区别
- AMCL 为什么依赖 `/scan + /odom`

---

## Entry 27 — Explained native Hesai lidar chain

### Time
2026-04-27 16:46 CST

### Action taken
用户继续追问这条真实链路：

- `Hesai(.20 on net1) -> unitree_slam.service -> /unitree/slam_lidar/points1`

本步骤专门解释“物理雷达 -> 网络接口 -> systemd 服务 -> ROS 话题”这条链路的分层含义。

### Tool or method used
基于最近真实排障中已经确认的网络、驱动和 ROS 话题关系做概念说明。

### Why this approach
这是理解当前真机点云为什么能/不能进入 ROS 的关键前置知识。

### Problems encountered
None

### Fixes applied
None

### Current result
已向用户解释：

- Hesai `.20`
- `net1`
- `unitree_slam.service`
- `/unitree/slam_lidar/points1`

在真实系统中的角色分工。

### Remaining risks or follow-ups
后续如用户继续深入，可以单独解释：

- `point_cloud_fusion`
- `navigation_mapping_node`
- `/unitree/slam_lidar/points1 -> /scan -> amcl`

---

## Entry 28 — Explained pointcloud to scan conversion

### Time
2026-04-27 16:49 CST

### Action taken
用户继续追问：

- `/unitree/slam_lidar/points1 -> pointcloud_to_laserscan -> /scan`

本步骤专门解释“3D 点云为什么要转成 2D 激光扫描”以及 `pointcloud_to_laserscan` 的具体作用。

### Tool or method used
基于当前代码与 Nav2/AMCL 常规输入语义做概念说明。

### Why this approach
这是理解为什么真实点云恢复后，系统还要额外生成 `/scan` 才能做定位/导航的关键一步。

### Problems encountered
None

### Fixes applied
None

### Current result
已向用户解释：

- `/unitree/slam_lidar/points1`
- `pointcloud_to_laserscan`
- `/scan`

三者之间的角色关系与数据变换意义。

### Remaining risks or follow-ups
后续如用户继续追问，可以再讲：

- `LaserScan` 消息长什么样
- AMCL 为什么直接吃 `/scan`
- 为什么 Nav2 常用 2D，而不是直接吃 3D 点云

---

## Entry 29 — Explained AMCL localization chain

### Time
2026-04-27 16:52 CST

### Action taken
用户继续追问：

- `/map + /scan + /odom -> amcl -> /amcl_pose`

本步骤解释 AMCL 在系统中的角色，以及地图、激光、里程计三者如何共同生成定位结果。

### Tool or method used
基于当前系统架构与 AMCL 的标准输入输出语义做概念说明。

### Why this approach
这是理解“为什么雷达已经恢复了，系统还是要求 initial pose”的关键。

### Problems encountered
None

### Fixes applied
None

### Current result
已向用户解释：

- `/map`
- `/scan`
- `/odom`
- `amcl`
- `/amcl_pose`

在定位链中的作用与相互关系。

### Remaining risks or follow-ups
后续如用户继续追问，可以再讲：

- `map -> odom` TF 是怎么来的
- initial pose 为什么必要
- Nav2 为什么更信任 `/amcl_pose` 而不是裸 `/odom`

---

## Entry 30 — Explained goal-to-motion execution chain

### Time
2026-04-27 16:56 CST

### Action taken
用户要求详细解释这条最关键的执行链：

- `goal_bridge / web / task_manager -> /navigate_to_pose -> Nav2 -> /cmd_vel -> a2_control_bridge -> A2运动命令`

本步骤按“输入、输出、责任、失败点”的方式拆解整条导航执行链。

### Tool or method used
基于当前架构和接口合同做概念说明，不修改代码。

### Why this approach
这是系统里最贴近“用户点一下导航按钮，机器人为什么会动”的主路径，也是后续开发最容易出行为问题的一条链。

### Problems encountered
None

### Fixes applied
None

### Current result
已向用户解释：

- `goal_bridge`
- `web`
- `task_manager`
- `/navigate_to_pose`
- `Nav2`
- `/cmd_vel`
- `a2_control_bridge`
- A2 最终运动命令

的职责边界和执行关系。

### Remaining risks or follow-ups
后续如用户继续深入，可以再讲：

- `NavigateToPose` action 的 goal/feedback/result
- `cmd_vel` 为什么只是速度而不是“直接走到坐标点”
- `a2_control_bridge` 的限速/门控/急停逻辑

---

## Entry 31 — Investigated precision hardening entry points

### Time
2026-04-27 17:05 CST

### Action taken
用户询问“如果现在要提高精度，应该动哪里”。本步骤没有直接改参数，而是重新检查当前与精度直接相关的配置层：

- AMCL 定位参数
- `pointcloud_to_laserscan` 投影参数
- Nav2 controller / goal tolerance / costmap 参数
- `a2_state_publisher` 里程计协方差
- `localization_gate` 与 `sync_monitor` 门控阈值

并准备基于现有配置给出按优先级排序的调参入口建议。

### Tool or method used
- `rg` 全局检索 `amcl`、`xy_goal_tolerance`、`yaw_goal_tolerance`、`inflation_radius`、`resolution`、`transform_tolerance`、`pointcloud_to_laserscan`、`covariance`、`sync_monitor`
- `sed` / `nl -ba` 检查并定位：
  - `/home/dell/a2_system_ws/src/a2_system/config/nav2_stack.yaml`
  - `/home/dell/a2_system_ws/src/a2_system/config/localization.yaml`
  - `/home/dell/a2_system_ws/src/a2_system/config/pointcloud_to_scan.yaml`
  - `/home/dell/a2_system_ws/src/a2_system/config/state_bridge.yaml`
  - `/home/dell/a2_system_ws/src/a2_system/config/sensor_sync.yaml`
  - `/home/dell/a2_system_ws/src/a2_system/config/motion_limits.yaml`
  - `/home/dell/a2_system_ws/src/a2_system/docs/fault_tree.md`

### Why this approach
“精度”不是单一参数问题。若不先确认当前系统把精度压在定位、投影、控制还是地图层，直接改容差或速度很容易得到“看起来更稳但实际更差”的假象。

### Problems encountered
None

### Fixes applied
None

### Current result
已确认当前影响精度的主要入口位于：

- `nav2_stack.yaml`
  - AMCL: 里程噪声、`max_beams`、`update_min_d/a`
  - goal tolerance: `xy_goal_tolerance=0.08`，`yaw_goal_tolerance=0.10`
  - DWB controller: `max_vel_x=0.28`、`max_vel_theta=0.55`、`sim_time=2.0`
  - costmap: global `resolution=0.05`，local `resolution=0.03`
- `pointcloud_to_scan.yaml`
  - `min_height=-0.15`、`max_height=1.20`、`angle_increment≈1deg`
- `state_bridge.yaml`
  - `/odom` pose/twist covariance 当前较宽
- `localization.yaml`
  - `max_xy_variance=0.18`、`max_yaw_variance=0.12`
- `sensor_sync.yaml`
  - `warn_skew_sec=0.05`

已形成一个清晰判断：如果目标是“导航更准”，优先看

1. `/scan` 几何质量
2. AMCL 与 `/odom` 一致性
3. DWB 接近目标时的减速与旋转行为
4. local/global costmap 分辨率和 inflation
5. 速度上限与控制平滑

而不是先去放宽 goal tolerance 或恢复 `manual_odom`。

### Remaining risks or follow-ups
- 还没有结合真实 A2 的 repeated-goal 误差数据做定量建议，因此当前结论仍是“架构层优先级”而不是最终参数值。
- 如果下一步要真正调精度，建议先做一轮固定目标点重复实验，再按“定位误差 / 控制误差 / 地图误差”分型调整。

---

## Entry 32 — Implemented conservative precision tuning and one-click startup scripts

### Time
2026-04-27 17:18 CST

### Action taken
用户要求“稍微细致地调整精度”，并把“关闭干扰进程、拉起所有节点、拉起前端 web”收口成一个一键脚本。

本步骤完成两类本地改动：

1. 保守精度调参
2. 一键启动脚本收口

### Tool or method used
- 检查并编辑：
  - `/home/dell/a2_system_ws/src/a2_system/config/nav2_stack.yaml`
  - `/home/dell/a2_system_ws/src/a2_system/config/pointcloud_to_scan.yaml`
  - `/home/dell/a2_system_ws/src/a2_system/tools/start_real1_suite.sh`
  - `/home/dell/a2_system_ws/scripts/start_a2_real1.sh`
- 本地验证：
  - `bash -n ...`
  - `python3 /home/dell/a2_system_ws/src/a2_system/scripts/config_schema_check.py`
  - `python3 /home/dell/a2_system_ws/src/a2_system/scripts/nav_contract_check.py`

### Why this approach
用户当前目标不是继续分析，而是把真实启动路径变成“可直接执行、可清理现场、可拉起 web”的工程入口；同时只做保守调参，避免在缺少 repeated-goal 统计前过度收紧。

### Problems encountered
None

### Fixes applied
完成以下调参与脚本改造。

精度参数：

- `nav2_stack.yaml`
  - `amcl.max_beams`: `90 -> 120`
  - `amcl.update_min_a`: `0.08 -> 0.05`
  - `amcl.update_min_d`: `0.05 -> 0.03`
  - `general_goal_checker.xy_goal_tolerance`: `0.08 -> 0.06`
  - `general_goal_checker.yaw_goal_tolerance`: `0.10 -> 0.08`
  - `FollowPath.max_vel_x`: `0.28 -> 0.22`
  - `FollowPath.max_vel_theta`: `0.55 -> 0.45`
  - `FollowPath.max_speed_xy`: `0.28 -> 0.22`
  - `FollowPath.acc_lim_x`: `0.8 -> 0.6`
  - `FollowPath.acc_lim_theta`: `1.2 -> 1.0`
  - `FollowPath.sim_time`: `2.0 -> 1.6`
  - `FollowPath.xy_goal_tolerance`: `0.08 -> 0.06`
  - `FollowPath.trans_stopped_velocity`: `0.03 -> 0.02`
  - `FollowPath.RotateToGoal.scale`: `32.0 -> 40.0`
  - `velocity_smoother.max_velocity`: `[0.28, 0.0, 0.55] -> [0.22, 0.0, 0.45]`
  - `velocity_smoother.max_accel`: `[0.8, 0.0, 1.2] -> [0.6, 0.0, 1.0]`
- `pointcloud_to_scan.yaml`
  - `min_height`: `-0.15 -> -0.10`
  - `max_height`: `1.20 -> 0.90`
  - `max_range`: `12.0 -> 10.0`

一键脚本：

- `start_real1_suite.sh`
  - 增加 web backend/bootstrap 与 systemd 安装兜底
  - 增加 ROS1 干扰进程清理
  - 增加 Unitree 原生 `navigation_mapping.py` / `dwa_obstacle_avoidance.py` 清理
  - 增加 `/a2/lidar/status`、`/scan`、`/navigate_to_pose` 验收
  - 改为打印所有可访问 web URL
- 新增本机入口：
  - `/home/dell/a2_system_ws/scripts/start_a2_real1.sh`
  - 用于 “本机部署 + SSH 远程执行一键启动”

### Current result
本地离线验证通过，新的启动入口和精度参数已经准备好，可以直接部署到 A2 验证。

### Remaining risks or follow-ups
- 这些调参仍然属于“保守首轮”，还未结合终点误差统计做闭环验证。
- 一键脚本是否真正稳定，还需要在 A2 上完整跑通一次。

---

## Entry 33 — Deployed to A2 and fixed frontend build regression

### Time
2026-04-27 17:24 CST

### Action taken
将修改后的工作区部署到 A2 并远端构建。

首次部署时，前端 `vite build` 失败；随后修复缺失字段后重新部署成功。

### Tool or method used
- `BUILD_WEB=1 START_SERVICE=0 /home/dell/a2_system_ws/scripts/deploy_to_a2.sh a2`
- 检查并编辑：
  - `/home/dell/a2_system_ws/web_console/frontend/src/App.tsx`
- 本地前端验证：
  - `npm -C /home/dell/a2_system_ws/web_console/frontend run build`

### Why this approach
一键脚本最终必须能把 web 一起拉起来，所以不能绕过前端构建错误；需要先把远端 deploy/build 这层打通。

### Problems encountered
首次 deploy 失败，错误为：

- `Property 'task_manager_status' is missing ... but required in type 'RobotStatus'`

说明 `App.tsx` 的初始快照结构没有跟上 `types.ts` 新增字段。

### Fixes applied
在 `web_console/frontend/src/App.tsx` 的 `createEmptySnapshot().status` 中补齐：

- `task_manager_status`

随后本地 `npm run build` 通过，第二次 `deploy_to_a2.sh` 成功完成：

- ROS 包构建通过
- `config_schema_check.py`：`PASS`
- `nav_contract_check.py`：`PASS`
- backend bootstrap 完成
- frontend build 完成

### Current result
A2 远端已经拿到新的：

- 精度参数
- `start_real1_suite.sh`
- `start_a2_real1.sh`
- web 前端修复

### Remaining risks or follow-ups
- 还需实际执行一键启动脚本，确认不是“构建成功但启动失败”。

---

## Entry 34 — Debugged and validated one-click startup on A2

### Time
2026-04-27 17:35 CST

### Action taken
实际执行新的一键入口，并在运行过程中连续修复了三个脚本级问题，最终在 A2 上成功完成：

- 干扰清理
- 原生前雷达链复用
- `real1` bringup
- web 服务启动

### Tool or method used
- 一键启动执行：
  - `/home/dell/a2_system_ws/scripts/start_a2_real1.sh --no-deploy --host a2`
- 远端调试：
  - `ssh a2 'systemctl ...'`
  - `ssh a2 'journalctl -u unitree_slam.service ...'`
  - `ssh a2 'ros2 topic ...'`
  - `ssh a2 'ros2 node info /pointcloud_to_laserscan'`
  - `ssh a2 'curl http://127.0.0.1:8080/api/health'`
- 热同步脚本修复：
  - `rsync -az ...start_real1_suite.sh a2:...`

### Why this approach
只有实际跑完整启动链，才能发现“非交互 SSH 环境”“原生雷达服务复用”“topic 等待逻辑”这些脚本层 bug；这些问题离线检查抓不出来。

### Problems encountered
依次发现三个真实脚本问题：

1. `start_real1_suite.sh` 在 source ROS 环境前就执行 `require_cmd ros2`
   - 结果：非交互 SSH 下直接报 `Missing required command: ros2`
2. 脚本原本会强制 `restart unitree_slam.service`
   - 结果：重启原生服务时会把当前启动链带进不稳定状态，且没必要
3. `wait_topic_ready()` 使用无超时的 `ros2 topic echo --once`
   - 结果：等待 `/a2/real/report` 时会假死，最终误报超时

另外，运行中还确认：

- `/scan` 实际是有数据的
- `/navigate_to_pose` action 实际已在线
- 之前的主要阻塞已不再是雷达链

### Fixes applied
对 `start_real1_suite.sh` 做了三轮热修：

1. 提前 source：
   - `/opt/ros/humble/setup.bash`
   - `${WORKSPACE}/install/setup.bash`
2. 原生雷达管理策略改成：
   - `unitree_slam.service` 已经 `active` 时，不再强制重启
   - 只在未运行时才 `start`
3. `wait_topic_ready()` 改为：
   - `timeout 2s ros2 topic echo --once ...`
   - 以短超时轮询代替无限等待

并确认脚本会额外做：

- 停掉 `navigation_mapping.py`
- 停掉 `dwa_obstacle_avoidance.py`
- 停掉 `rosmaster` / `foxglove_bridge` / `a2_ros1_sdk`
- 停掉旧 web / docker 干扰

### Current result
最终一键启动在 A2 上实跑成功，输出包含：

- `real1 suite started successfully`
- web backend health:
  - `backend_ok=true`
  - `ros_connected=true`
  - `map_received=true`
- web 已可访问：
  - `http://192.168.31.49:8080/`

现场验证到的关键运行态：

- `/unitree/slam_lidar/points1`：在线
- `/scan`：在线，且可 `echo --once`
- `/a2/lidar/status`：
  - `mode=real;state=ready;ready=true;reason=pointcloud_ok`
- `/navigate_to_pose`：action 在线
- `a2-web-console.service`：
  - `active`
  - `enabled`

当前真实系统状态仍然是：

- `/a2/real/report`：
  - `state=degraded`
  - `reason=localization_down`
- `/a2/localization/status`：
  - `state=waiting_pose`
  - `reason=no_pose`

这符合当前实机状态：系统已经启动成功，但 AMCL 还没有收到初始位姿。

### Remaining risks or follow-ups
- 一键启动已成功，但还没自动发 initial pose；若要直接进入 ready，需要：
  - `--initial-pose x y yaw`
  - 或网页发 `/api/localization/initialpose`
- `sync_monitor` 仍在报：
  - `IMU / point cloud skew ≈ 0.149s`
  这会影响系统 ready 评估，是下一轮精度/稳定性硬化的重点。

---

## Final outcome update 2

### Summary
本轮完成了两件关键工作：

1. 做了一轮保守精度调参，优先改善 `/scan` 质量、AMCL 更新频率、DWB 接近目标时的速度和停靠行为。
2. 把 A2 真机真实启动路径收口成了可实跑的一键脚本，并已在 A2 上验证通过。

新的推荐入口已经是：

- 本机：
  - `./scripts/start_a2_real1.sh --host a2`
- A2 本机：
  - `/home/unitree/a2_system_ws/src/a2_system/tools/start_real1_suite.sh --iface eth0 --map-yaml ...`

### Files changed
- `agent-logs/2026-04-27-agent-session.md`
- `readme/README_A2_Quickstart.md`
- `scripts/start_a2_real1.sh`
- `src/a2_system/config/nav2_stack.yaml`
- `src/a2_system/config/pointcloud_to_scan.yaml`
- `src/a2_system/tools/start_real1_suite.sh`
- `web_console/frontend/src/App.tsx`

### Commands run
- `bash -n /home/dell/a2_system_ws/src/a2_system/tools/start_real1_suite.sh /home/dell/a2_system_ws/scripts/start_a2_real1.sh`
- `python3 /home/dell/a2_system_ws/src/a2_system/scripts/config_schema_check.py`
- `python3 /home/dell/a2_system_ws/src/a2_system/scripts/nav_contract_check.py`
- `npm -C /home/dell/a2_system_ws/web_console/frontend run build`
- `BUILD_WEB=1 START_SERVICE=0 /home/dell/a2_system_ws/scripts/deploy_to_a2.sh a2`
- `/home/dell/a2_system_ws/scripts/start_a2_real1.sh --no-deploy --host a2`
- 多次 `ssh a2 'systemctl ...'`
- 多次 `ssh a2 'ros2 topic ...'`
- 多次 `ssh a2 'journalctl ...'`

### Verification
- 本地：
  - `bash -n`：通过
  - `config_schema_check.py`：`PASS`
  - `nav_contract_check.py`：`PASS`
  - `npm run build`：通过
- A2 远端：
  - deploy/build：通过
  - `/scan`：在线
  - `/a2/lidar/status`：`ready=true`
  - `/navigate_to_pose`：在线
  - `a2-web-console.service`：`active + enabled`
  - `/api/health`：返回 `backend_ok=true`

### Known limitations
- 当前一键启动“成功”指的是：栈和 web 已起、核心 topic/action 已在线。
- 当前还不是“导航 ready”，因为：
  - AMCL 仍需 initial pose
  - `/a2/localization/status=waiting_pose`
- `sync_monitor` 的 IMU/pointcloud skew 仍偏大，需要下一轮继续硬化。

---

## Entry 35 — Web 导航启动超时与建图精度排查

### Time
2026-04-27 17:54:59 CST

### Action taken
开始排查网页选择 `test4-27` 后“导航模式启动超时，缺少节点: manual localization”，以及先建图但地图精度很差的问题。

### Tool or method used
- 检查 `web_console/backend/stack_control.py`
- 检查 `src/a2_bringup/launch/bringup.launch.py`
- 检查 `src/a2_bringup/launch/mapping.launch.py`
- 检查 `src/a2_bringup/launch/localization.launch.py`
- 检查 `src/a2_bringup/launch/nav2.launch.py`
- 检查 `src/a2_system/config/occupancy_mapper.yaml`
- 检查 `src/map_manager/map_manager/occupancy_mapper.py`
- 检查 `src/a2_system/tools/start_real_stack.sh`
- 检查 `src/a2_system/tools/start_real1_suite.sh`

### Why this approach
启动失败显示的是“缺少节点”，所以优先检查 Web 后端启动后的节点等待清单，而不是先调 Nav2。建图精度差显示在 `/map` 上，所以检查 Web 建图路径使用的占据栅格生成器、点云输入、分辨率和滤波参数。

### Problems encountered
- Web 后端 `NAVIGATION_NODES` 仍把真实导航定位节点写成旧的 `manual_localization_publisher`。
- 当前真实默认定位已经改成 AMCL，因此 Web 会等待一个默认情况下不会启动的旧节点。
- Web 等待超时后会调用 `_terminate_runtime_processes()`，所以用户看到的结果是“所有节点都没有拉起来”。
- 建图路径仍使用简单 `occupancy_mapper`：它只把点云按 `/odom` 投影到栅格，不做激光/点云 scan matching、闭环或全局优化；如果里程计漂移，地图会直接被拉歪。
- 当前建图参数偏粗：`resolution=0.1`、`point_stride=6`、`max_range=12.0`、高度过滤范围较宽。

### Fixes applied
None yet. 下一步修改 Web 导航契约为 AMCL，显式传入 `A2_REAL_LOCALIZATION_MODE=amcl`，补齐 AMCL/Nav2 残留清理，并收紧建图点云与栅格参数。

### Current result
根因已明确：导航启动失败主要是 Web 后端旧节点契约导致的超时与主动清理，不是雷达链路本身不可用。建图精度差主要是当前 Web 建图模式仍是 odom 投影式简易占据栅格，不是正式 SLAM。

### Remaining risks or follow-ups
- 修改后需要部署到 A2，并通过 Web API 或页面重新启动导航验证不再报 `manual localization`。
- 即使参数调细，`occupancy_mapper` 仍无法消除 odom 漂移；工业级建图需要接入真实 SLAM 或使用 Unitree 原生建图结果作为地图来源。

---

## Entry 36 — 修复 Web AMCL 启动契约并收紧建图参数

### Time
2026-04-27 17:56:32 CST

### Action taken
完成本地修改：

- Web 导航启动节点清单从 `manual_localization_publisher` 改为 `amcl`
- Web 启动导航时显式传入 `A2_REAL_LOCALIZATION_MODE=amcl`
- 停止/一键启动脚本补齐 AMCL、`pointcloud_to_laserscan`、`localization_gate`、Nav2 smoother/behavior/waypoint 等残留进程清理
- 建图 launch 增加 `pointcloud_topic` 参数，并由 `bringup.launch.py` 在真实前雷达模式下传入真实前雷达点云 topic
- `occupancy_mapper.yaml` 从 0.1m 栅格改成 0.05m 栅格，保持 30m x 30m 范围，并把点云抽样从 6 收紧到 3、最大距离从 12m 收紧到 10m、高度上限从 1.8m 收紧到 1.2m
- 增加 Web 后端测试，防止导航契约重新退回 `manual localization`
- 在 `nav_contract_check.py` 增加 Web 启动契约检查

### Tool or method used
- `apply_patch`
- `bash -n`
- `python3 -m py_compile`
- `python3 src/a2_system/scripts/config_schema_check.py`
- `python3 src/a2_system/scripts/nav_contract_check.py`
- `python3 -m pytest web_console/backend/test/test_web_contracts.py`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest web_console/backend/test/test_web_contracts.py`
- `git diff --check`

### Why this approach
启动失败的直接根因在 Web 后端节点契约，所以优先修 Web 检查条件和启动环境。建图精度问题先做低风险参数收紧和点云输入显式化，不引入新的 SLAM 架构，避免在实机上扩大变量。

### Problems encountered
本机第一次运行 `pytest` 失败，原因是 pytest 自动加载了用户环境中的不兼容 `anyio` 插件：

- `ModuleNotFoundError: No module named '_pytest.scope'`

### Fixes applied
用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 禁止第三方 pytest 插件自动加载后，Web 后端测试通过。

### Current result
本地验证结果：

- `bash -n`：通过
- Python 编译检查：通过
- `config_schema_check.py`：`PASS`
- `nav_contract_check.py`：`PASS`
- Web 后端测试：`3 passed`
- `git diff --check`：通过

### Remaining risks or follow-ups
- 还需要部署到 A2，并通过 Web `/api/stack/start-navigation` 或网页按钮验证 `test4-27` 启动不再因 `manual localization` 超时。
- 建图参数只能改善地图显示粒度和噪声过滤，不能解决 odom 漂移导致的根本建图误差。

---

## Entry 37 — 部署到 A2 并验证 `test4-27` 导航启动

### Time
2026-04-27 18:04:06 CST

### Action taken
将修改部署到 A2，重启 Web 服务，并通过 Web API 启动 `test4-27` 导航模式验证。

### Tool or method used
- `BUILD_WEB=0 START_SERVICE=1 scripts/deploy_to_a2.sh a2`
- `curl http://127.0.0.1:8080/api/health`
- `curl http://127.0.0.1:8080/api/stack/status`
- `curl -X POST http://127.0.0.1:8080/api/stack/start-navigation`
- `ros2 topic echo --once /a2/real/report`
- `ros2 topic echo --once /a2/lidar/status`
- `ros2 topic echo --once /a2/localization/status`
- `ros2 topic echo --once /a2/control/status`
- `ros2 action list`
- `ros2 topic info /scan`
- `ros2 topic echo --once /scan`
- `ros2 node list | sort | uniq -d`
- `pgrep` / `ps` 检查残留进程

### Why this approach
用户遇到的是网页按钮真实启动失败，必须在 A2 上通过同一个 Web API 路径验证，而不能只靠本地静态检查。

### Problems encountered
- 第一次远端启动已成功返回 `HTTP 200`，但随后为了部署清理补丁又覆盖了 install 目录，正在运行的 symlink-install ROS 进程被中断。
- 发现旧建图栈残留了一个 `task_manager.py`，导致 ROS graph 报重复节点名。
- `ros2 node list` 仍提示 `/hesai_ros_driver_node` 重名；该节点来自 `unitree_slam.service` 内部，不是本次 A2 host stack 残留。

### Fixes applied
- 将 `task_manager.py` 纳入 Web 后端、`stop_stack.sh`、`start_real1_suite.sh` 的清理模式。
- 杀掉 A2 上旧的 `task_manager.py` 残留进程。
- 重新部署后再次通过 Web API 启动 `test4-27` 导航模式。

### Current result
最终 A2 远端验证：

- `/api/stack/start-navigation`：`HTTP_STATUS=200`
- Web stack status：`mode=navigation`
- 选中地图：`test4-27`
- Web 节点清单全部 running：
  - `bringup.launch.py`
  - `a2_sdk_bridge`
  - `a2_control_bridge`
  - `AMCL localization`
  - `goal_bridge`
  - `map_server`
  - `controller_server`
  - `planner_server`
  - `bt_navigator`
  - `velocity_smoother`
  - `lifecycle_manager`
- `/a2/lidar/status`：`ready=true;reason=pointcloud_ok`
- `/scan`：publisher=1，`echo --once` 成功
- `/navigate_to_pose`：action 在线
- `/a2/localization/status`：`waiting_pose;reason=no_pose`
- `/a2/control/status`：`blocked;reason=allow_motion_false`

### Remaining risks or follow-ups
- 当前导航栈已经能启动，但还不是可运动状态；AMCL 需要通过网页或 API 设置初始位姿后才会发布 `/amcl_pose` 和 `map->odom`。
- 控制桥当前因为 `allow_motion_false` 保持阻塞，这是安全状态；真正发导航目标前必须先完成 initial pose 和允许运动流程。
- 建图精度的根因仍是 `occupancy_mapper` 不是 SLAM，只能作为临时 2D 栅格生成器；要显著提升地图精度，需要接入正式 SLAM/原生地图源。

---

## Entry 38 — 当前阶段总结答复

### Time
2026-04-28 09:47:46 CST

### Action taken
整理当前进度，回答“现在到哪一步了，建图精度提高了吗”。

### Tool or method used
- 回看 `agent-logs/2026-04-27-agent-session.md`

### Why this approach
这个问题是阶段总结，不需要再改代码；直接基于昨日已经完成的本地验证和 A2 远端验证给结论即可。

### Problems encountered
None.

### Fixes applied
None.

### Current result
当前阶段：

- 导航启动链路已经修到可拉起：
  - Web 点击 `test4-27` 启动导航不再报 `manual localization`
  - `bringup + AMCL + Nav2 + /scan + /navigate_to_pose` 已验证能上线
- 但导航还没进入 ready：
  - 还缺 initial pose
  - 当前状态仍是 `waiting_pose / no_pose`
- 建图参数做了保守优化：
  - 栅格分辨率从 `0.1m` 收紧到 `0.05m`
  - 点云抽样从 `6` 收紧到 `3`
  - 距离/高度过滤更保守
  - 建图点云输入显式绑定到真实前雷达链路
- 这些修改只能改善地图颗粒度和噪声过滤，不能从根本上解决 odom 漂移导致的地图变形

### Remaining risks or follow-ups
- 下一步应先完成 initial pose 流程验证，让导航真正进入 ready 并可执行目标。
- 如果目标是“明显提高建图精度”，下一阶段不能继续只调 `occupancy_mapper` 参数，必须换到正式 SLAM/原生地图源方案。

---

## Entry 39 — 打通 initial pose 并切换真实建图主链

### Time
2026-04-28 10:03:49 CST

### Action taken
开始处理两件事：

1. 让 initial pose 从“只发布消息”变成“发布后验证定位 ready”
2. 把真实建图主链从 `occupancy_mapper` 切到原生 SLAM 地图源

### Tool or method used
- 检查 `web_console/backend/ros_bridge.py`
- 检查前端 `App.tsx` / `ControlSidebar.tsx`
- 检查 `src/a2_bringup/launch/mapping.launch.py`
- 检查 `src/slam_manager/slam_manager/slam_orchestrator.py`
- 检查 `原生SLAM接入改造Prompt.md`
- 远端检查 A2 话题：
  - `/global_map`
  - `/gridmap`
  - `/utlidar/robot_pose`
  - `/uslam/localization/odom`

### Why this approach
需要先确认现有代码里哪些能力已经存在，避免重复实现。现场 topic 盘点表明：`/global_map` 已经是稳定可用的 `nav_msgs/msg/OccupancyGrid` 原生地图源，因此最小可落地切换点就是让真实建图直接消费它。

### Problems encountered
- Web 的 initial pose 接口之前只是盲发 `/initialpose`，并不验证 AMCL 是否真的进入 ready。
- 原生定位类 topic 当前没有一个比 `/global_map` 更稳定的“立刻可替换 AMCL”的接口，因此这轮不适合同时硬切 native localization。
- `native_map_relay` 如果只在原生地图新消息到来时转发，`safety_supervisor` 可能把 `/map` 判 stale。

### Fixes applied
已完成本地改造：

- 新增 `map_manager/native_map_relay.py`
  - 订阅原生 `/global_map`
  - 转发到本系统 `/map`
  - 使用 transient-local publisher
  - 缓存最后一帧并按定时器重发，避免 map freshness 失效
- 新增 `src/a2_system/config/native_map_relay.yaml`
- `mapping.launch.py` 在真实模式下默认起 `native_map_relay`，不再默认起 `occupancy_mapper`
- Web stack / stop script / start script 增加 `native_map_relay` 进程识别与清理
- `ros_bridge.set_initial_pose()` 改成：
  - 持续发布 `/initialpose`
  - 等待 `/a2/localization/status` 真正 ready
  - 若超时则显式报错，不再假成功
- 补充 config/schema/contract 测试与检查

### Current result
本地验证全部通过：

- `bash -n`：通过
- `py_compile`：通过
- `config_schema_check.py`：`PASS`
- `nav_contract_check.py`：`PASS`
- `pytest`：`6 passed`
- `git diff --check`：通过

### Remaining risks or follow-ups
- 还需要部署到 A2，远端验证：
  - initial pose 后 `/a2/localization/status` 是否转为 `ready`
  - mapping 模式下 `/map` 是否来自 `native_map_relay`
  - `occupancy_mapper` 是否已不再作为真实主路径运行

---

## Entry 40 — 排查原生 SLAM 地图候选源

### Time
2026-04-28 10:08:17 CST

### Action taken
开始第二轮远端排查，重点核实 Unitree 原生地图候选话题的消息类型、QoS、是否连续发布，以及哪一路最适合作为 `/map` 的正式来源。

### Tool or method used
- 本地 `date`
- 准备通过 `ssh a2` 执行 `ros2 topic info`、`ros2 topic echo --once`、`ros2 topic hz`、日志检查

### Why this approach
上一轮已经确认 `native_map_relay` 结构本身可用，当前阻塞点在于 `/global_map` 这个输入源没有被稳定消费。要真正把建图切到正式 SLAM，就必须先找到一个真实可用的原生地图话题，而不是继续盲调 relay 参数。

### Problems encountered
- 上一轮远端日志显示 `/global_map` 与 relay 订阅存在 durability 不兼容告警
- `/map` 没有形成有效地图输出，`map_ready=false`

### Fixes applied
None.

### Current result
已进入原生地图源排查阶段，下一步将根据真实话题行为改默认源并重新部署验证。

### Remaining risks or follow-ups
- 如果所有候选 2D 地图话题都不稳定，就需要退一步改为直接消费 Unitree 原生定位/地图服务或接入其正式建图产物，而不是继续依赖被动 relay。

---

## Entry 41 — 确认原生建图私有接口在当前 A2 固件上不可用

### Time
2026-04-28 10:26:11 CST

### Action taken
远端继续追查 Unitree 原生建图控制面，验证旧 `go2_web` 的 `slam_operate` 命令是否还能在当前 A2 运行时生效，并核实可用服务列表与话题发布状态。

### Tool or method used
- `ssh a2`
- 远端检查：
  - `ros2 topic info -v /api/slam_operate/request`
  - `ros2 topic info -v /api/slam_operate/response`
  - `grep` 检查 `go2_web/ros_handler.py`
  - `python3` 调 `unitree_sdk2py` 的 `RobotStateClient`
  - `ros2 topic info` / `ros2 topic hz` 检查 `/global_map`、`/planner_map`、`/gridmap`、`/lio_sam_ros2/*`、`/grid_clouds`

### Why this approach
如果原生地图源和原生建图控制命令都还有效，就应该优先直接复用 Unitree 原生链路；如果原生命令面已经在当前固件中失效，就不能继续把系统绑定在这个私有接口上。

### Problems encountered
- `/api/slam_operate/request` 对 `api_id=1801` 的返回码是 `3203`
- 在远端 `unitree_sdk2py/rpc/internal.py` 中确认 `3203 = RPC_ERR_SERVER_API_NOT_IMPL`
- `RobotStateClient.ServiceList()` 返回的服务列表中没有任何 `slam` / `map` 类标准服务
- `/lio_sam_ros2/mapping/*`、`/utlidar/voxel_map_compressed` 等名字存在，但真实发布者为 `0` 或长时间无消息
- `/global_map`、`/gridmap`、`/planner_map` 属于裸 DDS 原生话题，但没有证据表明在当前 A2 运行时可稳定作为 Web 建图主链的实时来源

### Fixes applied
- 在 Web 后端中补齐了 `unitree_api` 兼容消息包与 request/response 同步等待逻辑，先把“是否是我们消息格式错了”这个可能性排除
- 结论是：消息格式和 topic 对齐没有问题，真正的问题是当前服务端没有实现 `1801`

### Current result
确认了一个关键结论：

- 当前 A2 上“旧 go2_web 通过 `/api/slam_operate/request` 发 `1801` 开始建图”的方法已经不是可靠控制面
- 继续把真实建图主链绑在 `native_map_relay + 1801` 上不可接受

### Remaining risks or follow-ups
- 需要切到我们可控、可验证、可复现的正式 SLAM 方案
- 同时保留 `native_map_relay` 作为后续如果 Unitree 原生 2D 地图源恢复时的兼容 fallback

---

## Entry 42 — 将真实建图默认主链切换到 slam_toolbox

### Time
2026-04-28 10:39:18 CST

### Action taken
在本地代码中把真实建图的默认主链从 `native_map_relay/occupancy_mapper` 切换为 `slam_toolbox`，并同步修正 Web 后端的建图启动逻辑、进程清理规则、配置契约和文档。

### Tool or method used
- 编辑文件：
  - `src/a2_system/config/slam.yaml`
  - `src/a2_system/config/slam_toolbox_mapping.yaml`
  - `src/a2_bringup/launch/mapping.launch.py`
  - `web_console/backend/stack_control.py`
  - `web_console/backend/main.py`
  - `src/a2_system/tools/stop_stack.sh`
  - `src/a2_system/tools/start_real1_suite.sh`
  - `web_console/backend/test/test_web_contracts.py`
  - `src/a2_system/scripts/config_schema_check.py`
  - `src/a2_system/scripts/nav_contract_check.py`
  - `src/a2_system/docs/interface_contracts.md`
  - `src/a2_system/docs/operations_runbook.md`
- 本地校验：
  - `python3 -m py_compile ...`
  - `pytest web_console/backend/test/test_web_contracts.py`
  - `python3 src/a2_system/scripts/config_schema_check.py`
  - `python3 src/a2_system/scripts/nav_contract_check.py`
  - `git diff --check`

### Why this approach
用户的目标不是继续微调 `occupancy_mapper`，而是切到“正式 SLAM 或原生地图源”。既然原生私有控制面在当前固件上已经不可靠，最直接、最工程化、最可复现的替代就是使用系统已安装的 `slam_toolbox`。

### Problems encountered
- Web `/api/stack/start-mapping` 之前无条件调用 `start_native_mapping()`，即使 launch 已切到其它图源，也会先触发失败的 `1801`
- 原有 mapping contract 只接受 `native_map_relay` / `occupancy_mapper`
- 真实建图模式之前不会主动起 `/scan` 生成链，因此 `slam_toolbox` 没有输入

### Fixes applied
- 在 `slam.yaml` 中新增 `mapping_stack_profile: slam_toolbox`，把真实建图默认源切到 `slam_toolbox`
- 新增 `slam_toolbox_mapping.yaml`，定义 A2 专用参数：
  - `scan_topic=/scan`
  - `map_frame=map`
  - `odom_frame=odom`
  - `base_frame=base_link`
  - `resolution=0.05`
  - `minimum_travel_distance: 0.5 -> 0.08`
  - `minimum_travel_heading: 0.5 -> 0.08`
  - `map_update_interval: 5.0 -> 1.0`
  - `do_loop_closing=true`
- `mapping.launch.py` 在真实模式且未起 Nav2 时：
  - 先起 `pointcloud_to_laserscan`
  - 再起 `sync_slam_toolbox_node`
  - 仅在显式 profile 为 `native_global_map` 时才起 `native_map_relay`
- Web 后端启动建图时：
  - 读取当前 mapping profile
  - 只有 profile=`native_global_map` 时才发送 native `1801/1802`
  - `slam_toolbox` 模式下不再触发已失效的原生命令
- 把 `slam_toolbox` 纳入 Web 节点契约和残留进程清理脚本
- 更新 config/schema/nav contract，确保默认 real mapping 源保持为 `slam_toolbox`

### Current result
本地所有静态和契约检查通过，代码已经具备远端部署条件。

### Remaining risks or follow-ups
- 还需要在 A2 上验证：
  - Web 建图启动是否返回 200
  - `slam_toolbox` 是否真实起进程
  - `/map` 是否真实产图
  - 地图保存是否走标准 `/map`，而不是再回退到 native save

---

## Entry 43 — 部署到 A2 并完成真实建图回归

### Time
2026-04-28 10:46:55 CST

### Action taken
将新版本部署到 A2，启动真实建图模式，验证 `slam_toolbox` 进程、`/map` 输出和保存地图流程。

### Tool or method used
- 部署：
  - `BUILD_WEB=0 START_SERVICE=1 scripts/deploy_to_a2.sh a2`
- 远端回归：
  - `curl -X POST http://127.0.0.1:8080/api/stack/start-mapping`
  - `curl http://127.0.0.1:8080/api/stack/status`
  - `curl http://127.0.0.1:8080/api/health`
  - `ros2 node list`
  - `tail runtime/logs/bringup_real_20260428_104506.log`
  - `ros2 topic echo --once /map`
  - `curl -X POST http://127.0.0.1:8080/api/maps/save`
  - `find /home/unitree/a2_system_ws/runtime/maps/slam_switch_smoke`

### Why this approach
这一步必须在真实 A2 上闭环验证，否则只能证明“代码能编译”，不能证明“真实建图主链真的已经切到正式 SLAM”。

### Problems encountered
- 一开始并行查询时，`/api/stack/status` 出现过一次旧状态推断抖动，后续复查恢复为 `mapping`
- `slam_toolbox` 启动初期有一条首帧 message-filter 丢帧日志：
  - `timestamp ... earlier than all the data in the transform cache`
- `sync_monitor` 仍持续报告 IMU / point cloud skew 约 `0.088s`

### Fixes applied
- 复查进程列表和实时状态，确认不是当前主链失败，而是启动初期状态采样时机问题
- 对地图保存再次做文件级确认，排除只在 API 层“回成功”但磁盘没落盘的情况

### Current result
真实回归通过，关键证据如下：

- Web 启动建图返回 `HTTP 200`
- 返回体明确显示：
  - `mapping_profile = slam_toolbox`
  - `native_slam = null`
- 远端真实运行进程包括：
  - `pointcloud_to_laserscan`
  - `slam_toolbox`
  - `map_manager`
- `/api/health` 显示：
  - `map_received = true`
- `/map` 已真实输出 `nav_msgs/msg/OccupancyGrid`
  - 分辨率 `0.05`
  - 当前回归样例尺寸 `176 x 71`
- 保存地图接口返回 `HTTP 200`
  - 新地图 `slam_switch_smoke`
  - 元数据为 `176 x 71 @ 0.05m`
  - `native_slam_save = null`
- 远端磁盘已生成：
  - `runtime/maps/slam_switch_smoke/map.pgm`
  - `runtime/maps/slam_switch_smoke/map.yaml`
  - `runtime/maps/slam_switch_smoke/metadata.yaml`

### Remaining risks or follow-ups
- `initial pose -> AMCL ready` 的代码路径已经打通，但还没有在这轮用“真实正确初始位姿”完成闭环验证
- `sync_monitor` 报告的 `0.088s` 点云/IMU skew 仍可能继续影响精度，这是下一轮提高建图质量的主要候选问题
- `slam_toolbox` 当前产图已经从链路层替换成功，但最终精度仍需要真实走线建图实验来量化对比旧 `occupancy_mapper`

---

## Final outcome

### Summary
- 真实建图默认主链已从 `occupancy_mapper/native_map_relay` 切到 `slam_toolbox`
- Web 建图启动已不再依赖已失效的 Unitree 原生 `1801` 开始建图接口
- A2 实机已验证：
  - `slam_toolbox` 起进程
  - `/map` 出图
  - 保存地图成功
- `initial pose` 的 AMCL 等待逻辑已在代码层打通，但这轮未完成“真实正确初始位姿”的现场闭环验证

### Files changed
- `agent-logs/2026-04-27-agent-session.md`
- `src/a2_system/config/slam.yaml`
- `src/a2_system/config/slam_toolbox_mapping.yaml`
- `src/a2_bringup/launch/mapping.launch.py`
- `web_console/backend/stack_control.py`
- `web_console/backend/main.py`
- `src/a2_system/tools/stop_stack.sh`
- `src/a2_system/tools/start_real1_suite.sh`
- `web_console/backend/test/test_web_contracts.py`
- `src/a2_system/scripts/config_schema_check.py`
- `src/a2_system/scripts/nav_contract_check.py`
- `src/a2_system/docs/interface_contracts.md`
- `src/a2_system/docs/operations_runbook.md`

### Commands run
- 本地：
  - `python3 -m py_compile ...`
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest web_console/backend/test/test_web_contracts.py`
  - `python3 src/a2_system/scripts/config_schema_check.py`
  - `python3 src/a2_system/scripts/nav_contract_check.py`
  - `git diff --check ...`
- 远端：
  - `BUILD_WEB=0 START_SERVICE=1 scripts/deploy_to_a2.sh a2`
  - `curl -X POST /api/stack/start-mapping`
  - `curl /api/stack/status`
  - `curl /api/health`
  - `ros2 node list`
  - `ros2 topic echo --once /map`
  - `curl -X POST /api/maps/save`

### Verification
- 本地静态/契约检查通过
- A2 实机回归通过：
  - `start-mapping` 返回 `HTTP 200`
  - `mapping_profile=slam_toolbox`
  - `native_slam=null`
  - `/map` 输出分辨率为 `0.05`
  - 地图文件 `slam_switch_smoke` 已落盘

### Known limitations
- 还未完成真实正确 initial pose 的导航 ready 闭环
- 点云/IMU `0.088s` skew 仍需后续治理
- 尚未形成新旧建图精度的量化对比报告

---

## Entry 44 — 核对启动脚本与节点集合变更

### Time
2026-04-28 11:15:03 CST

### Action taken
根据用户问题核对当前启动脚本是否已反映真实建图链路切换后的节点变化，重点检查 `start_real_stack.sh`、`mapping.launch.py`、`start_real1_suite.sh` 和 Web 的节点契约。

### Tool or method used
- `nl -ba` 查看：
  - `src/a2_system/tools/start_real_stack.sh`
  - `src/a2_bringup/launch/mapping.launch.py`
  - `src/a2_system/tools/start_real1_suite.sh`
  - `web_console/backend/stack_control.py`

### Why this approach
用户问的是“脚本有没有更新、拉起节点有没有变化”，核心不在入口脚本名字，而在入口脚本最终透传到 `bringup.launch.py` 后，真实模式建图子链到底起了哪些节点。

### Problems encountered
None.

### Fixes applied
None.

### Current result
确认结果如下：

- `start_real_stack.sh` 入口没有改名，也没有硬编码 `slam_toolbox`
- 真正的变化在 `mapping.launch.py`
- 真实建图模式现在默认从 `slam.yaml` 读取 `mapping_stack_profile`
- 默认 profile 已是 `slam_toolbox`
- 因此 mapping 模式拉起的主建图节点已变为：
  - `pointcloud_to_laserscan`
  - `slam_toolbox`
  - `map_manager`
- `native_map_relay` 和 `occupancy_mapper` 现在只保留为 fallback 分支
- `start_real1_suite.sh` 和 Web `stack_control.py` 的残留进程清理/节点契约也已经同步加入 `slam_toolbox`

### Remaining risks or follow-ups
- 如果后续还要把导航模式下的节点检查改得更细，可以继续把 Web 的 `mapping`/`navigation` 状态判定与真实 ROS graph 做更严格对齐。

---

## Entry 45 — 提供实操建图与前端启动命令

### Time
2026-04-28 11:20:00 CST

### Action taken
根据用户要求，整理当前“实操建图 + 前端”的最短启动命令，明确使用建图模式而不是导航套件。

### Tool or method used
- 基于当前仓库脚本与已验证的运行方式：
  - `start_real_stack.sh`
  - `stop_stack.sh`
  - `a2-web-console.service`

### Why this approach
当前用户要立刻实操建图，不应使用会强制打开 Nav2 的 `start_real1_suite.sh`。建图模式应该直接走 `start_real_stack.sh`，再单独拉起 Web 前端。

### Problems encountered
None.

### Fixes applied
None.

### Current result
已提供一套用于：
- 清理旧栈
- 保留 Unitree 前雷达源
- 启动 `slam_toolbox` 建图模式
- 启动 Web 前端/后端服务
- 验证节点与话题
- 保存地图

### Remaining risks or follow-ups
- 用户现场操作时仍需确认机器人慢速走线，避免急转和原地长时间抖动。

---

## Entry 46 — 解释 Web `ready` 状态跳变原因

### Time
2026-04-28 11:23:40 CST

### Action taken
针对用户提出的“为什么 ready 一直在跳”，检查 Web `ready` 显示的真实数据来源，以及 `/a2/real/report`、`/a2/localization_ok`、`/a2/map_ready` 的判定逻辑。

### Tool or method used
- 检查：
  - `src/safety_manager/safety_manager/real_readiness_monitor.py`
  - `src/safety_manager/safety_manager/safety_supervisor.py`
  - `src/localization_manager/localization_manager/localization_gate.py`
  - `web_console/backend/ros_bridge.py`
  - `web_console/frontend/src/components/StatusSidebar.tsx`

### Why this approach
`ready` 在前端并不是一个独立的 UI 变量，而是从 ROS 状态汇总链路映射过来的。要解释“为什么跳”，必须看它依赖哪些底层条件。

### Problems encountered
None.

### Fixes applied
None.

### Current result
确认了两个核心原因：

1. 前端 `ready` 显示的是 `status.system_ready`
   - 该值直接来自 `/a2/real/report`
   - `ros_bridge.py` 中 `_on_real_report()` 会把 `parsed.ready` 写入 `system_ready`

2. `/a2/real/report` 的 `ready` 由四个条件共同决定：
   - `sdk_connected`
   - `lidar_connected`
   - `map_ready`
   - `localization_ok`
   - 任意一个不满足，`ready=false`

并且：

- 在建图模式下，如果还没有 AMCL 初始位姿，则 `localization_ok=false`
- 所以建图时 `ready` 本来就不应该稳定为 `true`
- 同时 `safety_supervisor` 对 `lidar` 和 `robot_state` 使用 `0.5s` 超时
- 如果点云或状态有短暂抖动，底层门控也会短时切换

### Remaining risks or follow-ups
- 如果希望建图模式下界面“不再误导”，应把前端的 `ready` 从“全系统 ready”改成区分：
  - 建图 ready
  - 导航 ready
  - 安全门控 ready

---

## Entry 47 — 设计 Web 待机一键脚本职责边界

### Time
2026-04-28 11:30 CST

### Action taken
重新梳理“一个脚本拉起所有节点”的实际工程需求，确认本轮目标不是直接自动进入 mapping/navigation，而是先清场、保留原生前雷达源、拉起 Web 并停在可点击模式切换的待机态。

### Tool or method used
- 检查现有入口与职责边界：
  - `src/a2_system/tools/start_real1_suite.sh`
  - `src/a2_system/tools/start_real_stack.sh`
  - `web_console/backend/main.py`
  - `web_console/backend/stack_control.py`
  - `web_console/systemd/a2-web-console.service`

### Why this approach
如果脚本一上来就自动拉 `bringup.launch.py`，它会立刻进入 mapping 或 navigation 子链，与“先在 Web 上点击建图/导航模式”的操作方式冲突。真正需要的一键入口应当只负责底座、清理、服务可用性和错误归因。

### Problems encountered
现有 `start_real1_suite.sh` 明确偏导航套件：会直接启 Nav2、等待 `/navigate_to_pose` 和 `/scan`，不适合作为纯 Web 控制待机入口。

### Fixes applied
决定新增独立脚本：
- 只负责：
  - 清理残留 bringup
  - 关闭干扰 ROS1/native helper
  - 启动并验证原生前雷达源
  - 安装/重启 Web 服务
  - 输出失败上下文
- 不直接启动 mapping/navigation

### Current result
脚本设计边界已固定，避免再复用不合适的 `start_real1_suite.sh`。

### Remaining risks or follow-ups
- 仍需补 Web 端的启动失败摘要，否则用户从页面点建图/导航时仍只能看到泛化超时。

---

## Entry 48 — 新增 Web 待机一键脚本与本地 SSH 包装入口

### Time
2026-04-28 11:38 CST

### Action taken
新增机器人端一键待机脚本和本地 SSH 包装脚本，并把机器人端脚本加入 `a2_system` 安装清单。

### Tool or method used
- `apply_patch` 新增/修改：
  - `src/a2_system/tools/start_web_console_suite.sh`
  - `scripts/start_a2_console.sh`
  - `src/a2_system/CMakeLists.txt`

### Why this approach
需要同时满足两种使用方式：
- 在 A2 机器上直接运行安装后的 share 脚本
- 在开发机上一条命令 `ssh a2` 远程部署并启动

### Problems encountered
需要兼顾“脚本本身不启动 mapping/navigation”与“依然尽早暴露前雷达和 Web 服务问题”这两个目标。

### Fixes applied
机器人端脚本实现了以下职责：
- 调用 `configure_real_network.sh` 配置真实网口别名
- 停止 `stop_stack.sh` 和已知残留 ROS2 进程
- 停止 ROS1/native 干扰进程及已知 Docker 干扰容器
- 启动 `unitree_slam.service` 并验证 `/unitree/slam_lidar/points1`
- 杀掉 `navigation_mapping.py` / `dwa_obstacle_avoidance.py`
- 准备 `.venv`、必要时 build 前端
- 安装并重启 `a2-web-console.service`
- 输出 Web 健康状态、URL 和失败日志上下文
- 将 `runtime/web_stack_state.yaml` 重置为 `stopped` 待机态

本地包装脚本支持：
- `--host`
- `--iface`
- `--no-deploy`
- `--no-build-web`
- `--force-build-web`

### Current result
已形成新的待机入口：
- 机器人端：`start_web_console_suite.sh`
- 开发机端：`scripts/start_a2_console.sh`

### Remaining risks or follow-ups
- 还未在 A2 实机上跑通这个新入口，需要后续远端回归。

---

## Entry 49 — 补强 Web 栈启动失败日志摘要

### Time
2026-04-28 11:42 CST

### Action taken
增强 Web 后端 `stack_control.py` 的建图/导航启动失败信息，在“缺少节点”之外附带最新 bringup 日志路径和错误摘要；同时让前端侧边栏显示当前栈提示与日志路径。

### Tool or method used
- `apply_patch` 修改：
  - `web_console/backend/stack_control.py`
  - `web_console/frontend/src/components/ControlSidebar.tsx`

### Why this approach
用户明确要求“如果有报错日志显示出那个节点出错”。仅返回“建图模式启动超时，缺少节点”不够工程化，必须把最近的 `bringup_real_*.log` 摘要一起暴露出来。

### Problems encountered
前端此前只展示 `lastError` / `lastSuccess`，没有直接展示 `stack.message` 与 `stack.log_file`，导致即便后端保存了状态，页面也不一定能看到。

### Fixes applied
后端新增：
- 启动超时时拼接：
  - 缺失节点列表
  - 最新 bringup 日志路径
  - 最近错误高亮摘要
- mapping/navigation 启动异常时，把失败消息写回 `runtime/web_stack_state.yaml`

前端新增：
- 在“最近提示”面板显示：
  - `stack.message`
  - `stack.log_file`

### Current result
现在从页面点建图/导航时，若失败，除了 HTTP 错误信息外，还能看到：
- 哪些节点缺失
- 对应日志文件路径
- 最新日志中的错误摘要

### Remaining risks or follow-ups
- 还没有在真实失败场景下截图验证前端显示效果，但前端构建已通过。

---

## Entry 50 — 本地校验与文档补充

### Time
2026-04-28 11:45 CST

### Action taken
对新增脚本和前后端改动执行本地静态校验，并补充运行文档。

### Tool or method used
- 赋予可执行权限：
  - `chmod +x src/a2_system/tools/start_web_console_suite.sh`
  - `chmod +x scripts/start_a2_console.sh`
- 校验：
  - `bash -n src/a2_system/tools/start_web_console_suite.sh`
  - `bash -n scripts/start_a2_console.sh`
  - `python3 -m py_compile web_console/backend/stack_control.py`
  - `cd web_console/frontend && npm run build`
  - `git diff --check`
- 文档更新：
  - `src/a2_system/docs/operations_runbook.md`
  - `web_console/README.md`

### Why this approach
这次修改跨 shell、Python、React 三层，如果只做单层校验，很容易把一键脚本或者前端状态展示带坏。

### Problems encountered
None.

### Fixes applied
None.

### Current result
本地校验全部通过：
- shell 语法通过
- Python 编译通过
- 前端生产构建通过
- `git diff --check` 通过

### Remaining risks or follow-ups
- 还未实际 SSH 进 A2 执行 `start_web_console_suite.sh`
- 尚未在真实 A2 上验证：
  - `unitree_slam.service` 被脚本拉起后的点云稳定性
  - `a2-web-console.service` 在新待机流程中的表现
  - Web 页面点建图/导航时的失败摘要是否符合现场预期

---

## Final outcome

### Summary
本轮新增了一个“Web 待机一键启动”方案，目标是让机器人先进入一个干净、可诊断、由网页接管模式切换的稳定待机态，而不是直接拉起导航。脚本会清掉旧 bringup 和干扰进程、启动原生前雷达源、准备并重启 Web 服务，并在失败时打印原生服务、Web 服务和最近 bringup 日志的上下文。同时，Web 后端现在会在建图/导航启动失败时返回缺失节点、日志路径和错误摘要，前端也会把这些信息显示出来。

### Files changed
- `agent-logs/2026-04-27-agent-session.md`
- `scripts/start_a2_console.sh`
- `src/a2_system/CMakeLists.txt`
- `src/a2_system/docs/operations_runbook.md`
- `src/a2_system/tools/start_web_console_suite.sh`
- `web_console/README.md`
- `web_console/backend/stack_control.py`
- `web_console/frontend/src/components/ControlSidebar.tsx`

### Commands run
- `git -C /home/dell/a2_system_ws status --short`
- `sed -n ...` / `tail -n ...` inspection commands for startup scripts, backend, frontend, and logs
- `chmod +x src/a2_system/tools/start_web_console_suite.sh scripts/start_a2_console.sh`
- `bash -n src/a2_system/tools/start_web_console_suite.sh`
- `bash -n scripts/start_a2_console.sh`
- `python3 -m py_compile web_console/backend/stack_control.py`
- `cd web_console/frontend && npm run build`
- `git -C /home/dell/a2_system_ws diff --check`

### Verification
- Shell syntax checks passed
- Python compile check passed
- Frontend production build passed
- `git diff --check` passed
- Real-robot execution of the new standby script was not possible in this turn because A2 SSH/runtime validation was not available from the current session context

### Known limitations
- 新脚本还未在 A2 实机执行验证
- 前端当前仍把 `system_ready` 当作总 ready 展示，建图模式下仍可能显示 `false`
- 这次没有把 Web 按钮后的真实 ROS 节点成功/失败场景做现场回归，只完成了本地静态校验

---

## Entry 51 — A2 缺少新安装脚本的现场原因确认

### Time
2026-04-28 11:50 CST

### Action taken
根据用户在 A2 上执行 `/home/unitree/a2_system_ws/install/a2_system/share/a2_system/start_web_console_suite.sh` 得到的 `No such file or directory`，确认问题原因是机器人端尚未重新部署和构建，导致新的脚本还未进入 `install/a2_system/share/a2_system/`。

### Tool or method used
- 基于本地变更事实与安装路径规则判断：
  - `src/a2_system/CMakeLists.txt`
  - 新增脚本路径 `src/a2_system/tools/start_web_console_suite.sh`

### Why this approach
该错误路径明确指向安装产物不存在，不是权限问题，也不是脚本内部运行失败。当前最短修复路径是重新部署并 `colcon build`，而不是继续排查运行时。

### Problems encountered
A2 当前工作区仍是旧的 `install/` 产物，尚未包含新增脚本。

### Fixes applied
给出重新部署或直接使用源码路径运行的修复方式。

### Current result
已确认：需要先把本地改动同步到 A2，然后才能通过安装路径调用该脚本。

### Remaining risks or follow-ups
- 部署后仍需在 A2 上真实运行脚本并验证 Web、原生雷达和后续建图/导航点击流程。

---

## Entry 52 — 远端直接修复 A2 一键待机脚本并回归

### Time
2026-04-28 12:02 CST

### Action taken
直接通过 `ssh a2` 排查并修复新待机脚本在 A2 上的真实失败点，然后绕过全量部署脚本的问题，手动同步关键文件到 A2，重新构建并验证一键待机与 Web 建图启动。

### Tool or method used
- 远端排查：
  - `ssh a2 'systemctl status unitree_slam.service --no-pager'`
  - `ssh a2 'journalctl -u unitree_slam.service -n 160 --no-pager'`
  - `ssh a2 'pgrep -af ...'`
  - `ssh a2 'curl -fsS http://127.0.0.1:8080/api/health'`
  - `ssh a2 'curl -fsS http://127.0.0.1:8080/api/stack/status'`
  - `ssh a2 'curl -fsS -X POST http://127.0.0.1:8080/api/stack/start-mapping'`
  - `ssh a2 'curl -fsS http://127.0.0.1:8080/api/snapshot'`
- 本地修改：
  - `src/a2_system/tools/start_web_console_suite.sh`
- 同步方式：
  - `rsync -az --relative ... a2:/home/unitree/a2_system_ws/`
- 远端构建：
  - `colcon build --symlink-install --packages-select ...`
  - `npm run build`

### Why this approach
用户明确要求“你直接帮我解决 ssh a2”。最短路径不是继续让用户贴命令输出，而是直接连远端、看 service 日志、修脚本、同步、重建并回归。

### Problems encountered
1. `start_web_console_suite.sh` 初版在 A2 上卡在 `systemctl restart unitree_slam.service`
2. 即使避免 restart，`ros2 topic echo --once /unitree/slam_lidar/points1` 在 A2 当前 ROS CLI/daemon 状态下不稳定，导致脚本误判前雷达不可用
3. 本地 `scripts/deploy_to_a2.sh` 被 A2 上异常目录 `${A2_WORKSPACE}` 干扰，`rsync --delete` 失败
4. A2 当前 `ros2 node list` / `ros2 topic list` 仍偶发 `xmlrpc.client.Fault: !rclpy.ok()`

### Fixes applied
1. 脚本改为：
   - `unitree_slam.service` 已是 active 时不再 `restart`
   - 只复用当前原生点云源
2. 脚本改为：
   - 如果 `unitree_slam.service` 是本次新启动，则强制等待 `/unitree/slam_lidar/points1`
   - 如果 service 原本已 active，则只做“尽力验证”，失败仅告警，不中断 Web 待机流程
3. `prune_native_navigation_helpers()` 改成 `TERM + KILL` 两阶段
4. 部署阶段绕过 `deploy_to_a2.sh`，改用精确 `rsync --relative` 同步关键文件，再在 A2 上单独构建

### Current result
远端 A2 现在已经达到目标状态：

- `a2-web-console.service` 为 `active`
- `unitree_slam.service` 为 `active`
- 一键待机脚本已成功执行完成
- Web API 健康检查正常：
  - `GET /api/health` 返回 `backend_ok=true, ros_connected=true`
- Web 栈状态正常待机：
  - `GET /api/stack/status` 返回 `mode=stopped`
  - `message=Web 控制台已就绪，请在页面选择建图或导航模式`
- Web 建图按钮后端链路正常：
  - `POST /api/stack/start-mapping` 返回 `HTTP 200`
  - `mapping_profile=slam_toolbox`
  - `stack.mode=mapping`
  - `a2_sdk_bridge`、`a2_control_bridge`、`slam_toolbox`、`map_manager` 均已拉起
- `GET /api/snapshot` 显示：
  - `map.loaded=true`
  - 地图分辨率 `0.05`
  - `lidar_status.ready=true`
  - `map_manager_status.ready=true`
  - `localization_status=waiting_pose / no_pose`

这说明：
- 一键脚本已能把底座和 Web 拉起来
- Web 内点击建图模式能真实拉起 `slam_toolbox` 建图链
- 当前仍未进入导航 ready，仅因为还没给 initial pose

### Remaining risks or follow-ups
- A2 上 ROS CLI daemon 仍不稳定，`ros2 node list` / `ros2 topic list` 可能报 `!rclpy.ok()`，但 Web API 当前可正常工作
- `sync_monitor` 仍持续报 IMU/pointcloud skew 约 `0.189-0.190s`，这会继续影响建图质量，需要后续处理
- 本地 `deploy_to_a2.sh` 还未修复对异常目录 `${A2_WORKSPACE}` 的容错

---

## Entry 53 — 追查旧 ROS1 Docker 链路的建图节点

### Time
2026-04-28 12:15 CST

### Action taken
在当前无法重新 SSH 到 A2 的情况下，转而从本地保留的旧 ROS1 代码、Docker 使用攻略和架构总览文档中，重建那套“精度看起来更好”的建图链路，确认它到底调用了哪些节点和二进制。

### Tool or method used
- 代码检查：
  - `sed -n '1,520p' /home/dell/已有老代码/inside2/src/x_nav_control/scripts/robot_web_controller.py`
  - `nl -ba /home/dell/已有老代码/inside2/src/x_nav_control/scripts/robot_web_controller.py | sed -n '130,360p'`
  - `nl -ba /home/dell/已有老代码/outside/nav_map/x_nav.yaml | sed -n '1,220p'`
  - `sed -n '1,220p' /home/dell/已有老代码/inside2/src/a2_ros1_sdk/launch/a2_mid360_debug.launch`
  - `sed -n '1,220p' /home/dell/已有老代码/inside2/src/x_nav_control/launch/run.launch`
- 文档检查：
  - `sed -n '1,260p' /home/dell/桌面/已有老代码_全局导览.md`
  - `sed -n '1,260p' /home/dell/桌面/已有老代码使用攻略`
- 文本搜索：
  - `rg -n "z_mapping|z_slam|a2_ros1_sdk|livox_lidar_msg|foxglove_bridge|robot_web_controller" /home/dell/已有老代码 -S`

### Why this approach
用户明确指出前面 A2 上曾存在一套 ROS1 Docker 点云建图链路，而且扫描质量更好。当前最重要的是先还原那套链路的真实节点，而不是继续猜测它是不是 gmapping/cartographer。源码和现场操作攻略是最直接证据。

### Problems encountered
- 远端 A2 当前不可达，无法直接从容器现场取进程列表。
- 初次读取总览文档路径错误，实际文件在 `/home/dell/桌面/已有老代码_全局导览.md`。
- `rg` 输出过大，包含大量 build 产物噪声，需要以源码和文档为主筛选证据。

### Fixes applied
- 改为读取桌面上的总览文档和使用攻略。
- 使用精确源码片段和带行号的 YAML/脚本定位，而不是依赖全量搜索输出。

### Current result
已经确认旧 ROS1 Docker 链路不是 `gmapping`、`cartographer`、`move_base` 这种标准组合，而是一个自定义链：

- 主控入口：
  - `x_nav_control/robot_web_controller.py`
  - `x_nav_control/launch/run.launch`
- 底盘 SDK 桥：
  - `a2_ros1_sdk`
  - 发布 `/sdk/imu`、`/base_link/odom`、`/battery`
- 雷达输入：
  - `livox_ros_driver livox_lidar_msg.launch`
  - 主题 `/livox/lidar`
- 可视化 / Web：
  - `foxglove_bridge`
  - `python3 -m http.server 8000`
- 建图 / 定位核心：
  - 建图模式下 `robot_web_controller.py` 实际启动的是 `/catkin_ws/devel/lib/z_nav/z_mapping`
  - 非 mapping 模式下启动的是 `/catkin_ws/devel/lib/z_nav/z_slam`
  - planner 入口也直接指向 `/catkin_ws/devel/lib/z_nav/z_mapping`

这说明旧链路的核心精度来源大概率是：
- `MID360 + /sdk/imu + /base_link/odom`
- 自定义 `z_nav` 系列二进制
- 不是当前 ROS2 的前 Hesai 单雷达 `pointcloud_to_laserscan + slam_toolbox`

### Remaining risks or follow-ups
- 还没有从 `z_nav` 二进制内部拿到更细的算法实现，因为当前仓库没有对应源码。
- 需要后续把“旧 ROS1 MID360 + z_nav”与“当前 ROS2 front-Hesai + slam_toolbox”按传感器、时序、里程计和地图输出格式做一张正式对比表。

---

## Entry 54 — 修正 real mapping 的时间戳偏差与 `sync_monitor` 误报

### Time
2026-04-28 12:20-12:45 CST

### Action taken
针对 A2 实机上持续出现的 `sync_monitor` 约 `0.19s` skew，先在本地代码和远端 A2 上同时做了传感器时间链路排查、实现修正、重新部署、重建并回归验证。

### Tool or method used
- 本地代码检查与修改：
  - `pointcloud_frame_relay.py`
  - `sync_monitor.py`
  - `sensors.launch.py`
  - `real_lidar.yaml`
- 静态检查：
  - `python3 -m py_compile ...`
  - `git diff --check`
- 远端实机验证：
  - `ssh a2`
  - `colcon build --symlink-install --packages-select a2_system a2_bringup mid360_wrapper sensor_sync`
  - `bash ~/a2_system_ws/src/a2_system/tools/start_web_console_suite.sh --iface eth0`
  - `curl -fsS -X POST http://127.0.0.1:8080/api/stack/start-mapping`
  - 自定义 `rclpy` 订阅脚本同时统计 `/imu/data` 与 `/mid360/points` 的消息 age / nearest-pair skew
  - `curl -fsS -X POST http://127.0.0.1:8080/api/maps/save -d '{"map_id":"sync_fix_smoke"}'`

### Why this approach
`sync_monitor` 报 `0.19s` skew 已经直接影响建图质量判断。必须先确认这是“真实传感器时序问题”还是“监控算法误报”，再决定是调参数、重写监控逻辑，还是修正点云时间戳链路。

### Problems encountered
1. 初步远端对比发现：
   - `imu_age_avg ≈ 0.0006s`
   - `cloud_age_avg ≈ 0.1406s`
   - `latest_abs_skew ≈ 0.123423s`
   - `nearest_pair_skew_avg ≈ 0.023456s`
   这说明真正接近同步的 IMU/点云对并没有 `0.19s` 那么糟，监控逻辑和点云 header age 才是主要问题。
2. 原有 `sync_monitor` 用“最新 IMU header 与最新点云 header 直接相减”估算 skew，容易被异步到达和旧 header 放大。
3. 原有 `pointcloud_frame_relay` 直接透传原生点云 header，导致 `/mid360/points`、后续 `/scan` 继承了偏旧的时间戳。
4. 初次使用 `rsync --relative ... a2:/home/unitree/a2_system_ws/` 时把文件同步到了错误的嵌套目录：
   - `/home/unitree/a2_system_ws/home/dell/a2_system_ws/...`
   导致第一次远端构建并没有使用新代码。

### Fixes applied
1. 在 `mid360_wrapper/pointcloud_frame_relay.py` 增加 `restamp_on_receive` 参数。
   - 合同：
     - 输入：`/unitree/slam_lidar/points1`
     - 输出：`/mid360/points`
     - 行为：当 `restamp_on_receive=true` 时，用 relay 节点接收时刻重写 `header.stamp`
2. 在 `sensor_sync/sync_monitor.py` 中：
   - freshness 改为基于 receive time 判断，不再把旧 header 误判成 stale
   - skew 改为“最新点云对应最近 IMU”的 nearest-pair 估算
   - 增加时间历史窗口参数
3. 在 `sensors.launch.py` 与 `real_lidar.yaml` 中，把真实前雷达 relay 默认切为 `restamp_on_receive: true`
4. 用 `scp` 明确覆盖 A2 正确源码路径后重新构建：
   - `/home/unitree/a2_system_ws/src/...`

### Current result
修正后，A2 实机映射链路重新回归通过：

- `bringup_real_20260428_124500.log` 明确显示：
  - `restamp_on_receive=True`
  - `sync_monitor: state=ready;ready=true;reason=ok`
- 新实测指标：
  - `imu_age_avg ≈ 0.0006s`
  - `cloud_age_avg ≈ 0.0314s`
  - `nearest_pair_skew_avg ≈ 0.012502s`
- 说明：
  - 监控可用 skew 已从问题级别降到可接受范围
  - 点云 header age 从约 `140ms` 降到约 `31ms`
  - `/scan` 链路也不再持续继承明显过旧的点云时间戳
- 期间保存了一张回归烟测地图：
  - `map_id=sync_fix_smoke`
  - 路径 `/home/unitree/a2_system_ws/runtime/maps/sync_fix_smoke/map.yaml`
  - 分辨率 `0.05`

### Remaining risks or follow-ups
- 这次 `sync_fix_smoke` 只是时间链路回归烟测图，不代表最终导航精度地图。
- 启动阶段仍见过一次 `Message Filter dropping message ... earlier than all the data in the transform cache`，但随后 `sync_monitor` 保持 `ready=true`。
- 下一步必须继续处理导航侧 `AMCL not active / map_server bond timeout`，否则 initial pose 仍不能稳定闭环。

---

## Entry 55 — 追查导航栈 `AMCL inactive`，补强 lifecycle 超时与启动校验

### Time
2026-04-28 12:45-13:05 CST

### Action taken
对 `sync_fix_smoke` 启动导航并测试 initial pose，确认当前主阻塞点已经从时间同步转移到 Nav2 localization lifecycle：`map_server` 被激活，但 `amcl` 停在 `inactive`，导致 Web 虽显示导航栈已启动，实际上定位生命周期未就绪。

### Tool or method used
- 远端日志与状态：
  - `curl -fsS -X POST http://127.0.0.1:8080/api/stack/start-navigation -d '{"map_id":"sync_fix_smoke"}'`
  - `journalctl -u a2-web-console.service`
  - `ros2 lifecycle get /map_server`
  - `ros2 lifecycle get /amcl`
  - `ros2 lifecycle set /amcl activate`
  - `curl -X POST http://127.0.0.1:8080/api/localization/initialpose ...`
  - `ros2 topic echo --once /amcl_pose`
  - `ros2 topic echo --once /a2/localization/status`
- 本地代码检查与修改：
  - `web_console/backend/stack_control.py`
  - `src/a2_system/config/nav2_stack.yaml`
- 静态验证：
  - `python3 -m py_compile ...`
  - `python3 src/a2_system/scripts/config_schema_check.py`
  - `python3 src/a2_system/scripts/nav_contract_check.py`
  - `git diff --check`

### Why this approach
日志已经明确指出：
- `Received initial pose request, but AMCL is not yet in the active state`
- `lifecycle_manager_localization: Server map_server was unable to be reached after 4.00s by bond`

因此不该继续误判为 AMCL 算法问题，而应先修复生命周期编排与 Web 成功判定。

### Problems encountered
1. 导航 bringup 日志显示 `map_server` 读取地图成功，但 `lifecycle_manager_localization` 在默认 `4.0s` bond timeout 下中止 bringup，`amcl` 保持 `inactive [2]`。
2. Web 后端 `stack_control.py` 当前只检查“期望进程是否在线”，没有验证 Nav2 lifecycle 状态，因此会把“进程活着但 AMCL 未 active”的半失败状态误报成导航启动成功。
3. 初次修改 `stack_control.py` 时引入了一个缩进错误，被 `python3 -m py_compile` 立即抓到。

### Fixes applied
1. 在 `nav2_stack.yaml` 中显式新增：
   - `lifecycle_manager_localization.ros__parameters.bond_timeout: 12.0`
   - `lifecycle_manager_navigation.ros__parameters.bond_timeout: 12.0`
   变更记录：
   - 旧值：隐式默认 `4.0s`
   - 新值：`12.0s`
   - 原因：A2 当前导航 bringup 负载下，默认 bond 建连窗口过紧，导致 localization bringup 被过早中止
   - 预期影响：减少 `map_server/amcl` 生命周期建连误判，提升导航启动稳定性，不改变规划/控制精度参数
   - 验证方式：远端重新构建后执行 Web 导航启动，检查 `ros2 lifecycle get /map_server` 与 `ros2 lifecycle get /amcl`
2. 在 `web_console/backend/stack_control.py` 中补强导航启动校验：
   - `start_navigation()` 在原有“节点进程存在”之后，继续执行 `_ensure_navigation_lifecycle_ready()`
   - 新增 `_run_ros_shell()`，显式 `source /opt/ros/humble/setup.bash` 与工作区 `install/setup.bash`
   - 新增 `_get_lifecycle_state()` 与 `_set_lifecycle_transition()`
   - 新增 `_build_navigation_lifecycle_message()`
   - 行为合同：
     - 输入：Nav2 lifecycle 节点 `/map_server`、`/amcl`
     - 期望状态：两者均进入 `active`
     - 超时行为：返回明确的 lifecycle 错误与 bringup 日志摘要
     - 恢复行为：若节点停在 `inactive`，后端会自动尝试一次 `activate`
3. 修正了 `stack_control.py` 的缩进错误并重新通过静态检查。

### Current result
当前结论已经非常清楚：

- `sync_monitor` 的 `0.19s` skew 问题已经处理完毕并回归
- 导航 current blocker 不再是时间同步，而是 localization lifecycle 稳定性
- 手动执行 `ros2 lifecycle set /amcl activate` 后，`/amcl_pose` 立刻可出
- 再次发送 initial pose 时，错误从 `no_pose` 变成：
  - `xy_ok=false,yaw_ok=true,cov_x≈0.21-0.24,cov_y≈0.12-0.13,cov_yaw≈0.07`
- 这说明：
  - 生命周期问题是独立存在且已被准确定位
  - AMCL 已能工作
  - 当前地图/初始位姿匹配仍不足以满足 `localization_gate` 的工业阈值

### Remaining risks or follow-ups
- 还需要把上述 `bond_timeout` 与 `stack_control` 修正重新部署到 A2，并完成一次“无需手动 lifecycle set”的导航启动回归。
- `sync_fix_smoke` 地图只是烟测图，不足以证明导航精度；后续仍需用户在现场慢速闭环重建一张高质量地图，再验证 `AMCL ready`。
- 当前 `localization_gate` 阈值仍保持严格：
  - `max_xy_variance=0.18`
  - `max_yaw_variance=0.12`
  不应在没有正式验证前放宽。

---

## Entry 56 — 同步到 A2 并完成导航生命周期自动化回归

### Time
2026-04-28 13:05-13:15 CST

### Action taken
把 `nav2_stack.yaml` 与 `stack_control.py` 直接同步到 A2，重建 `a2_system`、重启 `a2-web-console.service`，然后用 Web API 重新执行待机脚本与导航启动，确认这次无需手动 `ros2 lifecycle set /amcl activate`。

### Tool or method used
- 同步：
  - `scp ... nav2_stack.yaml a2:/home/unitree/a2_system_ws/src/a2_system/config/nav2_stack.yaml`
  - `scp ... stack_control.py a2:/home/unitree/a2_system_ws/web_console/backend/stack_control.py`
- 远端构建与启动：
  - `colcon build --symlink-install --packages-select a2_system`
  - `sudo systemctl restart a2-web-console.service`
  - `bash ~/a2_system_ws/src/a2_system/tools/start_web_console_suite.sh --iface eth0`
  - `curl -fsS -X POST http://127.0.0.1:8080/api/stack/start-navigation -d '{"map_id":"sync_fix_smoke"}'`
- 远端验证：
  - `ros2 lifecycle get /map_server`
  - `ros2 lifecycle get /amcl`
  - `grep -n "bond" ~/a2_system_ws/runtime/logs/bringup_real_20260428_125554.log`
  - `curl -X POST http://127.0.0.1:8080/api/localization/initialpose ...`
  - `ros2 topic echo --once /amcl_pose`
  - `ros2 topic echo --once /a2/localization/status`

### Why this approach
本轮目标不是只在本地把代码写对，而是要证明 A2 上 Web 点击导航时，lifecycle 会自动闭环成功。最直接证据就是：`/map_server`、`/amcl` 都变成 `active [3]`，并且 bond 日志完整出现。

### Problems encountered
1. `bringup_real_20260428_125554.log` 很大，直接抓完整日志输出会被截断。
2. `/api/snapshot` 即使在 endpoint 已经返回 `covariance_rejected` 后，短时间内仍可能显示旧的 `no_pose` 状态，说明 Web 读数存在刷新时序差异。

### Fixes applied
1. 对日志验证改为 grep 关键 bond 片段，不再依赖整段日志。
2. 用三类证据交叉确认状态：
   - `ros2 lifecycle get`
   - `/amcl_pose` 实际输出
   - `/api/localization/initialpose` 返回值

### Current result
导航启动自动化回归已经通过：

- `POST /api/stack/start-navigation` 成功返回 `ok=true`
- `stack.status.mode=navigation`
- `ros2 lifecycle get /map_server` => `active [3]`
- `ros2 lifecycle get /amcl` => `active [3]`
- 新日志 `bringup_real_20260428_125554.log` 明确显示：
  - `Server map_server connected with bond`
  - `Server amcl connected with bond`
  - localization lifecycle manager 成功建立 bond timer

这说明：
- 之前的 `map_server bond timeout -> amcl inactive` 问题已经被修掉
- Web 启动导航不再停在“进程活着但生命周期半失败”的假成功状态

在这个自动化启动基础上再次发送 initial pose，结果是：
- `/amcl_pose` 可正常输出
- `/api/localization/initialpose` 返回：
  - `xy_ok=false,yaw_ok=true,cov_x≈0.21,cov_y≈0.12,cov_yaw≈0.06-0.07`
- `/a2/localization/status` 为 `covariance_rejected`

因此当前系统结论变为：
- 生命周期问题：已解决
- `sync_monitor` skew 误报：已解决
- 当前 remaining blocker：地图质量 / 初始位姿匹配不足，导致 `AMCL ready` 仍未达到工业阈值

### Remaining risks or follow-ups
- `sync_fix_smoke` 是烟测地图，不足以作为正式导航地图；需要现场重新慢速闭环建一张高质量地图。
- 若后续仍要继续提高精度，应优先围绕：
  - 实地重建地图
  - 初始位姿点选策略
  - 与旧 ROS1 `MID360 + z_mapping` 链路做对比验证

---

## Final outcome update 3

### Summary
- 已修复 A2 实机 `sync_monitor` 约 `0.19s` skew 的误报与点云旧时间戳问题。
- 已用修正后的真实链路保存新地图 `sync_fix_smoke`。
- 已修复导航启动时 `map_server bond timeout -> amcl inactive` 的生命周期问题。
- 现在 Web 启动导航后，`map_server` 与 `amcl` 都能自动进入 `active [3]`。
- 当前唯一未完成项已经收敛为：地图质量/匹配不足，`initial pose` 后 AMCL 协方差仍超出 `localization_gate` 严格阈值，所以 `ready=false`。

### Files changed
- `/home/dell/a2_system_ws/src/mid360_wrapper/mid360_wrapper/pointcloud_frame_relay.py`
- `/home/dell/a2_system_ws/src/sensor_sync/sensor_sync/sync_monitor.py`
- `/home/dell/a2_system_ws/src/a2_bringup/launch/sensors.launch.py`
- `/home/dell/a2_system_ws/src/a2_system/config/real_lidar.yaml`
- `/home/dell/a2_system_ws/src/a2_system/config/nav2_stack.yaml`
- `/home/dell/a2_system_ws/web_console/backend/stack_control.py`
- `/home/dell/a2_system_ws/agent-logs/2026-04-27-agent-session.md`

### Commands run
- 本地：
  - `python3 -m py_compile ...`
  - `python3 src/a2_system/scripts/config_schema_check.py`
  - `python3 src/a2_system/scripts/nav_contract_check.py`
  - `git diff --check`
- 远端 A2：
  - `colcon build --symlink-install --packages-select a2_system a2_bringup mid360_wrapper sensor_sync`
  - `bash ~/a2_system_ws/src/a2_system/tools/start_web_console_suite.sh --iface eth0`
  - `curl -X POST /api/stack/start-mapping`
  - `curl -X POST /api/maps/save`
  - `curl -X POST /api/stack/start-navigation`
  - `ros2 lifecycle get /map_server`
  - `ros2 lifecycle get /amcl`
  - `curl -X POST /api/localization/initialpose`
  - `ros2 topic echo --once /amcl_pose`
  - `ros2 topic echo --once /a2/localization/status`

### Verification
- 静态检查通过：
  - Python 编译
  - A2 配置 schema
  - A2 导航 contract
  - `git diff --check`
- A2 实机验证通过：
  - `sync_monitor: ready=true`
  - 新地图保存成功
  - 导航启动后 `/map_server`、`/amcl` 均为 `active [3]`
  - initial pose 后 `/amcl_pose` 可输出

### Known limitations
- 还没有现场重建一张正式高质量地图；`sync_fix_smoke` 只用于链路回归。
- `AMCL ready` 仍未达成，原因不是 lifecycle，而是协方差未收敛到工业阈值：
  - `max_xy_variance=0.18`
  - `max_yaw_variance=0.12`
- Web `/api/snapshot` 在 initial pose 刚发送后的短时间窗口内可能仍显示旧状态，需要后续单独核对前端刷新时序。

---

## Entry 57 — 收尾到 Web 待机态

### Time
2026-04-28 13:16 CST

### Action taken
在完成生命周期和 initial pose 回归后，把 A2 ROS 栈停止，保留 `a2-web-console.service` 在线，方便后续由用户直接从前端重新启动建图模式做正式实地建图。

### Tool or method used
- `curl -fsS -X POST http://127.0.0.1:8080/api/stack/stop`
- `curl -sS http://127.0.0.1:8080/api/stack/status`
- `systemctl is-active a2-web-console.service`

### Why this approach
当前 `sync_fix_smoke` 只是烟测地图，不应继续把系统停留在一套 `ready=false` 的 smoke 导航态。回到 Web 待机更适合下一步人工推狗重建正式地图。

### Problems encountered
None.

### Fixes applied
None.

### Current result
- A2 Web 服务仍为 `active`
- Web 栈状态已回到 `mode=stopped`
- 所有已保存地图仍可在前端下拉选择
- 可以直接从浏览器重新点“启动建图模式”

### Remaining risks or follow-ups
- 下一次正式验证应在现场重新建图，不应继续使用 `sync_fix_smoke` 做精度判断。

---

## Entry 58 — 确认现有“自动扫图”能力边界

### Time
2026-04-28 13:20 CST

### Action taken
检查仓库中是否已有“自动建图/自动扫图”实现，并确认它的能力边界、依赖和启动方式。

### Tool or method used
- `sed -n '1,260p' src/a2_system/docs/scan_mission.md`
- `sed -n '1,260p' src/a2_system/scripts/auto_scan_mission.py`
- `sed -n '1,260p' src/a2_system/config/scan_mission.yaml`
- `sed -n '1,220p' src/a2_bringup/launch/scan_mission.launch.py`

### Why this approach
用户现在不想手动推狗扫图，需要先判断现有系统里是否已经有可复用的自动路径扫描，而不是直接提出一个尚未落地的“探索式建图”方案。

### Problems encountered
None.

### Fixes applied
None.

### Current result
仓库里已有自动扫图链路，但它是“waypoint-based auto scan mission”，不是 frontier exploration：

- 文档：`src/a2_system/docs/scan_mission.md`
- 节点：`src/a2_system/scripts/auto_scan_mission.py`
- 参数：`src/a2_system/config/scan_mission.yaml`
- 启动：`src/a2_bringup/launch/scan_mission.launch.py`

能力是：
- 读取 YAML waypoint 路线
- 通过 `/navigate_to_pose` 逐点自动行走
- 任务模式切到 `mapping`
- 任务完成后自动保存地图并产出报告

边界是：
- 需要预先给定 waypoint 路线
- 不是机器人自己在未知区域做 frontier exploration
- 依赖现有导航/定位/地图契约已经正常

### Remaining risks or follow-ups
- 如果用户要“完全自动探索建图”，需要额外实现或接入 exploration planner，这不是当前现成稳定主链。
- 如果用户接受“预设路线自动扫图”，下一步可以直接准备 waypoint 文件并接入 Web 一键启动。

---

## Entry 59 — 确认 3D 建图与当前 Web 前端显示能力

### Time
2026-04-28 13:30 CST

### Action taken
检查当前 Web 前端、后端和 map manager 的地图数据模型，确认如果真实建图链改成“前自带雷达 3D 直建图、不压成 2D `/scan`”，现有网页还能否直接显示地图，以及显示的是不是 3D。

### Tool or method used
- `rg -n "OccupancyGrid|PointCloud2|MapCanvas|map.data|/map" web_console src/map_manager -S`
- `sed -n '1,260p' web_console/frontend/src/App.tsx`
- `sed -n '1,260p' web_console/backend/models.py`
- `sed -n '1,260p' web_console/backend/ros_bridge.py`

### Why this approach
这个问题不能靠猜。必须确认现有页面到底是 2D canvas + `OccupancyGrid`，还是已经支持 3D 点云/3D 地图可视化。

### Problems encountered
None.

### Fixes applied
None.

### Current result
已经确认：

- 当前 Web 后端地图模型是 `MapSnapshot(width,height,resolution,origin,data)`
- 当前 Web 订阅的是 `/map` 上的 `nav_msgs/msg/OccupancyGrid`
- 当前前端渲染组件是 `MapCanvas.tsx`，本质是 HTML canvas 渲染 2D 栅格

因此：
- 如果建图链改成“前自带雷达 3D 直建图”，**现有 Web 不能直接显示 3D 地图**
- 它仍然只能显示 2D 占据栅格
- 只有在 3D SLAM 额外再产出一个 2D `/map` 投影/切片时，现有 Web 才还能继续显示地图

### Remaining risks or follow-ups
- 如果后续要真正显示 3D 地图，需要新增 3D 可视化链路，例如：
  - Web 订阅 `PointCloud2`/mesh/marker
  - Three.js / Foxglove / RViz WebViewer 类前端
- 如果仍要继续使用 AMCL/Nav2，系统里通常仍然需要保留一份 2D 地图产物，而不是完全只保留 3D 地图。

---

## Entry 60 — 修复导航启动时的 lifecycle 查询抖动误判

### Time
2026-04-28 14:20 CST

### Action taken
针对导航模式启动时报：
- `map_server=active [3]`
- `amcl=active [3]`
但同时夹带 `map_server=query_failed: 命令超时: ros2 lifecycle get /map_server`

定位并修复 `stack_control.py` 中的 lifecycle 校验误判逻辑。

### Tool or method used
- 代码检查：
  - `sed -n '220,380p' web_console/backend/stack_control.py`
  - `sed -n '380,520p' web_console/backend/stack_control.py`
- 代码修改：
  - `apply_patch`
- 验证：
  - `python3 -m py_compile web_console/backend/stack_control.py`
  - `git diff --check`
- 部署：
  - `scp .../stack_control.py a2:/home/unitree/a2_system_ws/web_console/backend/stack_control.py`
  - `ssh a2 'sudo systemctl restart a2-web-console.service && systemctl is-active a2-web-console.service'`

### Why this approach
从用户提供的错误可以直接判断：
- `map_server` 和 `amcl` 实际已经 `active`
- 真正失败的是 `ros2 lifecycle get` 这个查询过程瞬时超时

也就是说这是“状态查询抖动”而不是“导航栈没起来”。

### Problems encountered
当前 `_ensure_navigation_lifecycle_ready()` 的逻辑是：
- 每轮都调用 `ros2 lifecycle get`
- 只要某一轮查询失败，就会把稳定计数打断
- 即使节点前一轮已经 `active`，也可能最终被拼成一个假失败信息

### Fixes applied
在 `web_console/backend/stack_control.py` 中增加了 `last_known_states`：

- 如果某节点这轮 `query_failed:*`
- 但上一轮已确认是 `active`
- 就继续沿用上一轮 `active` 状态，不再把它当作真正未就绪

同时在所有节点都为 `active` 时清空历史 `failures`，避免把旧的瞬时失败拼进最终报错文案。

### Current result
- 本地静态检查通过
- 新版 `stack_control.py` 已同步到 A2
- `a2-web-console.service` 已重启并保持 `active`

### Remaining risks or follow-ups
- 这个修复针对的是“查询抖动误判”，不是替代真实 lifecycle 检查。
- 如果后续再出现 `map_server/amcl` 真正不是 `active`，Web 仍会继续报真失败。

---

## Entry 61 — 生成“全链路 2D 改 3D”任务 Prompt

### Time
2026-04-28 14:35 CST

### Action taken
根据当前 A2 系统现状、用户的迁移目标和已知限制，整理一份可直接交给另一个模型或工程执行者的高质量 Prompt，目标是把建图、扫图、导航和 Web 前端从当前 2D 主链迁移到 3D 主链。

### Tool or method used
- 基于当前会话中已确认的系统现状和代码结构整理任务说明。
- 更新本次会话日志。

### Why this approach
用户当前不是要我立刻开改，而是要一份高质量、上下文完整、目标清晰的 Prompt 作为后续“全链路 3D 化”任务书。先把约束和目标写准，比直接开始大改更合理。

### Problems encountered
None.

### Fixes applied
None.

### Current result
已准备生成一份覆盖以下范围的 Prompt：
- 前自带雷达 3D 直连主链
- 放弃 `pointcloud_to_laserscan -> /scan -> slam_toolbox -> AMCL -> 2D OccupancyGrid` 作为系统真值主链
- 建图 / 自动扫图 / 定位 / 导航 / Web 前端同步切到 3D-first 设计

### Remaining risks or follow-ups
- Prompt 只是任务书，不等于已选定最终 3D SLAM / 3D localization / 3D planning 具体算法。
- 后续真正实施时，仍需要分阶段落地，不能一次性盲目替换所有底层模块。

---

## Entry 62 — 开始实施 3D 迁移 Phase 0：显式表示元数据 + 审计工具

### Time
2026-04-28 14:45 CST

### Action taken
按照“先冻结接口和现状，再替换主链”的思路，先在仓库中实施 3D 迁移的 Phase 0，而不是直接硬切建图/导航。

已完成的实现包括：

1. 给当前系统补上显式“表示方式”元数据
2. 给 map 保存元数据补上 representation/source_topic
3. 给 Web 地图快照和地图列表模型补上 representation 字段
4. 新增一个 2D->3D 迁移审计脚本
5. 新增一份仓库内的 3D 迁移落地文档

### Tool or method used
- 代码检查：
  - `mapping.launch.py`
  - `slam.launch.py`
  - `slam.yaml`
  - `map_manager_node.py`
  - `goal_bridge.py`
  - `web_console` backend/frontend model files
- 代码修改：
  - `apply_patch`
- 静态验证：
  - `python3 -m py_compile ...`
  - `python3 src/a2_system/scripts/three_d_migration_audit.py`
  - `cd web_console/frontend && npm run build`
  - `git diff --check`

### Why this approach
当前仓库大量 2D 假设是“隐式”散在各模块里的。直接替换主链会导致：
- 不知道哪些点仍默认 OccupancyGrid
- 地图保存/前端/自动扫图仍把 2D 当成真值
- 迁移过程不可观测

所以第一步必须先把“表示方式”显式化，让系统知道自己现在到底还是不是 `occupancy_grid_2d`。

### Problems encountered
None.

### Fixes applied
None.

### Current result
已新增/修改以下内容：

- `src/a2_system/config/slam.yaml`
  - 新增：
    - `primary_map_representation`
    - `localization_representation`
    - `navigation_representation`
    - `web_map_representation`
    - `front_lidar_input_topic`
    - `front_lidar_input_type`
    - `pointcloud_projection_enabled`
- `src/a2_system/config/map_manager.yaml`
  - 新增 `map_representation: occupancy_grid_2d`
- `src/map_manager/map_manager/map_manager_node.py`
  - 保存地图 metadata 时写入：
    - `representation`
    - `source_topic`
  - status 文本里也会带：
    - `representation`
    - `source_topic`
- `web_console/backend/models.py`
  - `MapSnapshot` 新增 `representation`
  - `SavedMapInfo` 新增 `representation` / `source_topic`
- `web_console/backend/ros_bridge.py`
  - 当前 `/map` 快照显式标记为 `occupancy_grid_2d`
- `web_console/backend/stack_control.py`
  - 读取/保存地图 metadata 时保留 `representation`
- `web_console/frontend/src/types.ts`
  - 同步新增 `representation`
- `web_console/frontend/src/App.tsx`
  - 初始 snapshot 默认值加入 `representation`
- 新增脚本：
  - `src/a2_system/scripts/three_d_migration_audit.py`
- 新增文档：
  - `src/a2_system/docs/three_d_migration_plan.md`

审计脚本当前输出已经能明确指出硬 2D 依赖：
- `mapping_stack_profile=slam_toolbox`
- `pointcloud_projection_enabled=True`
- `input_pose_topic=/amcl_pose`
- `lifecycle_manager_localization=['map_server', 'amcl']`
- `map_manager.occupancy_topic=/map`
- `scan_mission.map_topic=/map`
- `scan_mission.pose_topic=/amcl_pose`

### Remaining risks or follow-ups
- 这一步还没有引入真正的 3D mapper / 3D localization / 3D navigation。
- 当前 runtime 默认仍保持 2D，以避免立即打断现网。
- 下一步如果继续实施，应该进入 Phase 1：
  - 给前自带雷达 `/unitree/slam_lidar/points1` 接并行 3D mapping 主链
  - 保留 2D 只作为兼容副产物，而不再是主真值

---

## Entry 63 — Phase 1 设计收敛：先把前自带雷达 3D 资产纳入正式存图链

### Time
2026-04-28 15:18 CST

### Action taken
重新核对了本地实现与 A2 实机可用能力，决定 Phase 1 先不强行宣称“3D SLAM 已切换完成”，而是先把前自带雷达的 3D 原始资产纳入正式存图链。

已完成的调查包括：
- 检查 `map_manager_node.py` 当前只订阅 `/map`，只保存 `map.pgm/map.yaml`
- 检查 Web `/api/maps/save` 当前直接调用 `stack_controller.save_map(node.get_map_snapshot())`，绕开了 `map_manager`
- 通过 `ssh a2` 确认以下话题在线：
  - `/unitree/slam_lidar/points1` -> `sensor_msgs/msg/PointCloud2`
  - `/global_map` -> `nav_msgs/msg/OccupancyGrid`
  - `/gridmap` -> `grid_map_msgs/msg/GridMap`
  - `/planner_map` -> `grid_map_msgs/msg/GridMap`
- 通过 `ssh a2` 确认 A2 上 Python `sensor_msgs_py` 不可导入，但 `numpy` 可用

### Tool or method used
- 文件检查：
  - `src/map_manager/map_manager/map_manager_node.py`
  - `web_console/backend/main.py`
  - `web_console/backend/stack_control.py`
  - `web_console/backend/ros_bridge.py`
  - `src/a2_system/config/map_manager.yaml`
- 实机调查：
  - `ssh a2`
  - `ros2 topic list/type/info`
  - Python 模块存在性检查

### Why this approach
当前 A2 上并没有一个已验证可直接接管的全新 3D SLAM 包可立即替换现网，而前自带雷达 `/unitree/slam_lidar/points1` 是真实稳定输入。

因此第一步最稳妥的 Phase 1 落地方式是：
- 让 `map_manager` 正式订阅并保存前雷达 3D 点云快照
- 让 Web 存图走 `manage_map` 服务
- 让每次地图保存都同时包含：
  - 现有 2D Nav2 兼容地图
  - 3D 前雷达原始资产

这样能先把“3D 真值资产”纳入工程主线，而不是继续只把 2D 快照当唯一正式产物。

### Problems encountered
- A2 上 `sensor_msgs_py` Python 模块不可导入，不能简单依赖 `read_points`
- `/gridmap` 和 `/planner_map` 虽在线，但 Python 侧 `grid_map_msgs` 运行时绑定未确认可用

### Fixes applied
- 决定在 `map_manager` 内部手动解析 `PointCloud2` 的 XYZ 字段，避免依赖 `sensor_msgs_py`
- 决定本轮先以 `PointCloud2 -> PCD` 资产保存为核心，不在同一轮强接 `grid_map_msgs`

### Current result
已确定接下来的具体实现方向：
- `map_manager` 增加前自带雷达点云订阅与 PCD 保存
- Web `/api/maps/save` 改走 `/map_manager/manage_map`
- 地图 metadata 增加 3D 资产条目

### Remaining risks or follow-ups
- 这一步仍然不是“3D 导航主链切换完成”，而是 3D-first 存图链开始落地
- 后续仍需继续推进：
  - 3D localization
  - 3D navigation
  - Web 3D viewer

---

## Entry 64 — Phase 1 实施完成：前自带雷达 3D 资产进入正式存图链并在 A2 实机验证

### Time
2026-04-28 14:48 CST

### Action taken
完成了第一轮真正的 3D-first 工程落地，并在 A2 上验证通过：

1. 改造 `map_manager_node.py`
- 增加 `/unitree/slam_lidar/points1` 订阅
- 新增参数：
  - `pointcloud_topic_3d`
  - `pointcloud_snapshot_enabled`
  - `pointcloud_max_points`
- `save` 时除了继续保存 `map.pgm/map.yaml`，还会导出：
  - `front_lidar_snapshot.pcd`
- `metadata.yaml` 增加：
  - `pointcloud_topic_3d`
  - `artifacts[]`

2. 改造 Web 存图路径
- `web_console/backend/ros_bridge.py`
  - 新增 `ManageMap` service client
  - 新增 `save_managed_map()`
- `web_console/backend/main.py`
  - `/api/maps/save` 不再直接走 `stack_controller.save_map(snapshot)`
  - 改为调用 `/map_manager/manage_map`

3. 更新配置
- `src/a2_system/config/map_manager.yaml`
- `web_console/backend/config.py`

4. 将改动同步到 A2，构建并回归
- `rsync` 同步源码到 `a2`
- `ssh a2`
- `colcon build --symlink-install --packages-select map_manager a2_system`
- `systemctl restart a2-web-console.service`
- 通过 Web API 启动 mapping
- 保存烟测地图 `three_d_asset_smoke`

### Tool or method used
- 本地编辑：
  - `apply_patch`
- 静态验证：
  - `python3 -m py_compile`
  - `three_d_migration_audit.py`
  - `git diff --check`
- 实机部署与验证：
  - `rsync`
  - `ssh a2`
  - `colcon build`
  - `curl http://127.0.0.1:8080/api/...`
  - `ls`, `sed`, `head`

### Why this approach
这一步是当前最稳妥、最真实的 3D 迁移切入口：
- 不先碰建图/定位/导航主链，避免一次性破坏现网
- 先让正式“地图保存产物”里出现 3D 真值资产
- 这样后续 3D localization / 3D navigation / Web 3D viewer 都有标准输入可以对接

### Problems encountered
- A2 上 `sensor_msgs_py` 不可导入，不能直接用 `read_points`
- A2 上 Web API 返回中未体现 `representation/source_topic`

### Fixes applied
- 在 `map_manager` 内手动解析 `PointCloud2` 的 FLOAT32 `x/y/z`
- ASCII PCD 导出采用采样步长控制点数上限，避免依赖额外 Python 运行时
- 发现 A2 上 Web 模型文件未完全同步后，补同步：
  - `web_console/backend/models.py`
  - `web_console/backend/stack_control.py`
  并重启 `a2-web-console.service`

### Current result
A2 实机上已验证：

- `POST /api/stack/start-mapping` 成功
- `POST /api/maps/save` 成功
- 新地图目录：
  - `/home/unitree/a2_system_ws/runtime/maps/three_d_asset_smoke/`
- 目录内同时包含：
  - `map.yaml`
  - `map.pgm`
  - `front_lidar_snapshot.pcd`
  - `metadata.yaml`

其中 `metadata.yaml` 已写入：
- `representation: occupancy_grid_2d`
- `pointcloud_topic_3d: /unitree/slam_lidar/points1`
- `artifacts`
  - `occupancy_grid_2d`
  - `pointcloud_snapshot_3d`

`front_lidar_snapshot.pcd` 大小约 3.1 MB，点数：
- `points_total: 115200`
- `points_saved: 115200`

Web `/api/maps` 对新地图 `three_d_asset_smoke` 已能返回：
- `representation: occupancy_grid_2d`
- `source_topic: /map`

### Remaining risks or follow-ups
- 当前保存链已经 3D-first，但主 runtime 仍是：
  - `pointcloud_to_laserscan -> slam_toolbox -> /map`
- 3D 资产已进入正式产物，但还没有接入：
  - 3D localization
  - 3D navigation
  - Web 3D viewer
- `representation` 目前仍标记为 `occupancy_grid_2d`，因为当前主地图真值尚未切到 3D 表达

---

## Entry 65 — Web 地图模型升级：显式展示 3D 资产存在性

### Time
2026-04-28 15:05 CST

### Action taken
继续推进 3D 迁移的“可见性”层，把地图是否带 3D 资产正式接入 Web 数据模型和前端侧边栏。

已完成：
- `web_console/backend/models.py`
  - 新增 `MapArtifactInfo`
  - `SavedMapInfo` 新增：
    - `pointcloud_topic_3d`
    - `has_pointcloud_3d`
    - `artifacts`
- `web_console/backend/stack_control.py`
  - `list_maps()` 解析 `metadata.yaml` 里的 `artifacts`
  - 对 `pointcloud_snapshot_3d` 自动计算 `has_pointcloud_3d`
  - 旧 `stack_controller.save_map()` 也补上兼容 `artifacts`
- `web_console/frontend/src/types.ts`
  - 同步新增 `MapArtifactInfo`
  - `SavedMapInfo` 同步新增 3D 资产相关字段
- `web_console/frontend/src/components/ControlSidebar.tsx`
  - 在选中地图后显示：
    - `representation`
    - `2D source`
    - `3D asset`
    - `3D topic`
    - `3D points`
- `web_console/frontend/src/styles.css`
  - 增加地图资产卡片样式

### Tool or method used
- 代码修改：
  - `apply_patch`
- 静态验证：
  - `python3 -m py_compile`
  - `npm run build`
  - `git diff --check`

### Why this approach
前一轮已经把 3D 点云资产保存到磁盘，但如果 Web 不认识这些资产，系统层面仍然会继续把地图当成单纯 2D 文件。

这一步先把“3D 资产存在性”变成正式契约字段，能让后续工作更顺：
- 接 Web 3D viewer 时直接消费 `artifacts`
- 做 3D localization / 3D navigation 分流时，可按地图能力判断
- 调试时不用再手查磁盘目录

### Problems encountered
None.

### Fixes applied
None.

### Current result
本地已通过：
- `python3 -m py_compile web_console/backend/models.py web_console/backend/stack_control.py`
- `cd web_console/frontend && npm run build`
- `git diff --check`

新的 Web 契约已经能够表达：
- 哪张地图有 `pointcloud_snapshot_3d`
- 该 3D 资产来自哪个 topic
- 大概保存了多少点

### Remaining risks or follow-ups
- 这一步目前还只是本地代码和前端静态构建，尚未同步到 A2 服务实例
- 下一步应同步：
  - `web_console/backend/models.py`
  - `web_console/backend/stack_control.py`
  - 前端静态构建产物
  到 A2 并重启 `a2-web-console.service`

---

## Entry 66 — A2 同步受阻：SSH 远端主动断开

### Time
2026-04-28 15:14 CST

### Action taken
尝试将最新的 Web 3D 资产展示改动同步到 A2：
- `rsync` backend:
  - `web_console/backend/models.py`
  - `web_console/backend/stack_control.py`
- `rsync` frontend/static:
  - `web_console/frontend/src/types.ts`
  - `web_console/frontend/src/components/ControlSidebar.tsx`
  - `web_console/frontend/src/styles.css`
  - `web_console/backend/static/`

随后又用最小命令做连通性检查：
- `ssh a2 'echo ok'`

### Tool or method used
- `rsync -av ... a2:...`
- `ssh a2`

### Why this approach
前一轮 3D 资产保存链已在 A2 验证成功，下一步自然是把新的 Web 模型与前端展示同步过去，让 A2 页面直接显示“这张地图有 3D 点云资产”。

### Problems encountered
远端 SSH 在握手阶段即被 A2 主动断开，错误为：
- `kex_exchange_identification: Connection closed by remote host`
- `Connection closed by 192.168.31.49 port 22`

这说明当前阻塞不是本地代码、也不是 rsync 参数，而是：
- A2 侧 SSH 服务异常
- 或 SSH 并发/限流/临时拒绝
- 或网络链路瞬时问题

### Fixes applied
None yet.

### Current result
- 本地代码、后端模型、前端构建都已完成
- 但这批“Web 识别 3D 资产”的更新尚未同步到 A2
- 现阶段 A2 上已生效的内容仍是上一轮：
  - `map_manager` 3D 点云资产保存
  - Web 后端存图走 `manage_map`

### Remaining risks or follow-ups
- 待 SSH 恢复后，需要继续：
  - 同步最新 Web 文件到 A2
  - 重启 `a2-web-console.service`
  - 验证 `/api/maps` 和页面侧边栏是否显示 `has_pointcloud_3d`

---

## Entry 67 — SSH 恢复后继续推进：A2 上启用 Web 3D 点云与 3D 资产接口

### Time
2026-04-28 15:34 CST

### Action taken
SSH 恢复后，继续把“Web 前端看到 3D”这条链落到 A2。

本地新增/修改：
- `web_console/backend/main.py`
  - 新增 `GET /api/maps/{map_id}/artifacts/{artifact_name}`
  - 允许按地图目录安全下载资产文件（如 `front_lidar_snapshot.pcd`）
- `web_console/backend/models.py`
  - 新增 `PointCloudSnapshot`
  - `DashboardSnapshot` 增加 `pointcloud`
- `web_console/backend/config.py`
  - 默认 `pointcloud_topic` 改为 `/unitree/slam_lidar/points1`
- `web_console/backend/ros_bridge.py`
  - 新增 `PointCloud2` 订阅
  - 手动解析前自带雷达点云为采样后的 3D 点列表
  - 通过 websocket / snapshot 广播 `pointcloud`
- `web_console/frontend/src/components/PointCloudCanvas3D.tsx`
  - 新增 3D 点云 viewer
  - 支持：
    - 实时点云显示
    - 从已保存 `front_lidar_snapshot.pcd` 拉取 ASCII PCD 并渲染
    - 鼠标拖动旋转
    - 滚轮缩放
- `web_console/frontend/src/App.tsx`
  - 主视图改为 `3D pointcloud` 优先，缺失时才退回 `MapCanvas`
- `web_console/frontend/src/styles.css`
  - 增加 3D viewer 视觉样式

同时把以下配置切到显式 3D-first：
- `src/a2_system/config/slam.yaml`
  - `mapping_stack_profile: front_lidar_pointcloud_3d`
  - `*_representation: pointcloud_map_3d`
  - `pointcloud_projection_enabled: false`
  - `project_to_nav2_map: false`
- `src/a2_system/config/map_manager.yaml`
  - `map_representation: pointcloud_map_3d`
- `src/a2_bringup/launch/mapping.launch.py`
  - 新增 `front_lidar_pointcloud_3d` profile

### Tool or method used
- 本地代码修改：
  - `apply_patch`
- 本地静态验证：
  - `python3 -m py_compile`
  - `npm run build`
  - `three_d_migration_audit.py`
  - `git diff --check`
- A2 同步：
  - `rsync`
  - `ssh a2`
  - `colcon build`
  - `systemctl restart a2-web-console.service`
  - `curl /api/...`

### Why this approach
上一轮只是把 3D 点云资产保存到了磁盘里，还不等于 Web 已经“用上了 3D”。

这一轮的目标是：
- Web 后端真实感知并广播 3D 点云
- Web 前端真实显示 3D 点云
- 已保存地图的 `PCD` 可以通过 API 被前端加载

这样“3D 地图在网页里可见”才成立。

### Problems encountered
- 两次 `rsync` 时把少量文件误同步到了 `/home/unitree/a2_system_ws/src/` 根目录，而不是包目录

### Fixes applied
- 立即补同步到正确路径
- 删除误同步的孤立文件：
  - `map_manager.yaml`
  - `mapping.launch.py`
  - `slam.yaml`
  - `three_d_migration_audit.py`
  - `localization.yaml`
  - `localization_gate.py`

### Current result
A2 上已验证：

1. `GET /api/maps`
- 地图 `three_d_asset_smoke` 已正确返回：
  - `has_pointcloud_3d: true`
  - `pointcloud_topic_3d: /unitree/slam_lidar/points1`
  - `artifacts[pointcloud_snapshot_3d]`

2. `GET /api/maps/three_d_asset_smoke/artifacts/front_lidar_snapshot.pcd`
- 成功返回 PCD 文件头

3. 启动 mapping 后 `GET /api/snapshot`
- `pointcloud.loaded = true`
- `pointcloud.representation = pointcloud_map_3d`
- `pointcloud.frame_id = hesai_lidar` / `lidar_link`
- `pointcloud.source_topic = /unitree/slam_lidar/points1`
- `points_sampled` 正常

这说明：
- 实时 3D 点云已经进入 Web snapshot
- 已保存 3D 资产也可以由前端按需拉取

### Remaining risks or follow-ups
- 当前 3D viewer 已上线，但 3D 场景中的“点选导航目标/初始位姿”尚未实现
- 当前 `map` 仍为空，因为 3D-first mapping profile 下不再产出 2D `/map`
- 后续若要真正全链路 3D，需要继续处理：
  - 3D localization 真值源
  - 3D navigation contract
  - 3D goal picking / task flow

---

## Entry 68 — 定位入口去 AMCL 化：仓库支持 Odometry 型 3D 位姿输入

### Time
2026-04-28 15:41 CST

### Action taken
继续推进全链路 3D，把“定位真值只能是 `/amcl_pose`”的硬依赖松开。

已完成：
- `src/localization_manager/localization_manager/localization_gate.py`
  - 新增参数：
    - `input_pose_msg_type`
  - 支持两类输入：
    - `geometry_msgs/msg/PoseWithCovarianceStamped`
    - `nav_msgs/msg/Odometry`
- `src/a2_system/config/localization.yaml`
  - 默认改为：
    - `input_pose_topic: /uslam/localization/odom`
    - `input_pose_msg_type: nav_msgs/msg/Odometry`
- `web_console/backend/config.py`
  - 新增：
    - `localization_pose_topic`
    - `localization_pose_msg_type`
- `web_console/backend/config.example.yaml`
- `web_console/backend/config.docker.yaml`
  - 默认改为 `localization_pose_topic: /uslam/localization/odom`
- `web_console/backend/ros_bridge.py`
  - 位姿订阅不再固定 AMCL
  - 如果配置是 `Odometry`，则从 `nav_msgs/Odometry` 解析位姿
- `web_console/backend/models.py`
  - `RobotPose.source` 默认从 `amcl_pose` 改为 `localization_pose`
- `web_console/frontend/src/App.tsx`
  - 初始 pose source 同步改名

### Tool or method used
- 代码修改：
  - `apply_patch`
- 验证：
  - `python3 -m py_compile`
  - `npm run build`
  - `three_d_migration_audit.py`
  - `rsync`
  - `ssh a2`
  - `colcon build --packages-select localization_manager a2_system`
  - `curl /api/snapshot`

### Why this approach
如果定位 gate 和 Web 位姿显示层仍然只接受 `/amcl_pose`，那系统再怎么强调 3D-first 都是假的，因为定位真值仍是 2D AMCL。

先把输入契约改为“可吃 `Odometry` 型 3D 位姿”，是继续往 3D localization 迁移的必要前提。

### Problems encountered
- A2 当前 `GET /api/snapshot` 中 `pose.available` 仍为 `false`

### Fixes applied
- 已确认这不是代码报错，而是当前 A2 侧 `/uslam/localization/odom` 在本次运行窗口里没有实际 publisher 数据进入 Web
- 代码层面已完成接入，只差上游真实 3D localization topic 稳定产出

### Current result
当前仓库和 A2 已经具备：
- `localization_gate` 接 `Odometry` 型定位真值
- Web 后端接 `Odometry` 型定位真值
- `three_d_migration_audit.py` 已显示：
  - `localization_gate.input_pose_topic=/uslam/localization/odom`

与此同时，A2 `/api/snapshot` 里已确认：
- `pointcloud.source_topic = /unitree/slam_lidar/points1`
- `pose.source = localization_pose`

说明链路契约已经完成从 AMCL 命名到 3D pose 命名的切换。

### Remaining risks or follow-ups
- 上游 `/uslam/localization/odom` 当前是否持续发布仍需单独实机确认
- `lifecycle_manager_localization=['map_server', 'amcl']` 仍在 audit 中残留
- `scan_mission` 仍依赖 `/map` 与 `/amcl_pose`
- 全链路 3D 还差：
  - 替换 Nav2/AMCL 生命周期栈
  - 替换 route/scan mission 的 2D 位姿依赖

---

## Entry 69 — 准备把本轮核心代码推送到 Codeup

### Time
2026-04-28 15:38 CST

### Action taken
开始整理本轮需要推送到 Codeup 的代码范围。

已确认：
- 当前分支是 `master`
- 当前仓库还没有配置任何 git remote
- 工作区中既有本轮核心代码，也混有无关改动与生成文件

已检查：
- `git status --short`
- `git branch --show-current`
- `git remote -v`
- `git diff --stat -- src web_console scripts`
- `find scripts/`

初步决定推送范围以核心工程目录为主：
- `src/`
- `web_console/`
- `scripts/`

需要排除的非核心内容：
- `agent-logs/*`
- `readme/Vikunja*`
- `readme/docker-compose.vikunja.yml`
- `readme/readmeDocker Compose.md`
- 前端构建噪音文件：
  - `web_console/frontend/tsconfig.node.tsbuildinfo`
  - `web_console/frontend/tsconfig.tsbuildinfo`
  - `web_console/frontend/vite.config.d.ts`
  - `web_console/frontend/vite.config.js`

### Tool or method used
- `git status --short`
- `git branch --show-current`
- `git remote -v`
- `git diff --stat -- src web_console scripts`
- `find`

### Why this approach
这次要推到外部 Codeup 仓库，先划定“核心代码”边界比直接 `git add .` 更安全。当前仓库明显有用户自己的日志与无关文档，如果一起推送，会污染远端提交历史。

### Problems encountered
- 仓库没有已有远端，需要后续手动补 remote
- 工作区改动较多，包含无关文件和生成文件

### Fixes applied
- 先按目录和文件类型进行推送范围筛选
- 明确把日志、无关 readme 和前端构建噪音文件列为排除项

### Current result
已经完成推送前的范围审计，接下来可以进行选择性暂存、提交，并为 Codeup 配置 remote 后执行 push。

### Remaining risks or follow-ups
- 仍需确认 Codeup 可用的 git remote URL 形式
- push 时可能遇到认证问题
- `src/` 下存在较多新增文件，需要在提交前再做一次范围复核

---

## Entry 70 — 核心代码已整理成本地提交，远端 push 卡在 Codeup 认证

### Time
2026-04-28 15:45 CST

### Action taken
将本轮核心代码按 `src/ + web_console/ + scripts/` 范围选择性暂存，并提交为单个本地 commit：

- commit: `6134c50`
- message: `feat: harden real stack and start 3d-first navigation migration`

同时验证了两类常见 Codeup 远端访问方式：
- HTTPS:
  - `https://codeup.aliyun.com/601416f22a8cae58be1e7201/feishuyz/device-navigation.git`
- SSH:
  - `git@codeup.aliyun.com:601416f22a8cae58be1e7201/feishuyz/device-navigation.git`
  - `git@codeup.aliyun.com:feishuyz/device-navigation.git`

### Tool or method used
- `git add scripts src web_console`
- `git restore --staged ...tsbuildinfo ...vite.config.*`
- `git diff --cached --check`
- `git commit`
- `git ls-remote`
- `ssh` / `GIT_SSH_COMMAND`

### Why this approach
先把改动固化为一个干净 commit，能够避免远端认证问题影响代码整理本身；随后再单独处理 Codeup 认证和 push。

### Problems encountered
- HTTPS 访问需要用户名口令，当前环境没有可用凭证
- SSH 访问返回 `Permission denied (publickey)`
- 本机没有：
  - `~/.git-credentials`
  - `~/.netrc`
  - `credential.helper`

### Fixes applied
- 先完成本地 commit，确保核心代码已固定
- 明确可用的远端 URL 形式，后续只需在有权限的环境中执行 push

### Current result
当前核心代码已经整理为本地提交 `6134c50`，可以在具备 Codeup 认证的本机或 A2 机器上直接执行远端添加与推送命令。

### Remaining risks or follow-ups
- 仍需在具备 Codeup 凭证的环境里执行 `git push`
- 如果远端 `master` 不是空仓库，push 前应先确认是否需要 `pull --rebase`

---

## Entry 71 — Codeup SSH 已打通，push 被远端现有 master 历史拒绝

### Time
2026-04-28 15:52 CST

### Action taken
用户已完成：
- 将本机 `~/.ssh/id_ed25519.pub` 加入 Codeup 账号 SSH Keys
- 在 `~/.ssh/config` 中为 `codeup.aliyun.com` 指定：
  - `User git`
  - `IdentityFile ~/.ssh/id_ed25519`
  - `IdentitiesOnly yes`

已确认：
- `ssh -T git@codeup.aliyun.com`
  - 返回 `Welcome to Codeup, nick4824401753!`
- 说明 SSH 认证已经通过

随后执行：
- `git push -u codeup master`

返回：
- `! [rejected] master -> master (fetch first)`
- 说明远端 `master` 已有本地尚不存在的提交

### Tool or method used
- 用户终端输出回传
- Git 远端 SSH 认证与 push 结果分析

### Why this approach
先打通 SSH 认证，再区分“权限问题”和“分支历史冲突问题”。认证通后，当前问题就明确变成远端历史整合，而不是访问权限。

### Problems encountered
- 远端 `master` 非空
- 当前本地 `master` 不能直接 fast-forward push

### Fixes applied
- 暂未直接修改历史
- 下一步应先 `fetch` 远端，再决定：
  - `pull --rebase`
  - 或在确认仓库允许覆盖时使用强推

### Current result
当前本地提交 `6134c50` 已具备推送条件；阻塞点仅剩远端 `master` 上已有历史，需要先整合或覆盖。

### Remaining risks or follow-ups
- 需确认远端已有提交是否应保留
- 如果本地与远端是两套独立初始历史，可能需要 `--allow-unrelated-histories`
- 若选择强推，需明确接受覆盖远端 `master` 风险

---

## Entry 72 — 远端历史为独立分支，合并冲突面过大，建议中止并强推

### Time
2026-04-28 16:00 CST

### Action taken
根据用户回传的 `git fetch`、`git log` 和 `git merge codeup/master --allow-unrelated-histories` 结果，确认：

- 本地与 Codeup 远端是两套独立历史
- 远端仅包含较早的 Docker 相关提交
- 执行 merge 后出现大面积 `双方添加` 冲突
- 冲突覆盖：
  - `src/`
  - `web_console/`
  - 核心 launch/config/backend/frontend 文件

### Tool or method used
- 用户终端输出分析
- Git 历史和合并冲突类型判断

### Why this approach
当前冲突不是常规同一主线上的少量修改冲突，而是两套项目树的大面积“添加/添加”。继续手工解冲突成本高、风险大，也不符合用户当前“把本地主代码推到 Codeup”的目标。

### Problems encountered
- `merge --allow-unrelated-histories` 产生大量 add/add conflict
- 合并状态下仓库不可继续正常 push

### Fixes applied
- 决策建议改为：
  - `git merge --abort`
  - `git push --force-with-lease`

### Current result
当前最合理的后续操作是中止本次 merge，并用本地 `master` 覆盖远端 `master`。

### Remaining risks or follow-ups
- 强推会改写远端 `master`
- 若远端 Docker 提交需要保留，应另建分支备份后再覆盖

---

## Entry 73 — 推进 3D-first 建图、导航、Web 闭环

### Time
2026-04-28 16:14 CST

### Action taken
按用户要求继续“全面使用 3D”，把默认 Web/导航/自动扫图路径从 2D Nav2/AMCL 迁移到 3D-first 合同。

主要改动：
- Web 后端新增 `pose_topic_3d` 导航后端
  - 默认发布 `geometry_msgs/PoseStamped` 到 `/goal_pose_`
  - 不再要求 2D `/map` 才能发送目标
  - 用当前 3D/odom 位姿判断目标距离、超时、完成状态
- Web 前端 3D 点云视图支持双击点云选目标点
- 自动扫图 `auto_scan_mission.py` 支持 `pose_topic_3d`
  - 默认用 `/odom` 作为 Odometry 位姿源
  - 默认发布目标到 `/goal_pose_`
  - 默认不再用 2D `/map` 做 waypoint 栅格校验
- `task_manager.py` 支持直接发布 3D pose goal
- `goal_bridge.py` 支持 `pose_topic_3d` 后端
- `stack_control.py` 支持 3D navigation 节点契约
  - 3D 导航启动时 `A2_ENABLE_NAV2=false`
  - `A2_REAL_LOCALIZATION_MODE=uslam_odom`
  - 显式传入 `enable_control_bridge:=true`
  - 状态显示优先使用 runtime state，避免 3D 导航被误判为 mapping
- `safety_supervisor.py` 支持 `pointcloud_map_3d` 表示
  - 3D 模式下不再要求 2D OccupancyGrid 才发布 map_ready
  - 仍要求 lidar、robot_state、localization
- `localization.yaml` 改为 `/odom` + `nav_msgs/msg/Odometry` + volatile QoS

### Tool or method used
- 本地编辑：
  - `apply_patch`
- 本地验证：
  - `python3 -m py_compile`
  - `npm run build`
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest ...`
  - `colcon build --symlink-install --packages-select a2_system a2_bringup nav2_integration safety_manager`
  - `three_d_migration_audit.py`
  - `git diff --check`
- A2 实机部署：
  - `rsync`
  - `ssh a2`
  - `colcon build --symlink-install`
  - `systemctl restart a2-web-console.service`
  - Web API:
    - `POST /api/stack/start-mapping`
    - `POST /api/stack/start-navigation`
    - `GET /api/snapshot`
    - `GET /api/stack/status`

### Why this approach
当前没有稳定可用的完整 3D SLAM/localization action server，因此先把系统默认导航执行合同切到已存在的原生 3D pose 目标入口 `/goal_pose_`，并把 Web 和自动扫图统一到这个后端。这样可以先让整套前雷达 3D 点云、Web 3D 视图、3D 位姿、目标发布和状态反馈跑通，再继续替换更强的 3D SLAM/LIO。

### Problems encountered
- 第一次启动 3D navigation 缺少 `a2_control_bridge`
  - 原因：`start_navigation` 没传 `enable_control_bridge:=true`
- Web stack status 把 3D navigation 显示成 mapping
  - 原因：3D navigation 和 mapping 都有 `map_manager_node`，旧推断逻辑优先使用进程推断
- `localization_gate` 没收到 `/odom`
  - 原因：配置仍使用 transient local QoS，不匹配 `/odom` 的 volatile 发布
- 本地 pytest 自动加载 anyio 插件时报 `_pytest.scope` 缺失
  - 原因：本机 pytest/anyio 插件版本不匹配

### Fixes applied
- `stack_control.py`
  - navigation 启动命令加入 `enable_control_bridge:=true`
  - runtime state 优先于进程推断
- `localization.yaml`
  - `pose_transient_local: false`
- `config_schema_check.py`
  - 审计合同改为 3D-first `/odom` + Odometry
- 测试时使用：
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`

### Current result
A2 实机已验证：
- 3D mapping API 启动成功
- 3D navigation API 启动成功
- Web `/api/snapshot` 显示：
  - `pointcloud.loaded=True`
  - `pointcloud.topic=/unitree/slam_lidar/points1`
  - `pose.available=True`
  - `pose.source=/odom`
  - `localization_ok=True`
  - `navigation.backend=pose_topic_3d`
  - `navigation.action_server_ready=True`
- ROS graph 中只看到 3D-first 关键节点：
  - `/a2_control_bridge`
  - `/goal_bridge`
  - `/localization_gate`
  - `/map_manager`
- 未看到 AMCL、map_server、bt_navigator、controller_server、slam_toolbox、pointcloud_to_laserscan

### Remaining risks or follow-ups
- 当前 3D 导航执行是 `/goal_pose_` pose topic 后端，不是完整 3D planner/action server
- Web 3D 点云选点是从点云投影中选最近点，frame 语义仍需和原生 `/goal_pose_` 最终确认
- `/odom` 是当前可用位姿源；后续应替换为稳定 3D SLAM/LIO localization 输出
- 未在本轮发送真实移动目标，避免实机误动

---

## Entry 74 — 3D-first changes committed and pushed

### Time
2026-04-28 16:20:20 CST

### Action taken
Committed the 3D-first mapping/navigation/Web continuation and pushed it to Codeup.

### Tool or method used
- `git status --short`
- `git diff --cached --stat`
- `git diff --cached --check`
- `git commit -m "feat: use 3d pose backend for mapping and navigation"`
- `git fetch codeup`
- `git rebase codeup/master`
- `git push codeup master`
- `git stash push -u -m "pre-rebase-local-uncommitted-files"`
- `git stash pop`
- `git reset -- agent-logs/2026-04-25-agent-session.md readme/README_A2_Quickstart.md`

### Why this approach
The code changes were already validated locally and on A2, so the next required step was to preserve them in the remote repository. The remote branch had new cleanup commits, so the local feature commit was rebased onto the latest Codeup `master` instead of force-pushing over remote history.

### Problems encountered
- Initial push was rejected because Codeup `master` had new commits after the previous local base.
- Rebase initially failed because unrelated local files were modified or untracked.
- `git stash pop` reported a modify/delete conflict for `agent-logs/2026-04-25-agent-session.md` because the remote cleanup commits removed tracked agent logs while the local stash contained a modified copy.

### Fixes applied
- Temporarily stashed unrelated local changes and untracked generated files.
- Rebasing onto `codeup/master` succeeded.
- Pushed the rebased feature commit successfully.
- Reset the non-core conflict back out of the index so local logs/readme/generated files remain local working-tree changes and are not included in the code commit.

### Current result
- Remote Codeup `master` now points to commit `0feaebc feat: use 3d pose backend for mapping and navigation`.
- Local `master` and `codeup/master` match at `0feaebc`.
- Core 3D-first code changes are committed and pushed.
- Local unrelated files remain outside the commit.

### Remaining risks or follow-ups
- A retained stash entry `pre-rebase-local-uncommitted-files` remains as an extra backup because `stash pop` encountered a conflict.
- Local working tree still has unrelated readme/log/generated-file changes that were intentionally not committed.
- Real robot motion goal validation was intentionally not run to avoid unexpected movement.

---

## Entry 75 — Start 3D closed-loop and one-key suite work

### Time
2026-04-28 16:35:07 CST

### Action taken
Started the next implementation pass for full 3D usage: close the `/goal_pose_` execution loop and provide a one-key script that starts the real 3D stack plus Web, while leaving mapping/navigation mode selection in the Web console.

### Tool or method used
- Inspected `src/a2_system/tools/start_real_stack.sh`
- Inspected `src/a2_system/tools/stop_stack.sh`
- Inspected `web_console/backend/stack_control.py`
- Inspected `web_console/backend/ros_bridge.py`
- Checked current git state and available tools under `src/a2_system/tools`

### Why this approach
The existing system already has start/stop scripts and Web stack controls. Extending those contracts is safer than introducing a separate launcher that may diverge from the Web backend and produce inconsistent runtime states.

### Problems encountered
None at this initial inspection step.

### Fixes applied
None yet.

### Current result
Confirmed the existing one-key script name already exists locally as `start_web_console_suite.sh`, but the new work still needs to ensure it is installed, starts the 3D defaults, reports failing nodes clearly, and supports Web-driven mapping/navigation.

### Remaining risks or follow-ups
- Need to verify whether `start_web_console_suite.sh` is included in package installation and available on A2.
- Need to add a safe 3D smoke-test/short-goal path without unexpectedly moving the robot.
- Need to validate `/goal_pose_` frame and feedback using real robot checks before claiming closed-loop completion.

---

## Entry 76 — 3D one-key suite and goal smoke-test implementation

### Time
2026-04-28 16:44:46 CST

### Action taken
Implemented and deployed the next 3D closed-loop hardening pass:
- Added a clear `start_3d_web_console_suite.sh` one-key 3D entrypoint.
- Added `goal_pose_3d_smoke_test.py` for protected `/goal_pose_` dry-run and optional short-goal execution.
- Hardened Web `pose_topic_3d` cancel/timeout/reached behavior to publish stop signals.
- Updated navigation contract checks from AMCL/Nav2 primary assumptions to 3D-first `/odom` + `/goal_pose_` assumptions.
- Deployed to A2, rebuilt, started the 3D Web suite, started 3D navigation through the Web API, and ran dry-run goal preflight.

### Tool or method used
- Local edits with `apply_patch`
- Local validation:
  - `python3 -m py_compile ...`
  - `bash -n src/a2_system/tools/start_web_console_suite.sh`
  - `bash -n src/a2_system/tools/start_3d_web_console_suite.sh`
  - `python3 src/a2_system/scripts/nav_contract_check.py`
  - `npm run build`
  - `colcon build --symlink-install --packages-select a2_system a2_bringup nav2_integration safety_manager`
  - `source /opt/ros/humble/setup.bash && source install/setup.bash && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest ...`
  - `config_schema_check.py`
  - `three_d_migration_audit.py`
- A2 deployment and validation:
  - `BUILD_WEB=1 START_SERVICE=0 ./scripts/deploy_to_a2.sh a2`
  - `/home/unitree/a2_system_ws/install/a2_system/share/a2_system/start_3d_web_console_suite.sh --iface eth0`
  - `POST /api/stack/start-navigation` with `three_d_asset_smoke`
  - `ros2 run a2_system goal_pose_3d_smoke_test.py --goal-frame map --relative-x 0.25`
  - `GET /api/snapshot`

### Why this approach
Physical movement needs an explicit safety boundary, so the smoke-test defaults to dry-run and requires both `--execute` and `--i-understand-robot-will-move` before publishing a moving goal. The Web cancel path must also do more than clear UI state; publishing current-pose retargeting plus zero `/cmd_vel` provides a conservative stop request for the current 3D bridge.

### Problems encountered
- Initial pytest run failed because ROS/install environment was not sourced; local packages and `a2_interfaces` were not importable.
- A2 deployment printed `cannot delete non-empty directory: ${A2_WORKSPACE}` from a stale literal remote directory; deployment continued successfully.
- One snapshot parsing command used broken SSH quoting and failed with Python syntax errors.
- Dry-run smoke test reported `pose_frame=odom` while `goal_frame=map`; this is important before executing real movement.

### Fixes applied
- Re-ran pytest after sourcing `/opt/ros/humble/setup.bash` and `install/setup.bash`; all tests passed.
- Ignored the stale literal `${A2_WORKSPACE}` directory because it is outside the active workspace path and did not block deployment.
- Re-ran snapshot check via local LAN URL `http://192.168.31.49:8080/api/snapshot`.
- Kept the real movement test dry-run only until a human confirms the robot has clear space and frame semantics are acceptable.

### Current result
- A2 Web suite starts from installed script.
- Web URL confirmed: `http://192.168.31.49:8080/`.
- A2 3D navigation stack started with expected nodes:
  - bringup
  - a2_sdk_bridge
  - a2_control_bridge
  - localization_gate
  - goal_bridge
  - map_manager
- Snapshot after navigation startup:
  - `pointcloud=True`, topic `/unitree/slam_lidar/points1`
  - `pose=True`, source `/odom`, frame `odom`
  - `localization=True`, status `ready`
  - `navigation.backend=pose_topic_3d`
  - `navigation.action_server_ready=True`
- 3D smoke-test dry-run passed preflight and printed the planned 0.25 m goal without publishing it.

### Remaining risks or follow-ups
- Real movement goal has not been executed yet for safety.
- Need either operator confirmation of a clear area or a smaller supervised goal before publishing `--execute`.
- Need to resolve/verify `odom` vs `map` frame alignment before using the smoke-test result as a precision metric.

---

## Entry 77 — 3D smoke-test commit pushed

### Time
2026-04-28 16:46:00 CST

### Action taken
Committed and pushed the 3D suite launcher, smoke-test script, cancel hardening, and 3D contract updates.

### Tool or method used
- `git add` for the 10 code/config/test files only
- `git diff --cached --stat`
- `git diff --cached --check`
- `git commit -m "feat: add 3d goal smoke test and suite launcher"`
- `git push codeup master`
- `git log --oneline --decorate -4`

### Why this approach
The implementation was already deployed and validated on A2, so pushing the exact code changes to Codeup keeps the robot workspace and remote repository aligned. Unrelated local readme/log/generated files were intentionally excluded.

### Problems encountered
None during commit and push.

### Fixes applied
None.

### Current result
Codeup `master` now points to `359e7bd feat: add 3d goal smoke test and suite launcher`.

### Remaining risks or follow-ups
- Local uncommitted unrelated files remain in the working tree.
- Real movement execution still requires operator confirmation and frame check.

---

## Entry 78 — User insists on staying 3D for mapping

### Time
2026-04-28 17:05:00 CST

### Action taken
Stopped the temporary fallback direction toward 2D occupancy mapping after the user explicitly rejected returning to 2D mapping. Reframed the task back to true 3D mapping with real-time Web visibility, saved 3D map assets, navigation usability, and clear robot pose display.

### Tool or method used
- Reasoning from current implementation state and recent A2 runtime checks

### Why this approach
The user requirement is explicit: keep 3D mapping as the primary truth. The next correct step is to identify whether A2 native SLAM already exposes an accumulated 3D map source we can consume; only if that path is unavailable should we add our own 3D accumulation/mapping implementation.

### Problems encountered
- Current `front_lidar_pointcloud_3d` mode only shows live pointcloud and saves snapshots; it is not a true accumulated 3D map.
- A temporary switch toward `native_global_map` would improve usability but would violate the user's stated requirement to avoid returning to 2D mapping.

### Fixes applied
None yet in this entry; work direction corrected before further changes.

### Current result
The task direction is now explicitly: preserve 3D mapping, real-time 3D Web display, A2 front-lidar source, saved map usable for navigation, and a clear robot pose marker in the Web frontend.

### Remaining risks or follow-ups
- Need to inspect A2 native SLAM topics/interfaces for accumulated 3D map output.
- If no suitable native 3D map output exists, need to add an internal 3D map accumulator / mapper path.

---

## Entry 79 — Confirmed current 3D mapping path is only a live scan snapshot

### Time
2026-04-28 17:26:00 CST

### Action taken
Inspected the current `front_lidar_pointcloud_3d` mapping path, Web backend/frontend contracts, map save logic, and A2 native SLAM hooks to determine why the Web "3D mapping" view did not grow into a usable map.

### Tool or method used
- `sed` on:
  - `src/a2_bringup/launch/mapping.launch.py`
  - `src/map_manager/map_manager/map_manager_node.py`
  - `web_console/backend/ros_bridge.py`
  - `web_console/backend/stack_control.py`
  - `web_console/backend/main.py`
  - `web_console/frontend/src/components/PointCloudCanvas3D.tsx`
  - `web_console/frontend/src/App.tsx`
  - `web_console/backend/config.py`
  - `src/a2_system/config/slam.yaml`
  - `src/a2_system/config/map_manager.yaml`
- `ssh a2` inspection of Unitree native stack files and topics:
  - `/home/unitree/graph_pid_ws/bin/tools/go2_web/ros_handler.py`
  - `ros2 topic info /grid_clouds`
  - `curl http://127.0.0.1:8080/api/stack/status`

### Why this approach
The user's symptom was not a cosmetic Web problem. The correct fix required identifying whether the stack was actually performing accumulated 3D mapping or only rendering/saving a single live scan.

### Problems encountered
- `mapping.launch.py` does not launch any mapper when `mapping_stack_profile=front_lidar_pointcloud_3d`; it only launches `map_manager_node`.
- `map_manager_node` currently stores only `latest_pointcloud` and exports a one-frame PCD snapshot; it does not accumulate a 3D map.
- The Web backend default `pointcloud_topic` still points to `/unitree/slam_lidar/points1`, so the Web 3D canvas shows raw front-LiDAR scans rather than an accumulated map.
- Saved-map listing in `stack_control.py` still filters on `map.yaml`, which biases the system toward 2D map artifacts.
- In 3D mode, `set_initial_pose()` currently returns a no-op message instead of actually sending a 3D localization request.

### Fixes applied
None yet in this entry. The implementation plan was narrowed to:
- switch Web/map save sources to accumulated native 3D map topics first,
- preserve 3D PCD artifacts as primary map assets,
- make 3D initial pose call the Unitree native SLAM API with a selected map path,
- add an obvious robot marker in the 3D viewer.

### Current result
The root cause is now explicit: the current system is "3D live scan display" rather than "true accumulated 3D mapping". The next edits will replace raw-scan display/save defaults with native accumulated 3D map sources and pointcloud-first metadata.

### Remaining risks or follow-ups
- Need to verify at runtime whether `/grid_clouds` is the correct accumulated 3D map topic once mapping is started.
- Need to ensure 3D-only maps without `map.yaml` can still be listed and selected in the Web UI.
- Need to confirm whether Unitree native initial-pose API `1804` is sufficient for re-localizing against saved PCD maps in this stack.

---

## Entry 80 — Continue 3D mapping hardening

### Time
2026-04-28 17:49:29 CST

### Action taken
Resumed work on the user's requirement to keep mapping fully 3D, show the real-time accumulated 3D map in Web, save 3D map assets, and show the robot pose clearly. Started by checking the current dirty tree and all references to the new accumulated pointcloud path.

### Tool or method used
- `date '+%Y-%m-%d %H:%M:%S %Z'`
- `git status --short --branch`
- `rg -n "pointcloud_accumulator|pointcloud_map_3d|native_global_map|latest_pointcloud|pointcloud_fallback" src web_console agent-logs/2026-04-27-agent-session.md`

### Why this approach
The previous work left a new 3D accumulator and Web 3D display changes in the local tree. Before deploying to A2, the implementation needs static checks and consistency review to avoid shipping a half-integrated path.

### Problems encountered
- The local tree is dirty with both task-related changes and unrelated readme/generated files.
- The new 3D accumulator path has not yet been deployed or built on A2.

### Fixes applied
None yet in this entry.

### Current result
Confirmed the active implementation direction:
- `pointcloud_accumulator` is wired in local launch/setup files.
- Backend/Web defaults point at `/a2/pointcloud_map_3d` with `/unitree/slam_lidar/points1` as fallback.
- A2 deployment and runtime validation remain pending.

### Remaining risks or follow-ups
- Need to run local compile/build checks.
- Need to rsync the modified code to A2, rebuild ROS packages, restart Web, and start the 3D suite.
- Need to verify the real topic `/a2/pointcloud_map_3d` accumulates while the robot moves.

---

## Entry 81 — Local 3D accumulator and Web checks

### Time
2026-04-28 17:56:00 CST

### Action taken
Reviewed the 3D accumulator launch path, map saving path, Web ROS bridge pointcloud subscription logic, and frontend 3D canvas robot marker. Ran local static checks and frontend production build.

### Tool or method used
- `sed` on:
  - `src/a2_bringup/launch/mapping.launch.py`
  - `src/map_manager/map_manager/map_manager_node.py`
  - `src/map_manager/map_manager/pointcloud_accumulator.py`
  - `src/a2_system/config/pointcloud_accumulator.yaml`
  - `web_console/backend/ros_bridge.py`
  - `web_console/backend/stack_control.py`
  - `web_console/backend/main.py`
  - `web_console/frontend/src/App.tsx`
  - `web_console/frontend/src/components/PointCloudCanvas3D.tsx`
- `python3 -m py_compile web_console/backend/*.py src/map_manager/map_manager/*.py`
- `git diff --check`
- `python3 src/a2_system/scripts/three_d_migration_audit.py`
- `npm run build` in `web_console/frontend`

### Why this approach
This change touches ROS launch, a new ROS node, backend snapshot contracts, map save/list logic, and the frontend viewer. Static checks catch integration errors before deploying to A2.

### Problems encountered
- Initial review suspected a frontend object-brace issue in `App.tsx`, but the file on disk was already syntactically correct when checked with `nl`.

### Fixes applied
None required after the direct file check.

### Current result
- Python compile passed.
- `git diff --check` passed.
- 3D migration audit confirms `pointcloud_map_3d` is the primary representation and `front_lidar_pointcloud_3d` is the mapping profile.
- Frontend production build passed.

### Remaining risks or follow-ups
- Need to deploy these changes to A2 and rebuild there.
- Need runtime validation that `/a2/pointcloud_map_3d` is published by `pointcloud_accumulator` and grows when the robot moves.

---

## Entry 82 — A2 deploy and native lidar startup check fix

### Time
2026-04-28 17:58:00 CST

### Action taken
Synced the 3D mapping/Web files to A2, rebuilt the relevant ROS packages, rebuilt frontend assets, restarted the Web service, and attempted to start the one-key 3D suite.

### Tool or method used
- `ssh -o BatchMode=yes -o ConnectTimeout=5 a2 'hostname && pwd && test -d /home/unitree/a2_system_ws && echo workspace_ok'`
- `rsync -avR ... a2:/home/unitree/a2_system_ws/`
- On A2:
  - `colcon build --packages-select a2_bringup map_manager a2_system`
  - `npm run build` in `web_console/frontend`
  - `sudo systemctl restart a2-web-console.service`
  - `/home/unitree/a2_system_ws/install/a2_system/share/a2_system/start_3d_web_console_suite.sh --iface eth0`
- Inspected `src/a2_system/tools/start_web_console_suite.sh` and current A2 ROS topics/processes.

### Why this approach
The code passed local checks, so the next validation layer is the real robot runtime. The one-key script is the intended operator entrypoint and must handle cleanup, native lidar startup, Web startup, and standby mode reliably.

### Problems encountered
- The one-key suite failed at the native lidar validation step: `Native lidar topic did not become active: /unitree/slam_lidar/points1`.
- A2 inspection immediately after failure showed `/unitree/slam_lidar/points1` had `Publisher count: 1`, and Unitree/Hesai/point cloud fusion processes were active.
- Root cause: the script used `ros2 topic echo --once` as the only readiness check. That can time out on this PointCloud2 stream due QoS mismatch or startup timing even when the publisher exists.

### Fixes applied
- Updated `start_web_console_suite.sh`:
  - `wait_topic_message` now uses `--qos-reliability best_effort`.
  - Added `wait_topic_publisher` to validate publisher count through `ros2 topic info`.
  - Fresh native lidar startup now waits up to 60 seconds for a publisher and treats sample echo as a best-effort secondary check.

### Current result
The native lidar source is active on A2, and the startup script has been hardened locally. The patched script still needs to be deployed/rebuilt on A2 and rerun.

### Remaining risks or follow-ups
- Need to deploy the patched script to A2 and rerun the one-key suite.
- Need to verify mapping mode launches `pointcloud_accumulator`, not the previous `native_map_relay` path.

---

## Entry 83 — 3D accumulator mapping path validated on A2

### Time
2026-04-28 18:06:00 CST

### Action taken
Deployed the startup-script fix, corrected A2's installed 3D mapping profile, launched mapping through the Web API, verified the new `pointcloud_accumulator` path, improved the accumulator to use full odometry quaternion orientation, and validated saving 3D-only maps.

### Tool or method used
- Synced and rebuilt on A2:
  - `src/a2_system/tools/start_web_console_suite.sh`
  - `src/a2_system/config/slam.yaml`
  - `src/a2_system/config/pointcloud_accumulator.yaml`
  - `src/map_manager/map_manager/pointcloud_accumulator.py`
  - `web_console/backend/stack_control.py`
- A2 builds:
  - `colcon build --packages-select a2_system`
  - `colcon build --packages-select map_manager a2_system`
- Web/API runtime checks:
  - `/home/unitree/a2_system_ws/install/a2_system/share/a2_system/start_3d_web_console_suite.sh --iface eth0`
  - `curl -X POST http://127.0.0.1:8080/api/stack/start-mapping`
  - `curl http://127.0.0.1:8080/api/stack/status`
  - `ros2 topic info /a2/pointcloud_map_3d`
  - `timeout 6s ros2 topic hz /a2/pointcloud_map_3d`
  - `curl http://127.0.0.1:8080/api/snapshot | jq ...`
  - `curl -X POST http://127.0.0.1:8080/api/maps/save ...`
- Local checks:
  - `python3 -m py_compile web_console/backend/*.py src/map_manager/map_manager/*.py`
  - `git diff --check`
  - `python3 src/a2_system/scripts/three_d_migration_audit.py`
  - `pytest web_console/backend/test/test_web_contracts.py`

### Why this approach
The user's requirement is not a 2D fallback. The implementation needed a real accumulated 3D topic as the map truth, Web display sourced from that topic, explicit node-status visibility, and saved PCD artifacts that do not depend on `map.yaml`.

### Problems encountered
- A2's source/install `slam.yaml` still had `mapping_stack_profile: native_global_map`, so Web mapping attempted Unitree native API `1801` and failed with `code=3203`.
- Restarting the Web systemd service while mapping was running killed the ROS bringup because Web-started subprocesses share the service cgroup.
- `ros2 topic echo --once` can hang on some topics during diagnostics; using `timeout` avoids blocking SSH.
- `pytest` is not installed in the local environment.

### Fixes applied
- Synced local `slam.yaml` to A2 and rebuilt `a2_system`; installed config now uses `mapping_stack_profile: front_lidar_pointcloud_3d` and `primary_map_representation: pointcloud_map_3d`.
- Updated `stack_control.py` so mapping node status includes `map_source`, which now reports `pointcloud_accumulator` as running.
- Updated `pointcloud_accumulator.py` to use full `/odom` 3D position and quaternion rotation instead of planar x/y/yaw only.
- Added `lidar_offset_rpy` to `pointcloud_accumulator.yaml`; legacy `lidar_offset_yaw` remains supported.

### Current result
- One-key suite succeeds and leaves Web in standby:
  - `http://192.168.31.49:8080/`
- Web API mapping starts the correct 3D chain:
  - `mapping_profile=front_lidar_pointcloud_3d`
  - `map_source=running`
  - `pointcloud_accumulator` process present
- `/a2/pointcloud_map_3d` is published at 2.0 Hz.
- Web snapshot reports:
  - `pointcloud.loaded=true`
  - `source_topic=/a2/pointcloud_map_3d`
  - `frame_id=odom`
  - `pose.available=true`
  - `pose.frame_id=odom`
- Saved 3D-only smoke map:
  - `three_d_quat_accum_smoke_180626`
  - `map_yaml=null`
  - `representation=pointcloud_map_3d`
  - artifact `pointcloud_map_3d.pcd`
  - `points_saved=1485`

### Remaining risks or follow-ups
- The accumulator is an odom-anchored 3D map, not loop-closure SLAM. It will accumulate correctly while odom is locally stable, but long runs can still drift.
- Point count will only grow when the robot moves or rotates beyond configured thresholds; a stationary robot intentionally republishes the same accumulated map.
- Need supervised motion test in a clear area to validate map growth and distortion over a real route.
- Need a true 3D localization/planning backend before claiming complete industrial 3D navigation closure.

---

## Final outcome update 4

### Summary
Implemented and validated the first working 3D-primary mapping path for A2:
- Web standby starts with the one-key 3D suite script.
- Web "建图模式" now launches `pointcloud_accumulator` instead of Unitree native `1801` or 2D mapping.
- `/a2/pointcloud_map_3d` is the primary live map source.
- Web snapshot and 3D canvas consume `/a2/pointcloud_map_3d`.
- Saved maps can be 3D-only PCD bundles without `map.yaml`.
- The 3D accumulator now uses full `/odom` quaternion orientation rather than planar yaw-only projection.

### Files changed
- `src/a2_bringup/launch/mapping.launch.py`
- `src/a2_system/config/map_manager.yaml`
- `src/a2_system/config/pointcloud_accumulator.yaml`
- `src/a2_system/tools/start_web_console_suite.sh`
- `src/map_manager/map_manager/map_manager_node.py`
- `src/map_manager/map_manager/pointcloud_accumulator.py`
- `src/map_manager/setup.py`
- `web_console/backend/config.py`
- `web_console/backend/config.example.yaml`
- `web_console/backend/config.docker.yaml`
- `web_console/backend/main.py`
- `web_console/backend/models.py`
- `web_console/backend/ros_bridge.py`
- `web_console/backend/stack_control.py`
- `web_console/backend/test/test_web_contracts.py`
- `web_console/frontend/src/App.tsx`
- `web_console/frontend/src/api.ts`
- `web_console/frontend/src/components/ControlSidebar.tsx`
- `web_console/frontend/src/components/PointCloudCanvas3D.tsx`
- `web_console/frontend/src/types.ts`
- `agent-logs/2026-04-27-agent-session.md`

### Commands run
- Local:
  - `python3 -m py_compile web_console/backend/*.py src/map_manager/map_manager/*.py` passed
  - `git diff --check` passed
  - `python3 src/a2_system/scripts/three_d_migration_audit.py` passed with 3D primary representation
  - `npm run build` passed
  - `pytest web_console/backend/test/test_web_contracts.py` failed because `pytest` is not installed
- A2:
  - `colcon build --packages-select a2_bringup map_manager a2_system` passed
  - `colcon build --packages-select map_manager a2_system` passed after quaternion accumulator update
  - `npm run build` in `web_console/frontend` passed
  - `start_3d_web_console_suite.sh --iface eth0` passed
  - `POST /api/stack/start-mapping` passed with `mapping_profile=front_lidar_pointcloud_3d`
  - `ros2 topic hz /a2/pointcloud_map_3d` reported 2.0 Hz
  - `POST /api/maps/save` saved `three_d_quat_accum_smoke_180626`

### Verification
- A2 Web URL: `http://192.168.31.49:8080/`
- Current live 3D map topic: `/a2/pointcloud_map_3d`
- Current live pointcloud frame: `odom`
- Current Web snapshot:
  - pointcloud loaded from `/a2/pointcloud_map_3d`
  - pose available in `odom`
  - map received true
  - pose received true
- Saved 3D smoke map:
  - `three_d_quat_accum_smoke_180626`
  - `map_yaml=null`
  - `representation=pointcloud_map_3d`
  - `pointcloud_map_3d.pcd`
  - `points_saved=1485`

### Known limitations
- This is 3D accumulated mapping, not full loop-closure 3D SLAM.
- The map is anchored to A2 odom; long routes can drift until a true 3D SLAM/localization backend is integrated.
- Growth was not validated with supervised robot motion in this pass.
- Restarting the Web systemd service while a Web-started ROS stack is running kills that stack due systemd cgroup ownership; use Web stop/start buttons or the suite script instead.

---

## Entry 84 — JT128 替换方案前置信息核对

### Time
2026-04-29 09:22:39 CST

### Action taken
按用户要求先做方案前的信息核对，不直接写代码。检查了仓库中的 launch、配置、接口契约、TF 约定、控制桥、SLAM 编排、真实雷达输入配置，以及第三方依赖目录，目的是区分“仓库里已知事实”和“必须由用户补充的实机信息”。

### Tool or method used
- `rg` 搜索：
  - ROS 版本
  - Nav2 / goal / cmd_vel / TF / lidar / imu / Hesai / JT128 / FAST_LIO / DLIO
- `sed` 检查：
  - `src/a2_bringup/launch/bringup.launch.py`
  - `src/a2_bringup/launch/sensors.launch.py`
  - `src/a2_bringup/launch/nav2.launch.py`
  - `src/a2_bringup/launch/localization.launch.py`
  - `src/a2_bringup/launch/slam.launch.py`
  - `src/a2_system/config/real_lidar.yaml`
  - `src/a2_system/config/network.yaml`
  - `src/a2_system/config/tf.yaml`
  - `src/a2_system/config/extrinsics.yaml`
  - `src/a2_system/config/state_bridge.yaml`
  - `src/a2_system/config/nav2.yaml`
  - `src/a2_system/config/localization.yaml`
  - `src/a2_system/config/slam.yaml`
  - `src/a2_system/config/nav2_stack.yaml`
  - `src/a2_control_bridge/src/a2_control_bridge_node.cpp`
  - `src/tf_manager/tf_manager/static_tf_manager.py`
  - `src/slam_manager/slam_manager/slam_orchestrator.py`
  - `src/a2_system/docs/interface_contracts.md`
- `find` 检查：
  - URDF / xacro
  - 第三方 SLAM/驱动目录

### Why this approach
用户明确要求“凡是不确定、缺失、会影响方案设计或代码实现的内容，必须一次性列出来问”。因此先把仓库内可确认事实收集完整，再仅针对关键缺口发问，避免边做边追问。

### Problems encountered
- 仓库能确认“设计意图”和“当前默认配置”，但不能完全替代实机当前运行态。
- 仓库当前没有 DLIO 代码，也没有 HesaiLidar_ROS_2.0 驱动代码；只看到 `FAST_LIO` 和 `livox_ros_driver2` 第三方目录。
- 实机 JT128 官方驱动是否已跑通、实际 IP/端口、双雷达是否都在线，这些不能从当前仓库可靠得出。

### Fixes applied
None.

### Current result
已确认的仓库事实包括：
- ROS2 目标版本是 `Humble`
- 当前真实雷达主输入配置为 `/unitree/slam_lidar/points1`
- 当前控制桥把 `/cmd_vel` 转成 Unitree SDK `SportClient` 运动指令
- 当前 TF 约定是 `map / odom / base_link / lidar_link / imu_link`
- 当前 `odom -> base_link` 由 `a2_state_publisher` 发布
- 当前 real 模式 `map -> odom` 设计上由定位/SLAM层拥有
- 当前系统同时保留 Nav2 和 3D pose-topic 导航桥
- 当前仓库没有真实机器人 URDF / robot_state_publisher，真实机主要依赖 `tf_manager` 的静态 TF

### Remaining risks or follow-ups
- 需要一次性向用户索取缺失的实机和部署信息，再输出 JT128 + DLIO/FAST-LIO2 的完整工程方案。

---

## Entry 84 — Wrote newcomer-facing 2D->3D debugging guide

### Time
2026-04-29 09:09:45 CST

### Action taken
Created a standalone Markdown guide that rewrites the whole 2D-to-3D debugging journey into a beginner-friendly engineering narrative. The document explains the original 2D chain, why it hit its ceiling, what was observed on the real A2, how each debugging step was performed, how the 3D accumulator path was introduced, what is verified today, and how a newcomer should operate and continue the system.

### Tool or method used
- Inspected documentation directories with `rg --files`
- Searched the session log and repository for relevant 2D/3D migration keywords with `rg`
- Added `src/a2_system/docs/a2_2d_to_3d_debug_journey.md`

### Why this approach
The user explicitly asked for a detailed MD file that turns the conversation into something a newcomer can read and quickly understand. A standalone doc in `src/a2_system/docs/` is easier to maintain and cite than leaving the knowledge buried in the long session log.

### Problems encountered
- The session knowledge was spread across many steps: 2D AMCL debugging, Web contract fixes, native Unitree API failures, 3D asset saving, Web 3D viewer work, startup-script hardening, and A2 runtime validation.

### Fixes applied
- Consolidated the narrative into one ordered document with:
  - original system explanation
  - observed failures
  - chronological debugging steps
  - current 3D data flow
  - operational commands
  - current limitations and next steps

### Current result
New documentation file created:
- `src/a2_system/docs/a2_2d_to_3d_debug_journey.md`

### Remaining risks or follow-ups
- The new guide is detailed, but it is still a static document. If later startup commands, topics, or file names change, it should be updated together with the code.

---

## Entry 85 — Placed the 2D->3D guide on the desktop

### Time
2026-04-29 09:16:40 CST

### Action taken
Placed a desktop copy of the new 2D-to-3D debugging guide for easier access while keeping the repository copy intact.

### Tool or method used
- Confirmed desktop paths with `ls -d /home/dell/Desktop /home/dell/桌面`
- Copied the file with:
  - `cp /home/dell/a2_system_ws/src/a2_system/docs/a2_2d_to_3d_debug_journey.md '/home/dell/Desktop/A2_2D到3D调试实录.md'`

### Why this approach
The user asked for the file on the desktop. Copying it there satisfies that need without removing the canonical project documentation from the repository.

### Problems encountered
None.

### Fixes applied
None.

### Current result
Desktop copy created:
- `/home/dell/Desktop/A2_2D到3D调试实录.md`

Repository source remains:
- `src/a2_system/docs/a2_2d_to_3d_debug_journey.md`

### Remaining risks or follow-ups
- If the repository version is updated later, the desktop copy will not update automatically.

---

## Entry 86 — Started JT128 + DLIO migration planning

### Time
2026-04-29 09:32:44 CST

### Action taken
Started the engineering planning pass for replacing the current mapping/localization LiDAR chain with a single front Hesai JT128 and prioritizing JT128 + DLIO mapping with PCD saving. Confirmed the local repository state before touching files.

### Tool or method used
- Ran `date '+%Y-%m-%d %H:%M:%S %Z'`
- Ran `git -C /home/dell/a2_system_ws status --short --branch`
- Reviewed the tail of the current session log

### Why this approach
The user provided the missing direction: real A2 and rosbag only, no simulation/mock, single JT128 first, no legacy fallback, and Phase 1 should complete JT128 + DLIO mapping and PCD saving. Before writing a concrete plan, the current dirty worktree and session log had to be preserved and understood.

### Problems encountered
The worktree already contains many prior 3D/Web changes plus unrelated readme/generated files. These are pre-existing and must not be reverted.

### Fixes applied
None. The next steps are limited to read-only A2 inspection and adding a planning document.

### Current result
Ready to inspect the A2 real machine for current ROS graph, TF ownership, JT128/Hesai configuration, network routes, and package availability.

### Remaining risks or follow-ups
- Need to confirm the actual JT128 driver/config state on `ssh a2`.
- Need to distinguish facts verified on the robot from assumptions in the final plan.

---

## Entry 87 — Inspected A2 real JT128 and ROS state

### Time
2026-04-29 09:33-09:36 CST

### Action taken
Connected to the A2 development unit over SSH and inspected the current ROS2 graph, live topics, Hesai/JT128 configuration, network route, installed packages, and active processes without changing the robot state.

### Tool or method used
- `ssh a2`
- `source /opt/ros/humble/setup.bash`
- `ros2 node list`
- `ros2 topic list -t`
- `ros2 topic info`
- `ros2 topic echo --once /unitree/slam_lidar/points1`
- `ros2 topic echo --once /tf_static`
- `ros2 pkg list`
- `systemctl status unitree_slam.service --no-pager`
- `ip route get 192.168.124.20`
- `ping -I net1 -c 2 -W 1 192.168.124.20`
- `ping -I eth0 -c 2 -W 1 192.168.124.20`
- Inspected:
  - `/home/unitree/graph_pid_ws/config_files/hs_lidar_jt128/config.yaml`
  - `/home/unitree/graph_pid_ws/config_files/hs_lidar_jt128/config_new.yaml`
  - `/home/unitree/graph_pid_ws/config/slam_interfaces_server_config/param.yaml`
  - `/home/unitree/graph_pid_ws/bin/tools/service/launch_slam.sh`

### Why this approach
The user asked to determine missing facts from the real A2 machine instead of repeatedly asking. These checks establish the real sensor network, topic names, point cloud fields, available packages, and current Unitree-native interference state before writing the migration plan.

### Problems encountered
- `ros2 topic echo` printed DDS deserialization warnings related to participant discovery, but still returned useful topic metadata and messages.
- The current robot state is not a clean A2 self-managed stack: `unitree_slam.service` is active and owns the native Hesai driver/process chain.
- `/odom` and `/tf` had no current publishers in the checked runtime state, so TF ownership for the final stack must be explicitly reassigned during migration.

### Fixes applied
None. This was a read-only inspection pass.

### Current result
Confirmed facts:
- A2 real machine hostname: `unitree-a2-pc2`
- ROS distro: Humble
- JT128 reachable on `net1` at `192.168.124.20`; `eth0` cannot reach it.
- Host sensor-side IP is `192.168.124.162/24` on `net1`.
- Unitree control-side IP is `192.168.123.162/24` on `eth0`.
- Unitree native Hesai config uses front JT128 `.20`, UDP `2368`, PTC `9347`.
- Live point cloud topic: `/unitree/slam_lidar/points1`
- Live IMU topic: `/unitree/slam_lidar/imu1`
- Point cloud frame is `hesai_lidar`.
- Point cloud fields include `x`, `y`, `z`, `intensity`, `ring`, and `timestamp`.
- `unitree_slam.service` starts `hesai_ros_driver_node`, `point_cloud_fusion`, `navigation_mapping.py`, `dwa_obstacle_avoidance.py`, and `unitree_slam`.
- Source `/home/unitree/graph_pid_ws/install/setup.bash` exposes `hesai_ros_driver` and `point_cloud_fusion`; DLIO is not installed.
- Local A2 repo has `src/third_party/FAST_LIO`, but DLIO is not present.

### Remaining risks or follow-ups
- Need official standalone HesaiLidar_ROS_2.0 validation outside `unitree_slam.service`.
- Need to add or vendor DLIO before Phase 2 can run.
- Need calibrated `base_link -> jt128_front_link` extrinsic; current static TF uses approximate `base_link -> lidar_link` `[0.32, 0.0, 0.24]`.

---

## Entry 88 — Added JT128 + DLIO engineering plan

### Time
2026-04-29 09:40 CST

### Action taken
Added a detailed repository documentation file for the single-front-JT128 migration plan. The document covers the verified A2 facts, target JT128 topic contracts, TF ownership, Hesai driver integration, DLIO mapping, FAST-LIO2 fallback, map/navigation fusion, phased validation, safety requirements, deliverables, and immediate implementation tasks.

### Tool or method used
- Added `src/a2_system/docs/jt128_dlio_engineering_plan.md`
- Ran `wc -l` on the document
- Ran `rg` checks for major headings and critical topic/network strings

### Why this approach
The user asked for an engineering-grade plan after providing the remaining design constraints. A standalone document makes the migration scope explicit and prevents mixing verified facts with assumptions before code changes begin.

### Problems encountered
None.

### Fixes applied
None.

### Current result
New document created:
- `src/a2_system/docs/jt128_dlio_engineering_plan.md`

The document records that Phase 1 must isolate the Hesai JT128 driver from `unitree_slam.service`, publish `/jt128/front/points` and `/jt128/front/imu`, then Phase 2 can add DLIO and managed PCD saving.

### Remaining risks or follow-ups
- The plan is not implementation yet.
- DLIO is not installed in the current workspace.
- Official standalone Hesai driver launch still needs to be created and validated on `net1`.
- Accurate JT128 extrinsics still need to be confirmed or calibrated.

---

## Entry 89 — Started implementing JT128 + DLIO pipeline

### Time
2026-04-29 09:42:39 CST

### User request
Start implementing the plan: independently launch the JT128 Hesai driver, output `/jt128/front/points` and `/jt128/front/imu`, connect DLIO to produce `/jt128/dlio/odom` and `/jt128/dlio/map_points`, save `pointcloud_map_3d.pcd` through `map_manager`, then move toward 3D PCD relocalization and 3D navigation closure.

### Action taken
Started the implementation phase and checked the current local worktree before editing.

### Tool or method used
- Ran `date '+%Y-%m-%d %H:%M:%S %Z'`
- Ran `git -C /home/dell/a2_system_ws status --short --branch`

### Why this approach
The requested work touches hardware interface, ROS topics, TF, mapping, map management, launch files, scripts, and future navigation. Checking the dirty worktree first avoids accidentally overwriting existing user or prior agent changes.

### Problems encountered
The repository already contains many uncommitted prior 3D/Web changes and unrelated untracked files. These must be preserved.

### Fixes applied
None yet.

### Current result
Implementation work is starting from the current dirty `master` workspace.

### Remaining risks or follow-ups
- Need to inspect existing launch/package setup before adding new files.
- Need to handle missing DLIO as a clear startup error until the package is vendored or installed.

---

## Entry 90 — JT128/DLIO implementation and first real-robot validation

### Time
2026-04-29 10:35 CST

### User request
Independently launch the JT128 Hesai driver, publish `/jt128/front/points` and `/jt128/front/imu`, connect DLIO to produce `/jt128/dlio/odom` and `/jt128/dlio/map_points`, save `pointcloud_map_3d.pcd` through `map_manager`, then proceed toward 3D PCD relocalization and 3D navigation closure.

### Action taken
Implemented and synchronized the first JT128 3D pipeline pieces to A2:
- Added standalone JT128 Hesai launch support that runs the Unitree-installed `hesai_ros_driver` with a runtime config directory so the binary reads our JT128 config without editing `/home/unitree/graph_pid_ws`.
- Added a one-command JT128/DLIO mapping startup script that stops known 2D/Unitree SLAM interference, validates the JT128 network route on `net1`, starts the driver, DLIO, `map_manager`, and optionally Web.
- Added DLIO JT128 config and launch remaps for `/jt128/front/points`, `/jt128/front/imu`, `/jt128/dlio/odom`, and `/jt128/dlio/map_points`.
- Installed/synced DLIO source onto A2 and built `direct_lidar_inertial_odometry`.
- Extended `map_manager` path so it can save a 3D point cloud map as `pointcloud_map_3d.pcd`.
- Added a conservative `pcd_relocalizer_3d` node and `jt128_3d_navigation.launch.py` for later map-based 3D relocalization.

### Tool or method used
- Local file edits with `apply_patch`
- Local validation with Python compile checks, YAML parse checks, and `colcon build`
- A2 synchronization with `rsync` over `ssh a2`
- A2 build with `colcon build --symlink-install`
- A2 runtime checks with `ros2 topic list`, `ros2 topic hz`, `ros2 topic echo`, and `ros2 service call`

### Why this approach
The user explicitly asked to stop treating 2D as the main truth source. The safest migration path is to first isolate JT128 driver output, then run DLIO as an independent 3D odometry/map source, then connect map saving and relocalization. This avoids changing the existing control bridge until the 3D pose source is proven stable.

### Problems encountered
- The A2 machine initially did not have DLIO installed. Direct GitHub clone from A2 failed due TLS/network issues, so DLIO source had to be synced from the local machine.
- The Unitree Hesai driver binary ignored normal ROS parameter expectations and looked for `./config_files/hs_lidar_jt128/config.yaml`; the standalone launch had to set a runtime working directory and copy config there.
- The startup script initially failed because `ros2` was checked before sourcing ROS, then failed again because `set -u` conflicted with ROS setup scripts.
- The first full DLIO run produced the requested topics and saved a PCD map, but DLIO later diverged catastrophically to implausible positions and crashed with `eprosima::fastcdr::exception::NotEnoughMemoryException`.
- The first relocalizer version could auto-seed identity and accept a bad ICP result; it was unsafe for closed-loop navigation.

### Fixes applied
- Moved `ros2` command checks after ROS workspace sourcing.
- Wrapped ROS sourcing in `set +u` / `set -u`.
- Added a host route check/replacement so `192.168.124.20` uses the selected JT128 interface.
- Reworked the Hesai launch to use a runtime `config_files/hs_lidar_jt128/config.yaml` directory.
- Changed the 3D relocalizer to require an explicit `/initialpose` seed by default and to reject large map-to-odom corrections.
- Added safety bounds to prevent publishing obviously invalid `map -> odom` transforms.

### Current result
Verified on A2:
- `/jt128/front/points` is published by the standalone JT128 driver.
- `/jt128/front/imu` is published by the standalone JT128 driver.
- DLIO can start and publish `/jt128/dlio/odom` and `/jt128/dlio/map_points`.
- `map_manager` can save a 3D map file at `runtime/maps/<map_id>/pointcloud_map_3d.pcd`.
- The current blocker is DLIO stability, not topic plumbing.

### Remaining risks or follow-ups
- DLIO output must not be used for closed-loop navigation until the divergence is fixed.
- A2 JT128 IMU reported gravity primarily on `+Y`, so the provisional DLIO IMU extrinsic was changed to map A2 base `+Z` to IMU `+Y`; this still needs live validation.
- Proper JT128 `base_link -> lidar/imu` calibration is still not verified.
- Need to re-run the full stack after the IMU rotation fix and monitor DLIO pose for at least a short stationary window before saving or navigating.

---

## Entry 91 — Continue JT128 3D stack hardening after DLIO divergence

### Time
2026-04-29 11:04 CST

### User request
Continue from the JT128 3D implementation and complete the independent JT128 driver, DLIO mapping, PCD saving, 3D relocalization, and 3D navigation closure path.

### Action taken
Resumed by checking the local repository state and the A2 runtime process state. Confirmed the local workspace contains the new JT128/DLIO launch files, 3D relocalizer, 3D pose controller, one-click stack scripts, and the newly added DLIO watchdog. Found a stale A2-side one-shot point cloud statistics process still running from earlier diagnostics.

### Tool or method used
- Ran `git status --short` in `/home/dell/a2_system_ws`.
- Ran `ssh a2 'hostname; pgrep -af ...'` to inspect A2-side JT128/DLIO/navigation processes.
- Inspected `start_jt128_3d_stack.sh`, `start_jt128_dlio_mapping.sh`, `dlio_mapping.launch.py`, `jt128_3d_navigation.launch.py`, `jt128_dlio_watchdog.py`, and `a2_system/CMakeLists.txt`.

### Why this approach
The last real-robot run showed that topic plumbing worked but DLIO could still diverge catastrophically. Before any further mapping or navigation validation, the safety watchdog and launch changes must be synced and rebuilt on A2, and stale diagnostic processes must be stopped.

### Problems encountered
The A2 runtime still had a leftover `/jt128/front/points` statistics process. This is not expected to control the robot, but it can consume point cloud traffic and confuse process checks.

### Fixes applied
None yet in this entry; next step is to stop stale processes, sync the latest package sources to A2, rebuild, then re-run a bounded static validation.

### Current result
The next safe action is clear: deploy the watchdog-enabled stack to A2 and verify that the stack stops itself if DLIO odometry leaves conservative bounds.

### Remaining risks or follow-ups
- Do not run `--live-motion` until watchdog deployment and stationary DLIO stability are verified.
- Need to confirm the installed A2 launch actually starts `jt128_dlio_watchdog.py`.
- Need to verify the watchdog status topic `/a2/jt128/dlio_watchdog`.

---

## Entry 92 — JT128 3D mapping, PCD save, relocalization, and dry-run navigation validation

### Time
2026-04-29 11:25 CST

### Action taken
Completed a deploy-and-validate pass on A2 for the JT128 3D stack:
- Synced the latest `a2_system`, `a2_bringup`, `localization_manager`, `nav2_integration`, and `map_manager` sources to A2.
- Rebuilt missing A2 overlay packages: `a2_interfaces`, `gazebo_bridge`, `direct_lidar_inertial_odometry`, `tf_manager`, `safety_manager`, `a2_sdk_bridge`, `a2_state_publisher`, `a2_control_bridge`, `a2_system`, `a2_bringup`, `localization_manager`, `nav2_integration`, and `map_manager`.
- Started JT128 standalone driver and DLIO through `start_jt128_3d_stack.sh`.
- Verified `/jt128/front/points`, `/jt128/front/imu`, `/jt128/dlio/odom`, `/jt128/dlio/map_points`, and `/a2/jt128/dlio_watchdog`.
- Saved a 3D PCD map through `map_manager`: `runtime/maps/jt128_static_111130/pointcloud_map_3d.pcd`.
- Started 3D navigation dry-run mode using that PCD map.
- Sent `/initialpose` and verified `pcd_relocalizer_3d`, `localization_gate`, `safety_supervisor`, and `real_readiness_monitor` reached ready.
- Sent a short dry-run goal and verified `goal_bridge -> /goal_pose_ -> pose_goal_controller_3d` produced `/a2/nav3/status` running with `dry_run=True`.
- Cleaned duplicate stale launch/static-TF processes, fixed the stop script, and restarted the stack cleanly.

### Tool or method used
- `rsync` to deploy package sources to `ssh a2`.
- `colcon build --symlink-install --packages-select ...` on A2.
- `ros2 topic hz`, `ros2 topic echo --once`, `ros2 topic info`, `ros2 service call`, `pgrep`, and `curl`.
- Python compile checks and shell syntax checks locally.

### Why this approach
The system had already proven topic-level connectivity, but real-robot safety required proving that stale processes are removed, watchdog status is visible, and 3D relocalization can put the stack into `ready` before any motion is considered.

### Problems encountered
- A2 install was missing several package environment files, so dependent package builds failed until `a2_interfaces` and `gazebo_bridge` were rebuilt.
- `direct_lidar_inertial_odometry` was present in source but not discoverable in the active ROS overlay, so the one-click stack initially rejected startup.
- `tf_manager` was missing from the active overlay, causing `dlio_mapping.launch.py` to fail before driver startup.
- Early stop/start cycles left duplicate `dlio_mapping.launch.py` and `jt128_static_tf_manager` processes.
- `sudo pkill -f` in the interference cleanup printed noisy `Killed` messages because the pkill command could match itself.
- `localization_gate`, `pcd_relocalizer_3d`, `pose_goal_controller_3d`, and the DLIO watchdog were too chatty because status reasons changed every cycle.

### Fixes applied
- Rebuilt the missing overlay packages on A2.
- Added and deployed `jt128_dlio_watchdog.py`.
- Added ROS1/Livox/Foxglove/native navigation process cleanup to `start_jt128_dlio_mapping.sh`.
- Reworked kill logic in `start_jt128_dlio_mapping.sh` and `stop_jt128_stack.sh` to collect PIDs first and kill them, avoiding self-matching `pkill` noise.
- Added `jt128_dlio_watchdog.py` and `jt128_static_tf_manager` cleanup to `stop_jt128_stack.sh`.
- Added a Web fallback path in `start_jt128_3d_stack.sh` so the backend starts directly if systemd restart is unavailable.
- Throttled repeated OK/ready/running status logs in watchdog, relocalizer, localization gate, and pose controller.

### Current result
Clean final A2 state after restart:
- One `dlio_mapping.launch.py` process.
- One `jt128_static_tf_manager` process.
- Web is reachable on `http://127.0.0.1:8080` from A2 and should be reachable externally at `http://192.168.31.49:8080`.
- `/a2/real/report`: `state=ready;ready=true`.
- `/a2/jt128/dlio_watchdog`: `state=ok;ready=true`.
- `/a2/relocalization/status`: `state=ready;ready=true`, fitness around `0.153`, correspondences around `793`.
- DLIO odom remained near origin during the final stationary validation.

### Remaining risks or follow-ups
- Live motion was intentionally not enabled. The final validation is 3D dry-run, not a robot-moving closed loop.
- The map `jt128_static_111130` is a small stationary test map, not a useful operational map.
- DLIO still needs longer stationary, slow-walk, and rosbag validation before enabling `--live-motion`.
- JT128 extrinsics are still provisional and must be calibrated before claiming mapping precision.
- The current 3D pose controller is a conservative short-range servo, not a full obstacle-aware 3D planner.

---

## Final outcome

### Summary
Implemented and validated the first real JT128-first 3D pipeline on A2: standalone Hesai JT128 driver, DLIO mapping, 3D PCD saving through `map_manager`, PCD-based 3D relocalization, and dry-run 3D goal-control closure through the Web/goal bridge path. The stack is currently left running in safe dry-run navigation mode with `/a2/real/report` ready.

### Files changed
- `src/a2_bringup/launch/dlio_mapping.launch.py`
- `src/a2_bringup/launch/jt128_3d_navigation.launch.py`
- `src/a2_bringup/launch/jt128_driver.launch.py`
- `src/a2_system/CMakeLists.txt`
- `src/a2_system/config/dlio_jt128.yaml`
- `src/a2_system/config/jt128_front_hesai.yaml`
- `src/a2_system/config/pcd_relocalization_3d.yaml`
- `src/a2_system/config/pose_goal_controller_3d.yaml`
- `src/a2_system/scripts/jt128_dlio_watchdog.py`
- `src/a2_system/tools/start_jt128_3d_stack.sh`
- `src/a2_system/tools/start_jt128_dlio_mapping.sh`
- `src/a2_system/tools/stop_jt128_stack.sh`
- `src/localization_manager/localization_manager/localization_gate.py`
- `src/localization_manager/localization_manager/pcd_relocalizer_3d.py`
- `src/localization_manager/package.xml`
- `src/localization_manager/setup.py`
- `src/map_manager/map_manager/map_manager_node.py`
- `src/map_manager/map_manager/pointcloud_map_loader.py`
- `src/map_manager/setup.py`
- `src/nav2_integration/nav2_integration/pose_goal_controller_3d.py`
- `src/nav2_integration/setup.py`
- `agent-logs/2026-04-27-agent-session.md`

### Commands run
- Local syntax checks: `python3 -m py_compile ...`, `bash -n ...`
- A2 deploy: `rsync -az --delete ... a2:/home/unitree/a2_system_ws/src/...`
- A2 builds: `colcon build --symlink-install --packages-select ...`
- A2 runtime: `start_jt128_3d_stack.sh --mode navigation --map-id jt128_static_111130 --lidar-iface net1 --sdk-iface eth0`
- A2 verification: `ros2 topic echo --once /a2/real/report`, `/a2/jt128/dlio_watchdog`, `/a2/relocalization/status`, `/jt128/dlio/odom`

### Verification
- JT128 points and IMU were verified live.
- DLIO odom remained near origin in final stationary validation.
- `map_manager` saved `runtime/maps/jt128_static_111130/pointcloud_map_3d.pcd`.
- 3D relocalization reached ready after `/initialpose`.
- Real readiness reached `state=ready;ready=true`.
- Web backend returned HTTP OK.
- Final process check showed one mapping launch and one static TF manager, not duplicate stacks.

### Known limitations
- No live motion was enabled.
- The saved PCD is a stationary smoke-test map, not an operational map.
- DLIO stability must be validated with longer stationary and slow-motion bags before robot movement.
- Full 3D obstacle-aware global planning is not implemented; current 3D navigation closure is a conservative short-range dry-run pose servo.

---

## Entry 93 — Script viability re-check

### Time
2026-04-29 11:39 CST

### User request
Confirm whether the current one-click script can still launch all of the nodes in the present system state.

### Action taken
Checked the installed A2 scripts, required package overlays, currently running processes, and live status topics. Verified that the active A2 stack is in fact being run by `start_jt128_3d_stack.sh` and that the expected driver, DLIO, watchdog, map manager, relocalizer, safety, SDK, state publisher, goal bridge, pose controller, and Web backend processes are all present.

### Tool or method used
- `ssh a2`
- `test -x .../start_jt128_3d_stack.sh`
- `ros2 pkg prefix ...`
- `pgrep -af ...`
- `ros2 topic echo --once /a2/real/report`
- `ros2 topic echo --once /a2/relocalization/status`
- `ros2 topic echo --once /a2/jt128/dlio_watchdog`

### Why this approach
This answers the question directly from the live A2 machine instead of inferring from prior edits or local files.

### Problems encountered
None.

### Fixes applied
None.

### Current result
The script is currently viable and is already running the stack on A2. Observed live processes include:
- `dlio_mapping.launch.py`
- `hesai_ros_driver_node`
- `dlio_odom_node`
- `dlio_map_node`
- `jt128_dlio_watchdog.py`
- `map_manager_node`
- `jt128_3d_navigation.launch.py`
- `a2_sdk_bridge_node`
- `a2_state_publisher_node`
- `pcd_relocalizer_3d`
- `localization_gate`
- `safety_supervisor`
- `real_readiness_monitor`
- `goal_bridge`
- `pose_goal_controller_3d`
- Web backend `backend.main`

### Remaining risks or follow-ups
- The script launches the full dry-run 3D stack correctly, but real robot motion is still intentionally disabled because the controller remains in `dry_run=true`.
- Long-duration DLIO stability and real movement closure are still pending.
