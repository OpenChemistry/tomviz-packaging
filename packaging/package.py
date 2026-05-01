"""
Tomviz standalone installer packaging script.

This script:
1. Creates a conda environment with tomviz from conda-forge
2. Uses conda-pack to make it relocatable
3. Extracts and post-processes for the target platform
4. Prepares the result for CPack to create the final installer

Usage:
    python package.py [--python-version 3.13] [--tomviz-version 2.3.1]
"""

from __future__ import annotations

import argparse
import fnmatch
import glob
import json
import os
import platform
import shutil
import subprocess
import tarfile
import zipfile
from typing import Any


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(SCRIPT_DIR, "_build")


def run(cmd: list[str], **kwargs: Any) -> None:
    print(f"  >> {' '.join(cmd)}")
    subprocess.check_call(cmd, **kwargs)


def get_conda_cmd() -> str:
    """Find conda/mamba/micromamba (including .bat variants on Windows)."""
    candidates = ["mamba", "conda", "micromamba"]
    if platform.system() == "Windows":
        # On Windows, setup-miniconda puts .bat wrappers on PATH
        candidates = ["mamba.bat", "conda.bat"] + candidates
    for cmd in candidates:
        if shutil.which(cmd):
            return cmd
    raise RuntimeError("No conda/mamba/micromamba found in PATH")


def query_latest_version(python_version: str) -> tuple[str, str]:
    """Query conda-forge for the latest tomviz version."""
    conda = get_conda_cmd()
    result = subprocess.run(
        [conda, "search", "-c", "conda-forge", "tomviz", "--json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"conda search failed (exit {result.returncode}): {result.stderr}")
    data: dict[str, Any] = json.loads(result.stdout)
    packages: list[dict[str, Any]] = data.get("tomviz", [])

    # Filter to the requested python version
    py_prefix = f"py{python_version.replace('.', '')}"
    matching = [p for p in packages if p["build"].startswith(py_prefix)]

    if not matching:
        # Try without python filter
        matching = packages

    if not matching:
        raise RuntimeError("No tomviz packages found on conda-forge")

    # Sort by version (as int tuples) and build number to get the latest
    def version_key(p: dict[str, Any]) -> tuple[tuple[int, ...], int]:
        parts: list[int] = []
        for x in p["version"].split("."):
            try:
                parts.append(int(x))
            except ValueError:
                parts.append(0)
        return (tuple(parts), p["build_number"])

    latest = sorted(matching, key=version_key)[-1]
    return latest["version"], latest["build"]


def create_environment(python_version: str, tomviz_version: str) -> str:
    """Create a conda environment with tomviz installed."""
    conda = get_conda_cmd()
    env_dir = os.path.join(BUILD_DIR, "env")

    if os.path.exists(env_dir):
        print(f"Removing existing environment at {env_dir}")
        shutil.rmtree(env_dir)

    print(f"Creating environment with tomviz={tomviz_version}, python={python_version}")
    run([
        conda, "create", "-y", "-p", env_dir,
        "-c", "conda-forge",
        f"python={python_version}",
        f"tomviz={tomviz_version}",
        "tomopy",
        "pystackreg",
    ])

    # ITK is only available to install from pip. Install it here.
    pip = os.path.join(env_dir, "bin", "pip")
    if platform.system() == "Windows":
        pip = os.path.join(env_dir, "Scripts", "pip.exe")
    run([pip, "install", "itk"])

    return env_dir


def conda_pack_env(env_dir: str) -> str:
    """Use conda-pack to create a relocatable archive."""
    is_windows = platform.system() == "Windows"
    ext = "zip" if is_windows else "tar.gz"
    archive_path = os.path.join(BUILD_DIR, f"tomviz-env.{ext}")

    print(f"Running conda-pack on {env_dir}")
    run([
        "conda-pack",
        "-p", env_dir,
        "-o", archive_path,
        "--ignore-missing-files",
    ])

    return archive_path


def extract_archive(archive_path: str, dest_dir: str) -> str:
    """Extract the conda-pack archive."""
    print(f"Extracting {archive_path} to {dest_dir}")
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir)

    if archive_path.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(dest_dir)
    else:
        with tarfile.open(archive_path) as tf:
            # Use fully_trusted filter to preserve symlinks and permissions
            tf.extractall(dest_dir, filter='fully_trusted')

    return dest_dir


def fix_qt_conf(env_dir: str) -> None:
    """Fix qt6.conf to use relative paths instead of hardcoded build paths."""
    for conf_name in ["qt6.conf", "qt.conf"]:
        for subdir in ["bin", "Library/bin"]:
            conf_path = os.path.join(env_dir, subdir, conf_name)
            if os.path.exists(conf_path):
                print(f"  Fixing {os.path.relpath(conf_path, env_dir)}")
                with open(conf_path, "w") as f:
                    f.write("[Paths]\n")
                    f.write("Prefix = ..\n")
                break


def cleanup_conda_pack_files(env_dir: str) -> None:
    """Remove conda-pack leftover files that tomviz might pick up as operators."""
    for name in ["conda_unpack_progress.py", "conda-unpack"]:
        for subdir in ["bin", "Scripts"]:
            path = os.path.join(env_dir, subdir, name)
            if os.path.exists(path):
                os.remove(path)
                print(f"  Removed {os.path.relpath(path, env_dir)}")


def stage_bundled_env(env_dir: str, bundle_env_dir: str) -> None:
    """Move the unpacked conda env into its final bundle location and post-process it.

    We deliberately skip `conda-unpack`: the launcher scripts set up PATH /
    CONDA_PREFIX themselves, so hardcoded shebangs in the bundled env don't
    matter, and re-running unpack would slow the build for no benefit.
    """
    if os.path.exists(bundle_env_dir):
        shutil.rmtree(bundle_env_dir)
    shutil.move(env_dir, bundle_env_dir)
    cleanup_conda_pack_files(bundle_env_dir)
    # conda-pack leaves hardcoded build-machine paths in qt.conf; rewrite them.
    fix_qt_conf(bundle_env_dir)


def _dir_size(path: str) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total += os.path.getsize(fp)
    return total


def _fmt_size(nbytes: int | float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def _matches_any(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def _resolve_dirs(env_dir: str, rel_paths: list[str]) -> list[str]:
    """Expand relative paths (with globs) to existing directories under env_dir.

    On conda-forge, the Unix layout puts files under lib/, share/, bin/ etc.
    while the Windows layout mirrors them under Library/. Rather than
    duplicating every path, callers can use a single list and this function
    probes both layouts automatically.
    """
    result = []
    for rel in rel_paths:
        for match in glob.glob(os.path.join(env_dir, rel)):
            if os.path.isdir(match) or os.path.islink(match):
                result.append(match)
    return result


def _remove_dirs(env_dir: str, paths: list[str]) -> int:
    """Remove a list of absolute directory paths, returning bytes saved."""
    saved = 0
    for d in paths:
        rel = os.path.relpath(d, env_dir)
        if os.path.islink(d):
            os.remove(d)
            print(f"  Removed {rel} (symlink)")
        elif os.path.isdir(d):
            size = _dir_size(d)
            shutil.rmtree(d)
            saved += size
            print(f"  Removed {rel}/ ({_fmt_size(size)})")
    return saved


def _remove_files_by_glob(env_dir: str, patterns: list[str]) -> tuple[int, int]:
    """Remove files matching glob patterns, returning (count, bytes)."""
    count = 0
    saved = 0
    for pattern in patterns:
        for f in glob.glob(os.path.join(env_dir, pattern), recursive=True):
            if os.path.isfile(f):
                saved += os.path.getsize(f)
                os.remove(f)
                count += 1
    return count, saved


def _cleanup_dir_entries(directory: str, keep_patterns: list[str], files_only: bool = False) -> int:
    """Remove entries from a directory unless their name matches keep_patterns.

    Returns bytes saved.  When files_only is True, only regular files and
    symlinks are considered (directories are left alone).
    """
    if not os.path.isdir(directory):
        return 0
    saved = 0
    for entry in os.listdir(directory):
        if _matches_any(entry, keep_patterns):
            continue
        p = os.path.join(directory, entry)
        if os.path.isdir(p) and not os.path.islink(p):
            if files_only:
                continue
            saved += _dir_size(p)
            shutil.rmtree(p)
        else:
            if not os.path.islink(p):
                saved += os.path.getsize(p)
            os.remove(p)
    return saved


def cleanup_bundled_env(env_dir: str) -> None:
    """Remove development-only files to reduce installer size."""
    print("Cleaning up bundled environment...")
    saved = 0

    # --- Directories ---
    # Paths may use globs; both Unix (lib/, share/) and Windows (Library/...)
    # layouts are listed. Non-existent paths are silently skipped.
    dirs = _resolve_dirs(env_dir, [
        # Headers
        "include", "Library/include",
        # Build system files
        "lib/cmake", "Library/lib/cmake", "Library/cmake",
        "lib/pkgconfig", "Library/lib/pkgconfig",
        # Conda metadata
        "conda-meta",
        # Documentation
        "share/doc", "Library/share/doc", "Library/doc",
        "share/man", "Library/share/man",
        "share/info", "Library/share/info",
        # GObject introspection data (build-time only)
        "share/gir-1.0", "Library/share/gir-1.0",
        # Qt dev tools and build files
        "lib/qt6/bin", "Library/lib/qt6/bin",
        "lib/qt6/mkspecs", "Library/lib/qt6/mkspecs", "Library/mkspecs",
        "lib/qt6/metatypes", "Library/lib/qt6/metatypes",
        "lib/qt6/sbom", "Library/lib/qt6/sbom",
        "lib/qt6/modules", "Library/lib/qt6/modules",
        "share/qt6/phrasebooks", "Library/share/qt6/phrasebooks",
        # Terminal database
        "lib/terminfo", "share/terminfo", "Library/share/terminfo",
        # Build artifacts
        "lib/objects-Release", "Library/lib/objects-Release",
        # System admin tools / toolchain
        "sbin",
        "x86_64-conda*-linux-gnu",
        # CUPS printing
        "share/cups", "Library/share/cups",
        # macOS: bundled ParaView app launcher (not needed)
        "Applications",
        # Windows: cmake shims, Fortran modules, Python tools
        "Library/SPIRV-Tools*", "Library/WebP",
        "Library/mod", "Tools",
    ])
    saved += _remove_dirs(env_dir, dirs)

    # --- Test directories inside site-packages ---
    for sp in _resolve_dirs(env_dir, [
            "lib/python*/site-packages", "Lib/site-packages"]):
        for root, subdirs, _ in os.walk(sp):
            for d in list(subdirs):
                if d in ("test", "tests"):
                    test_path = os.path.join(root, d)
                    saved += _remove_dirs(env_dir, [test_path])
                    subdirs.remove(d)

    # --- Static / import libraries (.a, .la, .lib) ---
    count, lib_saved = _remove_files_by_glob(
        env_dir, ["**/*.a", "**/*.la", "**/*.lib"])
    if count:
        saved += lib_saved
        print(f"  Removed {count} static/import libraries ({_fmt_size(lib_saved)})")

    # --- Non-essential executables ---
    # bin/ (Linux/macOS): keep tomviz, python, pip, and config files
    bin_saved = _cleanup_dir_entries(
        os.path.join(env_dir, "bin"),
        keep_patterns=["tomviz", "tomviz.*", "python*", "pip*", "*.conf"])
    if bin_saved:
        saved += bin_saved
        print(f"  Cleaned bin/ ({_fmt_size(bin_saved)})")

    # Library/bin/ (Windows): keep tomviz.exe and all DLLs; remove other .exe
    lib_bin_saved = _cleanup_dir_entries(
        os.path.join(env_dir, "Library", "bin"),
        keep_patterns=["tomviz.exe", "*.dll", "*.conf"],
        files_only=True)
    if lib_bin_saved:
        saved += lib_bin_saved
        print(f"  Cleaned Library/bin/ ({_fmt_size(lib_bin_saved)})")

    # Scripts/ (Windows): keep pip
    scripts_saved = _cleanup_dir_entries(
        os.path.join(env_dir, "Scripts"),
        keep_patterns=["pip*"],
        files_only=True)
    if scripts_saved:
        saved += scripts_saved
        print(f"  Cleaned Scripts/ ({_fmt_size(scripts_saved)})")

    print(f"  Total cleanup saved: {_fmt_size(saved)}")


def install_launcher(src: str, dst: str, executable: bool = True) -> None:
    """Copy a launcher script into place, marking it executable on POSIX."""
    shutil.copy2(src, dst)
    if executable:
        os.chmod(dst, 0o755)


def post_process_darwin(env_dir: str, tomviz_version: str) -> str:
    """Create a macOS .app bundle."""
    app_dir = os.path.join(BUILD_DIR, "install", "tomviz.app")
    contents_dir = os.path.join(app_dir, "Contents")
    macos_dir = os.path.join(contents_dir, "MacOS")
    resources_dir = os.path.join(contents_dir, "Resources")

    for d in [macos_dir, resources_dir]:
        os.makedirs(d, exist_ok=True)

    bundle_env_dir = os.path.join(contents_dir, "env")
    stage_bundled_env(env_dir, bundle_env_dir)
    cleanup_bundled_env(bundle_env_dir)

    install_launcher(
        os.path.join(SCRIPT_DIR, "darwin", "launcher.sh"),
        os.path.join(macos_dir, "tomviz"),
    )

    # Render Info.plist from template
    plist_template = os.path.join(SCRIPT_DIR, "darwin", "Info.plist.in")
    with open(plist_template) as f:
        plist = f.read().replace("@VERSION@", tomviz_version)
    with open(os.path.join(contents_dir, "Info.plist"), "w") as f:
        f.write(plist)

    icon_src = os.path.join(SCRIPT_DIR, "darwin", "tomviz.icns")
    if os.path.exists(icon_src):
        shutil.copy2(icon_src, os.path.join(resources_dir, "tomviz.icns"))

    return os.path.join(BUILD_DIR, "install")


def post_process_linux(env_dir: str, tomviz_version: str) -> str:
    """Set up Linux standalone bundle."""
    install_dir = os.path.join(BUILD_DIR, "install", "tomviz")
    os.makedirs(install_dir, exist_ok=True)

    bundle_env_dir = os.path.join(install_dir, "env")
    stage_bundled_env(env_dir, bundle_env_dir)
    cleanup_bundled_env(bundle_env_dir)

    install_launcher(
        os.path.join(SCRIPT_DIR, "linux", "tomviz.sh"),
        os.path.join(install_dir, "tomviz"),
    )

    return os.path.join(BUILD_DIR, "install")


def post_process_windows(env_dir: str, tomviz_version: str) -> str:
    """Set up Windows standalone bundle."""
    install_dir = os.path.join(BUILD_DIR, "install", "tomviz")
    os.makedirs(install_dir, exist_ok=True)

    bundle_env_dir = os.path.join(install_dir, "env")
    stage_bundled_env(env_dir, bundle_env_dir)
    cleanup_bundled_env(bundle_env_dir)

    install_launcher(
        os.path.join(SCRIPT_DIR, "windows", "tomviz.bat"),
        os.path.join(install_dir, "tomviz.bat"),
        executable=False,
    )

    return os.path.join(BUILD_DIR, "install")


def main() -> None:
    parser = argparse.ArgumentParser(description="Package tomviz standalone installers")
    parser.add_argument("--python-version", default="3.13",
                        help="Python version (default: 3.13)")
    parser.add_argument("--tomviz-version", default=None,
                        help="Tomviz version (default: latest on conda-forge)")
    args = parser.parse_args()

    os.makedirs(BUILD_DIR, exist_ok=True)

    # Determine version
    if args.tomviz_version:
        tomviz_version = args.tomviz_version
    else:
        tomviz_version, build_string = query_latest_version(args.python_version)
        print(f"Latest tomviz on conda-forge: {tomviz_version} ({build_string})")

    # Set environment variables for CPack
    os.environ["TOMVIZ_VERSION"] = tomviz_version
    os.environ["TOMVIZ_PYTHON_VERSION"] = args.python_version

    # Step 1: Create conda environment
    env_dir = create_environment(args.python_version, tomviz_version)

    # Step 2: conda-pack
    archive_path = conda_pack_env(env_dir)

    # Step 3: Extract
    extracted_dir = os.path.join(BUILD_DIR, "extracted_env")
    extract_archive(archive_path, extracted_dir)

    # Step 4: Platform-specific post-processing
    system = platform.system()
    if system == "Darwin":
        install_dir = post_process_darwin(extracted_dir, tomviz_version)
    elif system == "Linux":
        install_dir = post_process_linux(extracted_dir, tomviz_version)
    elif system == "Windows":
        install_dir = post_process_windows(extracted_dir, tomviz_version)
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    print(f"\nPackaging complete. Install directory: {install_dir}")
    print(f"Tomviz version: {tomviz_version}")
    print(f"Run 'cpack' from {SCRIPT_DIR} to create the final installer.")


if __name__ == "__main__":
    main()
