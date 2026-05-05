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
| `final_error_tf_map_base_link` | 0.0088 | 0.0009 | 0.0143 | 0.0044 |
| `final_error_tf_map_base_footprint` | 0.2525 | 0.2444 | 0.2611 | 0.0059 |
| `final_error_amcl` | 0.0084 | 0.0013 | 0.0141 | 0.0042 |
| `final_error_odom` | 0.0088 | 0.0009 | 0.0143 | 0.0044 |
| `yaw_error_tf_map_base_link` | 0.0006 | 0.0002 | 0.0011 | 0.0003 |

## Runtime Tolerances

- controller_server.xy_goal_tolerance(runtime): `0.0600`
- controller_server.yaw_goal_tolerance(runtime): `0.0800`
- pose_goal_controller_3d.goal_tolerance_xy(runtime): ``
- runner_arrival_tolerance: `0.200`
