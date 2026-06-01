#!/usr/bin/env bash
# Install and headlessly smoke-test the Tomviz flatpak bundle.
#
# Mirrors the rigor the other Tomviz artifacts get: install the bundle, confirm
# the app is registered with the expected files, then launch it under a virtual
# X server with software OpenGL and confirm it doesn't crash on startup.
#
# Usage:
#   test_flatpak.sh <path-to.flatpak> [wait_secs=20]
#
# Requires flatpak + a flathub remote (for the runtime) and an X stack + mesa
# software GL on the host side (the local orchestrator/CI install these).
set -euo pipefail

BUNDLE="${1:?usage: $0 <bundle.flatpak> [wait_secs]}"
WAIT_SECS="${2:-20}"
APP_ID="org.tomviz.Tomviz"

echo "=== Installing runtime (from flathub) + the app bundle ==="
flatpak remote-add --user --if-not-exists flathub \
    https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user -y "$BUNDLE"

echo "=== Registered application metadata ==="
flatpak info --user "$APP_ID"

echo "=== Verify in-sandbox layout ==="
# `flatpak run --command=...` runs an arbitrary command inside the sandbox.
flatpak run --user --command=sh "$APP_ID" -c '
  set -e
  test -x /app/tomviz/tomviz       && echo "OK: /app/tomviz/tomviz launcher"
  test -x /app/tomviz/env/bin/tomviz && echo "OK: /app/tomviz/env/bin/tomviz"
  test -L /app/bin/tomviz          && echo "OK: /app/bin/tomviz -> $(readlink /app/bin/tomviz)"
  test -d /app/tomviz/env/lib/qt6/plugins && echo "OK: Qt plugins present"
'

echo "=== Headless smoke test (xvfb + software GL) ==="
# Qt offscreen would skip GL entirely; we want a real (software) GL context to
# exercise ParaView/VTK rendering, so use Xvfb + llvmpipe.
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
xvfb-run -a -s "-screen 0 1280x1024x24" bash -c "
    flatpak run --user '$APP_ID' &
    PID=\$!
    sleep $WAIT_SECS
    if kill -0 \$PID 2>/dev/null; then
        echo 'OK: tomviz flatpak still running after ${WAIT_SECS}s'
        flatpak kill '$APP_ID' 2>/dev/null || kill \$PID 2>/dev/null || true
    else
        wait \$PID 2>/dev/null
        echo \"FAIL: tomviz flatpak exited early with code \$?\"
        exit 1
    fi
"

echo
echo "ALL FLATPAK TESTS PASSED"
