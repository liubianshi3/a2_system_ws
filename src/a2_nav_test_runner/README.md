# a2_nav_test_runner

`a2_nav_test_runner` 是 A2 真机导航测试与精度诊断工具包。它的目标不是替代底层导航，也不是直接做 PADS 调度，而是在真机到位后把“导航接口是否可用、目标是否真的到达、误差到底来自哪里”这件事查清楚。

## 1. 本包用途

本包用于 A2 真机导航链路的工程化检查与诊断：

- 检测 `/map`、`/tf`、`/odom`、`/amcl_pose` 等运行态接口；
- 检测 Nav2 `NavigateToPose` action；
- 检测 A2 自定义 `NavCommand` service；
- 支持 `dry_check_only` 安全模式；
- 支持单点近距离导航测试；
- 支持固定多点导航测试；
- 记录 backend 成功、runner 判定成功、最终位姿误差；
- 导出运行时参数、TF 稳定性、静止定位抖动和单点重复误差报告；
- 为后续接入 PADS 提供可靠的导航层前置验证。

## 2. 本包不是

本包不是：

- PADS 任务调度算法；
- 论文实验结果；
- Nav2 planner；
- Nav2 controller；
- Gazebo 仿真；
- 真实机器人结果替代品；
- 底层导航系统本身。

它只调用已经启动的导航接口，不改写底层导航逻辑。

## 3. 当前支持的导航后端

| 后端 | 接口 | 用途 | 成功判定 |
|---|---|---|---|
| Nav2 action | `/navigate_to_pose` | 标准 Nav2 目标发送 | 以 action result 为主 |
| A2 NavCommand service | `/nav_command` 等候选 service | A2 自定义导航命令发送 | service 接受命令不等于真实到达，必要时必须结合 pose feedback |

`NavCommand.srv` 当前真实字段：

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

注意：这里的 `response.success` 只能说明服务端是否接受了命令，不能直接当成“机器人已经停到目标点”。

## 4. 构建

```bash
cd /home/dell/a2_sys_ws
colcon build --packages-select a2_interfaces a2_nav_test_runner
source install/setup.bash
```

如果全工作区构建：

```bash
cd /home/dell/a2_sys_ws
colcon build
source install/setup.bash
```

如果 `a2_interfaces` 尚未先构建，`a2_nav_test_runner` 中的 `NavCommand` client 会因为接口包不可用而失败。

## 5. 启动导航栈

根据现场系统选择一个入口。

当前推荐主线是 **2D Nav2**：

- `mapping_2d`: JT128 点云 -> `/scan` -> `slam_toolbox` -> `/map`
- `navigation_2d`: `/map + /scan + /odom` -> `AMCL` -> Nav2 `/navigate_to_pose`

3D 路线仍然保留，但它是 **backup path**，不是默认推荐主线。

可选入口：

```bash
ros2 launch a2_bringup nav2.launch.py
```

或：

```bash
ros2 launch a2_bringup jt128_3d_navigation.launch.py
```

启动后先检查：

```bash
ros2 topic list
ros2 action list
ros2 service list
ros2 action list | grep navigate_to_pose
```

## 6. 基础导航测试阶段

### 阶段 1：dry check

默认配置里：

- `dry_check_only: true`
- `first_goal_only: true`

这意味着初始运行不会真的发目标。

```bash
ros2 launch a2_nav_test_runner nav_test.launch.py dry_check_only:=true
```

输出：

```text
src/a2_nav_test_runner/results/a2_runtime_check_YYYYMMDD_HHMMSS.md
```

这不是实验结果，只是接口检查。

### 阶段 2：单点近距离测试

真机首次测试前，先修改：

```text
src/a2_nav_test_runner/config/nav_test_goals.yaml
```

只保留实际地图中重新标定的一个近距离目标点，建议距离小于 2 m。

```bash
ros2 launch a2_nav_test_runner nav_test.launch.py dry_check_only:=false first_goal_only:=true runs:=1
```

### 阶段 3：多点固定序列测试

单点稳定后再运行：

```bash
ros2 launch a2_nav_test_runner nav_test.launch.py dry_check_only:=false first_goal_only:=false runs:=3
```

## 7. 导航精度彻查流程

这部分是本包新增的精度诊断主线，目的是查清楚“20–25 cm 到点误差到底来自哪里”。

### 先知道几个很重要的事实

1. **25 cm 误差不一定来自 Nav2 默认容差。**
2. 当前仓库静态 Nav2 `xy_goal_tolerance` 不是 `0.25`，而是 `0.06`，见：
   - `src/a2_system/config/nav2_stack.yaml:85`
3. `pose_goal_controller_3d.goal_tolerance_xy = 0.15`，见：
   - `src/a2_system/config/pose_goal_controller_3d.yaml:21`
4. `arrival_tolerance = 0.35` 只是测试程序的判定阈值，不代表底层控制器真的停到了 35 cm。
5. **运行时参数才是最终依据。**
6. 目标点和最终位姿必须在同一 frame 下比较。
7. `/odom` 不能直接和 map-frame 目标比较，除非已经通过 TF 转换。
8. A2 现场很可能走的是 `NavCommand` 或 `pose_goal_controller_3d` 链路，而不是标准 Nav2 `controller_server`。

### Step 1：运行时链路判断

```bash
ros2 run a2_nav_test_runner nav_runtime_diagnosis
```

它会判断当前更像是哪条链路：

- `nav2_action`
- `pose_goal_controller_3d`
- `a2_navcommand`
- `unknown`

### Step 2：导出运行时参数

```bash
ros2 run a2_nav_test_runner runtime_param_dumper
```

它会抓取运行中的导航相关节点参数，重点汇总：

- `xy_goal_tolerance`
- `yaw_goal_tolerance`
- `goal_checker`
- `progress_checker`
- `robot_base_frame`
- `global_frame`
- `odom_frame`
- `transform_tolerance`
- `robot_radius`
- `inflation_radius`
- 速度上限等

### Step 3：机器人静止时录 60 秒定位抖动

```bash
ros2 run a2_nav_test_runner pose_accuracy_recorder --ros-args -p duration_sec:=60
```

如果静止不动时 `map -> base_link` 自身抖动已经接近 `0.1 m`，那最终 20–25 cm 误差就很可能不是“到达判定太松”，而是定位本身已经不稳定。

### Step 4：做 TF 诊断

```bash
ros2 run a2_nav_test_runner tf_diagnosis
```

重点看：

- `map -> odom`
- `odom -> base_link`
- `map -> base_link`
- `map -> base_footprint`
- `base_link -> base_footprint`

如果 `map -> odom` 有跳变，问题更偏定位。
如果 `base_link -> base_footprint` 有固定偏移，视觉上看到的“没停准”可能只是参考点不一致。

### Step 5：同一个近距离目标重复 5 次

```bash
ros2 run a2_nav_test_runner single_goal_accuracy_test --ros-args -p goal_x:=1.0 -p goal_y:=0.5 -p repeats:=5
```

这个工具会同时记录：

- `backend_success`
- `runner_arrival_success`
- `final_error_amcl`
- `final_error_odom`
- `final_error_tf_map_base_link`
- `final_error_tf_map_base_footprint`
- `yaw_error_tf_map_base_link`
- 运行时 tolerance

### Step 6：综合分析

```bash
ros2 run a2_nav_test_runner navigation_precision_analyzer
```

它会自动读取最新的一组诊断结果，输出根因分析报告，并给出结论之一：

- `PASS_NAV_FOR_PADS`
- `NEED_NAV_TUNING`
- `NEED_LOCALIZATION_FIX`
- `NEED_FRAME_FIX`
- `NEED_BACKEND_CLARIFICATION`
- `INSUFFICIENT_DATA`

### Step 7：只有 PASS 后才接 PADS

只有当导航本身已经足够稳定，才可以接 Greedy-PADS / RH-PADS-L。  
否则任务调度实验会被底层导航误差污染。

## 8. 如何判断 25 cm 的来源

建议按下面逻辑看：

- 如果 runtime `xy_goal_tolerance` 接近 `0.25`，那到达容差是强嫌疑。
- 如果 runtime `xy_goal_tolerance` 是 `0.06`，但最终 `final_error_tf_map_base_link` 仍接近 `0.25`，那要优先看定位、TF 和控制停稳误差。
- 如果 `amcl` 误差和 `TF map->base_link` 误差明显不一致，先查 frame 和比较方法。
- 如果静止时 pose 抖动很大，优先修定位。
- 如果 pose 很稳但停不准，优先查 controller / 执行层。
- 如果 `backend_success` 和 `runner_arrival_success` 不一致，说明“后端说成功”和“程序按位姿判定成功”不是一回事。

## 9. 输出文件

### 常规导航测试

真实发送目标后才会生成：

```text
src/a2_nav_test_runner/results/a2_nav_test_log_YYYYMMDD_HHMMSS.csv
src/a2_nav_test_runner/results/a2_nav_test_summary_YYYYMMDD_HHMMSS.csv
```

### 精度诊断

会生成：

```text
src/a2_nav_test_runner/results/a2_navigation_precision_static_scan.md
src/a2_nav_test_runner/results/nav_runtime_diagnosis_YYYYMMDD_HHMMSS.md
src/a2_nav_test_runner/results/runtime_params_YYYYMMDD_HHMMSS/runtime_param_summary.md
src/a2_nav_test_runner/results/tf_diagnosis_YYYYMMDD_HHMMSS.csv
src/a2_nav_test_runner/results/tf_diagnosis_YYYYMMDD_HHMMSS.md
src/a2_nav_test_runner/results/static_pose_accuracy_YYYYMMDD_HHMMSS.csv
src/a2_nav_test_runner/results/static_pose_accuracy_summary_YYYYMMDD_HHMMSS.md
src/a2_nav_test_runner/results/single_goal_accuracy_YYYYMMDD_HHMMSS.csv
src/a2_nav_test_runner/results/single_goal_accuracy_summary_YYYYMMDD_HHMMSS.md
src/a2_nav_test_runner/results/navigation_precision_root_cause_report_YYYYMMDD_HHMMSS.md
```

## 10. 安全要求

真机测试必须满足：

- 必须人工看护；
- 必须确认急停可用；
- 初次目标距离小于 2 m；
- 场地清空障碍；
- 不要一开始跑多点；
- 定位未稳定时不要运行；
- 导航失败立即停止；
- dry check 通过后才允许运行单点；
- 单点稳定后才允许运行多点和重复试验。

## 11. 论文说明

以下内容不能写成论文“真实机器人实验结果”：

- 代码框架已经完成；
- dry check 报告；
- 只做了参数 dump；
- 没有真实发送目标；
- 没有真实生成导航 log / summary；
- 当前二维仿真或小车运动学仿真冒充真机结果。

只有当机器人真的运行，并由 ROS2 action/service 与 pose/TF 日志共同支持时，相关 CSV 和报告才可以进入论文实机部分。

## 12. 后续接入 PADS

下一阶段的正确顺序是：

1. 先让单点导航精度过关；
2. 再做固定多点导航稳定性；
3. 最后才接 PADS；
4. 接入顺序建议先 `Greedy-PADS`，再 `RH-PADS-L`。

相关规划见：

```text
src/a2_nav_test_runner/PADS_INTEGRATION_PLAN.md
```

## 13. 无真机 Mock 诊断测试

Mock 测试的目的，是验证诊断工具链和日志字段是否工作正常，不是验证 A2 真机导航精度。

可运行：

```bash
ros2 launch a2_nav_test_runner mock_navigation_test.launch.py scenario:=clean_nav
```

或批量运行：

```bash
ros2 run a2_nav_test_runner mock_precision_scenario_runner
```

输出路径：

```text
src/a2_nav_test_runner/results/mock_precision/
```

严格说明：

- Mock 数据不能作为论文真机实验结果；
- Mock 数据不能证明 A2 导航精度；
- Mock 只能证明诊断软件链路工作正常；
- Mock 结果文件会明确标记 `THIS_IS_MOCK_DATA` 和 `data_source: mock_navigation_test`。

真机到位后仍必须重新运行：

```bash
ros2 run a2_nav_test_runner nav_runtime_diagnosis
ros2 run a2_nav_test_runner runtime_param_dumper
ros2 run a2_nav_test_runner pose_accuracy_recorder --ros-args -p duration_sec:=60
ros2 run a2_nav_test_runner tf_diagnosis
ros2 run a2_nav_test_runner single_goal_accuracy_test --ros-args -p goal_x:=1.0 -p goal_y:=0.5 -p goal_yaw:=0.0 -p repeats:=5 -p backend_type:=auto
ros2 run a2_nav_test_runner navigation_precision_analyzer
```
