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

# fontconfig in the conda build bakes its build-time prefix as the default
# config path, which doesn't exist at runtime. FONTCONFIG_FILE overrides the
# default with the bundle's fonts.conf (FONTCONFIG_PATH only adds a search
# directory and does not suppress the "Cannot load default config" error).
export FONTCONFIG_FILE="$ENV_DIR/etc/fonts/fonts.conf"

exec "$ENV_DIR/bin/tomviz" "$@"
