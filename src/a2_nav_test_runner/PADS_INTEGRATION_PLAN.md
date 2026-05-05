# PADS 接入 A2 导航测试 Runner 计划

## 1. 当前阶段

当前阶段目标是完成 A2 导航稳定性测试工具：

- 检测运行态接口；
- 测试单个导航目标；
- 测试固定多点序列；
- 记录真实导航 log 和 summary。

当前阶段不执行 PADS 真机调度实验，也不生成 PADS 真机结果。

## 2. 下一阶段目标

下一阶段才接入 PADS 调度器：

- `AStarOnly`
- `Greedy-PADS`
- `RH-PADS-L`
- 后续可扩展 `A-RH-PADS-L`

真机阶段优先接入 `RH-PADS-L`，因为它计算量更小，更适合安全测试起步。

## 3. 接入方式

建议的软件链路：

```text
任务列表 -> PADS 调度器 -> next_task -> A2NavClient.send_goal() -> Nav2/NavCommand -> logger
```

其中：

- PADS 大脑只决定下一任务；
- A2NavClient 只负责把目标发给底层导航；
- logger 只记录真实导航接口返回；
- 任何 dry run 都不能写成真实实验结果。

## 4. 未来模块建议

后续可新增：

- `a2_pads_task_runner.py`
- `pads_task_loader.py`
- `pads_method_adapter.py`
- `pads_experiment_logger.py`

这些模块当前不实现真实调度运行，避免在没有真机数据时误生成实验结果。

## 5. 真机实验阶段设计

建议分阶段推进：

1. 固定单点 P1 测试；
2. 固定多点 P1-P5 测试；
3. `AStarOnly` 调度测试；
4. `Greedy-PADS` 调度测试；
5. `RH-PADS-L` 调度测试；
6. 异常任务插入测试；
7. 汇总真实 log/summary；
8. 做统计分析。

## 6. 论文可用数据边界

只有满足以下条件的数据才可写入论文：

- A2 真机启动；
- 真实 ROS2 导航接口可用；
- 真实发送目标；
- action/service 返回真实状态；
- log/summary 自动生成；
- CSV 未被人工修改。

以下内容不能写入论文实机结果：

- 代码框架；
- 接口 dry check；
- 手工构造 CSV；
- 未连接真机的模拟运行；
- 未确认到达反馈的 service 调用成功。
