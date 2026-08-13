# Tomviz RPM spec.
#
# This packages the *prebuilt* Tomviz conda-forge environment (already staged by
# package.py and made relocatable with conda-pack) into an RPM that installs
# under /opt/tomviz. It does not compile anything; the payload is a
# self-contained conda environment plus a launcher script.
#
# Variable bits are passed by build_rpm.sh via --define, so this stays a real,
# lintable .spec file that can be checked into the repo and handed to NSLS-II
# (the SOW requires shipping the .spec):
#
#   rpmbuild -bb linux/tomviz.spec \
#       --define "tomviz_version 2.3.1" \
#       --define "tomviz_release 1" \
#       --define "staged_root /abs/path/to/_build/install"
#
# staged_root must contain a "tomviz/" directory holding the bundle:
#   tomviz/tomviz        (launcher, from linux/tomviz.sh)
#   tomviz/env/...       (the conda-pack'd environment)
#   tomviz/share/...     (desktop file + icon, added by build_rpm.sh)

### --- Preserve the prebuilt bundle exactly as-is ----------------------------
# The conda binaries already carry correct $ORIGIN-relative RPATHs and are
# stripped as upstream intends. rpmbuild's default post-install "brp" scripts
# would re-strip, mangle RPATHs, byte-compile .py files and rewrite shebangs,
# which corrupts a conda environment. Disable all of that.
%global __os_install_post %{nil}
%global __brp_check_rpaths %{nil}
%global debug_package %{nil}
# Everything the app needs lives under /opt/tomviz, so do not auto-generate
# Requires/Provides from the bundled ELF files (they'd pull in bogus deps and
# advertise bundled sonames to the system).
AutoReqProv: no

Name:           tomviz
Version:        %{tomviz_version}
Release:        %{?tomviz_release}%{!?tomviz_release:1}%{?dist}
Summary:        3D tomography data processing and visualization

# tomviz itself is BSD-3-Clause; the bundle also ships a GPL ffmpeg
# executable (invoked as a separate process for movie export), with its
# license texts under share/licenses/ffmpeg/ in the payload.
License:        BSD-3-Clause AND GPL-2.0-or-later
URL:            https://tomviz.org
Vendor:         Kitware, Inc.

# Relocatable: the whole payload sits under this single prefix, so users can
#   rpm -i --prefix=/some/other/tomviz tomviz-*.rpm
# (or dnf install with --setopt, or rpm --relocate). The launcher resolves its
# own location at runtime and conda's RPATHs are $ORIGIN-relative, so the
# bundle runs correctly from any prefix.
Prefix:         /opt/tomviz

%description
Tomviz is an open source platform for the processing, visualization, and
analysis of 3D tomographic data, tailored to high-resolution electron and
synchrotron tomography. This package bundles a complete, self-contained Tomviz
environment (Python, Qt, ParaView/VTK and all dependencies) under
%{prefix}; it does not use or conflict with system Python or Qt.

%prep
# Nothing to unpack: we install a prebuilt, already-staged tree.

%build
# Nothing to build: the payload is prebuilt from conda-forge.

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}%{prefix}
# Copy the staged bundle, preserving symlinks/modes/timestamps but NOT ownership
# (rpm assigns root:root via %files anyway). Avoiding ownership preservation
# keeps this working on filesystems where lchown is unavailable, e.g. a virtiofs
# bind-mount when building under Docker on macOS.
cp -dR --preserve=mode,timestamps,links %{staged_root}/tomviz/. %{buildroot}%{prefix}/

%files
# Own the entire prefix tree. Desktop integration outside the prefix
# (/usr/bin symlink, .desktop, icon) is wired up in %post so it follows the
# real install location even when the package is relocated.
%{prefix}

%post
# $RPM_INSTALL_PREFIX0 is the actual install prefix (honours --prefix/--relocate).
PREFIX="${RPM_INSTALL_PREFIX0:-%{prefix}}"

# Launcher on PATH.
ln -sf "$PREFIX/tomviz" /usr/bin/tomviz

# Desktop entry + icon for menu integration. The shipped .desktop uses
# "Exec=tomviz" and "Icon=tomviz", so it stays valid regardless of prefix as
# long as the /usr/bin symlink and themed icon below exist.
if [ -f "$PREFIX/share/applications/tomviz.desktop" ]; then
    mkdir -p /usr/share/applications
    cp -f "$PREFIX/share/applications/tomviz.desktop" /usr/share/applications/tomviz.desktop
fi
if [ -f "$PREFIX/share/icons/hicolor/128x128/apps/tomviz.png" ]; then
    mkdir -p /usr/share/icons/hicolor/128x128/apps
    cp -f "$PREFIX/share/icons/hicolor/128x128/apps/tomviz.png" \
        /usr/share/icons/hicolor/128x128/apps/tomviz.png
fi
if [ -f "$PREFIX/share/metainfo/org.tomviz.Tomviz.metainfo.xml" ]; then
    mkdir -p /usr/share/metainfo
    cp -f "$PREFIX/share/metainfo/org.tomviz.Tomviz.metainfo.xml" \
        /usr/share/metainfo/org.tomviz.Tomviz.metainfo.xml
fi

# Refresh desktop/icon caches if the tools are present (best-effort).
update-desktop-database /usr/share/applications &>/dev/null || :
touch --no-create /usr/share/icons/hicolor &>/dev/null || :
gtk-update-icon-cache /usr/share/icons/hicolor &>/dev/null || :

%postun
# Only clean up the out-of-prefix integration files on a real uninstall
# ($1 == 0), not during an upgrade ($1 >= 1), to avoid removing files the new
# package's %post just installed.
if [ "$1" -eq 0 ]; then
    rm -f /usr/bin/tomviz
    rm -f /usr/share/applications/tomviz.desktop
    rm -f /usr/share/icons/hicolor/128x128/apps/tomviz.png
    rm -f /usr/share/metainfo/org.tomviz.Tomviz.metainfo.xml
    update-desktop-database /usr/share/applications &>/dev/null || :
    gtk-update-icon-cache /usr/share/icons/hicolor &>/dev/null || :
fi

%changelog
* Mon Jun 01 2026 Kitware, Inc. <kitware@kitware.com> - %{tomviz_version}
- Packaged from the Tomviz conda-forge build into a relocatable /opt RPM.
