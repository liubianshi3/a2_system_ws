#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${A2_WORKSPACE:-$HOME/a2_system_ws}"
MODE="standby"
MAP_ID=""
LIDAR_IFACE="${A2_JT128_INTERFACE:-net1}"
SDK_IFACE="${A2_SDK_INTERFACE:-eth0}"
CONTROL_IFACE="${A2_CONTROL_INTERFACE:-$SDK_IFACE}"
ENABLE_MOTION=false
LIVE_MOTION=false
STOP_EXISTING=1
WEB_URL="${A2_WEB_URL:-http://127.0.0.1:8080}"
LOG_DIR="${WORKSPACE}/runtime/logs"
WEB_LOG="${LOG_DIR}/web_console_manual_$(date +%Y%m%d_%H%M%S).log"
WEB_STATE_FILE="${WORKSPACE}/runtime/web_stack_state.yaml"
WEB_RUN_SCRIPT="${WORKSPACE}/web_console/scripts/run_backend.sh"
STACK_SCRIPT="${WORKSPACE}/src/a2_system/tools/start_jt128_3d_stack.sh"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") [--mode standby] [--lidar-iface net1]
  $(basename "$0") --mode mapping [--lidar-iface net1]
  $(basename "$0") --mode navigation --map-id MAP_ID [--lidar-iface net1] [--sdk-iface eth0] [--enable-motion] [--live-motion]

Default behavior:
  Starts the Web backend directly and leaves Web stack state as "stopped".
  Open the Web page and choose mapping or navigation yourself.

Safety:
  --mode navigation defaults to dry-run.
  Physical /cmd_vel output requires both --enable-motion and --live-motion.
EOF
}

log() {
  printf '[INFO] %s\n' "$*"
}

warn() {
  printf '[WARN] %s\n' "$*" >&2
}

die() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --map-id)
      MAP_ID="$2"
      shift 2
      ;;
    --lidar-iface|--iface)
      LIDAR_IFACE="$2"
      shift 2
      ;;
    --sdk-iface)
      SDK_IFACE="$2"
      CONTROL_IFACE="$2"
      shift 2
      ;;
    --control-iface)
      CONTROL_IFACE="$2"
      shift 2
      ;;
    --enable-motion)
      ENABLE_MOTION=true
      shift
      ;;
    --live-motion)
      LIVE_MOTION=true
      ENABLE_MOTION=true
      shift
      ;;
    --no-stop-existing)
      STOP_EXISTING=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

[[ "$MODE" == "standby" || "$MODE" == "mapping" || "$MODE" == "navigation" ]] || die "mode must be standby, mapping, or navigation"
if [[ "$MODE" == "navigation" && -z "$MAP_ID" ]]; then
  die "--map-id is required for navigation mode"
fi
if [[ "$LIVE_MOTION" == "true" && "$ENABLE_MOTION" != "true" ]]; then
  die "--live-motion requires --enable-motion"
fi

wait_http_ok() {
  local url="$1"
  local timeout_sec="$2"
  local start_ts
  start_ts="$(date +%s)"
  while true; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    if (( $(date +%s) - start_ts >= timeout_sec )); then
      return 1
    fi
    sleep 1
  done
}

show_urls() {
  ip -4 -o addr show scope global 2>/dev/null | awk '{print $2 " " $4}' | while read -r name cidr; do
    case "$name" in
      lo|docker0|br-*|veth*)
        continue
        ;;
    esac
    printf '[INFO] Open: http://%s:8080/ (%s)\n' "${cidr%%/*}" "$name"
  done
}

write_web_state() {
  local mode="$1"
  local message="$2"
  mkdir -p "$(dirname "$WEB_STATE_FILE")"
  cat > "$WEB_STATE_FILE" <<EOF
mode: ${mode}
target_mode: null
selected_map_id: ${MAP_ID:-null}
selected_map_yaml: null
message: "${message}"
EOF
}

kill_own_pattern() {
  local signal="$1"
  local pattern="$2"
  local pids=()
  local pid
  while IFS= read -r pid; do
    [[ -n "$pid" ]] || continue
    [[ "$pid" == "$$" || "$pid" == "$BASHPID" ]] && continue
    pids+=("$pid")
  done < <(pgrep -u "$(id -u)" -f "$pattern" 2>/dev/null || true)
  ((${#pids[@]} > 0)) || return 0
  kill "-${signal}" "${pids[@]}" >/dev/null 2>&1 || true
}

stop_owned_robot_stack() {
  local pattern
  for pattern in \
    "jt128_3d_navigation.launch.py" \
    "dlio_mapping.launch.py" \
    "jt128_driver.launch.py" \
    "hesai_ros_driver_node" \
    "jt128_hesai_driver" \
    "dlio_odom_node" \
    "dlio_map_node" \
    "jt128_dlio_odom" \
    "jt128_dlio_map" \
    "pointcloud_guard" \
    "pointcloud_map_loader" \
    "pcd_relocalizer_3d" \
    "localization_gate" \
    "goal_bridge" \
    "pose_goal_controller_3d" \
    "safety_supervisor" \
    "real_readiness_monitor" \
    "a2_sdk_bridge_node" \
    "a2_state_publisher_node" \
    "a2_control_bridge_node" \
    "map_manager_node" \
    "jt128_dlio_watchdog.py" \
    "jt128_static_tf_manager"; do
    kill_own_pattern TERM "$pattern"
  done
  sleep 1
  for pattern in \
    "jt128_3d_navigation.launch.py" \
    "dlio_mapping.launch.py" \
    "jt128_driver.launch.py" \
    "hesai_ros_driver_node" \
    "dlio_odom_node" \
    "dlio_map_node" \
    "pointcloud_map_loader" \
    "pcd_relocalizer_3d" \
    "goal_bridge" \
    "pose_goal_controller_3d" \
    "a2_control_bridge_node" \
    "map_manager_node"; do
    kill_own_pattern KILL "$pattern"
  done
}

start_web_backend() {
  mkdir -p "$LOG_DIR"
  [[ -x "$WEB_RUN_SCRIPT" ]] || die "missing Web run script: $WEB_RUN_SCRIPT"

  if wait_http_ok "${WEB_URL}/api/health" 2; then
    log "Web backend is already healthy: ${WEB_URL}"
    return
  fi

  kill_own_pattern TERM "python.*-m backend.main"
  kill_own_pattern TERM "web_console/scripts/run_backend.sh"
  sleep 1

  log "Starting Web backend directly"
  nohup bash -lc "
    cd '${WORKSPACE}/web_console'
    exec '${WEB_RUN_SCRIPT}'
  " >"$WEB_LOG" 2>&1 &
  log "Web backend pid=$! log=${WEB_LOG}"

  if ! wait_http_ok "${WEB_URL}/api/health" 25; then
    tail -120 "$WEB_LOG" >&2 || true
    die "Web API did not become ready: ${WEB_URL}/api/health"
  fi
}

start_stack_mode() {
  local args=("--mode" "$MODE" "--lidar-iface" "$LIDAR_IFACE" "--no-web")
  [[ -x "$STACK_SCRIPT" ]] || die "missing stack script: $STACK_SCRIPT"

  if [[ "$MODE" == "navigation" ]]; then
    args+=("--map-id" "$MAP_ID" "--sdk-iface" "$SDK_IFACE" "--control-iface" "$CONTROL_IFACE")
    if [[ "$ENABLE_MOTION" == "true" ]]; then
      args+=("--enable-motion")
    fi
    if [[ "$LIVE_MOTION" == "true" ]]; then
      args+=("--live-motion")
    fi
  fi

  log "Starting ${MODE} stack through ${STACK_SCRIPT}"
  "$STACK_SCRIPT" "${args[@]}"
  write_web_state "$MODE" "Started ${MODE} through start_jt128_3d_closed_loop.sh"
}

cd "$WORKSPACE"
command -v curl >/dev/null 2>&1 || die "missing command: curl"

if [[ "$MODE" == "standby" ]]; then
  if [[ "$STOP_EXISTING" -eq 1 ]]; then
    log "Stopping user-owned JT128/3D stack processes for Web standby"
    stop_owned_robot_stack
  fi
  write_web_state "stopped" "Web console ready; choose mapping or navigation in the UI"
  start_web_backend
else
  start_web_backend
  start_stack_mode
fi

echo
log "Web health"
curl -fsS "${WEB_URL}/api/health" || true
echo
log "Web stack status"
curl -fsS "${WEB_URL}/api/stack/status" || true
echo
show_urls
if [[ "$MODE" == "standby" ]]; then
  log "Standby ready: Web should show stopped. Choose mapping or navigation in the UI."
elif [[ "$MODE" == "navigation" && "$LIVE_MOTION" != "true" ]]; then
  log "Navigation is running in dry-run mode. Use --live-motion only after confirming the area is clear."
fi
