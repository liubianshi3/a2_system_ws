# Navigation Precision Root Cause Report

- data_source: `mock_navigation_test`
- THIS_IS_MOCK_DATA

- Conclusion: `NEED_FRAME_FIX`
- Primary root cause: `tf_or_base_frame_offset`

## 1. Runtime Navigation Chain

- backend_candidate: `a2_navcommand`

## 2. Runtime Tolerance Parameters

- `/controller_server` | `FollowPath.xy_goal_tolerance` | `0.06` | Directly affects when navigation is considered close enough to goal.
- `/controller_server` | `general_goal_checker.plugin` | `nav2_controller::SimpleGoalChecker` | Determines which goal checker plugin actually decides arrival.
- `/controller_server` | `general_goal_checker.xy_goal_tolerance` | `0.06` | Directly affects when navigation is considered close enough to goal.
- `/controller_server` | `general_goal_checker.yaw_goal_tolerance` | `0.08` | Directly affects when navigation is considered close enough to goal.

## 3. Static Config vs Runtime

- Static scan report was not available.

## 4. Single Goal Repeat Statistics

- count: `5`
- backend_success_rate: `1.0000`
- runner_arrival_success_rate: `1.0000`
- mean_final_error_tf_map_base_link: `0.0485`
- mean_final_error_tf_map_base_footprint: ``
- max_final_error_tf_map_base_link: `0.0529`
- std_final_error_tf_map_base_link: `0.0027`

## 5. Static Pose Stability

- tf_map_base_x_std: `0.0079`
- tf_map_base_y_std: `0.0072`
- amcl_x_std: `0.0057`
- amcl_y_std: `0.0022`
- odom_x_std: `0.0000`
- odom_y_std: `0.0000`

## 6. TF Stability

- `base_link->base_footprint` available_count=0 error_count=3
- `base_link->imu_link` available_count=3 error_count=0
- `base_link->lidar` available_count=0 error_count=3
- `map->base_footprint` available_count=0 error_count=3
- `map->base_link` available_count=2 error_count=1
- `map->odom` available_count=2 error_count=1
- `odom->base_link` available_count=2 error_count=1

## 7. Top 5 Suspects

- Primary suspect from current evidence: `tf_or_base_frame_offset`.
- TF chain inconsistency or missing transforms can distort final-error calculation.

## 8. Evidence-Based Recommendations

- Verify base_link vs base_footprint offset and goal comparison frame.
- Recompute final error in the correct frame before controller tuning.

## 9. Do Not Adjust Yet

- Do not blame PADS or task scheduling before navigation precision is understood.
- Do not write mock or diagnosis-only outputs as real robot experiment results.
- Do not tune runner arrival tolerance alone and claim navigation improved.

## 10. PADS Readiness

- Do not connect PADS yet.
- Fix navigation precision first so scheduling results are not confounded by backend error.

## 11. Conclusion Reasons

- TF lookups showed missing edges or repeated errors.
