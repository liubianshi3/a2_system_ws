# Single Goal Accuracy Summary

- data_source: `mock_navigation_test`
- THIS_IS_MOCK_DATA

Goal: `(1.000, 0.500, yaw=0.000)` in frame `map`

- repeats: `5`
- backend_success_rate: `0/5`
- runner_arrival_success_rate: `5/5`
- timeout_count: `0`

| Metric | mean | min | max | std |
|---|---:|---:|---:|---:|
| `final_error_tf_map_base_link` | 0.2975 | 0.2860 | 0.3107 | 0.0088 |
| `final_error_tf_map_base_footprint` | 0.2975 | 0.2860 | 0.3107 | 0.0088 |
| `final_error_amcl` | 0.2974 | 0.2862 | 0.3104 | 0.0085 |
| `final_error_odom` | 0.2975 | 0.2860 | 0.3107 | 0.0088 |
| `yaw_error_tf_map_base_link` | 0.0016 | 0.0004 | 0.0028 | 0.0010 |

## Runtime Tolerances

- controller_server.xy_goal_tolerance(runtime): `0.0600`
- controller_server.yaw_goal_tolerance(runtime): `0.0800`
- pose_goal_controller_3d.goal_tolerance_xy(runtime): ``
- runner_arrival_tolerance: `0.350`
