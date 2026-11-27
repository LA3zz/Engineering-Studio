"""P5.1b fix: only plot commands (and close) are rewritten after ; or , in the middle of a line.
Old behaviour for clc/clear/format/more/syms mid-line is kept (existing tests rely on it)."""

from pathlib import Path

path = Path("src/engstudio/app/kernel/inprocess.py")
with open(path, encoding="utf-8", newline="") as f:
    text = f.read()
nl = "\r\n" if "\r\n" in text else "\n"


def swap(old: str, new: str) -> None:
    global text
    old, new = old.replace("\n", nl), new.replace("\n", nl)
    if new in text:
        print("already applied:", new.strip()[:50])
        return
    if text.count(old) != 1:
        raise SystemExit(f"anchor not found exactly once: {old.strip()[:60]!r}")
    text = text.replace(old, new, 1)
    print("patched:", new.strip()[:50])


swap("def _separators(line: str) -> list[int]:",
     "_MIDLINE_WORDS = frozenset(\n"
     "    (\"hold\", \"figure\", \"clf\", \"cla\", \"drawnow\", \"close\"))\n\n\n"
     "def _separators(line: str) -> list[int]:")
swap("            if _COMMAND.match(line[k + 1:]):\n"
     "                return line[:k + 1] + _rewrite_command(line[k + 1:])\n",
     "            tail = _COMMAND.match(line[k + 1:])\n"
     "            if tail and tail.group(2) in _MIDLINE_WORDS:\n"
     "                return line[:k + 1] + _rewrite_command(line[k + 1:])\n")
with open(path, "w", encoding="utf-8", newline="") as f:
    f.write(text)
print("done")
