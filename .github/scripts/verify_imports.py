"""
Smoke-test that the bundled Python in a packaged Tomviz install can import
the tomviz package and its key submodules.

Intended to be run with the bundled interpreter from a packaged install, e.g.:
    env/bin/python verify_imports.py             (Linux/macOS)
    env\\python.exe verify_imports.py            (Windows)
"""

import importlib

REQUIRED = [
    "tomviz",
    "tomviz.cli",
    "tomviz._wrapping",
    "tomviz._realtime.ctvlib",
    "tomopy",
    "pystackreg",
    "itk",
]


def main():
    for mod in REQUIRED:
        importlib.import_module(mod)
        print(f"  OK: import {mod}")

    print("Python imports OK")


if __name__ == "__main__":
    main()
