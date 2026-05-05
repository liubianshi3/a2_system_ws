# Static Pose Accuracy Summary

- data_source: `mock_navigation_test`
- THIS_IS_MOCK_DATA

Sampling window: `2.0` sec at `5.0` Hz

| Source | x_std | y_std | yaw_std | jump_detected |
|---|---:|---:|---:|---|
| `amcl` | 0.0032 | 0.0069 | 0.0015 | False |
| `odom` | 0.0000 | 0.0000 | 0.0000 | False |
| `tf_map_base` | 0.0080 | 0.0061 | 0.0015 | False |
| `tf_odom_base` | 0.0000 | 0.0000 | 0.0000 | False |

## Interpretation

- If `tf_map_base` or `amcl` standard deviation approaches 0.10 m, localization itself can explain large final error.
- If `odom` is stable but `map`-based sources jump, suspect localization or frame correction rather than controller stopping.
- If all pose sources are stable while final stop error is large, controller or execution layer becomes the stronger suspect.
