import os

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from a2_bringup.runtime_mode import normalize_runtime_mode


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _load_yaml(path):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_real_lidar_config(a2_system_share):
    cfg = _load_yaml(os.path.join(a2_system_share, "config", "real_lidar.yaml"))
    return cfg.get("real_lidar", {}).get("ros__parameters", {})


def _launch_setup(context, *args, **kwargs):
    del args, kwargs
    runtime_mode = normalize_runtime_mode(LaunchConfiguration("runtime_mode").perform(context))
    use_sim_time = _as_bool(LaunchConfiguration("use_sim_time").perform(context))
    a2_system_share = get_package_share_directory("a2_system")
    bringup_share = get_package_share_directory("a2_bringup")
    diagnostic_only = os.environ.get("A2_REAL_DIAGNOSTIC_ONLY", "0") == "1"
    real_lidar_cfg = _load_real_lidar_config(a2_system_share)
    real_lidar_profile = real_lidar_cfg.get("profile", "hesai_jt128_front")
    real_lidar_driver_mode = real_lidar_cfg.get("driver_mode", "")
    real_lidar_imu_topic = real_lidar_cfg.get("imu_topic", "/jt128/front/imu")
    real_lidar_input_topic = real_lidar_cfg.get("input_topic", "/jt128/front/points")
    real_lidar_output_topic = real_lidar_cfg.get("output_topic", "/jt128/front/points")
    real_lidar_output_frame = real_lidar_cfg.get("output_frame_id", "jt128_front_link")
    direct_pointcloud_mode = (
        real_lidar_driver_mode == "external_pointcloud"
        or real_lidar_profile == "unitree_native_fused"
    )
    guard_pointcloud_topic = (
        real_lidar_input_topic if direct_pointcloud_mode else real_lidar_output_topic
    )
    guard_stale_timeout = float(real_lidar_cfg.get("stale_timeout_sec", 1.0))
    use_jt128_extrinsics = real_lidar_output_frame.startswith("jt128_") or "jt128" in real_lidar_profile
    extrinsics_file = (
        f"{a2_system_share}/config/jt128_extrinsics.yaml"
        if use_jt128_extrinsics
        else f"{a2_system_share}/config/extrinsics.yaml"
    )

    actions = [
        Node(
            package="tf_manager",
            executable="static_tf_manager",
            name="static_tf_manager",
            parameters=[{
                "extrinsics_file": extrinsics_file,
                "tf_file": f"{a2_system_share}/config/tf.yaml",
                "base_height": 0.28,
                "use_sim_time": use_sim_time,
            }],
        ),
        Node(
            package="sensor_sync",
            executable="sync_monitor",
            name="sync_monitor",
            parameters=[f"{a2_system_share}/config/sensor_sync.yaml", {
                "imu_topic": real_lidar_imu_topic,
                "pointcloud_topic": guard_pointcloud_topic,
                "runtime_mode": runtime_mode,
                "use_sim_time": use_sim_time,
            }],
        ),
        Node(
            package="sensor_sync",
            executable="pointcloud_guard",
            name="pointcloud_guard",
            parameters=[{
                "pointcloud_topic": guard_pointcloud_topic,
                "stale_timeout_sec": guard_stale_timeout,
                "connected_topic": "/a2/lidar/connected",
                "status_topic": "/a2/lidar/status",
                "status_label": "lidar",
                "use_sim_time": use_sim_time,
            }],
        ),
    ]

    if diagnostic_only:
        actions.append(
            LogInfo(
                msg="Real diagnostic mode enabled. JT128 driver launch is deferred until the wired data path is validated."
            )
        )
        return actions

    if direct_pointcloud_mode:
        restamp_on_receive = bool(real_lidar_cfg.get("restamp_on_receive", False))
        if (
            real_lidar_input_topic != real_lidar_output_topic
            or real_lidar_output_frame
            or restamp_on_receive
        ):
            actions.append(
                LogInfo(
                    msg=(
                        f"Using external pointcloud input_topic={real_lidar_input_topic} "
                        f"consumer_topic={guard_pointcloud_topic} compatibility_output={real_lidar_output_topic} "
                        f"frame_id={real_lidar_output_frame} restamp_on_receive={restamp_on_receive}"
                    )
                )
            )
            actions.append(
                Node(
                    package="sensor_sync",
                    executable="pointcloud_relay",
                    name="pointcloud_relay",
                    parameters=[{
                        "input_topic": real_lidar_input_topic,
                        "output_topic": real_lidar_output_topic,
                        "frame_id": real_lidar_output_frame,
                        "restamp_on_receive": restamp_on_receive,
                    }],
                )
            )
        return actions

    if real_lidar_profile == "hesai_jt128_front" or real_lidar_driver_mode == "dedicated_hesai_ros_driver":
        actions.append(
            LogInfo(
                msg=(
                    "Starting JT128 driver from sensors.launch.py "
                    f"profile={real_lidar_profile} output_topic={real_lidar_output_topic}"
                )
            )
        )
        actions.append(
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(f"{bringup_share}/launch/jt128_driver.launch.py"),
                launch_arguments={
                    "config_path": f"{a2_system_share}/config/jt128_front_hesai.yaml",
                    "use_sim_time": str(use_sim_time).lower(),
                }.items(),
            )
        )
        return actions

    actions.append(
        LogInfo(
            msg=(
                "Unsupported real_lidar profile for the cleaned real-only stack: "
                f"profile={real_lidar_profile} driver_mode={real_lidar_driver_mode}"
            )
        )
    )
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("runtime_mode", default_value=""),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("network_interface", default_value=""),
        OpaqueFunction(function=_launch_setup),
    ])
