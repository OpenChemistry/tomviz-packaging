#!/bin/bash
# Launcher script for the Tomviz macOS app bundle.
# This sets up the environment from the bundled conda env and runs tomviz.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_DIR="$SCRIPT_DIR/../env"

# Activate the conda environment paths
export PATH="$ENV_DIR/bin:$PATH"
export CONDA_PREFIX="$ENV_DIR"

# Qt plugin path
export QT_PLUGIN_PATH="$ENV_DIR/lib/qt6/plugins"

# Python paths are handled by the tomviz binary itself

exec "$ENV_DIR/bin/tomviz" "$@"
