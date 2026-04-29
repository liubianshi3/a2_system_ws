# A2 从 2D 到 3D 的完整调试实录

## 1. 这份文档是干什么的

这不是一份“概念介绍”文档，而是一份**真实调试实录 + 上手指南**。

目标是让一个刚加入项目的人，哪怕之前没完整接触过 ROS2、Nav2、AMCL、Web 控制台、Unitree 原生链路，也能快速搞清楚：

- 我们最开始的系统到底是什么样
- 为什么 2D 链路虽然能跑，但已经成了上限
- 我们在真实 A2 机器人上到底遇到了什么问题
- 每一步是怎么查出来的
- 每一步改了哪些文件
- 现在 3D 链路到底跑到什么程度
- 你接下来应该怎么继续调

这份文档覆盖的是一次真实的工程迁移过程：

- 从 `3D 点云 -> 压成 2D scan -> slam_toolbox/AMCL/Nav2`
- 逐步迁移到
- `前置雷达 3D 点云 -> 3D 累积地图 -> Web 3D 可视化 -> 3D-first 控制合同`

注意：截至当前，这条链路已经是**真实可运行的 3D 主链**，但它还不是“带回环闭环优化的完整工业级 3D SLAM”。这一点必须说清楚。

---

## 2. 先讲清楚：我们原来的系统是什么

### 2.1 原来的主链

最开始我们真实机器人主链本质上是：

```text
/unitree/slam_lidar/points1
  -> pointcloud_to_laserscan
  -> /scan
  -> slam_toolbox
  -> /map
  -> AMCL
  -> /amcl_pose
  -> Nav2
  -> /navigate_to_pose
  -> a2_control_bridge
  -> 机器狗运动
```

Web 前端吃的是 2D 栅格地图：

```text
/map (OccupancyGrid)
  -> backend MapSnapshot
  -> frontend MapCanvas
```

### 2.2 这条链为什么一开始看起来合理

因为 ROS2 和 Nav2 的成熟默认工程路径，天然就是 2D：

- `slam_toolbox` 很成熟，输入 `/scan`，输出 `/map`
- `AMCL` 很成熟，输入 `/map + /scan + /odom`，输出 `/amcl_pose`
- `Nav2` 天然围绕 2D OccupancyGrid 工作
- Web 前端最容易做的也是 2D canvas

所以从“先跑起来”的角度，这条链很常见。

### 2.3 但它的问题也非常明确

真正的问题不是“它不能动”，而是“它的上限太低”。

核心损失发生在这里：

```text
3D 点云 -> pointcloud_to_laserscan -> 2D LaserScan
```

也就是说，我们前面的真实雷达明明给的是 3D 信息，但系统主链第一步就把它压扁了。

这样带来几个后果：

1. 丢掉高度信息
   地面以上的结构、立柱、桌腿、边角、斜面、局部遮挡信息会被严重简化。

2. 地图质量依赖“投影效果”
   不是原始点云本身不行，而是你投影成 `/scan` 之后已经失真了。

3. AMCL 只能在 2D 栅格上做匹配
   所以初始位姿、局部收敛、协方差收缩，都受 2D 栅格质量限制。

4. Web 看到的是 2D“结果图”，不是 3D 真值
   你在页面上看到的东西，不一定代表雷达真正看到了什么。

---

## 3. 我们第一次真实复现时，现场到底遇到了什么

### 3.1 最开始的现象

第一次在真实 A2 上复现时，用户看到的是：

- 远端启动脚本 `start_real_stack.sh` 仍然带着旧默认值
- `unitree_slam.service` 还在跑
- 在线的是 Unitree 自带链路：
  - `/navigation_mapping_node`
  - `/point_cloud_fusion`
  - `/hesai_ros_driver_node`
- 但我们自己期待的链路没起来：
  - `/map`
  - `/scan`
  - `/amcl_pose`
  - `/a2/real/report`
  - `/navigate_to_pose`

这说明一件非常关键的事：

**机器人上并不是“什么都没跑”，而是“别人的栈已经在跑，我们自己的栈没真正接管”。**

这是后面所有问题的起点。

### 3.2 这一步我们学到的第一个工程原则

真实机器人上，最怕的不是“起不来”，而是：

- 旧进程残留
- 原生服务还活着
- ROS1/ROS2 混合
- Web 以为自己控制了系统，实际上没有

所以从这一步开始，我们把“先清干扰，再起自己栈”当成硬规则。

---

## 4. 我们先修的不是算法，而是启动契约

### 4.1 为什么先修启动脚本

因为如果默认入口还是旧逻辑，后面所有调图、调导航、调 Web 都会被污染。

我们最开始先处理了这些问题：

- 旧默认 `manual_odom`
- 启动脚本没有把 AMCL 作为真实默认定位
- 停止脚本没有清完残留进程
- Web 的节点等待逻辑还在等旧节点

### 4.2 典型结论

那一轮我们明确了：

- 真实默认定位不应该再回到 `manual_odom`
- AMCL 应该是当时的真实默认
- Web 的 ready 逻辑不能再盯旧的 manual localization 节点
- `unitree_slam.service` 和我们自己的 bringup 之间必须有清晰边界

这时系统还没变成 3D，只是先把 2D 栈拉正了。

---

## 5. 2D 阶段我们具体查清了什么

在真正开始 3D 改造前，我们其实把 2D 链路吃得很透。

### 5.1 搞清楚了 `/unitree/slam_lidar/points1 -> /scan`

这个链路当时很多人不理解，核心解释很简单：

- `/unitree/slam_lidar/points1` 是前置雷达点云
- `pointcloud_to_laserscan` 会在一个高度切片上，把点云投成 2D 激光扫描
- 输出 `/scan`
- `slam_toolbox` 和 `AMCL` 都习惯直接吃 `/scan`

也就是说，它不是“雷达坏了”，而是**系统故意把 3D 压成 2D 给老模块用**。

### 5.2 搞清楚了 `/map + /scan + /odom -> AMCL -> /amcl_pose`

AMCL 的作用不是建图，而是定位：

- `/map`：静态地图
- `/scan`：当前激光扫描
- `/odom`：机器人短时间运动估计
- 输出 `/amcl_pose`：机器人在地图中的位置估计

所以当时常见的问题不是“AMCL 崩了”，而是：

- 地图太差
- 初始位姿不对
- `/scan` 投影质量不够
- `/odom` 抖动
- 协方差收不下来

### 5.3 最关键的 2D 结论

那时我们已经明确：

- 建图模式能起
- 导航模式也能起
- 但地图质量和定位收敛性差
- 黑点晃动、`xy_ok=false` 本质上是匹配质量不够

所以从工程判断上，继续死调 2D 参数已经没有性价比。

---

## 6. 为什么后来决定必须切 3D

这个决定不是“喜欢新东西”，而是被现象逼出来的。

### 6.1 用户现场反馈非常明确

用户反复指出：

- 建图精度差
- 该扫描的地方没有扫出来
- initial pose 发了，`ready` 还是进不去
- 机器人在地图里的黑点一直晃
- Web 里看起来像是图，但实际上导航不好用

这些问题如果只是 2D 参数调优问题，一两轮就该有明显改善。

但事实是：

- 2D 栈能工作
- 但很难达到用户要的精度和稳定性

这就是“上限问题”，不是“小 bug 问题”。

### 6.2 我们当时的工程判断

真正的矛盾点是：

- 传感器本身给的是 3D 点云
- 但主链第一步就把它压成了 2D
- 后面的地图、定位、导航、Web 全围绕 2D 假设设计

所以后面我们正式收敛成一句话：

> 不再把 `3D 点云 -> 2D scan -> 2D map` 当作系统主真值链路。

---

## 7. 我们不是直接乱改，而是先做了 Phase 0

这一轮非常重要，因为它决定了后面的大改不会失控。

### 7.1 Phase 0 的目标

不是马上宣称“3D 全改完”，而是先做三件事：

1. 把仓库里哪些地方硬编码依赖 2D 找出来
2. 把地图表示类型显式写进配置和模型里
3. 加一个迁移审计工具，避免改着改着又回去了

### 7.2 当时新增/确认的东西

- 3D 迁移计划文档：`src/a2_system/docs/three_d_migration_plan.md`
- 3D 迁移审计脚本：`src/a2_system/scripts/three_d_migration_audit.py`
- 各模块显式表示：
  - `primary_map_representation`
  - `localization_representation`
  - `navigation_representation`
  - `web_map_representation`

### 7.3 这一步的意义

这一步看起来“不炫”，但其实最重要。

因为如果不先冻结合同，后面会出现这种情况：

- 建图模块说自己是 3D
- Web 还是按 2D `/map` 读
- 定位还是默认 `/amcl_pose`
- 保存地图还是只认 `map.yaml`

那就是“嘴上 3D，骨子里还是 2D”。

---

## 8. 第一次真正的 3D-first 落地：先把 3D 资产纳入正式存图链

### 8.1 为什么不是一上来就换完整 3D SLAM

因为当时实际约束很硬：

- 前置雷达 `/unitree/slam_lidar/points1` 是真的可用
- rear `.21` 还离线
- Unitree 原生私有接口不稳定
- 没有一个马上能全量替代现网的成熟 3D SLAM 包已经在这台 A2 上稳定跑着

所以更稳的第一步不是“喊口号”，而是：

> 先让正式地图产物里出现 3D 真值资产。

### 8.2 这一轮我们做了什么

重点在 `map_manager` 和 Web 模型：

- `map_manager_node.py` 支持保存 3D 点云快照
- 地图 metadata 里记录 3D artifacts
- Web 后端 `SavedMapInfo` 能识别地图有没有 3D 资产
- 前端控制侧边栏能显示：
  - 3D asset
  - 3D topic
  - 3D points

### 8.3 这一轮的价值

这意味着哪怕主 runtime 还没完全 3D 化，我们至少已经做到：

- 保存地图时不只保存 2D `map.yaml`
- 还保存前雷达 3D 真值资产

这是后面继续接 3D viewer、3D localization、3D navigation 的地基。

---

## 9. Web 真正进入 3D：不是只显示标签，而是真的画 3D 点云

### 9.1 我们当时先确认了一个事实

原来的 Web 其实根本不会显示 3D。

旧页面本质是：

- 后端返回 `OccupancyGrid`
- 前端 `MapCanvas.tsx` 用 2D canvas 画格子

所以如果主链变成纯 3D，旧页面会直接“看不到地图”。

### 9.2 后来怎么做的

我们新增了 3D viewer 路径：

- 后端解析点云，生成采样后的点列表
- 前端新增 `PointCloudCanvas3D.tsx`
- 主界面优先显示点云视图
- 没有点云时才退回 2D `MapCanvas`

### 9.3 这一步很关键

从这一步开始，Web 终于不再只是“2D 结果图展示器”，而是真正开始看见 3D 点云。

但那时还有一个重大问题没解决：

> Web 看到的只是**实时点云**，还不是**累计 3D 地图**。

这就是后面继续深挖的起点。

---

## 10. 我们为什么后来发现“现在这个 3D 其实还是假的一半”

这个发现很关键。

### 10.1 用户现场现象

用户在页面上看到的是：

- Web 已经切成 3D 风格
- 页面上有点云
- 但点云只是机器人眼前一小团
- 让机器人再跑，图也没像真正地图那样增长

这说明系统可能只是把“当前一帧点云”显示在 Web 上，而不是在做累计建图。

### 10.2 我们怎么查出来的

这一轮重点看了三个地方：

1. `mapping.launch.py`
   看 3D 建图模式到底起了什么

2. `map_manager_node.py`
   看它保存的是不是累计地图

3. `ros_bridge.py` / Web 后端配置
   看前端吃的是不是原始点云 topic

### 10.3 最终查出来的真相

当时的 `front_lidar_pointcloud_3d` 路径其实是：

- launch 并没有真正起一个 mapper
- `map_manager` 只是拿到 latest pointcloud
- Web 默认也直接订阅原始 `/unitree/slam_lidar/points1`

所以页面上看到的只是：

> 实时点云预览

不是：

> 真实累计 3D 地图

这一步非常重要，因为它把“看起来是 3D”跟“真的在做 3D map accumulation”区分开了。

---

## 11. 我们尝试过直接接 Unitree 原生 3D 建图，但没成功

### 11.1 为什么会想到这条路

因为最理想的情况当然是：

- 机器人自带原生建图
- 我们直接吃它输出的 3D 地图
- 自己少造轮子

### 11.2 具体做了什么

我们尝试过：

- 检查 Unitree 原生 topic
- 查 `go2_web` / 内部 Python 接口
- 试图调用 native SLAM API
  - `1801` 开始建图
  - `1804` 初始位姿

### 11.3 最终结果

真实 A2 上返回的是：

- `1801 -> code=3203`
- 这是“API not implemented”

也就是说：

> 当前这台 A2 的实际固件/服务端，并没有把我们想调用的原生建图控制面真正开放出来。

所以这一条路不能作为当前主方案。

这时我们必须自己补一条可靠的 3D 主链。

---

## 12. 真正的关键改动：新增 `pointcloud_accumulator`

### 12.1 为什么一定要加这个节点

因为当时我们已经明确：

- 前置雷达是真实稳定输入
- 原生 3D 控制面不可依赖
- Web 不能只看“最新一帧”

所以必须有一个我们自己掌控的节点，负责：

- 订阅前置雷达点云
- 结合 `/odom`
- 把多帧点云累积到同一坐标系
- 发布一个真正的“累计 3D 地图 topic”

于是就有了：

```text
pointcloud_accumulator
```

### 12.2 这个节点到底干什么

它的逻辑可以简单理解成：

```text
/unitree/slam_lidar/points1 + /odom
  -> 过滤无效点
  -> 去掉机器人自己身体附近点
  -> 按体素降采样
  -> 按 odom 位姿把点变换到世界坐标
  -> 累积
  -> 发布 /a2/pointcloud_map_3d
```

### 12.3 这个节点最开始版本的不足

一开始 accumulator 只用了：

- x
- y
- yaw

也就是平面变换。

这样虽然比“只看一帧”强很多，但严格说还是不够 3D。

后面我们又继续升级成：

- 使用 `/odom` 的完整四元数姿态
- 使用完整 3D 位置

这样点云累积时不再只是假设机器人永远是二维平面姿态。

---

## 13. 3D 主链改造后，系统现在的真实数据流是什么

当前已经跑通的 3D mapping 主链是：

```text
/unitree/slam_lidar/points1
  -> pointcloud_accumulator
  -> /a2/pointcloud_map_3d
  -> ros_bridge
  -> Web PointCloudCanvas3D
```

地图保存链现在是：

```text
/a2/pointcloud_map_3d
  -> map_manager
  -> runtime/maps/<map_id>/pointcloud_map_3d.pcd
  -> metadata.yaml
```

当前 Web 上机器人位姿链是：

```text
Unitree SDK2
  -> a2_sdk_bridge
  -> /a2/raw_state
  -> a2_state_publisher
  -> /odom
  -> localization_gate / ros_bridge
  -> Web ROBOT marker
```

这意味着：

- 地图是真 3D 点云累计结果
- 机器人位置也在同一坐标系里显示
- Web 里的红色 ROBOT marker 不再是假的 UI 标记，而是实际 `/odom` 位姿

---

## 14. 一键启动为什么也要改

### 14.1 真实机器人上，一键脚本不是“锦上添花”，是系统边界

如果一键脚本做不好，会反复出现这些问题：

- 原生雷达服务没起稳就误判失败
- Web service 重启时把 ROS bringup 一起杀了
- 残留进程没清理干净
- 页面显示 ready，但底下没有实际节点

### 14.2 这次我们重点修了什么

`start_web_console_suite.sh` 做了几件关键修复：

1. 先清理干扰项
   包括旧 bringup、旧 Nav2、旧 2D 链、旧辅助进程。

2. 检查原生雷达 topic 的方式改了
   之前用：

```bash
ros2 topic echo --once
```

这在 PointCloud2 上会因为 QoS 或启动时机卡死。

后来改成：

- 先查 `ros2 topic info` 的 `Publisher count`
- 再用 `best_effort` 试图取样

这样更符合真实点云链路。

3. 启动后只让 Web 进入 standby
   不直接替用户开建图/导航，而是让用户在页面上点。

### 14.3 最终一键入口

当前 A2 上的正确命令是：

```bash
/home/unitree/a2_system_ws/install/a2_system/share/a2_system/start_3d_web_console_suite.sh --iface eth0
```

启动成功后，访问：

```text
http://192.168.31.49:8080/
```

---

## 15. 我们在 A2 上最后验证了什么

### 15.1 先验证建图模式真正起的是哪个链

不是只看“按钮点了”，而是看：

- `mapping_profile`
- 进程列表
- topic 列表
- Web snapshot

最后验证结果是：

- `mapping_profile=front_lidar_pointcloud_3d`
- `map_source=running`
- `pointcloud_accumulator` 在跑
- `/a2/pointcloud_map_3d` 有 publisher

### 15.2 验证 3D 地图 topic

实际验证到：

- `/a2/pointcloud_map_3d`
- 发布频率 `2.0 Hz`
- `frame_id=odom`

### 15.3 验证 Web snapshot

实际验证到：

- `pointcloud.loaded = true`
- `pointcloud.source_topic = /a2/pointcloud_map_3d`
- `pose.available = true`
- `pose.frame_id = odom`
- `map_received = true`
- `pose_received = true`

### 15.4 验证保存 3D-only 地图

我们保存了 smoke map，例如：

- `three_d_accum_smoke_180341`
- `three_d_quat_accum_smoke_180626`

保存结果是：

- `map_yaml = null`
- `representation = pointcloud_map_3d`
- artifact 是：
  - `pointcloud_map_3d.pcd`

这一步非常重要，因为它说明：

> 地图保存链已经不再依赖 2D `map.yaml`

---

## 16. 现在这条链到底算不算“3D 建图完成”

要严格说，答案是：

### 16.1 已完成的部分

已经完成的是：

- 真实前置雷达输入
- 自有 3D 地图累计节点
- Web 3D viewer
- 机器人位姿在 3D 视图中显示
- 3D-only 地图保存
- 一键启动和 Web standby 跑通

### 16.2 还没完成的部分

还没完成的是：

- 完整 loop-closure 3D SLAM
- 真正基于 3D map 的全局重定位
- 真正基于 3D map 的全局/局部规划器
- 工业级闭环精度验证

### 16.3 当前最准确的工程说法

当前系统不是“完整 3D 自主导航已经工业闭环”，而是：

> 我们已经把真实机器人主建图链从 2D 栅格真值，推进到 3D 点云真值；Web、保存链和启动链都已经跟着切过去了。

这句话是准确的。

---

## 17. 新手现在应该怎么理解整套系统

你可以把当前系统分成四层。

### 17.1 传感器层

- 前置雷达：`/unitree/slam_lidar/points1`
- 机器人状态/里程计：`/odom`

### 17.2 地图层

- 老 2D 路线：
  - `/scan -> slam_toolbox -> /map`
- 现在的 3D 主路线：
  - `pointcloud_accumulator -> /a2/pointcloud_map_3d`

### 17.3 Web 层

- 旧页面：只会画 2D occupancy grid
- 新页面：优先显示 3D 点云

### 17.4 控制层

当前 3D-first 控制合同更多是：

- 3D 点云做地图真值
- 机器人位姿用 `/odom`
- 目标入口走 `pose_topic_3d` / `/goal_pose_`

但这一层还不是完整 3D planner。

---

## 18. 新人第一次上手机器，应该按什么顺序做

### 18.1 第一步：只起 Web standby，不直接起建图

在 A2 上：

```bash
/home/unitree/a2_system_ws/install/a2_system/share/a2_system/start_3d_web_console_suite.sh --iface eth0
```

确认页面能打开：

```text
http://192.168.31.49:8080/
```

### 18.2 第二步：看 Web 是否已经有基础状态

至少要看：

- backend connected
- ros thread alive
- pose 是否可用
- 节点状态不要全空

### 18.3 第三步：点“建图模式”

点击后不要只看按钮颜色，要看：

- 节点状态里 `map source` 是否 running
- `map_manager` 是否 running
- 页面中央是不是开始出现 3D 点云
- 机器人 marker 是否在点云里合理位置

### 18.4 第四步：用命令确认 3D 主链确实在跑

在 A2 上：

```bash
source /opt/ros/humble/setup.bash
source /home/unitree/a2_system_ws/install/setup.bash

ros2 topic info /a2/pointcloud_map_3d
timeout 6s ros2 topic hz /a2/pointcloud_map_3d
curl -sS http://127.0.0.1:8080/api/snapshot | jq '{pc:.pointcloud, pose:.pose, health:.health}'
```

### 18.5 第五步：真的移动机器人，再观察点数和地图增长

这一步非常重要。

当前 accumulator 设计里，机器人不动时不会一直把同一帧重复累积。

所以如果你站着不动，看到点数不增长，不代表它坏了。

它需要：

- 平移超过阈值
- 或旋转超过阈值

才会继续把新视角累积进去。

---

## 19. 现在最容易误解的几个点

### 19.1 “Web 有点云”不等于“已经有地图”

如果只是原始实时点云，那只是“看见当前视野”。

必须是：

- 来自 `/a2/pointcloud_map_3d`
- 而不是 `/unitree/slam_lidar/points1`

才说明看的是累计图。

### 19.2 “保存成功”不等于“可用于高精度导航”

现在保存的 `.pcd` 是真实 3D 地图资产，但它还没有自动接入完整 3D localization/planner 闭环。

### 19.3 “3D-first”不等于“什么都已经完全摆脱 2D”

当前仓库里仍然保留了一些 2D 兼容代码和文档，例如：

- `nav2_stack.yaml`
- 一些旧的 AMCL/`/map` 兼容逻辑

但现在这些应该被理解为：

> fallback / compatibility

而不是系统主真值。

---

## 20. 这次迁移中最关键的文件有哪些

如果你要继续接手，先看这些文件。

### 20.1 启动与模式控制

- `src/a2_bringup/launch/mapping.launch.py`
- `src/a2_system/tools/start_web_console_suite.sh`
- `src/a2_system/tools/start_3d_web_console_suite.sh`

### 20.2 3D 地图主链

- `src/map_manager/map_manager/pointcloud_accumulator.py`
- `src/a2_system/config/pointcloud_accumulator.yaml`
- `src/map_manager/map_manager/map_manager_node.py`
- `src/a2_system/config/map_manager.yaml`

### 20.3 3D 表示与模式契约

- `src/a2_system/config/slam.yaml`
- `src/a2_system/scripts/three_d_migration_audit.py`
- `src/a2_system/docs/three_d_migration_plan.md`

### 20.4 Web 后端

- `web_console/backend/ros_bridge.py`
- `web_console/backend/stack_control.py`
- `web_console/backend/main.py`
- `web_console/backend/models.py`
- `web_console/backend/config.py`

### 20.5 Web 前端

- `web_console/frontend/src/App.tsx`
- `web_console/frontend/src/components/PointCloudCanvas3D.tsx`
- `web_console/frontend/src/components/ControlSidebar.tsx`
- `web_console/frontend/src/types.ts`

---

## 21. 现在最现实的后续路线是什么

### 21.1 第一阶段：把“3D 累积图”继续做稳

优先做：

- 实机慢速绕行测试
- 观察地图是否明显扭曲
- 调整 accumulator 参数：
  - `voxel_size`
  - `min_translation_delta_m`
  - `min_yaw_delta_rad`
  - `max_range_m`
  - `body_exclusion_*`

### 21.2 第二阶段：接真正的 3D localization

当前定位更多依赖 `/odom`。

后面如果要继续往工业闭环走，必须引入：

- 真正对保存 3D 地图做重定位的后端

### 21.3 第三阶段：再谈完整 3D navigation

也就是：

- 不只是 3D 地图显示
- 不只是 3D pose goal
- 而是完整 3D planner / controller / failure feedback

这是后续更大一阶段工作。

---

## 22. 一句话总结这次 2D->3D 调试过程

如果要把这次对话浓缩成一句工程总结，就是：

> 我们先把旧 2D 链路和真实机器人启动边界摸清，再确认“当前所谓 3D 其实只是实时点云预览”，随后自己补了一条受控的 3D 累积地图主链，把 Web、保存链和一键启动一起切过去，最终让 A2 真实前置雷达能够在网页中实时显示累计 3D 地图，并保存为 3D-only PCD 资产。

这就是这次迁移的核心价值。

---

## 23. 附：当前最常用命令

### 23.1 启动 3D Web 控制台待机

```bash
/home/unitree/a2_system_ws/install/a2_system/share/a2_system/start_3d_web_console_suite.sh --iface eth0
```

### 23.2 查看 Web 栈状态

```bash
curl -sS http://127.0.0.1:8080/api/stack/status | jq
```

### 23.3 启动建图模式

```bash
curl -sS -X POST http://127.0.0.1:8080/api/stack/start-mapping | jq
```

### 23.4 停止当前栈

```bash
curl -sS -X POST http://127.0.0.1:8080/api/stack/stop | jq
```

### 23.5 查看 3D 地图 topic

```bash
source /opt/ros/humble/setup.bash
source /home/unitree/a2_system_ws/install/setup.bash

ros2 topic info /a2/pointcloud_map_3d
timeout 6s ros2 topic hz /a2/pointcloud_map_3d
```

### 23.6 保存当前 3D 地图

```bash
curl -sS -X POST http://127.0.0.1:8080/api/maps/save \
  -H "Content-Type: application/json" \
  -d '{"map_id":"my_3d_map"}' | jq
```

### 23.7 查看当前 Web snapshot

```bash
curl -sS http://127.0.0.1:8080/api/snapshot | jq
```

---

## 24. 最后的建议

如果你是第一次接这个项目，不要一上来就试图“直接做完整 3D 自主导航”。

正确顺序应该是：

1. 先确认一键启动、干扰进程清理、Web standby 都稳
2. 再确认 `/a2/pointcloud_map_3d` 是真实累计图，不是原始单帧
3. 再让机器人慢速移动，验证累计图质量
4. 再去接 3D localization
5. 最后才是完整 3D navigation 闭环

这样做，系统是可验证、可回退、可继续接手的。
# Historical Debug Journey

This file is a historical debugging journal that records the transition from older front-lidar and 2D assumptions into the current JT128-first stack. It is not the current contract or launch guide.
