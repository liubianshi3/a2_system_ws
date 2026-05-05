import yaml

from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from a2_bringup.runtime_mode import normalize_runtime_mode, as_bool


def _load_yaml(path):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _pointcloud_scan_input_topic(a2_system_share):
    params = _load_yaml(f"{a2_system_share}/config/real_lidar.yaml").get("real_lidar", {}).get(
        "ros__parameters", {}
    )
    profile = params.get("profile", "")
    driver_mode = params.get("driver_mode", "")
    if profile == "unitree_native_fused" or driver_mode == "external_pointcloud":
        return params.get("input_topic", "/jt128/front/points")
    return params.get("output_topic", "/jt128/front/points")


def _launch_setup(context, *args, **kwargs):
    del args, kwargs
    runtime_mode = normalize_runtime_mode(LaunchConfiguration("runtime_mode").perform(context))
    enable_nav2_bringup = as_bool(LaunchConfiguration("enable_nav2_bringup").perform(context))
    real_localization_mode = (
        LaunchConfiguration("real_localization_mode").perform(context).strip() or "amcl"
    )
    stack_mode = LaunchConfiguration("stack_mode").perform(context).strip() or (
        "navigation_2d" if enable_nav2_bringup else "mapping_2d"
    )
    map_yaml = LaunchConfiguration("map").perform(context).strip()
    use_sim_time = as_bool(LaunchConfiguration("use_sim_time").perform(context))
    use_sim_time_text = str(use_sim_time).lower()
    a2_system_share = get_package_share_directory("a2_system")
    pointcloud_scan_input_topic = _pointcloud_scan_input_topic(a2_system_share)
    slam_params = _load_yaml(f"{a2_system_share}/config/slam.yaml").get("slam_manager", {}).get(
        "ros__parameters", {}
    )
    navigation_representation = str(slam_params.get("navigation_representation", "occupancy_grid_2d"))
    use_3d_navigation = (
        stack_mode == "navigation_3d_backup"
        or (runtime_mode == "real" and navigation_representation == "pointcloud_map_3d" and stack_mode != "navigation_2d")
    )
    use_manual_real_localization = (
        runtime_mode == "real"
        and enable_nav2_bringup
        and real_localization_mode == "manual_odom"
    )
    actions = [
        Node(
            package="nav2_integration",
            executable="goal_bridge",
            name="goal_bridge",
            parameters=[f"{a2_system_share}/config/nav2.yaml", {
                "runtime_mode": runtime_mode,
                "use_sim_time": use_sim_time,
            }],
        ),
    ]

    if stack_mode == "navigation_2d" and enable_nav2_bringup and not use_3d_navigation:
        actions.append(
            Node(
                package="sensor_sync",
                executable="pointcloud_to_laserscan",
                name="pointcloud_to_laserscan",
                parameters=[f"{a2_system_share}/config/pointcloud_to_scan.yaml", {
                    "input_topic": pointcloud_scan_input_topic,
                    "use_sim_time": use_sim_time,
                }],
            )
        )

    try:
        nav2_share = get_package_share_directory("nav2_bringup")
        if stack_mode == "navigation_2d" and enable_nav2_bringup and not use_3d_navigation:
            if not map_yaml:
                actions.append(
                    LogInfo(
                        msg=(
                            "Nav2 bringup requested but no map yaml provided for the current stack. "
                            "Run mapping first or pass map:=<saved_map.yaml>."
                        )
                    )
                )
                return actions
            if use_manual_real_localization:
                actions.extend([
                    Node(
                        package="nav2_map_server",
                        executable="map_server",
                        name="map_server",
                        output="screen",
                        parameters=[
                            f"{a2_system_share}/config/nav2_stack.yaml",
                            {
                                "use_sim_time": use_sim_time,
                                "yaml_filename": map_yaml,
                            },
                        ],
                    ),
                    Node(
                        package="nav2_lifecycle_manager",
                        executable="lifecycle_manager",
                        name="lifecycle_manager_localization",
                        output="screen",
                        parameters=[
                            {"use_sim_time": use_sim_time},
                            {"autostart": True},
                            {"node_names": ["map_server"]},
                        ],
                    ),
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(f"{nav2_share}/launch/navigation_launch.py"),
                        launch_arguments={
                            "use_sim_time": use_sim_time_text,
                            "params_file": f"{a2_system_share}/config/nav2_stack.yaml",
                            "autostart": "true",
                            "use_composition": "False",
                            "use_respawn": "False",
                        }.items(),
                    ),
                ])
            else:
                actions.append(
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(f"{nav2_share}/launch/bringup_launch.py"),
                        launch_arguments={
                            "use_sim_time": use_sim_time_text,
                            "params_file": f"{a2_system_share}/config/nav2_stack.yaml",
                            "autostart": "true",
                            "map": map_yaml,
                            "slam": "False",
                            "use_composition": "False",
                            "use_respawn": "False",
                        }.items(),
                    )
                )
    except PackageNotFoundError:
        pass

    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("runtime_mode", default_value=""),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("enable_nav2_bringup", default_value="false"),
        DeclareLaunchArgument("real_localization_mode", default_value="amcl"),
        DeclareLaunchArgument("map", default_value=""),
        DeclareLaunchArgument("stack_mode", default_value=""),
        OpaqueFunction(function=_launch_setup),
    ])
