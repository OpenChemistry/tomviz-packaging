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

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(SCRIPT_DIR, "_build")


def run(cmd, **kwargs):
    print(f"  >> {' '.join(cmd)}")
    subprocess.check_call(cmd, **kwargs)


def get_conda_cmd():
    """Find conda/mamba/micromamba (including .bat variants on Windows)."""
    candidates = ["mamba", "conda", "micromamba"]
    if platform.system() == "Windows":
        # On Windows, setup-miniconda puts .bat wrappers on PATH
        candidates = ["mamba.bat", "conda.bat"] + candidates
    for cmd in candidates:
        if shutil.which(cmd):
            return cmd
    raise RuntimeError("No conda/mamba/micromamba found in PATH")


def query_latest_version(python_version):
    """Query conda-forge for the latest tomviz version."""
    conda = get_conda_cmd()
    result = subprocess.run(
        [conda, "search", "-c", "conda-forge", "tomviz", "--json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"conda search failed (exit {result.returncode}): {result.stderr}")
    data = json.loads(result.stdout)
    packages = data.get("tomviz", [])

    # Filter to the requested python version
    py_prefix = f"py{python_version.replace('.', '')}"
    matching = [p for p in packages if p["build"].startswith(py_prefix)]

    if not matching:
        # Try without python filter
        matching = packages

    if not matching:
        raise RuntimeError("No tomviz packages found on conda-forge")

    # Sort by version (as int tuples) and build number to get the latest
    def version_key(p):
        parts = []
        for x in p["version"].split("."):
            try:
                parts.append(int(x))
            except ValueError:
                parts.append(0)
        return (tuple(parts), p["build_number"])

    latest = sorted(matching, key=version_key)[-1]
    return latest["version"], latest["build"]


def create_environment(python_version, tomviz_version):
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
    ])

    return env_dir


def conda_pack_env(env_dir):
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


def extract_archive(archive_path, dest_dir):
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


def cleanup_conda_pack_files(env_dir):
    """Remove conda-pack leftover files that tomviz might pick up as operators."""
    for name in ["conda_unpack_progress.py", "conda-unpack"]:
        for subdir in ["bin", "Scripts"]:
            path = os.path.join(env_dir, subdir, name)
            if os.path.exists(path):
                os.remove(path)
                print(f"  Removed {os.path.relpath(path, env_dir)}")


def post_process_darwin(env_dir, tomviz_version):
    """Create a macOS .app bundle."""
    app_name = "tomviz"
    app_dir = os.path.join(BUILD_DIR, "install", f"{app_name}.app")
    contents_dir = os.path.join(app_dir, "Contents")
    macos_dir = os.path.join(contents_dir, "MacOS")
    resources_dir = os.path.join(contents_dir, "Resources")
    bundle_env_dir = os.path.join(contents_dir, "env")

    for d in [macos_dir, resources_dir]:
        os.makedirs(d, exist_ok=True)

    # Move the environment into the bundle
    if os.path.exists(bundle_env_dir):
        shutil.rmtree(bundle_env_dir)
    shutil.move(env_dir, bundle_env_dir)

    # Remove conda-pack leftovers that tomviz might scan
    cleanup_conda_pack_files(bundle_env_dir)

    # Create the launcher script
    launcher_path = os.path.join(macos_dir, "tomviz")
    launcher_src = os.path.join(SCRIPT_DIR, "darwin", "launcher.sh")
    shutil.copy2(launcher_src, launcher_path)
    os.chmod(launcher_path, 0o755)

    # Create Info.plist
    plist_template = os.path.join(SCRIPT_DIR, "darwin", "Info.plist.in")
    with open(plist_template) as f:
        plist = f.read()
    plist = plist.replace("@VERSION@", tomviz_version)
    with open(os.path.join(contents_dir, "Info.plist"), "w") as f:
        f.write(plist)

    # Copy icon if it exists
    icon_src = os.path.join(SCRIPT_DIR, "darwin", "tomviz.icns")
    if os.path.exists(icon_src):
        shutil.copy2(icon_src, os.path.join(resources_dir, "tomviz.icns"))

    # Note: we skip conda-unpack here. The launcher scripts set up the
    # environment properly (PATH, CONDA_PREFIX, etc.), so hardcoded shebangs
    # in the bundled env's scripts don't matter.

    return os.path.join(BUILD_DIR, "install")


def post_process_linux(env_dir, tomviz_version):
    """Set up Linux standalone bundle."""
    install_dir = os.path.join(BUILD_DIR, "install", "tomviz")
    os.makedirs(install_dir, exist_ok=True)

    # Move the environment
    bundle_env_dir = os.path.join(install_dir, "env")
    if os.path.exists(bundle_env_dir):
        shutil.rmtree(bundle_env_dir)
    shutil.move(env_dir, bundle_env_dir)

    # Remove conda-pack leftovers
    cleanup_conda_pack_files(bundle_env_dir)

    # Create launcher script
    launcher_src = os.path.join(SCRIPT_DIR, "linux", "tomviz.sh")
    launcher_dst = os.path.join(install_dir, "tomviz")
    shutil.copy2(launcher_src, launcher_dst)
    os.chmod(launcher_dst, 0o755)

    # Note: we skip conda-unpack here. The launcher scripts set up the
    # environment properly (PATH, CONDA_PREFIX, etc.), so hardcoded shebangs
    # in the bundled env's scripts don't matter.

    return os.path.join(BUILD_DIR, "install")


def post_process_windows(env_dir, tomviz_version):
    """Set up Windows standalone bundle."""
    install_dir = os.path.join(BUILD_DIR, "install", "tomviz")
    os.makedirs(install_dir, exist_ok=True)

    # Move the environment
    bundle_env_dir = os.path.join(install_dir, "env")
    if os.path.exists(bundle_env_dir):
        shutil.rmtree(bundle_env_dir)
    shutil.move(env_dir, bundle_env_dir)

    # Remove conda-pack leftovers
    cleanup_conda_pack_files(bundle_env_dir)

    # Create launcher batch file
    launcher_src = os.path.join(SCRIPT_DIR, "windows", "tomviz.bat")
    shutil.copy2(launcher_src, os.path.join(install_dir, "tomviz.bat"))

    # Note: we skip conda-unpack here. The launcher script (tomviz.bat) sets
    # up the environment properly (PATH, CONDA_PREFIX, etc.).

    return os.path.join(BUILD_DIR, "install")


def main():
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
