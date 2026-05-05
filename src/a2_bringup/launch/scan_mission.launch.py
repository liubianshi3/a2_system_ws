from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue



def _launch_setup(context, *args, **kwargs):
    del args, kwargs
    a2_system_share = get_package_share_directory("a2_system")
    config = LaunchConfiguration("config")
    waypoints_file = LaunchConfiguration("waypoints_file")
    dry_run = LaunchConfiguration("dry_run")
    stack_mode = LaunchConfiguration("stack_mode").perform(context).strip()
    is_navigation_2d = stack_mode == "navigation_2d"

    return [
        Node(
            package="a2_system",
            executable="auto_scan_mission.py",
            name="auto_scan_mission",
            output="screen",
            parameters=[
                config,
                {
                    "waypoints_file": waypoints_file,
                    "dry_run": ParameterValue(dry_run, value_type=bool),
                    "navigation_backend": "nav2" if is_navigation_2d else "pose_topic_3d",
                    "pose_topic": "/amcl_pose" if is_navigation_2d else "/jt128/dlio/odom",
                    "pose_msg_type": (
                        "geometry_msgs/msg/PoseWithCovarianceStamped"
                        if is_navigation_2d
                        else "nav_msgs/msg/Odometry"
                    ),
                },
            ],
        )
    ]


def generate_launch_description():
    a2_system_share = get_package_share_directory("a2_system")
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "config",
                default_value=f"{a2_system_share}/config/scan_mission.yaml",
            ),
            DeclareLaunchArgument(
                "waypoints_file",
                default_value=f"{a2_system_share}/config/scan_waypoints.example.yaml",
            ),
            DeclareLaunchArgument(
                "dry_run",
                default_value="false",
                description="Validate mission readiness and waypoint map cells without sending navigation goals.",
            ),
            DeclareLaunchArgument(
                "stack_mode",
                default_value="navigation_3d_backup",
            ),
            OpaqueFunction(function=_launch_setup),
        ]
    )
