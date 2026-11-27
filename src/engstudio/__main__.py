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
    parser.add_argument("--run", metavar="SCRIPT",
                        help="run an .m script without the GUI, print its output and exit "
                             "(0 = ran without error)")
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
    if args.run:
        return run_script(args.run)
    print(f"{APP_NAME} {__version__}: start the desktop app with EngineeringStudio.exe or "
          "'python -m engstudio.gui'.")
    return 0


def run_script(path: str) -> int:
    """Run ``path`` in the real kernel without a GUI (figures are computed but not shown)."""
    from pathlib import Path

    from engstudio.app.kernel.inprocess import InProcessKernelClient
    from engstudio.app.kernel.protocol import Diagnostics, ExecutionFinished, Stdout

    script = Path(path)
    try:
        code = script.read_text(encoding="utf-8-sig")
    except OSError as exc:
        print(f"cannot read {script}: {exc}", file=sys.stderr)
        return 2
    kernel = InProcessKernelClient(threaded=False)
    status: list[str] = []

    def on_event(event: object) -> None:
        if isinstance(event, Stdout):
            sys.stdout.write(event.text)
        elif isinstance(event, Diagnostics):
            for d in event.items:
                where = f" ({d.location})" if d.location else ""
                print(f"[{d.severity}] {d.message}{where}", file=sys.stderr)
        elif isinstance(event, ExecutionFinished):
            status.append(event.status)

    kernel.subscribe(on_event)
    kernel.execute(code, str(script.resolve()))
    kernel.shutdown()
    return 0 if status == ["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
