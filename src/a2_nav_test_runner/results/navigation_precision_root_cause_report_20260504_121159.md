# Navigation Precision Root Cause Report

- Conclusion: `NEED_BACKEND_CLARIFICATION`

## 1. Runtime Navigation Chain

- backend_candidate: `unknown`

## 2. Runtime Tolerance Parameters

- No runtime parameter summary was available.

## 3. Static Config vs Runtime

- | `controller_server.general_goal_checker.xy_goal_tolerance` | `0.06` | `src/a2_system/config/nav2_stack.yaml:85` |
- | `controller_server.general_goal_checker.yaw_goal_tolerance` | `0.08` | `src/a2_system/config/nav2_stack.yaml:86` |
- | `controller_server.FollowPath.xy_goal_tolerance` | `0.06` | `src/a2_system/config/nav2_stack.yaml:111` |
- | `pose_goal_controller_3d.goal_tolerance_xy` | `0.15` | `src/a2_system/config/pose_goal_controller_3d.yaml:21` |
- | `a2_nav_test_runner.arrival_tolerance` | `0.35` | `src/a2_nav_test_runner/config/nav_test_config.yaml:25` |
- 1. The repository does **not** support the claim that the robot is simply using Nav2 default `xy_goal_tolerance = 0.25 m`.
- 4. The test runner `arrival_tolerance = 0.35 m` is only a **program-side arrival check**, not proof of backend stop precision.
- - `controller_server.general_goal_checker.xy_goal_tolerance`
- - `controller_server.general_goal_checker.yaw_goal_tolerance`
- - `pose_goal_controller_3d.goal_tolerance_xy`

## 4. Single Goal Repeat Statistics

- No single-goal accuracy CSV was available.

## 5. Static Pose Stability

- tf_map_base_x_std: ``
- tf_map_base_y_std: ``
- amcl_x_std: ``
- amcl_y_std: ``
- odom_x_std: ``
- odom_y_std: ``

## 6. TF Stability

- `base_link->base_footprint` available_count=0 error_count=1
- `base_link->imu_link` available_count=0 error_count=1
- `base_link->lidar` available_count=0 error_count=1
- `map->base_footprint` available_count=0 error_count=1
- `map->base_link` available_count=0 error_count=1
- `map->odom` available_count=0 error_count=1
- `odom->base_link` available_count=0 error_count=1

## 7. Top 5 Suspects

- TF chain inconsistency or missing transforms can distort final-error calculation.

## 8. Evidence-Based Recommendations

- First confirm runtime tolerances instead of assuming static YAML was loaded.
- Compare `backend_success` against TF-map final error on the same repeated goal.
- Fix TF availability and frame consistency before trusting any final-error statistic.

## 9. Do Not Adjust Yet

- Do not blame PADS or task scheduling before single-goal navigation precision is understood.
- Do not tune runner `arrival_tolerance` alone and then treat that as a navigation improvement.
- Do not compare map-frame goals against odom-frame pose without a validated transform path.

## 10. PADS Readiness

- Do not connect PADS yet.
- Fix navigation precision first so scheduling experiments are not confounded by backend stop error.
- Single-goal repeat data is missing, so there is no reliable precision baseline yet.
- TF diagnosis still shows unresolved issues that would contaminate task-level evaluation.

## 11. Conclusion Reasons

- Runtime backend is still unclear.
