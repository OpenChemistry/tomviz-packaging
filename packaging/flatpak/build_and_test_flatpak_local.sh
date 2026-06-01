#!/usr/bin/env bash
# Full local build + test of the Tomviz flatpak using Docker.
#
#   1. Ensure a staged conda bundle exists (reuse packaging/_build/install if
#      present, else build it with package.py in a miniforge image).
#   2. In a privileged Fedora container: build the flatpak (build_flatpak.sh)
#      and headlessly smoke-test it with software GL (test_flatpak.sh).
#
# flatpak-builder and `flatpak run` use bubblewrap, which needs user namespaces;
# hence --privileged. On Apple Silicon this runs under linux/amd64 emulation.
#
# Usage: build_and_test_flatpak_local.sh [version] [python_version]
set -euo pipefail

VERSION="${1:-2.3.1}"
PYVER="${2:-3.13}"
PLATFORM="${PLATFORM:-linux/amd64}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAGED="$REPO_ROOT/packaging/_build/install/tomviz"

echo "Repo:     $REPO_ROOT"
echo "Version:  $VERSION (python $PYVER)"
echo "Platform: $PLATFORM"

if [ ! -d "$STAGED/env" ]; then
    echo
    echo "=== Staged bundle not found; building it (package.py) ==="
    docker run --rm --platform "$PLATFORM" \
        -v "$REPO_ROOT:/src" -w /src/packaging \
        condaforge/miniforge3:latest bash -c "
set -e
mamba install -y -n base conda-pack >/dev/null
python package.py --tomviz-version '$VERSION' --python-version '$PYVER'
"
else
    echo "=== Reusing existing staged bundle at $STAGED ==="
fi

echo
echo "=== Build + test flatpak in a privileged Fedora container ==="
# Persist the flatpak user installation (runtime/sdk + built app) in a named
# volume so the ~1GB org.freedesktop.Platform//Sdk runtime is downloaded once
# and reused across runs (and works offline afterwards).
docker run --rm --platform "$PLATFORM" \
    --privileged --security-opt seccomp=unconfined \
    -v "$REPO_ROOT:/src" -w /src/packaging \
    -v tomviz-flatpak:/root/.local/share/flatpak \
    fedora:41 bash -c "
set -e
dnf install -y flatpak flatpak-builder xorg-x11-server-Xvfb \
    mesa-dri-drivers mesa-libGL libglvnd-glx procps-ng >/dev/null
flatpak remote-add --user --if-not-exists flathub \
    https://flathub.org/repo/flathub.flatpakrepo
# Build container-local (NOT on the /src bind mount): copying the multi-GB
# payload and the flatpak build tree onto the macOS virtiofs mount is slow and
# breaks 'cp -a' ownership preservation. We copy the small manifest/scripts to
# /root/fp, build there, then copy only the final .flatpak back to _build.
#
# Run from /root/fp so flatpak-builder's .flatpak-builder state dir is on the
# same (local) filesystem as the build dir (/root/fpout): with rofiles-fuse
# disabled it hardlinks between them, and a cross-filesystem state dir aborts
# the build before it starts.
cp -a flatpak /root/fp
( cd /root/fp && bash build_flatpak.sh \
    --staged /src/packaging/_build/install --version '$VERSION' --out /root/fpout )
cp /root/fpout/org.tomviz.Tomviz-'$VERSION'.flatpak _build/
bash flatpak/test_flatpak.sh _build/org.tomviz.Tomviz-'$VERSION'.flatpak
"

echo
echo "ALL DONE: flatpak built and smoke-tested"
