# Single Goal Accuracy Summary

- data_source: `mock_navigation_test`
- THIS_IS_MOCK_DATA

Goal: `(1.000, 0.500, yaw=0.000)` in frame `map`

- repeats: `5`
- backend_success_rate: `5/5`
- runner_arrival_success_rate: `5/5`
- timeout_count: `0`

| Metric | mean | min | max | std |
|---|---:|---:|---:|---:|
| `final_error_tf_map_base_link` | 0.0143 | 0.0036 | 0.0232 | 0.0065 |
| `final_error_tf_map_base_footprint` | 0.2548 | 0.2499 | 0.2627 | 0.0045 |
| `final_error_amcl` | 0.0137 | 0.0025 | 0.0231 | 0.0067 |
| `final_error_odom` | 0.0143 | 0.0036 | 0.0232 | 0.0065 |
| `yaw_error_tf_map_base_link` | 0.0007 | 0.0001 | 0.0013 | 0.0005 |

## Runtime Tolerances

- controller_server.xy_goal_tolerance(runtime): `0.0600`
- controller_server.yaw_goal_tolerance(runtime): `0.0800`
- pose_goal_controller_3d.goal_tolerance_xy(runtime): ``
- runner_arrival_tolerance: `0.200`
