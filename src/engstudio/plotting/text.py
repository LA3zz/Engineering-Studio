"""MATLAB TeX subset for plot text (pure, no Qt, no Matplotlib).

Supported: Greek letters and common symbols (``\\alpha`` .. ``\\Omega``, ``\\circ``, ``\\pm``,
``\\infty``, ``\\deg`` ...), superscript ``^x`` / ``^{...}``, subscript ``_x`` / ``_{...}``,
escaped ``\\_ \\^ \\{ \\} \\\\``. Unknown commands are kept as written. Text with
``interpreter='none'`` is shown literally.

``parse_tex`` returns runs ``(text, level)`` with level 0 (normal), 1 (superscript) or
-1 (subscript); ``tex_to_html`` (PyQtGraph labels) and ``tex_to_mathtext`` (Matplotlib)
are built from it.
"""

from __future__ import annotations

import html

__all__ = ["GREEK", "SYMBOLS", "parse_tex", "tex_to_html", "tex_to_mathtext", "tex_to_plain",
           "tex_to_unicode"]

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ",
    "varsigma": "ς", "tau": "τ", "upsilon": "υ", "phi": "φ", "varphi": "ϕ", "chi": "χ",
    "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}
SYMBOLS = {
    "circ": "°", "deg": "°", "pm": "±", "infty": "∞", "times": "×", "cdot": "·",
    "partial": "∂", "nabla": "∇", "approx": "≈", "neq": "≠", "ne": "≠", "leq": "≤",
    "geq": "≥", "le": "≤", "ge": "≥", "rightarrow": "→", "leftarrow": "←", "to": "→",
    "sqrt": "√", "int": "∫", "sum": "∑", "prod": "∏", "propto": "∝", "bullet": "•",
    "div": "÷", "prime": "′", "ldots": "…", "langle": "⟨", "rangle": "⟩",
}
_NAMES = {**GREEK, **SYMBOLS}
_ESCAPES = "_^{}\\%$&#"


def _command(text: str, i: int) -> tuple[str, int]:
    """``text[i] == '\\'``: (replacement, next index)."""
    if i + 1 < len(text) and text[i + 1] in _ESCAPES:
        return text[i + 1], i + 2
    j = i + 1
    while j < len(text) and text[j].isalpha():
        j += 1
    name = text[i + 1:j]
    if name in _NAMES:  # MATLAB keeps a following space ("\theta (deg)" -> "θ (deg)")
        return _NAMES[name], j
    if name in ("rm", "it", "bf", "sl", "fontsize", "color"):  # style commands: drop
        return "", j
    return text[i:j] or "\\", max(j, i + 1)


def _group(text: str, i: int) -> tuple[str, int]:
    """Argument of ^ or _ starting at ``i``: ``{...}`` or one (possibly command) char."""
    if i >= len(text):
        return "", i
    if text[i] == "{":
        depth, j, out = 1, i + 1, []
        while j < len(text):
            c = text[j]
            if c == "\\":
                rep, j = _command(text, j)
                out.append(rep)
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return "".join(out), j + 1
            out.append(c)
            j += 1
        return "".join(out), j  # unclosed brace: take the rest
    if text[i] == "\\":
        return _command(text, i)
    return text[i], i + 1


def parse_tex(text: str) -> list[tuple[str, int]]:
    runs: list[tuple[str, int]] = []

    def add(s: str, level: int) -> None:
        if not s:
            return
        if runs and runs[-1][1] == level:
            runs[-1] = (runs[-1][0] + s, level)
        else:
            runs.append((s, level))

    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\":
            rep, i = _command(text, i)
            add(rep, 0)
        elif c in "^_" and i + 1 < len(text):
            arg, i = _group(text, i + 1)
            add(arg, 1 if c == "^" else -1)
        elif c in "{}":
            i += 1  # bare grouping braces are not shown
        else:
            add(c, 0)
            i += 1
    return runs


def tex_to_plain(text: str, interpreter: str = "tex") -> str:
    if interpreter == "none":
        return text
    return "".join(s for s, _ in parse_tex(text))


_SUP = str.maketrans("0123456789+-=()niabcdehklmoprstuvwxyz",
                     "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵃᵇᶜᵈᵉʰᵏˡᵐᵒᵖʳˢᵗᵘᵛʷˣʸᶻ")
_SUB = str.maketrans("0123456789+-=()aehijklmnoprstuvx",
                     "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ")


def tex_to_unicode(text: str, interpreter: str = "tex") -> str:
    """Plain text for places without rich text (tick labels): sub/superscripts use Unicode
    sub/superscript characters where they exist, else ``_x`` / ``^x``."""
    if interpreter == "none":
        return text
    out = []
    for s, level in parse_tex(text):
        if level == 0:
            out.append(s)
            continue
        table, mark = (_SUP, "^") if level > 0 else (_SUB, "_")
        mapped = s.translate(table)
        ok = all(a != b or a == " " for a, b in zip(s, mapped, strict=True))
        out.append(mapped if ok else mark + (s if len(s) == 1 else "{" + s + "}"))
    return "".join(out)


def tex_to_html(text: str, interpreter: str = "tex") -> str:
    """HTML for Qt rich text (``<sup>``/``<sub>``); plain text is escaped."""
    if interpreter == "none":
        return html.escape(text, quote=False)
    out = []
    for s, level in parse_tex(text):
        e = html.escape(s, quote=False)
        out.append(e if level == 0 else f"<sup>{e}</sup>" if level > 0 else f"<sub>{e}</sub>")
    return "".join(out)


def _mt_escape(s: str) -> str:
    # Matplotlib mathtext: only the runs inside $...$ are math; escape specials there.
    return "".join("\\" + c if c in "\\{}_^$#%&~" else ("\\ " if c == " " else c) for c in s)


def tex_to_mathtext(text: str, interpreter: str = "tex") -> str:
    """Matplotlib label text: normal runs as text, sub/superscripts as ``$^{...}$``."""
    if interpreter == "none":
        return text.replace("$", r"\$")
    out = []
    for s, level in parse_tex(text):
        if level == 0:
            out.append(s.replace("$", r"\$"))
        else:
            out.append(f"$^{{{_mt_escape(s)}}}$" if level > 0 else f"$_{{{_mt_escape(s)}}}$")
    return "".join(out)
