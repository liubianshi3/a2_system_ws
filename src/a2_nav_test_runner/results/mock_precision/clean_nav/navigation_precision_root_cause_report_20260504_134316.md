# Navigation Precision Root Cause Report

- data_source: `mock_navigation_test`
- THIS_IS_MOCK_DATA

- Conclusion: `PASS_NAV_FOR_PADS`
- Primary root cause: `clean_navigation`

## 1. Runtime Navigation Chain

- backend_candidate: `nav2_action`

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
- mean_final_error_tf_map_base_link: `0.0507`
- mean_final_error_tf_map_base_footprint: `0.0507`
- max_final_error_tf_map_base_link: `0.0657`
- std_final_error_tf_map_base_link: `0.0102`

## 5. Static Pose Stability

- tf_map_base_x_std: `0.0018`
- tf_map_base_y_std: `0.0105`
- amcl_x_std: `0.0151`
- amcl_y_std: `0.0015`
- odom_x_std: `0.0000`
- odom_y_std: `0.0000`

## 6. TF Stability

- `base_link->base_footprint` available_count=7 error_count=0
- `base_link->imu_link` available_count=7 error_count=0
- `base_link->lidar` available_count=7 error_count=0
- `map->base_footprint` available_count=6 error_count=1
- `map->base_link` available_count=6 error_count=1
- `map->odom` available_count=6 error_count=1
- `odom->base_link` available_count=6 error_count=1

## 7. Top 5 Suspects

- Primary suspect from current evidence: `clean_navigation`.

## 8. Evidence-Based Recommendations

- Collect more runtime evidence.

## 9. Do Not Adjust Yet

- Do not blame PADS or task scheduling before navigation precision is understood.
- Do not write mock or diagnosis-only outputs as real robot experiment results.
- Do not tune runner arrival tolerance alone and claim navigation improved.

## 10. PADS Readiness

- Navigation precision looks acceptable for the first PADS handoff step.

## 11. Conclusion Reasons

- Single-goal success and final-error bounds are already acceptable for PADS handoff.
