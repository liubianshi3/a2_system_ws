# Runtime Parameter Summary

Runtime values take precedence over static YAML when diagnosing navigation precision.
- data_source: `mock_navigation_test`
- THIS_IS_MOCK_DATA

| Node | Parameter name | Runtime value | Possible impact |
|---|---|---:|---|
| `/controller_server` | `FollowPath.xy_goal_tolerance` | `0.06` | Directly affects when navigation is considered close enough to goal. |
| `/controller_server` | `general_goal_checker.plugin` | `nav2_controller::SimpleGoalChecker` | Determines which goal checker plugin actually decides arrival. |
| `/controller_server` | `general_goal_checker.xy_goal_tolerance` | `0.06` | Directly affects when navigation is considered close enough to goal. |
| `/controller_server` | `general_goal_checker.yaw_goal_tolerance` | `0.08` | Directly affects when navigation is considered close enough to goal. |
| `/controller_server` | `global_costmap.global_costmap.robot_base_frame` | `base_link` | Frame mismatch here can create systematic pose comparison errors. |
| `/controller_server` | `local_costmap.local_costmap.robot_base_frame` | `base_link` | Frame mismatch here can create systematic pose comparison errors. |
