# Static Pose Accuracy Summary

Sampling window: `1.0` sec at `5.0` Hz

| Source | x_std | y_std | yaw_std | jump_detected |
|---|---:|---:|---:|---|
| `amcl` |  |  |  | False |
| `odom` |  |  |  | False |
| `tf_map_base` |  |  |  | False |
| `tf_odom_base` |  |  |  | False |

## Interpretation

- If `tf_map_base` or `amcl` standard deviation approaches 0.10 m, localization itself can explain large final error.
- If `odom` is stable but `map`-based sources jump, suspect localization or frame correction rather than controller stopping.
- If all pose sources are stable while final stop error is large, controller or execution layer becomes the stronger suspect.
