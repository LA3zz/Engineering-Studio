"""G5.1 patch: place plotting/model and add FigureUpdate to the kernel protocol
(exact-match, idempotent). Run from the project root: python patches\\apply_g51_patch.py"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "src/engstudio")

PROTOCOL = [
    ("from engstudio.core.diagnostics import Diagnostic\n",
     "from engstudio.core.diagnostics import Diagnostic\n"
     "from engstudio.plotting.model import FigureSpec\n"),
    ("Event = Stdout | Diagnostics | WorkspaceSummary | ExecutionFinished | ToolboxList\n",
     "@dataclass(frozen=True)\nclass FigureUpdate:\n"
     '    """Full snapshot of one figure (the GUI creates or replaces its window)."""\n\n'
     "    request_id: int\n    figure: FigureSpec\n\n\n"
     "Event = (\n    Stdout | Diagnostics | WorkspaceSummary | ExecutionFinished | ToolboxList\n"
     "    | FigureUpdate\n)\n"),
]


def place_model() -> None:
    """The package may have been scaffolded as plotting/model/ (package) or not at all."""
    module = SRC / "plotting" / "model.py"
    package = SRC / "plotting" / "model"
    if not package.is_dir():
        print("plotting/model.py in place")
        return
    if not module.exists():
        print("plotting/model/ package already holds the model")
        return
    init = package / "__init__.py"
    existing = init.read_text(encoding="utf-8-sig").strip() if init.exists() else ""
    if existing and existing != module.read_text(encoding="utf-8-sig").strip():
        sys.exit(f"{package} already holds code in __init__.py; send it to me before going on")
    init.write_text(module.read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
    module.unlink()  # a model.py next to a model/ package would be shadowed
    print("plotting/model/ package found: model code placed in its __init__.py")


def patch(path: Path, edits: list[tuple[str, str]]) -> None:
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in edits:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            continue  # already applied
        if text.count(old) != 1:
            sys.exit(f"{path.name}: expected text not found exactly once:\n{old}")
        text = text.replace(old, new)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"patched {path.name}")


place_model()
patch(SRC / "app" / "kernel" / "protocol.py", PROTOCOL)
