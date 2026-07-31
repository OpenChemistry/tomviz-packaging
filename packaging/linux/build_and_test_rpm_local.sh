#!/usr/bin/env bash
# Full local build + test of the Tomviz /opt RPM using Docker.
#
# This reproduces what CI does, end to end:
#   1. build the real conda-pack bundle (package.py) and the RPM (build_rpm.sh)
#      inside a miniforge image that also has rpmbuild;
#   2. install + test the RPM in clean rockylinux:8 and rockylinux:9 images
#      (test_rpm.sh), including the relocation test.
#
# On an Apple Silicon / aarch64 host this runs under linux/amd64 emulation,
# because the Tomviz conda-forge packages are linux-64 only. That is correct but
# slow; expect the conda build step to take a while.
#
# Usage: build_and_test_rpm_local.sh [version] [python_version]
set -euo pipefail

VERSION="${1:-3.0.0}"
PYVER="${2:-3.13}"
PLATFORM="${PLATFORM:-linux/amd64}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "Repo:     $REPO_ROOT"
echo "Version:  $VERSION (python $PYVER)"
echo "Platform: $PLATFORM"

echo
echo "==================================================================="
echo "Step 1/3: build bundle + RPM (miniforge + rpmbuild)"
echo "==================================================================="
docker run --rm --platform "$PLATFORM" \
    -v "$REPO_ROOT:/src" -w /src/packaging \
    -v tomviz-conda-pkgs:/opt/conda/pkgs \
    condaforge/miniforge3:latest bash -c "
set -e
# Reduce the conda solver memory peak for local x86-on-ARM emulation (qemu
# inflates memory use). Using current_repodata.json -- the index of just the
# latest build of each package -- shrinks the libsolv pool ~10x vs the full
# repodata.json, which is what otherwise OOM-kills the solve under emulation.
# Harmless/unused on native CI runners, which build from the full repodata.
printf 'repodata_fns:\n  - current_repodata.json\n' > /root/.condarc
export CONDA_FETCH_THREADS=1
apt-get update -qq && apt-get install -y -qq rpm xz-utils file >/dev/null
# package.py needs conda-pack (CI gets it from packaging/environment.yml).
mamba install -y -n base conda-pack >/dev/null
python package.py --tomviz-version '$VERSION' --python-version '$PYVER'
bash linux/build_rpm.sh --staged _build/install --version '$VERSION' --out _build
"

echo
echo "==================================================================="
echo "Step 2/3 & 3/3: install + test in rockylinux:8 and rockylinux:9"
echo "==================================================================="
for img in rockylinux:8 rockylinux:9; do
    echo
    echo "######## Testing on $img ########"
    docker run --rm --platform "$PLATFORM" \
        -v "$REPO_ROOT:/src" -w /src/packaging \
        "$img" bash -c "
set -e
RPM=\$(ls _build/tomviz-*.rpm | head -1)
echo \"Testing \$RPM\"
bash linux/test_rpm.sh \"\$RPM\" \"\$PWD/verify.py\" '$PYVER'
"
done

echo
echo "ALL DONE: RPM built and passed tests on rockylinux:8 and rockylinux:9"
