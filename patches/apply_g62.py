"""Apply G6.2 edits to main_window.py and packaging/engstudio.spec (exact-match, idempotent).
Run from the project root: python patches\\apply_g62.py"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edit(path, pairs):
    if not path.exists():
        print(f"SKIP (missing): {path}")
        return
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("\r\n", "\n")
    for marker, old, new in pairs:
        if marker in text:
            print(f"already applied: {marker[:40]!r}")
            continue
        if text.count(old) != 1:
            raise SystemExit(f"ANCHOR NOT FOUND in {path.name}: {old[:60]!r}")
        text = text.replace(old, new)
        print(f"applied: {marker[:40]!r}")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace("\n", nl))


edit(ROOT / "src/engstudio/gui/main_window.py", [
    ("from engstudio.gui.docs_panel import DocsPanel",
     "from engstudio.gui.diagnostics_panel import DiagnosticsPanel\n",
     "from engstudio.gui.diagnostics_panel import DiagnosticsPanel\n"
     "from engstudio.gui.docs_panel import DocsPanel\n"),
    ("self.docs_panel = None",
     "            diagnostics if isinstance(diagnostics, DiagnosticsPanel) else None\n        )\n",
     "            diagnostics if isinstance(diagnostics, DiagnosticsPanel) else None\n        )\n"
     "        self.docs_panel = None\n"
     "        doc_id = next((k for k in self.docks if k.startswith(\"doc\")), None)\n"
     "        if doc_id is not None:\n"
     "            old = self.docks[doc_id].widget()\n"
     "            self.docs_panel = DocsPanel(theme=self.theme)\n"
     "            self.docks[doc_id].setWidget(self.docs_panel)\n"
     "            if old is not None:\n"
     "                old.deleteLater()\n"),
    ("self.docs_panel.set_theme",
     "            self.diagnostics_panel.set_theme(name)\n",
     "            self.diagnostics_panel.set_theme(name)\n"
     "        if self.docs_panel is not None:\n"
     "            self.docs_panel.set_theme(name)\n"),
])
edit(ROOT / "packaging/engstudio.spec", [
    ("resources\" / \"docs\"",
     "    datas=[],   # resources/docs/themes are added in later phases\n",
     "    datas=[(str(ROOT / \"src\" / \"engstudio\" / \"resources\" / \"docs\"),\n"
     "            \"engstudio/resources/docs\")],\n"),
])
