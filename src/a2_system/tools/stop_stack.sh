#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${A2_WORKSPACE:-$HOME/a2_system_ws}"
PID_FILE="${WORKSPACE}/runtime/bringup.pid"

if [[ ! -f "${PID_FILE}" ]]; then
  echo "No PID file found at ${PID_FILE}"
  exit 0
fi

PID="$(cat "${PID_FILE}")"
if kill -0 "${PID}" >/dev/null 2>&1; then
  kill "${PID}"
  wait "${PID}" 2>/dev/null || true
  echo "Stopped bringup pid=${PID}"
else
  echo "PID ${PID} is not running"
fi

rm -f "${PID_FILE}"
