#!/usr/bin/env bash
set -euo pipefail

export A2_WORKSPACE="${A2_WORKSPACE:-/opt/a2_system_ws}"
export CONFIG_PATH="${CONFIG_PATH:-${A2_WORKSPACE}/web_console/backend/config.docker.yaml}"
export LD_LIBRARY_PATH="/opt/unitree_robotics/lib:/opt/unitree_robotics/lib/x86_64:${LD_LIBRARY_PATH:-}"
export A2_NETWORK_INTERFACE="${A2_NETWORK_INTERFACE:-eth0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"

mkdir -p "${A2_WORKSPACE}/runtime/maps" "${A2_WORKSPACE}/runtime/logs"

source /opt/ros/humble/setup.bash
source "${A2_WORKSPACE}/install/setup.bash"

# Start the full robot stack in background
if [[ "${A2_AUTO_START_STACK:-1}" == "1" ]]; then
  echo "Starting A2 robot stack (network_interface=${A2_NETWORK_INTERFACE})..."
  ros2 launch a2_bringup bringup.launch.py \
    runtime_mode:=real \
    network_interface:="${A2_NETWORK_INTERFACE}" \
    enable_nav2_bringup:=false \
    enable_control_bridge:=true \
    real_localization_mode:=amcl \
    > "${A2_WORKSPACE}/runtime/logs/bringup.log" 2>&1 &
  echo "Robot stack started, PID: $!"
fi

# Start web console backend
exec "${A2_WORKSPACE}/web_console/scripts/run_backend.sh" "$@"
