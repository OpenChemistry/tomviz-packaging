#!/usr/bin/env bash
# Build the Tomviz flatpak single-file bundle from an already-staged conda-pack
# bundle (produced by package.py).
#
# Usage:
#   build_flatpak.sh --staged _build/install --version 2.3.1 [--out _build]
#
# Produces: <out>/org.tomviz.Tomviz-<version>.flatpak
#
# Requires: flatpak, flatpak-builder, and the org.freedesktop.{Platform,Sdk}
# 25.08 runtime/sdk installed (the local orchestrator and CI install these).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="org.tomviz.Tomviz"

STAGED=""
VERSION=""
OUT="_build"

while [ $# -gt 0 ]; do
    case "$1" in
        --staged)  STAGED="$2"; shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        --out)     OUT="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

if [ -z "$STAGED" ] || [ -z "$VERSION" ]; then
    echo "usage: $0 --staged <dir> --version <ver> [--out <dir>]" >&2
    exit 2
fi

STAGED="$(cd "$STAGED" && pwd)"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"

BUNDLE="$STAGED/tomviz"
if [ ! -d "$BUNDLE/env" ] || [ ! -f "$BUNDLE/tomviz" ]; then
    echo "FAIL: expected staged bundle at $BUNDLE (run package.py first)." >&2
    exit 1
fi

echo "=== Staging payload for flatpak-builder ==="
# The manifest references ./payload (type: dir); place the bundle there as
# payload/tomviz so the build-commands' "cp -a tomviz/. /app/tomviz/" works.
rm -rf "$SCRIPT_DIR/payload"
mkdir -p "$SCRIPT_DIR/payload"
cp -a "$BUNDLE" "$SCRIPT_DIR/payload/tomviz"

echo "=== flatpak-builder ==="
BUILDDIR="$OUT/flatpak-build"
REPO="$OUT/flatpak-repo"
rm -rf "$BUILDDIR" "$REPO"
# --disable-rofiles-fuse: rofiles-fuse needs FUSE, unavailable in most
#   containers; copying is fine here.
# --user + --install-deps-from=flathub: pull the runtime/sdk if missing.
flatpak-builder \
    --force-clean \
    --user \
    --disable-rofiles-fuse \
    --install-deps-from=flathub \
    --repo="$REPO" \
    "$BUILDDIR" \
    "$SCRIPT_DIR/$APP_ID.yaml"

echo "=== Exporting single-file bundle ==="
OUT_FILE="$OUT/$APP_ID-$VERSION.flatpak"
flatpak build-bundle "$REPO" "$OUT_FILE" "$APP_ID"

echo
echo "=== Built: $OUT_FILE ==="
ls -la "$OUT_FILE"
