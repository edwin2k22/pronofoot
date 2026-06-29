#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python}"
PORT="${PORT:-8077}"
LIVE_POLL="${LIVE_POLL:-30}"
PRONOFOOT_READONLY="${PRONOFOOT_READONLY:-1}"
PRONOFOOT_ENABLE_SCHEDULER="${PRONOFOOT_ENABLE_SCHEDULER:-1}"
PRONOFOOT_REFRESH_ON_START="${PRONOFOOT_REFRESH_ON_START:-0}"

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export PYTHONUTF8="${PYTHONUTF8:-1}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
export PRONOFOOT_READONLY

echo "PronoFoot public deploy"
echo "  port      : ${PORT}"
echo "  readonly  : ${PRONOFOOT_READONLY}"
echo "  scheduler : ${PRONOFOOT_ENABLE_SCHEDULER}"

if [ "${PRONOFOOT_REFRESH_ON_START}" = "1" ]; then
  echo "Running startup refresh..."
  "${PYTHON}" -m collector.refresh || {
    echo "Startup refresh failed; serving existing embedded data."
  }
else
  echo "Startup refresh skipped; serving bundled data."
fi

PIDS=""
cleanup() {
  if [ -n "${PIDS}" ]; then
    kill ${PIDS} 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

if [ "${PRONOFOOT_ENABLE_SCHEDULER}" = "1" ]; then
  "${PYTHON}" -m collector.smart_live --live-poll "${LIVE_POLL}" &
  PIDS="${PIDS} $!"
fi

exec "${PYTHON}" -m collector.server "${PORT}"
