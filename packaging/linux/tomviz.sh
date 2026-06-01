#!/bin/bash
# Launcher script for the Tomviz Linux standalone bundle.

# Resolve symlinks so the bundle is found correctly even when this launcher is
# invoked through a symlink (e.g. the /usr/bin/tomviz symlink the RPM creates,
# or the .desktop entry's "Exec=tomviz"). readlink -f is available on all
# supported Linux targets (RHEL/Fedora/Debian).
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
ENV_DIR="$SCRIPT_DIR/env"

# Activate the conda environment paths
export PATH="$ENV_DIR/bin:$PATH"
export LD_LIBRARY_PATH="$ENV_DIR/lib:${LD_LIBRARY_PATH:-}"
export CONDA_PREFIX="$ENV_DIR"

# Qt plugin path
export QT_PLUGIN_PATH="$ENV_DIR/lib/qt6/plugins"

exec "$ENV_DIR/bin/tomviz" "$@"
