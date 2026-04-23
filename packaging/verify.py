"""
Post-packaging verification for Tomviz standalone installers.

Checks:
1. Structural: expected files exist and are correct type
2. Library dependencies: no missing shared libraries
3. Prefix leaks: no conda build prefixes left behind
4. Artifact size: within expected range
"""

import argparse
import os
import platform
import re
import subprocess
import sys


EXPECTED_FILES_UNIX = [
    "env/bin/tomviz",
    "env/bin/python",
    "env/lib/libtomvizcore{shlib}",
]

EXPECTED_FILES_MACOS_APP = [
    "Contents/env/bin/tomviz",
    "Contents/env/bin/python",
    "Contents/env/lib/libtomvizcore{shlib}",
    "Contents/MacOS/tomviz",
    "Contents/Info.plist",
]

EXPECTED_FILES_WINDOWS = [
    "env/Library/bin/tomviz.exe",
    "env/Library/bin/tomvizcore.dll",
    "env/python.exe",
    "tomviz.bat",
]

# Directories that should exist
EXPECTED_DIRS_UNIX = [
    "env/lib/python{pyver}",
    "env/lib/python{pyver}/site-packages/tomviz",
]

EXPECTED_DIRS_MACOS_APP = [
    "Contents/env/lib/python{pyver}",
    "Contents/env/lib/python{pyver}/site-packages/tomviz",
]

EXPECTED_DIRS_WINDOWS = [
    "env/Lib/site-packages/tomviz",
]

# Minimum and maximum expected sizes in MB
MIN_SIZE_MB = 300
MAX_SIZE_MB = 8000


class Verifier:
    def __init__(self, install_dir, python_version="3.13"):
        self.install_dir = os.path.abspath(install_dir)
        self.python_version = python_version
        self.errors = []
        self.warnings = []
        self.system = platform.system()

    def error(self, msg):
        self.errors.append(msg)
        print(f"  FAIL: {msg}")

    def warn(self, msg):
        self.warnings.append(msg)
        print(f"  WARN: {msg}")

    def ok(self, msg):
        print(f"  OK:   {msg}")

    def check_structure(self):
        """Verify expected files and directories exist."""
        print("\n=== Structural Checks ===")

        shlib = ".dylib" if self.system == "Darwin" else ".so"
        pyver = self.python_version

        # Detect if this is a macOS .app bundle
        is_app_bundle = (self.system == "Darwin" and
                         os.path.exists(os.path.join(self.install_dir, "Contents")))

        if self.system == "Windows":
            expected_files = EXPECTED_FILES_WINDOWS
            expected_dirs = EXPECTED_DIRS_WINDOWS
        elif is_app_bundle:
            expected_files = EXPECTED_FILES_MACOS_APP
            expected_dirs = EXPECTED_DIRS_MACOS_APP
        else:
            expected_files = EXPECTED_FILES_UNIX
            expected_dirs = EXPECTED_DIRS_UNIX

        for f in expected_files:
            f = f.format(shlib=shlib, pyver=pyver)
            path = os.path.join(self.install_dir, f)
            if os.path.exists(path):
                self.ok(f"Found {f}")
            else:
                self.error(f"Missing file: {f}")

        for d in expected_dirs:
            d = d.format(pyver=pyver)
            path = os.path.join(self.install_dir, d)
            if os.path.isdir(path):
                self.ok(f"Found dir {d}")
            else:
                self.error(f"Missing directory: {d}")

    def check_binary_type(self):
        """Verify the main executable is the correct binary type."""
        print("\n=== Binary Type Checks ===")

        is_app_bundle = (self.system == "Darwin" and
                         os.path.exists(os.path.join(self.install_dir, "Contents")))

        if self.system == "Windows":
            exe = os.path.join(self.install_dir, "env", "Library", "bin", "tomviz.exe")
        elif is_app_bundle:
            exe = os.path.join(self.install_dir, "Contents", "env", "bin", "tomviz")
        else:
            exe = os.path.join(self.install_dir, "env", "bin", "tomviz")

        if not os.path.exists(exe):
            self.error(f"Executable not found: {exe}")
            return

        if self.system == "Windows":
            # Check it's a PE executable
            with open(exe, "rb") as f:
                magic = f.read(2)
            if magic == b"MZ":
                self.ok(f"tomviz.exe is a valid PE executable")
            else:
                self.error(f"tomviz.exe does not look like a PE executable")
        else:
            result = subprocess.run(["file", exe], capture_output=True, text=True)
            output = result.stdout
            if self.system == "Darwin":
                if "Mach-O" in output:
                    self.ok(f"tomviz is a Mach-O executable")
                else:
                    self.error(f"tomviz is not a Mach-O executable: {output.strip()}")
            else:
                if "ELF" in output:
                    self.ok(f"tomviz is an ELF executable")
                else:
                    self.error(f"tomviz is not an ELF executable: {output.strip()}")

    def check_library_deps(self):
        """Check for missing shared library dependencies."""
        print("\n=== Library Dependency Checks ===")

        is_app_bundle = (self.system == "Darwin" and
                         os.path.exists(os.path.join(self.install_dir, "Contents")))

        if self.system == "Windows":
            # Can't easily check DLL deps on Windows CI without dumpbin
            self.ok("Skipping library dep check on Windows (no ldd equivalent)")
            return

        if is_app_bundle:
            env_prefix = os.path.join(self.install_dir, "Contents", "env")
        else:
            env_prefix = os.path.join(self.install_dir, "env")

        exe = os.path.join(env_prefix, "bin", "tomviz")
        core_lib = None
        for ext in [".dylib", ".so"]:
            candidate = os.path.join(env_prefix, "lib", f"libtomvizcore{ext}")
            if os.path.exists(candidate):
                core_lib = candidate
                break

        binaries_to_check = [exe]
        if core_lib:
            binaries_to_check.append(core_lib)

        for binary in binaries_to_check:
            if not os.path.exists(binary):
                self.warn(f"Binary not found for dep check: {binary}")
                continue

            name = os.path.basename(binary)
            if self.system == "Darwin":
                result = subprocess.run(
                    ["otool", "-L", binary], capture_output=True, text=True)
                output = result.stdout
            else:
                result = subprocess.run(
                    ["ldd", binary], capture_output=True, text=True)
                output = result.stdout

            if "not found" in output:
                missing = [line.strip() for line in output.splitlines()
                           if "not found" in line]
                for m in missing:
                    self.error(f"{name}: {m}")
            else:
                self.ok(f"{name}: all library dependencies resolved")

    def check_prefix_leaks(self):
        """Check for conda build prefixes left in text files."""
        print("\n=== Prefix Leak Checks ===")

        is_app_bundle = (self.system == "Darwin" and
                         os.path.exists(os.path.join(self.install_dir, "Contents")))

        if is_app_bundle:
            env_prefix = os.path.join(self.install_dir, "Contents", "env")
        elif self.system == "Windows":
            env_prefix = os.path.join(self.install_dir, "env")
        else:
            env_prefix = os.path.join(self.install_dir, "env")

        # Common conda build prefix patterns
        prefix_patterns = [
            r"/home/conda/feedstock_root/",
            r"/Users/runner/miniforge3/",
            r"D:\\bld\\",
            r"/opt/conda/",
        ]

        # Check a sample of text files
        text_extensions = {".py", ".cfg", ".ini", ".conf", ".txt", ".sh", ".bat"}
        checked = 0
        leaked = 0

        for root, dirs, files in os.walk(env_prefix):
            for f in files:
                _, ext = os.path.splitext(f)
                if ext not in text_extensions:
                    continue

                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", errors="ignore") as fh:
                        content = fh.read(8192)  # Check first 8KB
                except (OSError, PermissionError):
                    continue

                checked += 1
                for pattern in prefix_patterns:
                    if re.search(pattern, content):
                        rel = os.path.relpath(filepath, self.install_dir)
                        self.warn(f"Possible prefix leak in {rel}: matches {pattern}")
                        leaked += 1
                        break

        if leaked == 0:
            self.ok(f"No prefix leaks found ({checked} text files checked)")
        else:
            self.warn(f"Found {leaked} files with possible prefix leaks")

    def check_size(self):
        """Check total size is within expected range."""
        print("\n=== Size Check ===")

        total = 0
        for root, dirs, files in os.walk(self.install_dir):
            for f in files:
                total += os.path.getsize(os.path.join(root, f))

        size_mb = total / (1024 * 1024)
        if size_mb < MIN_SIZE_MB:
            self.error(f"Install too small: {size_mb:.0f} MB (expected >= {MIN_SIZE_MB} MB)")
        elif size_mb > MAX_SIZE_MB:
            self.error(f"Install too large: {size_mb:.0f} MB (expected <= {MAX_SIZE_MB} MB)")
        else:
            self.ok(f"Install size: {size_mb:.0f} MB (within {MIN_SIZE_MB}-{MAX_SIZE_MB} MB range)")

    def run_all(self):
        """Run all verification checks."""
        print(f"Verifying Tomviz install at: {self.install_dir}")
        print(f"Platform: {self.system}")

        self.check_structure()
        self.check_binary_type()
        self.check_library_deps()
        self.check_prefix_leaks()
        self.check_size()

        print(f"\n{'='*40}")
        print(f"Results: {len(self.errors)} errors, {len(self.warnings)} warnings")

        if self.errors:
            print("\nErrors:")
            for e in self.errors:
                print(f"  - {e}")
            return False

        return True


def main():
    parser = argparse.ArgumentParser(description="Verify Tomviz standalone install")
    parser.add_argument("install_dir", help="Path to the install directory or .app bundle")
    parser.add_argument("--python-version", default="3.13")
    args = parser.parse_args()

    verifier = Verifier(args.install_dir, args.python_version)
    success = verifier.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
