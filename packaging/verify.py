"""
Post-packaging verification for Tomviz standalone installers.

Checks:
1. Structural: expected files exist and are correct type
2. Library dependencies: no missing shared libraries
3. Prefix leaks: no conda build prefixes left behind
4. Artifact size: within expected range
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib


# Windows system DLLs that ship with the OS and don't need to be bundled.
WINDOWS_SYSTEM_DLL_RE = re.compile(
    r"^(KERNEL32|USER32|ADVAPI32|SHELL32|ole32|OLEAUT32|GDI32|COMCTL32|"
    r"WS2_32|CRYPT32|WINSPOOL|COMDLG32|IMM32|WINMM|ntdll|SETUPAPI|"
    r"WTSAPI32|NETAPI32|USERENV|dbghelp|PSAPI|VERSION|SHLWAPI|"
    r"MSVCRT|MSVCP|VCRUNTIME|api-ms-|ext-ms-)",
    re.IGNORECASE,
)


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

# Sample datasets bundled into the installers (see package.py install_sample_data).
SAMPLE_DATA_FILES = [
    "Recon_NanoParticle_doi_10.1021-nl103400a.emd",
    "TiltSeries_NanoParticle_doi_10.1021-nl103400a.emd",
]

# Minimum and maximum expected sizes in MB
MIN_SIZE_MB = 300
MAX_SIZE_MB = 8000


def write_png(path: str, width: int, height: int,
              rgb: tuple[int, int, int]) -> None:
    """Write a solid-color RGB PNG using only the standard library."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
                chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class Verifier:
    def __init__(self, install_dir: str, python_version: str = "3.13") -> None:
        self.install_dir: str = os.path.abspath(install_dir)
        self.python_version: str = python_version
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.system: str = platform.system()

    def error(self, msg: str) -> None:
        self.errors.append(msg)
        print(f"  FAIL: {msg}")

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        print(f"  WARN: {msg}")

    def ok(self, msg: str) -> None:
        print(f"  OK:   {msg}")

    def check_structure(self) -> None:
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

    def check_sample_data(self) -> None:
        """Verify the bundled sample datasets were installed.

        These live in share/tomviz/Data relative to the env, with the Windows
        layout mirroring it under Library/share. tomviz only shows the
        "Star Nanoparticle" Sample Data menu entries when they are present.
        """
        print("\n=== Sample Data Checks ===")

        is_app_bundle = (self.system == "Darwin" and
                         os.path.exists(os.path.join(self.install_dir, "Contents")))

        if self.system == "Windows":
            data_dir = os.path.join(
                self.install_dir, "env", "Library", "share", "tomviz", "Data")
        elif is_app_bundle:
            data_dir = os.path.join(
                self.install_dir, "Contents", "env", "share", "tomviz", "Data")
        else:
            data_dir = os.path.join(
                self.install_dir, "env", "share", "tomviz", "Data")

        for name in SAMPLE_DATA_FILES:
            path = os.path.join(data_dir, name)
            if os.path.isfile(path):
                self.ok(f"Found sample data {name}")
            else:
                self.error(
                    f"Missing sample data: {os.path.relpath(path, self.install_dir)}")

    def check_binary_type(self) -> None:
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

    def check_ffmpeg(self) -> None:
        """Verify the bundled ffmpeg: present, right build, and working.

        tomviz's movie export runs the ffmpeg executable found next to
        the tomviz binary and encodes H.264 with libx264, which only the
        conda-forge gpl variant provides. The encode check below mirrors
        tomviz's exact ffmpeg invocation (MovieExportDialog).
        """
        print("\n=== ffmpeg Checks ===")

        is_app_bundle = (self.system == "Darwin" and
                         os.path.exists(os.path.join(self.install_dir, "Contents")))

        if self.system == "Windows":
            env_prefix = os.path.join(self.install_dir, "env")
            ffmpeg = os.path.join(env_prefix, "Library", "bin", "ffmpeg.exe")
            license_dir = os.path.join(
                env_prefix, "Library", "share", "licenses", "ffmpeg")
        elif is_app_bundle:
            env_prefix = os.path.join(self.install_dir, "Contents", "env")
            ffmpeg = os.path.join(env_prefix, "bin", "ffmpeg")
            license_dir = os.path.join(
                env_prefix, "share", "licenses", "ffmpeg")
        else:
            env_prefix = os.path.join(self.install_dir, "env")
            ffmpeg = os.path.join(env_prefix, "bin", "ffmpeg")
            license_dir = os.path.join(
                env_prefix, "share", "licenses", "ffmpeg")

        if not os.path.isfile(ffmpeg):
            self.error(f"Missing ffmpeg executable: "
                       f"{os.path.relpath(ffmpeg, self.install_dir)}")
            return
        self.ok("Found ffmpeg executable")

        # GPL license text must accompany the GPL binary.
        gpl_text = os.path.join(license_dir, "COPYING.GPLv2")
        notice = os.path.join(license_dir, "NOTICE.txt")
        for path, label in [(gpl_text, "ffmpeg GPL license text"),
                            (notice, "ffmpeg source-availability notice")]:
            if os.path.isfile(path):
                self.ok(f"Found {label}")
            else:
                self.error(f"Missing {label}: "
                           f"{os.path.relpath(path, self.install_dir)}")

        # The right build: gpl variant with libx264 compiled in.
        result = subprocess.run([ffmpeg, "-version"],
                                capture_output=True, text=True)
        if result.returncode != 0:
            self.error(f"ffmpeg -version failed (exit {result.returncode}): "
                       f"{result.stderr.strip()[:200]}")
            return
        for flag in ["--enable-gpl", "--enable-libx264"]:
            if flag in result.stdout:
                self.ok(f"ffmpeg built with {flag}")
            else:
                self.error(f"ffmpeg missing {flag} (wrong variant bundled? "
                           "MP4 export needs the gpl build)")
                return

        # Functional: encode PNG frames to MP4 exactly like tomviz does.
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(8):
                write_png(os.path.join(tmp, f"frame.{i:06d}.png"),
                          64, 48, (32 * i % 256, 80, 160))
            out = os.path.join(tmp, "out.mp4")
            cmd = [
                ffmpeg, "-y", "-framerate", "30", "-start_number", "0",
                "-i", os.path.join(tmp, "frame.%06d.png"),
                "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", out,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if (result.returncode == 0 and os.path.isfile(out) and
                    os.path.getsize(out) > 0):
                self.ok(f"ffmpeg encoded a test MP4 "
                        f"({os.path.getsize(out)} bytes)")
            else:
                self.error("ffmpeg failed to encode a test MP4 "
                           f"(exit {result.returncode}): "
                           f"{result.stderr.strip()[-300:]}")

    def check_library_deps(self) -> None:
        """Check for missing shared library dependencies."""
        print("\n=== Library Dependency Checks ===")

        if self.system == "Windows":
            self._check_library_deps_windows()
        else:
            self._check_library_deps_unix()

    def _check_library_deps_unix(self) -> None:
        is_app_bundle = (self.system == "Darwin" and
                         os.path.exists(os.path.join(self.install_dir, "Contents")))

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
            tool = "otool" if self.system == "Darwin" else "ldd"
            args = [tool, "-L", binary] if tool == "otool" else [tool, binary]
            result = subprocess.run(args, capture_output=True, text=True)
            output = result.stdout

            if "not found" in output:
                missing = [line.strip() for line in output.splitlines()
                           if "not found" in line]
                for m in missing:
                    self.error(f"{name}: {m}")
            else:
                self.ok(f"{name}: all library dependencies resolved")

    def _check_library_deps_windows(self) -> None:
        if not shutil.which("dumpbin"):
            self.error("dumpbin not found on PATH — cannot verify DLL dependencies")
            return

        env_prefix = os.path.join(self.install_dir, "env")
        search_dirs = [
            os.path.join(env_prefix, "Library", "bin"),
            env_prefix,
        ]
        binaries_to_check = [
            os.path.join(env_prefix, "Library", "bin", "tomviz.exe"),
            os.path.join(env_prefix, "Library", "bin", "tomvizcore.dll"),
        ]

        for binary in binaries_to_check:
            if not os.path.exists(binary):
                self.warn(f"Binary not found for dep check: {binary}")
                continue

            name = os.path.basename(binary)
            result = subprocess.run(
                ["dumpbin", "/DEPENDENTS", binary],
                capture_output=True, text=True)
            if result.returncode != 0:
                self.error(f"{name}: dumpbin failed: {result.stderr.strip()}")
                continue

            # dumpbin prints dependencies under an "Image has the following
            # dependencies:" header, with a blank line before the first DLL
            # and one DLL per indented line. The "Summary" section follows.
            # Only parse inside that section — the header preamble
            # ("Dump of file <path>.dll") would otherwise be misread as a dep.
            deps = []
            in_section = False
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if not in_section:
                    if "following dependencies" in stripped.lower():
                        in_section = True
                    continue
                if not stripped:
                    continue  # blank lines inside the deps section are noise
                if stripped.lower().endswith(".dll"):
                    deps.append(stripped)
                else:
                    break  # first non-blank, non-DLL line ends the section

            missing = []
            for dll in deps:
                if WINDOWS_SYSTEM_DLL_RE.match(dll):
                    continue
                if not any(os.path.isfile(os.path.join(d, dll)) for d in search_dirs):
                    missing.append(dll)

            if missing:
                for dll in missing:
                    self.error(f"{name}: missing dependency {dll}")
            else:
                self.ok(f"{name}: all non-system DLL dependencies found "
                        f"({len(deps)} checked)")

    def check_prefix_leaks(self) -> None:
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

    def check_size(self) -> None:
        """Check total size is within expected range."""
        print("\n=== Size Check ===")

        total = 0
        for root, dirs, files in os.walk(self.install_dir):
            for f in files:
                path = os.path.join(root, f)
                try:
                    total += os.path.getsize(path)
                except OSError:
                    pass

        size_mb = total / (1024 * 1024)
        if size_mb < MIN_SIZE_MB:
            self.error(f"Install too small: {size_mb:.0f} MB (expected >= {MIN_SIZE_MB} MB)")
        elif size_mb > MAX_SIZE_MB:
            self.error(f"Install too large: {size_mb:.0f} MB (expected <= {MAX_SIZE_MB} MB)")
        else:
            self.ok(f"Install size: {size_mb:.0f} MB (within {MIN_SIZE_MB}-{MAX_SIZE_MB} MB range)")

    def run_all(self) -> bool:
        """Run all verification checks."""
        print(f"Verifying Tomviz install at: {self.install_dir}")
        print(f"Platform: {self.system}")

        self.check_structure()
        self.check_sample_data()
        self.check_binary_type()
        self.check_ffmpeg()
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Tomviz standalone install")
    parser.add_argument("install_dir", help="Path to the install directory or .app bundle")
    parser.add_argument("--python-version", default="3.13")
    args = parser.parse_args()

    verifier = Verifier(args.install_dir, args.python_version)
    success = verifier.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
