# Navigation Precision Root Cause Report

- data_source: `mock_navigation_test`
- THIS_IS_MOCK_DATA

- Conclusion: `NEED_LOCALIZATION_FIX`
- Primary root cause: `localization_instability`

## 1. Runtime Navigation Chain

- backend_candidate: `nav2_action`

## 2. Runtime Tolerance Parameters

- No runtime parameter summary was available.

## 3. Static Config vs Runtime

- Static scan report was not available.

## 4. Single Goal Repeat Statistics

- count: `5`
- backend_success_rate: `1.0000`
- runner_arrival_success_rate: `0.4000`
- mean_final_error_tf_map_base_link: `0.2126`
- mean_final_error_tf_map_base_footprint: `0.2126`
- max_final_error_tf_map_base_link: `0.4020`
- std_final_error_tf_map_base_link: `0.1126`

## 5. Static Pose Stability

- tf_map_base_x_std: `0.2278`
- tf_map_base_y_std: `0.1622`
- amcl_x_std: `0.2003`
- amcl_y_std: `0.1472`
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

- Primary suspect from current evidence: `localization_instability`.

## 8. Evidence-Based Recommendations

- Improve localization stability before tuning controller stop behavior.
- Repeat static pose recording after localization changes.

## 9. Do Not Adjust Yet

- Do not blame PADS or task scheduling before navigation precision is understood.
- Do not write mock or diagnosis-only outputs as real robot experiment results.
- Do not tune runner arrival tolerance alone and claim navigation improved.

## 10. PADS Readiness

- Do not connect PADS yet.
- Fix navigation precision first so scheduling results are not confounded by backend error.

## 11. Conclusion Reasons

- Static pose jitter is already large enough to hurt final stop precision.
