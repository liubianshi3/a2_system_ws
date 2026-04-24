#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${A2_WORKSPACE:-$HOME/a2_system_ws}"
MAP_ID="${1:-outdoor_demo_map}"
WORLD="${A2_GAZEBO_WORLD:-$WORKSPACE/install/gazebo_bridge/share/gazebo_bridge/worlds/outdoor_research_park.world}"
HELPER="$WORKSPACE/install/a2_system/share/a2_system/gazebo_outdoor_pipeline.py"
LOG_DIR="${A2_OUTDOOR_LOG_DIR:-$WORKSPACE/runtime/outdoor_demo_logs}"
NAV_GOAL_X="${A2_NAV_GOAL_X:--1.0}"
NAV_GOAL_Y="${A2_NAV_GOAL_Y:-3.0}"
mkdir -p "$LOG_DIR"

set +u
source /opt/ros/humble/setup.bash
source "$WORKSPACE/install/setup.bash"
set -u

MAP_LOG="$LOG_DIR/mapping_${MAP_ID}.log"
NAV_LOG="$LOG_DIR/navigation_${MAP_ID}.log"

cleanup() {
  local pid="${1:-}"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill -INT "$pid" 2>/dev/null || true
    pkill -INT -P "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
      pkill -TERM -P "$pid" 2>/dev/null || true
      kill -TERM "$pid" 2>/dev/null || true
      sleep 2
    fi
    if kill -0 "$pid" 2>/dev/null; then
      pkill -KILL -P "$pid" 2>/dev/null || true
      kill -KILL "$pid" 2>/dev/null || true
    fi
    wait "$pid" 2>/dev/null || true
  fi
}

echo "[1/4] Start outdoor Gazebo mapping stack"
ros2 launch a2_bringup bringup.launch.py \
  runtime_mode:=gazebo \
  gazebo_world:="$WORLD" \
  auto_start_explore:=false >"$MAP_LOG" 2>&1 &
MAP_PID=$!
trap 'cleanup "${NAV_PID:-}"; cleanup "${MAP_PID:-}"' EXIT

sleep 5

echo "[2/4] Patrol and save map: $MAP_ID"
MAP_YAML="$(python3 "$HELPER" patrol-save --map-id "$MAP_ID")"
echo "Saved map: $MAP_YAML"

cleanup "$MAP_PID"
MAP_PID=""
sleep 3

echo "[3/4] Restart with saved map and Nav2"
ros2 launch a2_bringup bringup.launch.py \
  runtime_mode:=gazebo \
  gazebo_world:="$WORLD" \
  auto_start_explore:=false \
  enable_nav2_bringup:=true \
  map:="$MAP_YAML" >"$NAV_LOG" 2>&1 &
NAV_PID=$!
sleep 6

echo "[4/4] Run use-map navigation smoke"
python3 "$HELPER" nav-goal --x "$NAV_GOAL_X" --y "$NAV_GOAL_Y"

echo "Outdoor Gazebo pipeline PASS"
echo "Mapping log: $MAP_LOG"
echo "Navigation log: $NAV_LOG"
