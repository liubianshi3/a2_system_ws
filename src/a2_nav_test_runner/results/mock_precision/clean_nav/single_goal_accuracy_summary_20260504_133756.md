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
| `final_error_tf_map_base_link` | 0.0457 | 0.0398 | 0.0584 | 0.0069 |
| `final_error_tf_map_base_footprint` |  |  |  |  |
| `final_error_amcl` | 0.0449 | 0.0393 | 0.0555 | 0.0061 |
| `final_error_odom` | 0.0457 | 0.0398 | 0.0584 | 0.0069 |
| `yaw_error_tf_map_base_link` | 0.0027 | 0.0019 | 0.0035 | 0.0006 |

## Runtime Tolerances

- controller_server.xy_goal_tolerance(runtime): `0.0600`
- controller_server.yaw_goal_tolerance(runtime): `0.0800`
- pose_goal_controller_3d.goal_tolerance_xy(runtime): ``
- runner_arrival_tolerance: `0.200`
