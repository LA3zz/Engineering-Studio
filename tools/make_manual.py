"""Build the user manual: docs/manual/Engineering_Studio_User_Manual.pdf.

    python tools/make_manual.py            # check examples, write HTML and PDF
    python tools/make_manual.py --html     # HTML only (build/manual/manual.html)

The hand-written chapters live in docs/manual/chapters.html. The toolbox, block and command
references are generated from the same data the program uses (so they cannot drift), every
``<pre class="m">`` example in the chapters is run through the real interpreter (the build stops
if one fails), and the PDF is printed with Microsoft Edge in headless mode (no extra Python
packages needed).
"""

from __future__ import annotations

import html
import inspect
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from engstudio.app.function_help import (  # noqa: E402
    _arg_line,
    _field_docs,
    _result_class,
    split_forms,
    toolbox_help,
)
from engstudio.app.help_core import CORE_HELP  # noqa: E402
from engstudio.app.help_toolbox import ARG_DOCS, EXAMPLES  # noqa: E402
from engstudio.app.kernel.inprocess import _CATEGORIES, InProcessKernelClient  # noqa: E402
from engstudio.app.kernel.protocol import Diagnostics  # noqa: E402
from engstudio.app.toolbox_bindings import load_toolboxes  # noqa: E402
from engstudio.version import APP_NAME, __version__  # noqa: E402

SOURCE = ROOT / "docs" / "manual" / "chapters.html"
OUT_HTML = ROOT / "build" / "manual" / "manual.html"
OUT_PDF = ROOT / "docs" / "manual" / "Engineering_Studio_User_Manual.pdf"
E = html.escape

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.2pt; line-height: 1.45;
       color: #1d2329; }
h1 { font-size: 21pt; color: #12355b; border-bottom: 2px solid #12355b; padding-bottom: 4px;
     page-break-before: always; margin-top: 0; }
h2 { font-size: 14pt; color: #1b4f80; margin-top: 18px; page-break-after: avoid; }
h3 { font-size: 11.5pt; color: #12355b; margin: 14px 0 4px 0; page-break-after: avoid; }
code, pre { font-family: Consolas, 'Courier New', monospace; font-size: 9pt; }
code { background: #eef2f6; padding: 0 3px; border-radius: 3px; }
pre { background: #f4f6f8; border: 1px solid #d5dbe1; border-left: 3px solid #1b4f80;
      padding: 7px 9px; white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px 0; font-size: 9.4pt;
        page-break-inside: auto; }
tr { page-break-inside: avoid; }
th { background: #12355b; color: white; text-align: left; padding: 4px 6px; }
td { border-bottom: 1px solid #d5dbe1; padding: 3px 6px; vertical-align: top; }
td code { white-space: nowrap; }
.tip { background: #eaf4ea; border-left: 4px solid #3c8c3c; padding: 6px 10px; margin: 8px 0;
       page-break-inside: avoid; }
.fn { page-break-inside: avoid; border-top: 1px solid #c9d2dc; padding-top: 2px; }
.forms { background: #eef3f8; border-left-color: #12355b; }
.small { color: #5a6570; font-size: 9pt; }
.cover { height: 250mm; display: flex; flex-direction: column; justify-content: center; }
.cover h1 { border: none; font-size: 34pt; page-break-before: avoid; }
.cover .sub { font-size: 15pt; color: #1b4f80; }
.toc { page-break-before: always; }
.toc a { color: #1d2329; text-decoration: none; }
.toc ol { padding-left: 18px; } .toc li { margin: 2px 0; }
.toc > ol > li { font-weight: 600; margin-top: 6px; } .toc ol ol li { font-weight: 400; }
a { color: #1b4f80; }
"""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# ---------------------------------------------------------------------------- references
def toolbox_reference() -> str:
    parts = []
    for _name, display, specs in load_toolboxes():
        parts.append(f'<h2 id="tb-{slug(display)}">{E(display)}</h2>')
        for spec in specs:
            parts.append(function_block(spec, display))
    return "\n".join(parts)


def function_block(spec, display: str) -> str:
    h = toolbox_help(spec, display)
    func = inspect.unwrap(spec.func)
    sig = inspect.signature(func)
    by_name = {a.name: a for a in spec.args}
    docs = ARG_DOCS.get(spec.name, {})
    doc = " ".join((inspect.getdoc(func) or "").split())
    rows = []
    for p in sig.parameters:
        line = _arg_line(by_name.get(p), sig.parameters[p].default, docs.get(p, ""))
        rows.append(f"<tr><td><code>{E(p)}</code></td><td>{E(line)}</td></tr>")
    out = [f'<div class="fn"><h3 id="fn-{spec.name}">{E(spec.name)}</h3>',
           f'<pre class="forms">{E(chr(10).join(split_forms(h.signature)))}</pre>',
           f"<p>{E(doc)}</p>",
           "<table><tr><th style='width:16%'>Input</th><th>Meaning, unit, limits, default</th>"
           "</tr>" + "".join(rows) + "</table>"]
    outs = ", ".join(f"<code>{E(r.name)}</code>" + (f" [{E(r.unit)}]" if r.unit else "")
                     for r in spec.returns)
    out.append(f"<p><b>Outputs:</b> {outs}</p>")
    cls = _result_class(spec.func)
    if cls is not None:
        frows = "".join(f"<tr><td><code>{E(n)}</code></td><td>{E(c)}</td></tr>"
                        for n, c in _field_docs(cls))
        out.append("<table><tr><th style='width:16%'>Result field</th><th>Meaning</th></tr>"
                   + frows + "</table>")
    if spec.name in EXAMPLES:
        out.append(f"<p class='small'>Example:</p><pre>{E(EXAMPLES[spec.name])}</pre>")
    out.append("</div>")
    return "\n".join(out)


def block_reference() -> str:
    import engstudio.sim.runner  # noqa: F401  (registers the blocks)
    import engstudio.sim.subsystems  # noqa: F401
    from engstudio.sim import (  # noqa: F401
        blocks_continuous,
        blocks_discrete,
        blocks_nonlinear,
        blocks_sinks,
        blocks_sources,
    )
    from engstudio.sim.blocks import BLOCK_TYPES

    order = ["Sources", "Sinks", "Math Operations", "Continuous", "Discrete",
             "Discontinuities", "Signal Routing", "User-Defined Functions",
             "Ports & Subsystems"]
    cats: dict[str, list] = {}
    for name, bt in BLOCK_TYPES.items():
        cats.setdefault(bt.category, []).append((name, bt))
    parts = []
    for cat in order + sorted(set(cats) - set(order)):
        if cat not in cats:
            continue
        parts.append(f'<h2 id="blk-{slug(cat)}">{E(cat)}</h2>')
        for name, bt in sorted(cats[cat]):
            defaults = {p.name: p.default for p in bt.params}
            try:
                n_in, n_out = bt.n_inputs(defaults), bt.n_outputs(defaults)
                ports = f"{n_in} input(s), {n_out} output(s) with the default parameters"
            except Exception:
                ports = ""
            parts.append(f'<div class="fn"><h3 id="blk-{slug(name)}">{E(name)}</h3>'
                         f"<p>{E(' '.join(bt.doc.split()))}"
                         + (f" <span class='small'>({ports})</span>" if ports else "") + "</p>")
            if bt.params:
                rows = []
                for p in bt.params:
                    extra = " ".join(filter(None, [
                        ("one of " + ", ".join(p.choices)) if p.choices else "", p.doc]))
                    rows.append(f"<tr><td><code>{E(p.name)}</code></td><td>{E(p.kind)}</td>"
                                f"<td><code>{E(_fmt_param(p.default))}</code></td>"
                                f"<td>{E(extra)}</td></tr>")
                parts.append("<table><tr><th style='width:24%'>Parameter</th>"
                             "<th style='width:11%'>Type</th><th style='width:20%'>Default</th>"
                             "<th>Notes</th></tr>" + "".join(rows) + "</table>")
            else:
                parts.append("<p class='small'>No parameters.</p>")
            parts.append("</div>")
    return "\n".join(parts)


def _fmt_param(v: object) -> str:
    if isinstance(v, float):
        return "inf" if v == float("inf") else "-inf" if v == float("-inf") else f"{v:g}"
    if isinstance(v, (list, tuple)):
        if v and isinstance(v[0], (list, tuple)):
            return "[" + "; ".join(" ".join(_fmt_param(x) for x in row) for row in v) + "]"
        return "[" + " ".join(_fmt_param(x) for x in v) + "]"
    if isinstance(v, str):
        return f"'{v}'"
    return str(v)


def command_reference() -> str:
    parts = []
    for key, (title, names) in _CATEGORIES.items():
        rows = []
        for n in names:
            forms, summary = CORE_HELP.get(n, (n, ""))
            rows.append(f"<tr><td><code>{E(n)}</code></td><td><code>"
                        + "</code><br><code>".join(E(f) for f in split_forms(forms))
                        + f"</code></td><td>{E(summary)}</td></tr>")
        parts.append(f'<h2 id="cmd-{key}">{E(title)}</h2><table><tr><th style="width:13%">'
                     "Command</th><th style='width:45%'>Calling forms</th><th>What it does"
                     "</th></tr>" + "".join(rows) + "</table>")
    return "\n".join(parts)


# ------------------------------------------------------------------------- assemble
def number_and_toc(body: str) -> tuple[str, str]:
    toc: list[tuple[int, str, str]] = []
    counters = [0, 0]

    def repl(m: re.Match) -> str:
        level, attrs, text = int(m.group(1)), m.group(2), m.group(3)
        hid = re.search(r'id="([^"]+)"', attrs)
        ident = hid.group(1) if hid else slug(re.sub("<[^>]+>", "", text))
        if level == 1:
            counters[0] += 1
            counters[1] = 0
            label = f"{counters[0]}"
        else:
            counters[1] += 1
            label = f"{counters[0]}.{counters[1]}"
        toc.append((level, ident, f"{label} {re.sub('<[^>]+>', '', text)}"))
        return f'<h{level} id="{ident}">{label}&nbsp;&nbsp;{text}</h{level}>'

    body = re.sub(r"<h([12])([^>]*)>(.*?)</h\1>", repl, body)
    out = ["<div class='toc'><h2>Contents</h2><ol style='list-style:none'>"]
    open_sub = False
    for level, ident, text in toc:
        if level == 1:
            if open_sub:
                out.append("</ol></li>")
                open_sub = False
            out.append(f"<li><a href='#{ident}'>{E(text)}</a>")
            out.append("<ol style='list-style:none'>")
            open_sub = True
        else:
            out.append(f"<li><a href='#{ident}'>{E(text)}</a></li>")
    if open_sub:
        out.append("</ol></li>")
    out.append("</ol></div>")
    return body, "\n".join(out)


def check_examples(body: str) -> None:
    """Run every <pre class="m"> block; stop the build if one fails."""
    blocks = [html.unescape(b) for b in re.findall(r'<pre class="m">(.*?)</pre>', body, re.S)]
    work = Path(tempfile.mkdtemp(prefix="es_manual_"))
    old = Path.cwd()
    os.chdir(work)
    failures = []
    try:
        for code in blocks:
            k = InProcessKernelClient(threaded=False)
            events: list = []
            k.subscribe(events.append)
            k.execute(code, None)
            k.shutdown()
            errs = [d.message for e in events if isinstance(e, Diagnostics) for d in e.items]
            if errs:
                failures.append(f"{code.splitlines()[0]!r}: {errs[0]}")
    finally:
        os.chdir(old)
        shutil.rmtree(work, ignore_errors=True)
    print(f"manual examples: {len(blocks) - len(failures)} / {len(blocks)} ran clean")
    if failures:
        raise SystemExit("example failures:\n  " + "\n  ".join(failures))


def build_html() -> Path:
    src = SOURCE.read_text(encoding="utf-8")
    src = re.sub(r"<!--(?!REF:).*?-->", "", src, flags=re.S)
    check_examples(src)
    src = (src.replace("<!--REF:TOOLBOXES-->", toolbox_reference())
              .replace("<!--REF:BLOCKS-->", block_reference())
              .replace("<!--REF:COMMANDS-->", command_reference()))
    body, toc = number_and_toc(src)
    cover = (f"<div class='cover'><h1 style='border:none'>{E(APP_NAME)}</h1>"
             f"<div class='sub'>User Manual</div><p>Version {E(__version__)} &middot; "
             f"{date.today():%B %Y}</p><p class='small'>An offline MATLAB-style environment for "
             "engineering students: scripting, plotting, control systems, block-diagram "
             "simulation and engineering toolboxes.</p><p class='small'>Not affiliated with "
             "or endorsed by The MathWorks, Inc.; MATLAB and Simulink are trademarks of The "
             "MathWorks, Inc.</p></div>")
    doc = (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{E(APP_NAME)} "
           f"User Manual</title><style>{CSS}</style></head><body>{cover}{toc}{body}"
           "</body></html>")
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT_HTML}")
    return OUT_HTML


def find_edge() -> str:
    for p in (Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application",
              Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application"):
        exe = p / "msedge.exe"
        if exe.is_file():
            return str(exe)
    raise SystemExit("Microsoft Edge not found: open build/manual/manual.html and print to PDF")


def build_pdf(page: Path) -> None:
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix="es_edge_")
    try:
        subprocess.run([find_edge(), "--headless=new", "--disable-gpu",
                        "--no-pdf-header-footer", "--generate-pdf-document-outline",
                        f"--user-data-dir={profile}", f"--print-to-pdf={OUT_PDF}",
                        page.resolve().as_uri()], check=True, timeout=300,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    size = OUT_PDF.stat().st_size if OUT_PDF.exists() else 0
    if size < 10_000:
        raise SystemExit("PDF was not written")
    print(f"wrote {OUT_PDF} ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    page = build_html()
    if "--html" not in sys.argv:
        build_pdf(page)
