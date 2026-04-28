#!/usr/bin/env bash
# Launch the bundled Tomviz, wait WAIT_SECS, and verify the process is still
# running (i.e., it didn't crash on startup). Use Qt's offscreen platform on
# Linux/Windows so no display server is needed; macOS runners have a
# WindowServer available.
#
# Usage: smoke_test_launcher.sh <launcher_path> [wait_secs=15]
set -euo pipefail

LAUNCHER="${1:?usage: $0 <launcher_path> [wait_secs]}"
WAIT_SECS="${2:-15}"

if [ ! -e "$LAUNCHER" ]; then
  echo "FAIL: launcher not found at $LAUNCHER"
  exit 1
fi

"$LAUNCHER" &
PID=$!
sleep "$WAIT_SECS"

if kill -0 "$PID" 2>/dev/null; then
  echo "OK: tomviz process $PID is running after ${WAIT_SECS}s"
  kill "$PID" || true
  wait "$PID" 2>/dev/null || true
else
  wait "$PID" 2>/dev/null
  EXIT_CODE=$?
  echo "FAIL: tomviz exited early with code $EXIT_CODE"
  exit 1
fi
