"""PyInstaller entry point. ``freeze_support`` is required for spawned child processes."""

import multiprocessing
import sys


def _run() -> int:
    multiprocessing.freeze_support()
    from engstudio.__main__ import main

    return main()


if __name__ == "__main__":
    sys.exit(_run())
