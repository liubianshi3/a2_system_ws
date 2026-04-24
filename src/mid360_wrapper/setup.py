from setuptools import setup

package_name = "mid360_wrapper"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="dell",
    maintainer_email="dell@example.com",
    description="MID360 wrapper utilities with mock publishing and connectivity diagnostics.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "mock_mid360_publisher = mid360_wrapper.mock_mid360_publisher:main",
            "mid360_link_check = mid360_wrapper.mid360_link_check:main",
            "mid360_driver_guard = mid360_wrapper.mid360_driver_guard:main",
            "livox_custom_to_pointcloud = mid360_wrapper.livox_custom_to_pointcloud:main",
            "pointcloud_frame_relay = mid360_wrapper.pointcloud_frame_relay:main",
            "pointcloud_to_laserscan = mid360_wrapper.pointcloud_to_laserscan:main",
        ],
    },
)
