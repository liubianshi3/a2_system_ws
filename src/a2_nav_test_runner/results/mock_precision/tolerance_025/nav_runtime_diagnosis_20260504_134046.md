# Navigation Runtime Diagnosis

This report is a runtime interface diagnosis. It is not a navigation experiment result.
- data_source: `mock_navigation_test`
- THIS_IS_MOCK_DATA

- backend_candidate: `nav2_action`

## Evidence

- `/navigate_to_pose` action is available and `controller_server` is running.

## Nodes

- `/amcl`
- `/controller_server`
- `/task_manager`
- `/nav_runtime_diagnosis`
- `/mock_precision_scenario_runner`

## Topics

- `/amcl_pose`
- `/map`
- `/mock_nav/goal`
- `/navigate_to_pose/_action/feedback`
- `/navigate_to_pose/_action/status`
- `/odom`
- `/parameter_events`
- `/rosout`
- `/tf`
- `/tf_static`

## Actions

- No ROS2 actions were visible.

## Services

- `/a2/task_manager/command`
- `/amcl/describe_parameters`
- `/amcl/get_parameter_types`
- `/amcl/get_parameters`
- `/amcl/list_parameters`
- `/amcl/set_parameters`
- `/amcl/set_parameters_atomically`
- `/controller_server/describe_parameters`
- `/controller_server/get_parameter_types`
- `/controller_server/get_parameters`
- `/controller_server/list_parameters`
- `/controller_server/set_parameters`
- `/controller_server/set_parameters_atomically`
- `/mock_precision_scenario_runner/describe_parameters`
- `/mock_precision_scenario_runner/get_parameter_types`
- `/mock_precision_scenario_runner/get_parameters`
- `/mock_precision_scenario_runner/list_parameters`
- `/mock_precision_scenario_runner/set_parameters`
- `/mock_precision_scenario_runner/set_parameters_atomically`
- `/nav_runtime_diagnosis/describe_parameters`
- `/nav_runtime_diagnosis/get_parameter_types`
- `/nav_runtime_diagnosis/get_parameters`
- `/nav_runtime_diagnosis/list_parameters`
- `/nav_runtime_diagnosis/set_parameters`
- `/nav_runtime_diagnosis/set_parameters_atomically`
- `/navigate_to_pose/_action/cancel_goal`
- `/navigate_to_pose/_action/get_result`
- `/navigate_to_pose/_action/send_goal`
- `/task_manager/describe_parameters`
- `/task_manager/get_parameter_types`
- `/task_manager/get_parameters`
- `/task_manager/list_parameters`
- `/task_manager/set_parameters`
- `/task_manager/set_parameters_atomically`

## Key Interface Presence

- `/navigate_to_pose` action: True
- `/map` topic: True
- `/tf` topic: True
- `/odom` topic: True
- `/amcl_pose` topic: True
- `pose_goal_controller_3d` node: False
- `controller_server` node: True
- `bt_navigator` node: False
- `planner_server` node: False
- `goal_bridge` node: False
- `task_manager` node: True

## Missing Or Uncertain Pieces

- None

## Next Checks

- Dump runtime parameters to confirm which tolerances are actually active.
- Check TF chain stability before blaming goal tolerance.
- Compare goal frame with final pose frame before interpreting final_error.
- If NavCommand is present, verify whether it reports arrival or only command acceptance.
