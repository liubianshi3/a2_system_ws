# Single Goal Accuracy Summary

- data_source: `mock_navigation_test`
- THIS_IS_MOCK_DATA

Goal: `(1.000, 0.500, yaw=0.000)` in frame `map`

- repeats: `5`
- backend_success_rate: `5/5`
- runner_arrival_success_rate: `0/5`
- timeout_count: `0`

| Metric | mean | min | max | std |
|---|---:|---:|---:|---:|
| `final_error_tf_map_base_link` | 0.2406 | 0.2286 | 0.2594 | 0.0121 |
| `final_error_tf_map_base_footprint` | 0.2406 | 0.2286 | 0.2594 | 0.0121 |
| `final_error_amcl` | 0.2406 | 0.2279 | 0.2593 | 0.0123 |
| `final_error_odom` | 0.2406 | 0.2286 | 0.2594 | 0.0121 |
| `yaw_error_tf_map_base_link` | 0.0011 | 0.0002 | 0.0017 | 0.0005 |

## Runtime Tolerances

- controller_server.xy_goal_tolerance(runtime): `0.2500`
- controller_server.yaw_goal_tolerance(runtime): `0.0800`
- pose_goal_controller_3d.goal_tolerance_xy(runtime): ``
- runner_arrival_tolerance: `0.200`
