from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    world = LaunchConfiguration("world")
    gui = LaunchConfiguration("gui")
    paused = LaunchConfiguration("paused")
    gazebo_ros_share = get_package_share_directory("gazebo_ros")
    gazebo_bridge_share = get_package_share_directory("gazebo_bridge")

    default_world = f"{gazebo_bridge_share}/worlds/outdoor_research_park.world"
    robot_file = f"{gazebo_bridge_share}/models/sim_car.urdf"

    return LaunchDescription([
        DeclareLaunchArgument("world", default_value=default_world),
        DeclareLaunchArgument("gui", default_value="false"),
        DeclareLaunchArgument("paused", default_value="false"),
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f"{gazebo_ros_share}/launch/gazebo.launch.py"),
            launch_arguments={
                "world": world,
                "gui": gui,
                "pause": paused,
                "verbose": "false",
            }.items(),
        ),
        Node(
            package="gazebo_ros",
            executable="spawn_entity.py",
            name="spawn_gazebo_sim_car",
            output="screen",
            arguments=[
                "-entity", "a2_nav_sim",
                "-file", robot_file,
                "-x", "-7.2",
                "-y", "0.0",
                "-z", "0.15",
            ],
        ),
    ])
