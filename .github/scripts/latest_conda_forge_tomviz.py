"""
Print the latest tomviz version and build string from conda-forge as
"<version> <build_string>". Used by the packaging workflow to decide
whether a new build is needed.

Uses the anaconda.org per-package API rather than the full conda-forge
repodata (which is hundreds of MB).

Usage:
    python latest_conda_forge_tomviz.py <python_version>

Example:
    python latest_conda_forge_tomviz.py 3.13
"""

from __future__ import annotations

import json
import sys
import urllib.request
from typing import Any


API_URL = "https://api.anaconda.org/package/conda-forge/tomviz"
SUBDIR = "linux-64"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <python_version>")
    python_version = sys.argv[1]
    py_prefix = "py" + python_version.replace(".", "")

    data: dict[str, Any] = json.loads(urllib.request.urlopen(API_URL).read())
    files = [
        f for f in data.get("files", [])
        if f.get("attrs", {}).get("subdir") == SUBDIR
        # Only consider main-channel releases. Pre-release builds (e.g. betas)
        # are uploaded to other anaconda.org labels such as "beta", and the
        # anaconda API returns files for every label, so we must filter here
        # to keep packaging from picking up a beta as the "latest" version.
        and "main" in f.get("labels", [])
    ]

    if not files:
        sys.exit(f"No tomviz packages found for {SUBDIR} on conda-forge")

    # Fail loudly rather than falling back to every build: silently picking
    # a package built for another Python produces an environment that either
    # fails to solve or, worse, packages the wrong interpreter's extensions.
    matching = [
        f for f in files
        if f.get("attrs", {}).get("build", "").startswith(py_prefix)
    ]
    if not matching:
        available = sorted({
            f.get("attrs", {}).get("build", "").split("h")[0]
            for f in files
        })
        sys.exit(
            f"No tomviz build for Python {python_version} ({py_prefix}) on "
            f"conda-forge {SUBDIR}. Available: {', '.join(available)}. "
            "Wait for the feedstock to publish that Python version before "
            "bumping PYTHON_VERSION."
        )

    def ver_key(f: dict[str, Any]) -> tuple[tuple[int, ...], int]:
        parts = tuple(int(x) for x in f["version"].split(".") if x.isdigit())
        return (parts, f["attrs"].get("build_number", 0))

    latest = sorted(matching, key=ver_key)[-1]
    print(latest["version"], latest["attrs"]["build"])


if __name__ == "__main__":
    main()
