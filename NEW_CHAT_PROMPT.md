You are continuing Engineering Studio, an offline MATLAB-like desktop app (Python 3.11, PySide6, PyQtGraph, NumPy/SciPy/SymPy) at C:\Users\ma704\Downloads\EngineeringStudio (venv .venv, Windows, PowerShell 5.1). I am on the FREE plan, so usage is the scarcest resource. Follow these rules strictly.

SOURCE OF TRUTH
- Attached: HANDOFF.md, TASKS.md, and ONLY the source files the HANDOFF names for the next task. Do not ask for other files unless a step truly cannot be done without them; if so, name the exact file and why.
- Do not re-explain the project, re-plan finished phases, or restate the docs back to me.

ONE MILESTONE PER CHAT
- Work on exactly one milestone (e.g. P5.2). Split it into parts A, B, C... only if it is too big for one reply.
- Deliver each part as: (1) a zip named es_<milestone><part>.zip with new files at their project paths, (2) a patches\apply_<milestone><part>.py for edits to existing files (exact-match anchors, idempotent, open(..., newline="")), (3) the exact PowerShell commands to apply and test, as one block:
  cd C:\Users\ma704\Downloads\EngineeringStudio; .\.venv\Scripts\Activate.ps1
  Copy-Item "$env:USERPROFILE\Downloads\<zip>" "$env:USERPROFILE\Downloads\EngineeringStudio Backup files\" -Force
  Expand-Archive "$env:USERPROFILE\Downloads\<zip>" -DestinationPath . -Force
  python patches\apply_<...>.py
  python -m pytest -q; ruff check src tests
- Keep replies short: code + commands + at most 5 lines of explanation. No long summaries.
- Do NOT run your own sandbox test runs or install packages to "check" things (it burns my usage, and the sandbox has no PySide6). A quick syntax check is fine. My Windows run is the real test.
- When I paste a failure, fix only what failed; send the smallest patch.

CONTEXT BUDGET (very important)
- Count our exchanges. After the milestone is verified (tests pass), OR after 8 exchanges, OR if I have attached more than ~6 files, STOP and tell me: "Start a new chat now." Then give:
  a) a replacement "## Next task" + "## State" section for HANDOFF.md (max 15 lines, no history),
  b) the one-line TASKS.md change,
  c) the list of files to attach in the next chat.
  Put (a) and (b) in a patches\apply_docs_<milestone>.py so I just run it.
- Never let a chat continue past one verified milestone.

CODE RULES (from HANDOFF): ruff clean (line length 100, isort ignores case, no B008), GUI never imports lang/engine, every builtin in exactly one toolbox category in inprocess.py, tests headless (QT_QPA_PLATFORM=offscreen), files UTF-8 without BOM.

Start now with the "Next task" in HANDOFF.md. First message: list the parts you will deliver (one line each), then deliver part A.
