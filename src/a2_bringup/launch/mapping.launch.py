from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from a2_bringup.runtime_mode import as_bool


def _launch_setup(context, *args, **kwargs):
    del args, kwargs
    use_mock = LaunchConfiguration("use_mock")
    runtime_mode = LaunchConfiguration("runtime_mode")
    use_sim_time = LaunchConfiguration("use_sim_time")
    enable_nav2_bringup = as_bool(LaunchConfiguration("enable_nav2_bringup").perform(context))
    a2_system_share = get_package_share_directory("a2_system")
    actions = []

    if not enable_nav2_bringup:
        actions.append(
            Node(
                package="map_manager",
                executable="occupancy_mapper",
                name="occupancy_mapper",
                parameters=[f"{a2_system_share}/config/occupancy_mapper.yaml", {
                    "use_mock": use_mock,
                    "runtime_mode": runtime_mode,
                    "use_sim_time": use_sim_time,
                }],
            )
        )

    actions.append(
        Node(
            package="map_manager",
            executable="map_manager_node",
            name="map_manager",
            parameters=[f"{a2_system_share}/config/map_manager.yaml", {
                "use_mock": use_mock,
                "runtime_mode": runtime_mode,
                "map_transient_local": enable_nav2_bringup,
                "use_sim_time": use_sim_time,
            }],
        )
    )
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("runtime_mode", default_value=""),
        DeclareLaunchArgument("use_mock", default_value="true"),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("enable_nav2_bringup", default_value="false"),
        OpaqueFunction(function=_launch_setup),
    ])
