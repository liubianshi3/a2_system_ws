#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${A2_WORKSPACE:-$HOME/a2_system_ws}"
WORLD="${A2_GAZEBO_WORLD:-}"
GUI="${A2_GAZEBO_GUI:-false}"
ENABLE_NAV2="${A2_ENABLE_NAV2:-false}"
MAP_YAML="${A2_MAP_YAML:-}"
AUTO_EXPLORE="${A2_AUTO_EXPLORE:-}"

set +u
source /opt/ros/humble/setup.bash
source "${WORKSPACE}/install/setup.bash"
set -u

EXTRA_ARGS=()
if [[ -n "${WORLD}" ]]; then
  EXTRA_ARGS+=("gazebo_world:=${WORLD}")
fi
if [[ "${ENABLE_NAV2}" == "1" || "${ENABLE_NAV2}" == "true" ]]; then
  EXTRA_ARGS+=("enable_nav2_bringup:=true")
fi
if [[ -n "${MAP_YAML}" ]]; then
  EXTRA_ARGS+=("map:=${MAP_YAML}")
fi
if [[ -z "${AUTO_EXPLORE}" ]]; then
  if [[ "${ENABLE_NAV2}" == "1" || "${ENABLE_NAV2}" == "true" ]]; then
    AUTO_EXPLORE="false"
  else
    AUTO_EXPLORE="true"
  fi
fi

ros2 launch a2_bringup bringup.launch.py \
  runtime_mode:=gazebo \
  auto_start_explore:="${AUTO_EXPLORE}" \
  gazebo_gui:="${GUI}" \
  "${EXTRA_ARGS[@]}"
