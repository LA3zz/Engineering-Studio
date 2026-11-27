"""The user manual (tools/make_manual.py) covers everything and its examples run.

Edge (the PDF printer) is not used here; ``build_html`` and the reference builders are.
"""

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def manual():
    spec = importlib.util.spec_from_file_location("make_manual", ROOT / "tools" / "make_manual.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_toolbox_reference_covers_every_function(manual):
    from engstudio.app.toolbox_bindings import load_toolboxes

    ref = manual.toolbox_reference()
    names = [s.name for _n, _d, specs in load_toolboxes() for s in specs]
    missing = [n for n in names if f'id="fn-{n}"' not in ref]
    assert not missing and len(names) == 85, missing


def test_block_reference_covers_every_block(manual):
    ref = manual.block_reference()
    from engstudio.sim.blocks import BLOCK_TYPES

    missing = [n for n in BLOCK_TYPES if f'id="blk-{manual.slug(n)}"' not in ref]
    assert not missing and len(BLOCK_TYPES) >= 34, missing


def test_command_reference_covers_every_core_command(manual):
    from engstudio.app.kernel.inprocess import _CATEGORIES

    ref = manual.command_reference()
    names = [n for _k, (_t, ns) in _CATEGORIES.items() for n in ns]
    missing = [n for n in names if f"<td><code>{manual.E(n)}</code></td>" not in ref]
    assert not missing, missing


def test_manual_builds_with_working_links_and_examples(manual, tmp_path, monkeypatch):
    monkeypatch.setattr(manual, "OUT_HTML", tmp_path / "manual.html")
    page = manual.build_html()  # also runs every example of the chapters (raises on failure)
    text = page.read_text(encoding="utf-8")
    ids = set(re.findall(r'id="([^"]+)"', text))
    targets = set(re.findall(r"href=['\"]#([^'\"]+)['\"]", text))
    assert not targets - ids, f"broken links: {sorted(targets - ids)}"
    assert "<!--REF:" not in text and "Contents" in text
    for chapter in ("Simulation (block diagrams)", "Toolbox function reference",
                    "Simulation block reference", "Command reference", "Lab data files"):
        assert chapter in text
