"""
Print the latest tomviz version and build string from conda-forge as
"<version> <build_string>". Used by the packaging workflow to decide
whether a new build is needed.

Usage:
    python latest_conda_forge_tomviz.py <python_version>

Example:
    python latest_conda_forge_tomviz.py 3.13
"""

import json
import sys
import urllib.request


REPODATA_URL = "https://conda.anaconda.org/conda-forge/linux-64/repodata.json"


def main():
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <python_version>")
    python_version = sys.argv[1]

    data = json.loads(urllib.request.urlopen(REPODATA_URL).read())
    packages = [
        info for info in {
            **data.get("packages", {}),
            **data.get("packages.conda", {}),
        }.values()
        if info.get("name") == "tomviz"
    ]

    py_prefix = "py" + python_version.replace(".", "")
    matching = [p for p in packages if p["build"].startswith(py_prefix)] or packages

    def ver_key(p):
        parts = tuple(int(x) for x in p["version"].split(".") if x.isdigit())
        return (parts, p["build_number"])

    latest = sorted(matching, key=ver_key)[-1]
    print(latest["version"], latest["build"])


if __name__ == "__main__":
    main()
