# Build the Windows onedir app and run the packaging smoke tests.
# Usage (venv active):  .\packaging\build.ps1      -> also writes build_log.txt in the project root
# Native tools (PyInstaller) write normal progress to stderr, which Windows PowerShell 5.1 would
# treat as errors; so every native call goes through cmd, which merges stderr into stdout.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
$log = Join-Path (Get-Location) "build_log.txt"
Remove-Item $log -ErrorAction SilentlyContinue

function Say([string]$text) { $text | Tee-Object -FilePath $log -Append | Out-Host }
function Invoke-Native([string]$commandLine) {
  cmd /c "$commandLine 2>&1" | Tee-Object -FilePath $log -Append | Out-Host
  return $LASTEXITCODE
}

Remove-Item -Recurse -Force build, "dist\EngineeringStudio" -ErrorAction SilentlyContinue

Say "=== PyInstaller build ==="
$rc = Invoke-Native "python -m PyInstaller packaging\engstudio.spec --noconfirm --clean --distpath dist --workpath build"
if ($rc -ne 0) { Say "PyInstaller FAILED (exit $rc)"; exit 1 }
if (-not (Test-Path "dist\EngineeringStudio\EngineeringStudio.exe")) { Say "EngineeringStudio.exe not found after build"; exit 1 }

$bytes = (Get-ChildItem "dist\EngineeringStudio" -Recurse -File | Measure-Object Length -Sum).Sum
Say ("Build size: {0:N0} MB" -f ($bytes / 1MB))

Push-Location "dist\EngineeringStudio"
try {
  Say "=== --version ==="
  $c0 = Invoke-Native ".\EngineeringStudio.exe --version"

  Say "=== --selftest (normal environment) ==="
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $c1 = Invoke-Native ".\EngineeringStudio.exe --selftest"
  Say ("wall time: {0:N1} s" -f $sw.Elapsed.TotalSeconds)

  Say "=== --selftest (minimal PATH, no Python variables) ==="
  $oldPath = $env:PATH; $oldHome = $env:PYTHONHOME; $oldPP = $env:PYTHONPATH
  try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    Remove-Item Env:\PYTHONHOME -ErrorAction SilentlyContinue
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    $c2 = Invoke-Native ".\EngineeringStudio.exe --selftest"
  } finally {
    $env:PATH = $oldPath
    if ($oldHome) { $env:PYTHONHOME = $oldHome }
    if ($oldPP) { $env:PYTHONPATH = $oldPP }
  }

  Say "=== --selftest-gui (a small window should flash for half a second) ==="
  $c3 = Invoke-Native ".\EngineeringStudio.exe --selftest-gui"
} finally {
  Pop-Location
}

Say "SUMMARY: version=$c0 selftest=$c1 selftest-minimal-path=$c2 gui=$c3 (0 = pass)"
if ($c0 -ne 0 -or $c1 -ne 0 -or $c2 -ne 0 -or $c3 -ne 0) { Say "PACKAGING SPIKE FAILED"; exit 1 }
Say "PACKAGING SPIKE PASSED on this machine."
Say "STILL TO DO: copy dist\EngineeringStudio to a PC WITHOUT Python and run: EngineeringStudio.exe --selftest"
