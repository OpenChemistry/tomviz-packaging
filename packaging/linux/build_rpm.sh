#!/usr/bin/env bash
# Build the Tomviz /opt RPM from an already-staged conda-pack bundle.
#
# Prerequisite: run `python package.py ...` first so that
# <staged>/tomviz/{tomviz,env} exists (the relocatable Linux bundle).
#
# Usage:
#   build_rpm.sh --staged _build/install --version 3.0.0 [--release 1] [--out _build]
#
# Produces: <out>/tomviz-<version>-<release>.<arch>.rpm
#
# This only assembles a package from prebuilt files; it does not compile
# anything, so it runs anywhere rpmbuild is available (RHEL, Fedora, or even
# Debian/Ubuntu with the `rpm` package installed).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STAGED=""
VERSION=""
RELEASE="1"
OUT="_build"

while [ $# -gt 0 ]; do
    case "$1" in
        --staged)  STAGED="$2"; shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        --release) RELEASE="$2"; shift 2 ;;
        --out)     OUT="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

if [ -z "$STAGED" ] || [ -z "$VERSION" ]; then
    echo "usage: $0 --staged <dir> --version <ver> [--release <rel>] [--out <dir>]" >&2
    exit 2
fi

STAGED="$(cd "$STAGED" && pwd)"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

BUNDLE="$STAGED/tomviz"
if [ ! -d "$BUNDLE/env" ] || [ ! -f "$BUNDLE/tomviz" ]; then
    echo "FAIL: expected staged bundle at $BUNDLE (with env/ and tomviz launcher)." >&2
    echo "      Run 'python package.py' first." >&2
    exit 1
fi

echo "=== Staging desktop integration assets into the bundle ==="
# These live under the install prefix (/opt/tomviz/share/...) so the spec's
# %post can copy them out to /usr/share and they relocate with the package.
install -Dm0644 "$SCRIPT_DIR/tomviz.desktop" \
    "$BUNDLE/share/applications/tomviz.desktop"
install -Dm0644 "$SCRIPT_DIR/tomviz.png" \
    "$BUNDLE/share/icons/hicolor/128x128/apps/tomviz.png"
install -Dm0644 "$SCRIPT_DIR/org.tomviz.Tomviz.metainfo.xml" \
    "$BUNDLE/share/metainfo/org.tomviz.Tomviz.metainfo.xml"

echo "=== Setting up rpmbuild tree ==="
TOPDIR="$OUT/rpmbuild"
rm -rf "$TOPDIR"
mkdir -p "$TOPDIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS,BUILDROOT}

echo "=== Running rpmbuild ==="
rpmbuild -bb "$SCRIPT_DIR/tomviz.spec" \
    --define "_topdir $TOPDIR" \
    --define "tomviz_version $VERSION" \
    --define "tomviz_release $RELEASE" \
    --define "staged_root $STAGED" \
    --define "dist %{nil}"

RPM_FILE="$(find "$TOPDIR/RPMS" -name 'tomviz-*.rpm' | head -1)"
if [ -z "$RPM_FILE" ]; then
    echo "FAIL: rpmbuild did not produce an rpm" >&2
    exit 1
fi

cp -f "$RPM_FILE" "$OUT/"
FINAL="$OUT/$(basename "$RPM_FILE")"
echo
echo "=== Built: $FINAL ==="
ls -la "$FINAL"

# Quick metadata sanity check (does not require installation).
echo
echo "=== rpm -qpi ==="
rpm -qpi "$FINAL" || true
echo
echo "=== relocations ==="
rpm -qp --queryformat '[%{PREFIXES}\n]' "$FINAL" || true
