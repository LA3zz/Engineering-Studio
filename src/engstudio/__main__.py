"""Command-line entry point: ``python -m engstudio``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from engstudio.version import APP_NAME, __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="engstudio", description=APP_NAME)
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument("--selftest", action="store_true",
                        help="run built-in environment checks and exit (0 = all passed)")
    parser.add_argument("--selftest-gui", action="store_true",
                        help="open a test window briefly and exit")
    args = parser.parse_args(argv)
    if args.version:
        print(f"{APP_NAME} {__version__}")
        return 0
    if args.selftest:
        from engstudio.selftest import run_selftest

        return run_selftest()
    if args.selftest_gui:
        from engstudio.selftest import run_gui_check

        return run_gui_check()
    print(f"{APP_NAME} {__version__} - the GUI is not implemented yet (Phase 4).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
