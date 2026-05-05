# Single Goal Accuracy Summary

- data_source: `mock_navigation_test`
- THIS_IS_MOCK_DATA

Goal: `(1.000, 0.500, yaw=0.000)` in frame `map`

- repeats: `5`
- backend_success_rate: `5/5`
- runner_arrival_success_rate: `2/5`
- timeout_count: `0`

| Metric | mean | min | max | std |
|---|---:|---:|---:|---:|
| `final_error_tf_map_base_link` | 0.2126 | 0.0856 | 0.4020 | 0.1126 |
| `final_error_tf_map_base_footprint` | 0.2126 | 0.0856 | 0.4020 | 0.1126 |
| `final_error_amcl` | 0.2024 | 0.0616 | 0.3951 | 0.1224 |
| `final_error_odom` | 0.2126 | 0.0856 | 0.4020 | 0.1126 |
| `yaw_error_tf_map_base_link` | 0.0335 | 0.0086 | 0.0764 | 0.0243 |

## Runtime Tolerances

- controller_server.xy_goal_tolerance(runtime): `0.0600`
- controller_server.yaw_goal_tolerance(runtime): `0.0800`
- pose_goal_controller_3d.goal_tolerance_xy(runtime): ``
- runner_arrival_tolerance: `0.200`
