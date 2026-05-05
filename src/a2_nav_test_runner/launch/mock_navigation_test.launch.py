from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("scenario", default_value="clean_nav"),
            Node(
                package="a2_nav_test_runner",
                executable="mock_precision_scenario_runner",
                name="mock_precision_scenario_runner",
                output="screen",
                parameters=[
                    {
                        "scenario": LaunchConfiguration("scenario"),
                        "scenarios_yaml": "src/a2_nav_test_runner/config/mock_precision_scenarios.yaml",
                        "results_root": "src/a2_nav_test_runner/results/mock_precision",
                        "data_source": "mock_navigation_test",
                    }
                ],
            ),
        ]
    )
