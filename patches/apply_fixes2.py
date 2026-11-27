"""Fixes: vector norms, same-line command syntax, error-identifier test, tool lint. Idempotent."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NORM_OLD = (
    '        p = _norm_kind(args[1]) if len(args) == 2 else 2\n'
    '        return [_scalar(float(linalg.norm(_linalg_matrix(args[0], "norm"), p)))]\n'
)
NORM_NEW = (
    '        p = _norm_kind(args[1]) if len(args) == 2 else 2\n'
    '        x = _linalg_matrix(args[0], "norm")\n'
    '        if x.size and 1 in x.shape:  # vector: p-norm of the elements\n'
    '            if p == "fro":\n'
    '                p = 2\n'
    '            if p < 1:\n'
    '                raise ValidationError("norm: p of a vector p-norm must be at least 1.")\n'
    '            return [_scalar(float(np.linalg.norm(x.ravel(order="F"), ord=p)))]\n'
    '        return [_scalar(float(linalg.norm(x, p)))]\n'
)

REGEX_OLD = r'''_COMMAND = re.compile(
    r"^(\s*)(clear|clearvars|clc|format|more|close|syms)"
    r"((?:[ \t]+[A-Za-z_][\w.*]*)*)[ \t]*([;,]?)[ \t]*(%.*)?$"
)
'''
REGEX_NEW = r'''_COMMAND = re.compile(
    r"^(\s*)(clear|clearvars|clc|format|more|close|syms)"
    r"((?:[ \t]+[A-Za-z_][\w.*]*)*)[ \t]*(?:([;,])[ \t]*(.*)|(%.*))?$"
)
'''
FUNC_OLD = '''def to_function_syntax(code: str) -> str:
    """Rewrite command-style lines (``clear x y``) as calls; line numbers are preserved."""
    lines = code.split("\\n")
    for i, line in enumerate(lines):
        m = _COMMAND.match(line)
        if m:
            indent, word, args, term, _comment = m.groups()
            call = ", ".join(f"'{a}'" for a in args.split())
            lines[i] = f"{indent}{word}({call}){term}"
    return "\\n".join(lines)
'''
FUNC_NEW = '''def _rewrite_command(line: str) -> str:
    m = _COMMAND.match(line)
    if not m:
        return line
    indent, word, args, term, rest, _comment = m.groups()
    call = ", ".join(f"'{a}'" for a in args.split())
    out = f"{indent}{word}({call}){term or ''}"
    rest = (rest or "").strip()
    if rest and not rest.startswith("%"):
        out += " " + _rewrite_command(rest)  # ``clc; clear all; x = 1``
    return out


def to_function_syntax(code: str) -> str:
    """Rewrite command-style statements (``clear x y``, ``syms x; f = x^2``) as calls.

    A command may be followed by more statements on the same line. Line numbers are preserved.
    """
    return "\\n".join(_rewrite_command(line) for line in code.split("\\n"))
'''
EID_OLD = (
    '    it, _ = run("try, error(\'plain message\'); catch e, i = e.identifier; end")\n'
    '    assert text(it.workspace["i"]) == "E_EVAL"\n'
)
EID_NEW = (
    '    it, _ = run("try, error(\'plain message\'); catch e, i = e.identifier; end")\n'
    '    assert text(it.workspace["i"]) == ""  # MATLAB: no identifier given -> empty\n'
)
TOOL_OLD = (
    '    add(g, "chol of non-SPD raises", "ok = 0; try, chol([1 2; 2 1]); catch err, ok = 1; '
    'end", "ok", 1)\n'
)
TOOL_NEW = (
    '    add(g, "chol of non-SPD raises",\n'
    '        "ok = 0; try, chol([1 2; 2 1]); catch err, ok = 1; end", "ok", 1)\n'
)


def edit(path: Path, pairs: list) -> None:
    if not path.exists():
        print(f"SKIP (missing): {path}")
        return
    with open(path, newline="", encoding="utf-8") as fh:
        text = fh.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    changed = False
    for old, new in pairs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            continue
        if text.count(old) != 1:
            raise SystemExit(f"{path.name}: expected exactly one match for:\n{old}")
        text = text.replace(old, new)
        changed = True
    if changed:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            fh.write(text)
    print(("patched: " if changed else "already patched: ") + path.name)


edit(ROOT / "src/engstudio/lang/builtins_core.py", [(NORM_OLD, NORM_NEW)])
edit(ROOT / "src/engstudio/app/kernel/inprocess.py",
     [(REGEX_OLD, REGEX_NEW), (FUNC_OLD, FUNC_NEW)])
edit(ROOT / "tests/lang/test_builtins_numeric.py", [(EID_OLD, EID_NEW)])
edit(ROOT / "tools/validate_numerics.py", [(TOOL_OLD, TOOL_NEW)])
