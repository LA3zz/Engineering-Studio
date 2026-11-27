"""K1: use the real in-process kernel in the GUI entry point (``--stub`` keeps the stub) and
sync docs. Exact-match, idempotent. Run at the project root."""
from pathlib import Path

ROOT = Path(".")
D = ROOT / "docs" / "project"
MAIN = ROOT / "src" / "engstudio" / "gui" / "app_main.py"

EDITS = {
    MAIN: [
        ("``--smoke`` opens the window, quits after ~0.8 s, and does not read or write user "
         "settings.\n",
         "``--smoke`` opens the window, quits after ~0.8 s, and does not read or write user "
         "settings.\n``--stub`` uses the stub kernel instead of the interpreter "
         "(GUI development).\n"),
        ("    from engstudio.app.kernel.stub import StubKernelClient\n",
         "    from engstudio.app.kernel.inprocess import InProcessKernelClient\n"
         "    from engstudio.app.kernel.stub import StubKernelClient\n"),
        ('    smoke = "--smoke" in args\n    args = [a for a in args if a != "--smoke"]\n',
         '    smoke = "--smoke" in args\n    use_stub = "--stub" in args\n'
         '    args = [a for a in args if a not in ("--smoke", "--stub")]\n'),
        ("    window = MainWindow(\n"
         "        UiSettings(None if smoke else default_settings_path()), StubKernelClient()\n"
         "    )\n",
         "    client = StubKernelClient() if use_stub else InProcessKernelClient()\n"
         "    window = MainWindow(\n"
         "        UiSettings(None if smoke else default_settings_path()), client\n"
         "    )\n"),
    ],
    D / "TASKS.md": [
        ("disp/sprintf/fprintf/num2str/error/warning (pending user run)",
         "disp/sprintf/fprintf/num2str/error/warning (verified 2026-11-22)"),
        ("- [ ] K1 in-process kernel client + Command Window and Run/F5 hookup "
         "(first usable version)",
         "- [x] K1 `app.kernel.inprocess.InProcessKernelClient` (worker thread, cancel, "
         "workspace summary, command syntax for clear/clc/format/more, real toolbox list); "
         "GUI starts it by default (`--stub` = old stub) (pending user run)\n"
         "- [ ] K2 Run/F5 for the script editor, multi-line Command Window input, "
         "diagnostics click-to-line (needs main_window.py and the editor file)"),
    ],
    D / "HANDOFF.md": [
        ("Next in that series: K1 "
         "in-process kernel + Command Window and Run hookup (first usable version), then B1b "
         "(strings, struct/cell, cellfun/arrayfun, random, tic/toc) and B2 engine bindings "
         "(eig and the rest: attach the needed engine/*.py files).",
         "K1 done: `app.kernel.inprocess.InProcessKernelClient(threaded=True)` runs the real "
         "interpreter on a daemon worker thread (events from that thread; KernelBridge "
         "marshals), Interpreter.run(reset_cancel=False)/clear_cancel() make cancel race-free, "
         "`lang.display.short_text` feeds the Workspace browser, `to_function_syntax` turns "
         "`clear x`/`clc`/`format long`/`more` lines into calls. `python -m engstudio.gui` uses "
         "it by default (`--stub` for the stub). Next in that series: K2 (Run/F5 in the script "
         "editor, multi-line Command Window input; attach gui/main_window.py and the editor "
         "file), then B1b (strings, struct/cell, cellfun/arrayfun, random, tic/toc) and B2 "
         "engine bindings (eig and the rest: attach the needed engine/*.py files)."),
    ],
}
for path, pairs in EDITS.items():
    with open(path, newline="", encoding="utf-8") as fh:
        text = fh.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in pairs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            print(f"{path.name}: already applied")
        elif old in text:
            text = text.replace(old, new, 1)
            print(f"{path.name}: patched")
        else:
            raise SystemExit(f"{path}: expected text not found: {old[:60]!r}")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(text)
