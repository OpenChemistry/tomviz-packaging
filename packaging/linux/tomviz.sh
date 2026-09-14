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
# config dir, which doesn't exist at runtime. FONTCONFIG_FILE overrides the
# default with the bundle's fonts.conf. FONTCONFIG_PATH is needed as well:
# fonts.conf pulls in the generic-family aliases (sans-serif -> DejaVu Sans,
# etc.) via a relative <include>conf.d</include>, and fontconfig resolves
# relative includes against FONTCONFIG_PATH / its compiled-in dir rather than
# the including file. Without it conf.d is silently skipped and Qt's
# "sans-serif" request lands on an arbitrary, usually serif, font.
export FONTCONFIG_FILE="$ENV_DIR/etc/fonts/fonts.conf"
export FONTCONFIG_PATH="$ENV_DIR/etc/fonts"

exec "$ENV_DIR/bin/tomviz" "$@"
