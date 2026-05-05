from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory("a2_nav_test_runner")
    return LaunchDescription(
        [
            DeclareLaunchArgument("goals_yaml", default_value=f"{pkg_share}/config/nav_test_goals.yaml"),
            DeclareLaunchArgument("config_yaml", default_value=f"{pkg_share}/config/nav_test_config.yaml"),
            DeclareLaunchArgument("backend_type", default_value=""),
            DeclareLaunchArgument("runs", default_value="0"),
            DeclareLaunchArgument("dry_check_only", default_value="true"),
            DeclareLaunchArgument("first_goal_only", default_value="true"),
            Node(
                package="a2_nav_test_runner",
                executable="nav_test_node",
                output="screen",
                parameters=[
                    {
                        "goals_yaml": LaunchConfiguration("goals_yaml"),
                        "config_yaml": LaunchConfiguration("config_yaml"),
                        "backend_type": LaunchConfiguration("backend_type"),
                        "runs": LaunchConfiguration("runs"),
                        "dry_check_only": LaunchConfiguration("dry_check_only"),
                        "first_goal_only": LaunchConfiguration("first_goal_only"),
                    }
                ],
            ),
        ]
    )
