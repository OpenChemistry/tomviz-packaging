#!/usr/bin/env bash
# Install and test the Tomviz RPM in a clean RHEL-family environment.
#
# Designed to run *inside* a target container (e.g. rockylinux:8, rockylinux:9,
# or a UBI image) where the .rpm has been made available. Mirrors the checks the
# other Tomviz packages get in CI: structural verification, dependency
# resolution, desktop integration, a headless smoke test, and -- unique to the
# relocatable RPM -- a second install at a non-default prefix.
#
# Usage:
#   test_rpm.sh <path-to.rpm> [path-to-verify.py] [python_version]
set -euo pipefail

RPM_FILE="${1:?usage: $0 <rpm> [verify.py] [python_version]}"
VERIFY_PY="${2:-}"
PYVER="${3:-3.13}"

PKGMGR="$(command -v dnf || command -v yum)"

echo "############################################################"
echo "# Installing runtime test dependencies (Xvfb + software GL) #"
echo "############################################################"
# The bundle is self-contained, but the headless smoke test needs an X server
# and a software GL stack from the host side.
# Host-side runtime deps for the headless smoke test (X server + software GL).
# Note: we deliberately do NOT rely on a system python3 -- verify.py runs under
# the bundled Python 3.13 instead (RHEL/Rocky 8's python3 is 3.6, too old).
$PKGMGR install -y \
    xorg-x11-server-Xvfb mesa-dri-drivers mesa-libGL libglvnd-glx \
    libxkbcommon libxkbcommon-x11 fontconfig procps-ng findutils file \
    >/dev/null 2>&1 || \
$PKGMGR install -y xorg-x11-server-Xvfb mesa-dri-drivers mesa-libGL \
    libxkbcommon fontconfig procps-ng findutils file || true

smoke_test() {
    # $1 = launcher path
    local launcher="$1"
    echo "--- Smoke test: $launcher (wait ${SMOKE_WAIT:-15}s) ---"
    LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe \
        xvfb-run -a bash "$SMOKE" "$launcher" "${SMOKE_WAIT:-15}"
}

# Locate the shared smoke-test helper (shipped alongside this script in CI,
# or passed implicitly via the repo checkout).
SMOKE="$(dirname "$0")/../../.github/scripts/smoke_test_launcher.sh"
if [ ! -f "$SMOKE" ]; then
    # Fall back to an inline equivalent if the helper isn't mounted.
    SMOKE="/tmp/smoke_test_launcher.sh"
    cat > "$SMOKE" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
LAUNCHER="${1:?}"; WAIT_SECS="${2:-15}"
"$LAUNCHER" & PID=$!
sleep "$WAIT_SECS"
if kill -0 "$PID" 2>/dev/null; then
  echo "OK: tomviz process $PID still running after ${WAIT_SECS}s"; kill "$PID" || true
else
  wait "$PID" 2>/dev/null; echo "FAIL: tomviz exited early with code $?"; exit 1
fi
EOF
fi

echo
echo "############################################"
echo "# Test 1: default install (/opt/tomviz)     #"
echo "############################################"
$PKGMGR install -y "$RPM_FILE"

echo "--- Verify payload landed under /opt/tomviz ---"
test -x /opt/tomviz/tomviz        && echo "OK: /opt/tomviz/tomviz launcher present"
test -x /opt/tomviz/env/bin/tomviz && echo "OK: /opt/tomviz/env/bin/tomviz present"

echo "--- Verify desktop integration (wired by %post) ---"
test -L /usr/bin/tomviz && echo "OK: /usr/bin/tomviz symlink -> $(readlink /usr/bin/tomviz)"
test -f /usr/share/applications/tomviz.desktop && echo "OK: .desktop installed"
test -f /usr/share/icons/hicolor/128x128/apps/tomviz.png && echo "OK: icon installed"

if [ -n "$VERIFY_PY" ] && [ -f "$VERIFY_PY" ]; then
    echo "--- Structural verification (verify.py) ---"
    # Use the bundled interpreter (Python 3.13), not the host's: RHEL/Rocky 8
    # ship Python 3.6 as system python3, which is too old to even parse
    # verify.py. The bundled python is always present (it is the payload).
    /opt/tomviz/env/bin/python "$VERIFY_PY" /opt/tomviz --python-version "$PYVER"
fi

smoke_test /usr/bin/tomviz

echo
echo "############################################"
echo "# Test 2: uninstall cleans integration      #"
echo "############################################"
$PKGMGR remove -y tomviz
if [ -e /usr/bin/tomviz ] || [ -e /usr/share/applications/tomviz.desktop ]; then
    echo "FAIL: desktop integration not cleaned on uninstall"; exit 1
fi
echo "OK: /usr/bin symlink and .desktop removed on uninstall"

echo
echo "##################################################"
echo "# Test 3: relocated install (non-default prefix)  #"
echo "##################################################"
RELOC=/srv/shared/tomviz
mkdir -p "$(dirname "$RELOC")"
rpm -i --prefix="$RELOC" "$RPM_FILE"
test -x "$RELOC/tomviz" && echo "OK: bundle installed at relocated prefix $RELOC"
LINK_TARGET="$(readlink /usr/bin/tomviz || true)"
if [ "$LINK_TARGET" = "$RELOC/tomviz" ]; then
    echo "OK: /usr/bin/tomviz follows relocation -> $LINK_TARGET"
else
    echo "FAIL: /usr/bin/tomviz points to '$LINK_TARGET', expected '$RELOC/tomviz'"; exit 1
fi
smoke_test "$RELOC/tomviz"
rpm -e tomviz

echo
echo "ALL RPM TESTS PASSED"
