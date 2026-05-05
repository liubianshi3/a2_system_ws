import os
import yaml

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from a2_bringup.runtime_mode import as_bool, normalize_runtime_mode, use_sim_time_for_mode


def _load_yaml(path):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _real_lidar_consumer_topic(a2_system_share):
    params = _load_yaml(f"{a2_system_share}/config/real_lidar.yaml").get("real_lidar", {}).get(
        "ros__parameters", {}
    )
    profile = params.get("profile", "")
    driver_mode = params.get("driver_mode", "")
    if profile == "unitree_native_fused" or driver_mode == "external_pointcloud":
        return params.get("input_topic", "/jt128/front/points")
    return params.get("output_topic", "/jt128/front/points")


def _unitree_ddsc_env(runtime_mode):
    if runtime_mode != "real":
        return {}

    candidates = [
        "/opt/unitree_robotics/lib/x86_64/libddsc.so.0",
        "/unitree/opt/lib/libddsc.so.0",
    ]
    for candidate in candidates:
        if not os.path.exists(candidate):
            continue
        current = os.environ.get("LD_PRELOAD", "").strip()
        preload = candidate if not current else f"{candidate}:{current}"
        return {"LD_PRELOAD": preload}
    return {}


def _launch_setup(context, *args, **kwargs):
    del args, kwargs
    runtime_mode = normalize_runtime_mode(LaunchConfiguration("runtime_mode").perform(context))
    auto_start_explore = LaunchConfiguration("auto_start_explore").perform(context)
    network_interface = LaunchConfiguration("network_interface").perform(context)
    enable_nav2_bringup = LaunchConfiguration("enable_nav2_bringup").perform(context)
    enable_nav2_bringup_bool = as_bool(enable_nav2_bringup)
    enable_control_bridge = LaunchConfiguration("enable_control_bridge").perform(context)
    real_localization_mode = LaunchConfiguration("real_localization_mode").perform(context)
    requested_stack_mode = LaunchConfiguration("stack_mode").perform(context).strip()
    map_yaml = LaunchConfiguration("map").perform(context)
    use_sim_time = use_sim_time_for_mode(runtime_mode)
    use_sim_time_text = str(use_sim_time).lower()
    a2_system_share = get_package_share_directory("a2_system")
    bringup_share = get_package_share_directory("a2_bringup")
    unitree_ddsc_env = _unitree_ddsc_env(runtime_mode)
    real_lidar_topic = _real_lidar_consumer_topic(a2_system_share)
    slam_params = _load_yaml(f"{a2_system_share}/config/slam.yaml").get("slam_manager", {}).get(
        "ros__parameters", {}
    )
    map_representation = str(slam_params.get("primary_map_representation", "occupancy_grid_2d"))
    stack_mode = requested_stack_mode or ("navigation_2d" if enable_nav2_bringup_bool else "mapping_2d")
    is_mapping_2d = stack_mode == "mapping_2d"
    is_navigation_2d = stack_mode == "navigation_2d"
    is_navigation_3d_backup = stack_mode == "navigation_3d_backup"
    safety_config = (
        f"{a2_system_share}/config/safety_mapping.yaml"
        if is_mapping_2d
        else f"{a2_system_share}/config/safety_nav2.yaml"
    )

    actions = [
        Node(
            package="a2_sdk_bridge",
            executable="a2_sdk_bridge_node",
            name="a2_sdk_bridge",
            additional_env=unitree_ddsc_env,
            parameters=[f"{a2_system_share}/config/a2_sdk.yaml", {
                "use_mock": False,
                "allow_loopback": False,
                "network_interface": network_interface,
                "use_sim_time": use_sim_time,
            }],
        ),
        Node(
            package="a2_state_publisher",
            executable="a2_state_publisher_node",
            name="a2_state_publisher",
            parameters=[f"{a2_system_share}/config/state_bridge.yaml", {"use_sim_time": use_sim_time}],
        ),
        Node(
            package="a2_system",
            executable="task_manager.py",
            name="task_manager",
            parameters=[f"{a2_system_share}/config/task_manager.yaml", {
                "runtime_mode": runtime_mode,
                "use_sim_time": use_sim_time,
                "navigation_backend": "nav2" if is_navigation_2d else "pose_topic_3d",
            }],
        ),
        Node(
            package="a2_control_bridge",
            executable="a2_control_bridge_node",
            name="a2_control_bridge",
            condition=IfCondition(enable_control_bridge),
            additional_env=unitree_ddsc_env,
            parameters=[f"{a2_system_share}/config/motion_limits.yaml", {
                "use_mock": False,
                "allow_loopback": False,
                "network_interface": network_interface,
                "runtime_mode": runtime_mode,
                "sim_cmd_topic": "",
                "allow_motion_without_map": is_mapping_2d,
                "allow_motion_without_localization": False,
                "use_sim_time": use_sim_time,
            }],
        ),
        Node(
            package="safety_manager",
            executable="safety_supervisor",
            name="safety_supervisor",
            parameters=[safety_config, {
                "lidar_topic": real_lidar_topic,
                "runtime_mode": runtime_mode,
                "latch_map_ready": is_navigation_2d,
                "map_transient_local": is_navigation_2d,
                "map_representation": map_representation,
                "require_map": is_navigation_2d,
                "require_localization": True,
                "use_sim_time": use_sim_time,
            }],
        ),
        Node(
            package="safety_manager",
            executable="real_readiness_monitor",
            name="real_readiness_monitor",
            parameters=[{
                "runtime_mode": runtime_mode,
                "use_sim_time": use_sim_time,
            }],
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f"{bringup_share}/launch/sensors.launch.py"),
            launch_arguments={
                "runtime_mode": runtime_mode,
                "use_sim_time": use_sim_time_text,
                "network_interface": network_interface,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f"{bringup_share}/launch/slam.launch.py"),
            launch_arguments={
                "runtime_mode": runtime_mode,
                "use_sim_time": use_sim_time_text,
                "enable_nav2_bringup": enable_nav2_bringup,
                "map": map_yaml,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f"{bringup_share}/launch/mapping.launch.py"),
            launch_arguments={
                "runtime_mode": runtime_mode,
                "use_sim_time": use_sim_time_text,
                "enable_nav2_bringup": enable_nav2_bringup,
                "pointcloud_topic": real_lidar_topic,
                "stack_mode": stack_mode,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f"{bringup_share}/launch/localization.launch.py"),
            launch_arguments={
                "runtime_mode": runtime_mode,
                "use_sim_time": use_sim_time_text,
                "enable_nav2_bringup": enable_nav2_bringup,
                "real_localization_mode": real_localization_mode,
                "stack_mode": stack_mode,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f"{bringup_share}/launch/nav2.launch.py"),
            launch_arguments={
                "runtime_mode": runtime_mode,
                "use_sim_time": use_sim_time_text,
                "enable_nav2_bringup": enable_nav2_bringup,
                "real_localization_mode": real_localization_mode,
                "map": map_yaml,
                "stack_mode": stack_mode,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f"{bringup_share}/launch/explore.launch.py"),
            launch_arguments={
                "auto_start": auto_start_explore,
                "use_sim_time": use_sim_time_text,
            }.items(),
        ),
    ]
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("runtime_mode", default_value=""),
        DeclareLaunchArgument("auto_start_explore", default_value="false"),
        DeclareLaunchArgument("network_interface", default_value=""),
        DeclareLaunchArgument("enable_nav2_bringup", default_value="false"),
        DeclareLaunchArgument("enable_control_bridge", default_value="false"),
        DeclareLaunchArgument("real_localization_mode", default_value="amcl"),
        DeclareLaunchArgument("map", default_value=""),
        DeclareLaunchArgument("stack_mode", default_value=""),
        OpaqueFunction(function=_launch_setup),
    ])
