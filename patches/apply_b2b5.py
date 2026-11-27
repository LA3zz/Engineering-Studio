"""Apply B2b-5 (symbolic values): engine helpers, SymValue, interpreter hooks, kernel wiring."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "docs" / "project"

ENGINE_BLOCK = '''

# -- helpers for the interpreter's symbolic values (B2b-5) -------------------------------------
__all__ = [*__all__, "apply_function", "arith", "as_symexpr", "default_variable", "equation",
           "is_symbol", "negate", "residual_form", "symbol", "to_text"]


def as_symexpr(x: object) -> SymExpr:
    """``SymExpr`` from a ``SymExpr``, text or a number."""
    return SymExpr(_expr(x))


def symbol(name: str) -> SymExpr:
    """A plain symbol (reserved function/constant names are rejected)."""
    return SymExpr(_symbol(name))


def is_symbol(x: object) -> bool:
    return isinstance(x, SymExpr) and isinstance(x.expr, sp.Symbol)


def arith(op: str, a: object, b: object) -> SymExpr:
    """``a op b`` for op in ``+ - * / ^``; division by zero, huge exponents and undefined
    results raise ``ValidationError``."""
    if op not in ("+", "-", "*", "/", "^"):
        raise ValidationError(f"arith: unsupported operator {op!r}")
    x, y = _expr(a), _expr(b)
    if op == "/" and y == 0:
        raise ValidationError("division by zero")
    if op == "^" and y.is_Number and abs(y) > MAX_EXPONENT:
        raise ValidationError(f"exponent too large (limit {MAX_EXPONENT})")
    result = {"+": lambda: x + y, "-": lambda: x - y, "*": lambda: x * y,
              "/": lambda: x / y, "^": lambda: x**y}[op]()
    if result.has(sp.nan, sp.zoo):
        raise ValidationError("the result is undefined (division by zero or similar)")
    return SymExpr(result)


def negate(a: object) -> SymExpr:
    return SymExpr(-_expr(a))


def equation(a: object, b: object) -> SymExpr:
    """The equation ``a == b`` as a ``SymExpr`` (use ``residual_form`` before solving)."""
    return SymExpr(sp.Eq(_expr(a), _expr(b)))


def residual_form(x: object) -> SymExpr:
    """``lhs - rhs`` of an equation (text with one ``=`` or an equation object); an expression
    is taken as ``expr = 0``."""
    e = _expr(x) if isinstance(x, SymExpr) else _equation(x)
    if isinstance(e, sp.Equality):
        e = e.lhs - e.rhs
    return SymExpr(e)


def apply_function(name: str, x: object) -> SymExpr:
    """Apply one of ``FUNCTIONS`` (sin, exp, sqrt, ...) to an expression."""
    if name not in _FUNCS:
        raise ValidationError(f"unknown function {name!r}")
    result = _FUNCS[name](_expr(x))
    if result.has(sp.nan, sp.zoo):
        raise ValidationError(f"{name}: the result is undefined")
    return SymExpr(result)


def default_variable(expr: object) -> str:
    """Default variable: the only symbol, else the one closest to 'x' (later letter on ties);
    ``'x'`` for an expression without symbols."""
    e = _equation(expr) if isinstance(expr, str) else _expr(expr)
    names = sorted(s.name for s in e.free_symbols)
    if not names:
        return "x"
    return min(names, key=lambda n: (abs(ord(n[0].lower()) - ord("x")), -ord(n[0]), n))


def to_text(x: SymExpr) -> str:
    """MATLAB-style text: ``^`` for powers, ``lhs == rhs`` for equations."""
    e = x.expr
    if isinstance(e, sp.Equality):
        return f"{sp.sstr(e.lhs)} == {sp.sstr(e.rhs)}".replace("**", "^")
    return sp.sstr(e).replace("**", "^")
'''

VALUES_CLASS = '''class SymValue:
    """A symbolic scalar: wraps ``engine.symbolic.SymExpr`` (class ``sym``). Immutable."""

    __slots__ = ("expr",)

    def __init__(self, expr: object) -> None:
        self.expr = expr

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SymValue) and str(self.expr) == str(other.expr)

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"SymValue({self.expr})"


'''
RULE = "# ------------------------------------------------------------------ predicates\n"


def read(path: Path) -> str:
    with open(path, newline="", encoding="utf-8") as fh:
        return fh.read()


def write(path: Path, text: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(text)


def edit(path: Path, pairs: list) -> None:
    """Exact-match edits; a pair whose new text is already present is skipped (idempotent)."""
    if not path.exists():
        print(f"SKIP (missing): {path}")
        return
    text = read(path)
    nl = "\r\n" if "\r\n" in text else "\n"
    done = 0
    for old, new in pairs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            done += 1
            continue
        if text.count(old) != 1:
            raise SystemExit(f"{path.name}: expected exactly one match for:\n{old}")
        text = text.replace(old, new)
    if done == len(pairs):
        print(f"already patched: {path.name}")
        return
    write(path, text)
    print(f"patched: {path.name}")


def append(path: Path, block: str, marker: str) -> None:
    if not path.exists():
        print(f"SKIP (missing): {path}")
        return
    text = read(path)
    if marker in text:
        print(f"already patched: {path.name}")
        return
    nl = "\r\n" if "\r\n" in text else "\n"
    write(path, text.rstrip() + nl + nl + block.replace("\n", nl) + nl)
    print(f"patched: {path.name}")


append(ROOT / "src/engstudio/engine/symbolic.py", ENGINE_BLOCK.strip("\n"), "def apply_function")

edit(ROOT / "src/engstudio/lang/values.py", [
    ("    return isinstance(x, (CharArray, CellArray, StructValue, FunctionHandle))\n",
     "    return isinstance(x, (CharArray, CellArray, StructValue, FunctionHandle, SymValue))\n"),
    ('    if isinstance(v, FunctionHandle):\n        return "function_handle"\n',
     '    if isinstance(v, FunctionHandle):\n        return "function_handle"\n'
     '    if isinstance(v, SymValue):\n        return "sym"\n'),
    (RULE, VALUES_CLASS + RULE),
])

edit(ROOT / "src/engstudio/lang/interp.py", [
    ("from engstudio.lang import ops\n",
     "from engstudio.lang import ops, symops\n"),
    ("[self._guard(node, ops.unary_op, node.op, self.one(node.operand, env))]",
     "[self._guard(node, symops.unary_op, node.op, self.one(node.operand, env))]"),
    ("""[self._guard(node, ops.transpose, operand, node.op == "'")]""",
     """[self._guard(node, symops.transpose, operand, node.op == "'")]"""),
    ("self._guard(node, ops.binary_op, node.op, left_value, right_value, diags)",
     "self._guard(node, symops.binary_op, node.op, left_value, right_value, diags)"),
    ("[self._guard(node, ops.build_matrix, rows)]",
     "[self._guard(node, symops.build_matrix, rows)]"),
])

edit(ROOT / "src/engstudio/app/kernel/inprocess.py", [
    ("from engstudio.lang.display import format_value, short_text\n",
     "from engstudio.lang.builtins_sym import display_text, install_sym, preview_text\n"),
    ("Stdout(self.request_id, format_value(name, value))",
     "Stdout(self.request_id, display_text(name, value))"),
    ("size_of(ws[name]), short_text(ws[name])", "size_of(ws[name]), preview_text(ws[name])"),
    ("        install_analysis(self._interp)\n",
     "        install_analysis(self._interp)\n        install_sym(self._interp)\n"),
    ('r"^(\\s*)(clear|clearvars|clc|format|more|close)"',
     'r"^(\\s*)(clear|clearvars|clc|format|more|close|syms)"'),
    ('    "odes": ("Differential equations", ("ode45", "ode23", "ode15s")),\n',
     '    "odes": ("Differential equations", ("ode45", "ode23", "ode15s")),\n'
     '    "symbolic": ("Symbolic math", (\n'
     '        "syms", "sym", "int", "limit", "taylor", "solve", "simplify", "expand", "factor",\n'
     '        "subs", "laplace", "ilaplace", "latex", "symvar")),\n'),
])

edit(ROOT / "src/engstudio/lang/builtins_analysis.py", [
    ("from engstudio.engine import optimize\n"
     "from engstudio.engine import interp as engine_interp\n",
     "from engstudio.engine import interp as engine_interp\n"
     "from engstudio.engine import optimize\n"),
])

append(D / "CHANGELOG.md",
       "## B2b-5 (2026-11-25)\n- Symbolic values: `SymValue` (class `sym`) in `lang.values`, "
       "operator hooks `lang.symops`, builtins `lang.builtins_sym` (syms, sym, diff, int, limit, "
       "taylor, solve, simplify, expand, factor, subs, laplace, ilaplace, latex, symvar, "
       "double/char/disp/elementary overloads), engine helpers in `engine.symbolic`, "
       "`syms x y` command syntax, symbolic display in the Command Window and Workspace.",
       "B2b-5 (2026-11-25)")
append(D / "TEST_STATUS.md",
       "## B2b-5 (2026-11-25)\n- tests/lang/test_builtins_sym.py, tests/engine/"
       "test_symbolic_ext.py: PENDING user run.", "B2b-5 (2026-11-25)")
append(D / "HANDOFF.md",
       "## B2b-5 (2026-11-25)\n- Symbolic scalars are a value class (`SymValue`, class `sym`); "
       "interpreter operators go through `lang.symops` (patched call sites in `lang.interp`); "
       "`install_sym` runs last in InProcessKernelClient and wraps double/char/disp/diff and the "
       "elementary functions. No symbolic vectors/matrices; `solve` returns sym / cell / "
       "struct (see builtins_sym docstring). Pending user run. Not done: matlabFunction "
       "(sym -> handle). Next: Phase 4 close-out list.", "B2b-5 (2026-11-25)")
edit(D / "TASKS.md", [
    ("  - [ ] B2b-5 symbolic bindings (needs a value-model decision)",
     "  - [x] B2b-5 symbolic values + builtins (`SymValue`, `lang.symops`, `lang.builtins_sym`) "
     "(pending user run)"),
])
