You are continuing Engineering Studio, an offline MATLAB-like desktop app (Python 3.11, PySide6, PyQtGraph, Matplotlib, NumPy/SciPy/SymPy) at C:\Users\ma704\Downloads\EngineeringStudio (venv .venv, Windows, PowerShell 5.1). I am on the FREE plan, so usage is the scarcest resource. Follow these rules strictly.

SOURCE OF TRUTH
- Attached: HANDOFF.md, TASKS.md, and ONLY the source files HANDOFF names under "Next task". Do not ask for other files unless a step truly cannot be done without them; then name the exact file and why.
- Do not re-explain the project, re-plan finished phases, or restate the docs back to me.

ONE MILESTONE PER CHAT
- Work on exactly one milestone. Split it into parts A, B, C... only if it is too big for one reply.
- Deliver each part as: (1) a zip named es_<milestone><part>.zip with new files at their project paths, (2) a patches\apply_<milestone><part>.py for edits to existing files (exact-match anchors, idempotent, open(..., newline="")), (3) ONE PowerShell block to apply and test:
  cd C:\Users\ma704\Downloads\EngineeringStudio; .\.venv\Scripts\Activate.ps1
  $zip = Get-ChildItem "$env:USERPROFILE\Downloads" -Filter "<zip name>" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  Copy-Item $zip.FullName "$env:USERPROFILE\Downloads\EngineeringStudio Backup files\" -Force
  Expand-Archive $zip.FullName -DestinationPath . -Force
  python patches\apply_<...>.py
  python -m pytest -q; ruff check .
- Keep replies short: files + commands + at most 5 lines of explanation. No long summaries.
- Do NOT run test suites, install packages or run long commands in your own sandbox: it burns my usage, and my Windows run is the real test. A quick syntax check of a file you wrote is fine.
- When I paste a failure, fix only what failed with the smallest patch.

CONTEXT BUDGET (very important)
- Count our exchanges. After the milestone is verified (tests pass), OR after 8 exchanges, OR if more than ~6 files are attached, STOP and say: "Start a new chat now." Then give, inside a patches\apply_docs_<milestone>.py I can just run:
  a) a replacement "## Next task" section and a one-line "## State" addition for HANDOFF.md (max 15 lines, no history),
  b) the one-line TASKS.md change,
  and list the files to attach in the next chat.
- Never continue past one verified milestone in the same chat.

CODE RULES (see HANDOFF "Conventions"): ruff clean (line length 100, isort ignores case, no B008), gui never imports lang/engine, every builtin in exactly one toolbox category in app/kernel/inprocess.py, GUI tests headless (QT_QPA_PLATFORM=offscreen), files UTF-8 without BOM, document every difference from MATLAB in the module docstring.

Start now with "Next task" in HANDOFF.md. First message: list the parts you will deliver (one line each), then deliver part A.
