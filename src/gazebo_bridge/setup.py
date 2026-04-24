from glob import glob
from setuptools import setup

package_name = "gazebo_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/models", glob("models/*")),
        ("share/" + package_name + "/maps", glob("maps/*")),
        ("share/" + package_name + "/worlds", glob("worlds/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="dell",
    maintainer_email="dell@example.com",
    description="Gazebo adapters for the host-side A2 navigation stack.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "gazebo_state_adapter = gazebo_bridge.gazebo_state_adapter:main",
            "initial_pose_publisher = gazebo_bridge.initial_pose_publisher:main",
        ],
    },
)
