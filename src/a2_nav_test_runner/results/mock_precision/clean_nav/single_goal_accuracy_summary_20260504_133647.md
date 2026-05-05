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
| `final_error_tf_map_base_link` | 0.0581 | 0.0447 | 0.0693 | 0.0086 |
| `final_error_tf_map_base_footprint` |  |  |  |  |
| `final_error_amcl` | 0.0578 | 0.0449 | 0.0687 | 0.0089 |
| `final_error_odom` | 0.0581 | 0.0447 | 0.0693 | 0.0086 |
| `yaw_error_tf_map_base_link` | 0.0018 | 0.0002 | 0.0039 | 0.0013 |

## Runtime Tolerances

- controller_server.xy_goal_tolerance(runtime): `0.0600`
- controller_server.yaw_goal_tolerance(runtime): `0.0800`
- pose_goal_controller_3d.goal_tolerance_xy(runtime): ``
- runner_arrival_tolerance: `0.200`
