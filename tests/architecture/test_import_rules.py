"""Enforces the layer rules from docs/project/ARCHITECTURE.md section 2.

The checker works on any source root, so it is itself tested on synthetic trees.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = "engstudio"
SRC = Path(__file__).resolve().parents[2] / "src"

_L1 = {"core", "engine", "control", "data", "plotting"}
# Which top-level engstudio packages each package may import (besides itself).
ALLOWED: dict[str, set[str]] = {
    "core": set(),
    "engine": {"core"},
    "control": {"core"},
    "data": {"core"},
    "plotting": {"core"},
    "lang": set(_L1),
    "sim": set(_L1),
    "toolboxes": set(_L1),
    "app": {"core", "engine", "control", "data", "plotting", "lang", "sim", "toolboxes"},
    "gui": {"core", "app", "plotting", "sim"},
}
# gui may only touch these pure-data modules of plotting/sim.
GUI_DATA_MODULES = (
    "engstudio.plotting.model",
    "engstudio.plotting.text",
    "engstudio.sim.model",
    "engstudio.sim.serialization",
)
QT_LIBS = {"PySide6", "PyQt5", "PyQt6", "pyqtgraph", "pyvista", "pyvistaqt", "vtk"}
QT_ALLOWED_IN = "engstudio.gui"
# The bundle probe must touch every third-party library, wherever it normally lives.
THIRD_PARTY_EXEMPT = ("engstudio.selftest",)
MPL_ALLOWED_IN = ("engstudio.plotting.export", "engstudio.gui.mpl_view")


@dataclass(frozen=True)
class Imp:
    module: str
    target: str
    line: int
    type_only: bool


@dataclass(frozen=True)
class Third:
    module: str
    top: str
    line: int


@dataclass(frozen=True)
class Graph:
    modules: dict[str, bool]  # module name -> is_package
    imports: tuple[Imp, ...]
    third: tuple[Third, ...]
    missing_init: tuple[str, ...]


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _scan(node: ast.AST, in_tc: bool):
    if isinstance(node, ast.Import | ast.ImportFrom):
        yield node, in_tc
    elif isinstance(node, ast.If) and _is_type_checking(node.test):
        for stmt in node.body:
            yield from _scan(stmt, True)
        for stmt in node.orelse:
            yield from _scan(stmt, in_tc)
    else:
        for child in ast.iter_child_nodes(node):
            yield from _scan(child, in_tc)


def load_graph(src_root: Path) -> Graph:
    pkg_dir = src_root / ROOT
    modules: dict[str, bool] = {}
    paths: dict[str, Path] = {}
    for path in sorted(pkg_dir.rglob("*.py")):
        parts = list(path.relative_to(src_root).with_suffix("").parts)
        is_pkg = parts[-1] == "__init__"
        if is_pkg:
            parts = parts[:-1]
        name = ".".join(parts)
        modules[name] = is_pkg
        paths[name] = path
    missing = tuple(
        sorted(
            str(d.relative_to(src_root))
            for d in pkg_dir.rglob("*")
            if d.is_dir() and d.name != "__pycache__" and not (d / "__init__.py").exists()
        )
    )
    imports: list[Imp] = []
    third: list[Third] = []
    for name, path in paths.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node, in_tc in _scan(tree, False):
            raw: list[str] = []
            if isinstance(node, ast.Import):
                raw = [a.name for a in node.names]
            else:
                if node.level:
                    base = name.split(".") if modules[name] else name.split(".")[:-1]
                    if node.level - 1 > len(base):
                        raise ValueError(f"{name}:{node.lineno}: relative import beyond top")
                    base = base[: len(base) - (node.level - 1)]
                    mod = ".".join(base + ([node.module] if node.module else []))
                else:
                    mod = node.module or ""
                for alias in node.names:
                    cand = f"{mod}.{alias.name}"
                    raw.append(cand if cand in modules else mod)
            for target in raw:
                if target == ROOT or target.startswith(ROOT + "."):
                    imports.append(Imp(name, target, node.lineno, in_tc))
                else:
                    third.append(Third(name, target.split(".")[0], node.lineno))
    return Graph(modules, tuple(imports), tuple(third), missing)


def _pkg(name: str, modules: dict[str, bool]) -> str | None:
    parts = name.split(".")
    if len(parts) >= 2 and modules.get(f"{ROOT}.{parts[1]}") is True:
        return parts[1]
    return None


def _under(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def check_layers(g: Graph) -> list[str]:
    errs: list[str] = []
    for d in g.missing_init:
        errs.append(f"directory {d} has no __init__.py (layer checks would skip it)")
    for name, is_pkg in g.modules.items():
        if is_pkg and name.count(".") == 1 and name.split(".")[1] not in ALLOWED:
            errs.append(f"{name}: unknown top-level package; add it to the layer table and docs")
    for imp in g.imports:
        src, dst = _pkg(imp.module, g.modules), _pkg(imp.target, g.modules)
        where = f"{imp.module}:{imp.line} imports {imp.target}"
        if src is None or dst is None or src not in ALLOWED:
            continue
        if src == dst:
            if src == "toolboxes":
                a, b = imp.module.split("."), imp.target.split(".")
                if len(a) >= 3 and len(b) >= 3 and a[2] != b[2]:
                    errs.append(f"{where}: toolboxes may not import other toolboxes")
            continue
        if dst not in ALLOWED[src]:
            errs.append(f"{where}: layer violation ({src} -> {dst} not allowed)")
        elif src == "gui" and dst in {"plotting", "sim"}:
            is_root = imp.target == f"{ROOT}.{dst}"
            ok = is_root or any(_under(imp.target, m) for m in GUI_DATA_MODULES)
            if not ok:
                errs.append(f"{where}: gui may only import pure-data plotting/sim modules")
    for t in g.third:
        if any(_under(t.module, m) for m in THIRD_PARTY_EXEMPT):
            continue
        where = f"{t.module}:{t.line} imports {t.top}"
        if t.top in QT_LIBS and not _under(t.module, QT_ALLOWED_IN):
            errs.append(f"{where}: Qt/3D libraries are only allowed in engstudio.gui")
        if t.top == "matplotlib" and not any(_under(t.module, m) for m in MPL_ALLOWED_IN):
            errs.append(f"{where}: matplotlib is only allowed in {MPL_ALLOWED_IN}")
    return errs


def find_cycles(g: Graph) -> list[list[str]]:
    edges: dict[str, set[str]] = {m: set() for m in g.modules}
    for imp in g.imports:
        if not imp.type_only and imp.target in g.modules and imp.target != imp.module:
            edges[imp.module].add(imp.target)
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cycles: list[list[str]] = []

    def strong(v: str) -> None:
        index[v] = low[v] = len(index)
        stack.append(v)
        on_stack.add(v)
        for w in sorted(edges[v]):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                cycles.append(sorted(comp))

    for m in sorted(g.modules):
        if m not in index:
            strong(m)
    return cycles


# ---------------------------------------------------------------- real source tree

def test_source_tree_exists():
    assert (SRC / ROOT / "__init__.py").exists()


def test_layer_rules_hold_in_src():
    assert check_layers(load_graph(SRC)) == []


def test_no_import_cycles_in_src():
    assert find_cycles(load_graph(SRC)) == []


# ---------------------------------------------------------------- checker self-tests

def make_tree(root: Path, files: dict[str, str]) -> Graph:
    (root / ROOT).mkdir(parents=True, exist_ok=True)
    (root / ROOT / "__init__.py").write_text("", encoding="utf-8")
    for rel, text in files.items():
        path = root / ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        d = path.parent
        while d != root / ROOT:
            (d / "__init__.py").touch()
            d = d.parent
    return load_graph(root)


def test_detects_upward_import(tmp_path):
    g = make_tree(tmp_path, {"core/a.py": "import engstudio.engine.b\n", "engine/b.py": ""})
    errs = check_layers(g)
    assert len(errs) == 1 and "core -> engine" in errs[0]


def test_detects_relative_upward_import(tmp_path):
    g = make_tree(tmp_path, {"core/a.py": "from ..engine import b\n", "engine/b.py": ""})
    assert any("core -> engine" in e for e in check_layers(g))


def test_allows_downward_and_same_package(tmp_path):
    g = make_tree(
        tmp_path,
        {
            "core/a.py": "",
            "engine/b.py": "from engstudio.core import a\nfrom . import c\n",
            "engine/c.py": "",
        },
    )
    assert check_layers(g) == []


def test_l2_packages_cannot_import_each_other(tmp_path):
    g = make_tree(tmp_path, {"lang/a.py": "import engstudio.sim.b\n", "sim/b.py": ""})
    assert any("lang -> sim" in e for e in check_layers(g))


def test_toolboxes_isolated_from_each_other(tmp_path):
    files = {
        "toolboxes/mech/f.py": "import engstudio.toolboxes.fluids.g\n",
        "toolboxes/fluids/g.py": "",
        "toolboxes/mech/h.py": "",
    }
    errs = check_layers(make_tree(tmp_path, files))
    assert len(errs) == 1 and "other toolboxes" in errs[0]


def test_toolbox_may_import_own_modules(tmp_path):
    files = {"toolboxes/mech/f.py": "from engstudio.toolboxes.mech import h\n",
             "toolboxes/mech/h.py": ""}
    assert check_layers(make_tree(tmp_path, files)) == []


def test_gui_limited_to_pure_data_modules(tmp_path):
    files = {
        "sim/model.py": "",
        "sim/compiler.py": "",
        "gui/ok.py": "from engstudio.sim.model import Model\n",
        "gui/bad.py": "import engstudio.sim.compiler\n",
        "gui/worse.py": "import engstudio.lang.x\n",
        "lang/x.py": "",
    }
    errs = check_layers(make_tree(tmp_path, files))
    assert any("gui.bad" in e and "pure-data" in e for e in errs)
    assert any("gui.worse" in e and "gui -> lang" in e for e in errs)
    assert not any("gui.ok" in e for e in errs)


def test_qt_only_in_gui(tmp_path):
    files = {
        "engine/a.py": "import PySide6.QtCore\n",
        "gui/w.py": "from PySide6 import QtWidgets\n",
    }
    errs = check_layers(make_tree(tmp_path, files))
    assert len(errs) == 1 and "engine.a" in errs[0]


def test_matplotlib_only_in_plotting_export(tmp_path):
    files = {
        "plotting/model.py": "import matplotlib\n",
        "plotting/export.py": "import matplotlib\n",
    }
    errs = check_layers(make_tree(tmp_path, files))
    assert len(errs) == 1 and "plotting.model" in errs[0]


def test_lazy_import_inside_function_is_checked(tmp_path):
    g = make_tree(
        tmp_path,
        {"core/a.py": "def f():\n    import engstudio.gui.w\n", "gui/w.py": ""},
    )
    assert any("core -> gui" in e for e in check_layers(g))


def test_unknown_package_and_missing_init_reported(tmp_path):
    g = make_tree(tmp_path, {"mystery/a.py": ""})
    assert any("unknown top-level package" in e for e in check_layers(g))
    (tmp_path / ROOT / "core").mkdir()
    (tmp_path / ROOT / "core" / "x.py").write_text("", encoding="utf-8")
    assert any("no __init__.py" in e for e in check_layers(load_graph(tmp_path)))


def test_detects_cycle(tmp_path):
    files = {
        "engine/a.py": "import engstudio.engine.b\n",
        "engine/b.py": "import engstudio.engine.a\n",
    }
    cycles = find_cycles(make_tree(tmp_path, files))
    assert cycles == [["engstudio.engine.a", "engstudio.engine.b"]]


def test_type_checking_import_does_not_create_cycle(tmp_path):
    files = {
        "engine/a.py": "import engstudio.engine.b\n",
        "engine/b.py": (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    import engstudio.engine.a\n"
        ),
    }
    assert find_cycles(make_tree(tmp_path, files)) == []


def test_selftest_probe_is_exempt_only_for_third_party_rules(tmp_path):
    files = {
        "selftest.py": "import matplotlib\nimport PySide6\n",
        "core/a.py": "import matplotlib\n",
    }
    errs = check_layers(make_tree(tmp_path, files))
    assert len(errs) == 1 and "core.a" in errs[0]
