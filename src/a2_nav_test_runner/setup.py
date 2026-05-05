import glob
import os

from setuptools import setup

package_name = "a2_nav_test_runner"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "config"), glob.glob("config/*.yaml")),
        (os.path.join("share", package_name, "launch"), glob.glob("launch/*.py")),
    ],
    install_requires=["setuptools", "PyYAML"],
    zip_safe=True,
    maintainer="dell",
    maintainer_email="dell@example.com",
    description="A2 navigation test runner.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "nav_test_node = a2_nav_test_runner.nav_test_node:main",
            "runtime_param_dumper = a2_nav_test_runner.runtime_param_dumper:main",
            "nav_runtime_diagnosis = a2_nav_test_runner.nav_runtime_diagnosis:main",
            "tf_diagnosis = a2_nav_test_runner.tf_diagnosis:main",
            "pose_accuracy_recorder = a2_nav_test_runner.pose_accuracy_recorder:main",
            "single_goal_accuracy_test = a2_nav_test_runner.single_goal_accuracy_test:main",
            "navigation_precision_analyzer = a2_nav_test_runner.navigation_precision_analyzer:main",
            "mock_nav2_action_server = a2_nav_test_runner.mock_nav2_action_server:main",
            "mock_navcommand_service = a2_nav_test_runner.mock_navcommand_service:main",
            "mock_pose_tf_publisher = a2_nav_test_runner.mock_pose_tf_publisher:main",
            "mock_precision_scenario_runner = a2_nav_test_runner.mock_precision_scenario_runner:main",
        ],
    },
)
