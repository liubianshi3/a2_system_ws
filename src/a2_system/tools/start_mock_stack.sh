#!/usr/bin/env bash
set -euo pipefail

source /opt/ros/humble/setup.bash
source "${1:-$HOME/a2_system_ws/install/setup.bash}"
ros2 launch a2_bringup bringup.launch.py runtime_mode:=mock auto_start_explore:=true
