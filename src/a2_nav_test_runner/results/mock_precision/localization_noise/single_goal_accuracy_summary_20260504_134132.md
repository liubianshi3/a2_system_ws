# Single Goal Accuracy Summary

- data_source: `mock_navigation_test`
- THIS_IS_MOCK_DATA

Goal: `(1.000, 0.500, yaw=0.000)` in frame `map`

- repeats: `5`
- backend_success_rate: `5/5`
- runner_arrival_success_rate: `3/5`
- timeout_count: `0`

| Metric | mean | min | max | std |
|---|---:|---:|---:|---:|
| `final_error_tf_map_base_link` | 0.1882 | 0.0409 | 0.3227 | 0.1118 |
| `final_error_tf_map_base_footprint` | 0.1882 | 0.0409 | 0.3227 | 0.1118 |
| `final_error_amcl` | 0.1873 | 0.0459 | 0.3233 | 0.1038 |
| `final_error_odom` | 0.1882 | 0.0409 | 0.3227 | 0.1118 |
| `yaw_error_tf_map_base_link` | 0.0278 | 0.0043 | 0.0505 | 0.0178 |

## Runtime Tolerances

- controller_server.xy_goal_tolerance(runtime): `0.0600`
- controller_server.yaw_goal_tolerance(runtime): `0.0800`
- pose_goal_controller_3d.goal_tolerance_xy(runtime): ``
- runner_arrival_tolerance: `0.200`
