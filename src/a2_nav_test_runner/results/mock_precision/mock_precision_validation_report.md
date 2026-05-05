# Mock Precision Validation Report

- THIS_IS_MOCK_DATA
- data_source: `mock_navigation_test`

| 场景 | 注入问题 | 期望根因 | Analyzer 输出 | 是否匹配 | 备注 |
|---|---|---|---|---|---|
| `clean_nav` | 正常导航，误差小 | `PASS_NAV_FOR_PADS` | `PASS_NAV_FOR_PADS` | True |  |
| `tolerance_025` | 模拟运行时到达容差为 0.25 m | `goal_tolerance_too_large` | `goal_tolerance_too_large` | True |  |
| `runner_tolerance_issue` | runner arrival_tolerance 过大 | `runner_arrival_tolerance` | `runner_arrival_tolerance` | True |  |
| `localization_noise` | 静止定位抖动大 | `localization_instability` | `localization_instability` | True |  |
| `tf_offset` | base_link 存在固定 TF 偏移 | `tf_or_base_frame_offset` | `tf_or_base_frame_offset` | True |  |
| `controller_stop_error` | 定位稳定但最终停不准 | `controller_or_execution_stop_error` | `controller_or_execution_stop_error` | True |  |
