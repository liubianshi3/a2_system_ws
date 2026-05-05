# Navigation Runtime Diagnosis

This report is a runtime interface diagnosis. It is not a navigation experiment result.

- backend_candidate: `unknown`

## Evidence

- No decisive evidence was detected.

## Nodes

- `/nav_runtime_diagnosis`

## Topics

- `/parameter_events`
- `/rosout`

## Actions

- No ROS2 actions were visible.

## Services

- `/nav_runtime_diagnosis/describe_parameters`
- `/nav_runtime_diagnosis/get_parameter_types`
- `/nav_runtime_diagnosis/get_parameters`
- `/nav_runtime_diagnosis/list_parameters`
- `/nav_runtime_diagnosis/set_parameters`
- `/nav_runtime_diagnosis/set_parameters_atomically`

## Key Interface Presence

- `/navigate_to_pose` action: False
- `/map` topic: False
- `/tf` topic: False
- `/odom` topic: False
- `/amcl_pose` topic: False
- `pose_goal_controller_3d` node: False
- `controller_server` node: False
- `bt_navigator` node: False
- `planner_server` node: False
- `goal_bridge` node: False
- `task_manager` node: False

## Missing Or Uncertain Pieces

- NavigateToPose action was not detected.
- No A2 NavCommand candidate service was detected.
- ROS graph appears empty or navigation stack is not running.
- /map is not available; map server or SLAM output must be checked on robot.
- /tf is not available; transforms must be checked before navigation.
- No pose feedback topic detected; final_error and NavCommand arrival checks may be unavailable.

## Next Checks

- Dump runtime parameters to confirm which tolerances are actually active.
- Check TF chain stability before blaming goal tolerance.
- Compare goal frame with final pose frame before interpreting final_error.
- If NavCommand is present, verify whether it reports arrival or only command acceptance.
