# Build the Windows app folder (PyInstaller onedir) and run the packaging smoke tests.
# Usage (venv active):  .\packaging\build.ps1      -> also writes build\build_log.txt
# Then make the installer:  .\packaging\make_installer.ps1
# Native tools (PyInstaller) write normal progress to stderr, which Windows PowerShell 5.1 would
# treat as errors; so every native call goes through cmd, which merges stderr into stdout.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force build | Out-Null
$log = Join-Path (Get-Location) "build\build_log.txt"
Remove-Item $log -ErrorAction SilentlyContinue

function Say([string]$text) { $text | Tee-Object -FilePath $log -Append | Out-Host }
function Invoke-Native([string]$commandLine) {
  cmd /c "$commandLine 2>&1" | Tee-Object -FilePath $log -Append | Out-Host
  return $LASTEXITCODE
}

Get-ChildItem build -Exclude build_log.txt -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Remove-Item -Recurse -Force "dist\EngineeringStudio" -ErrorAction SilentlyContinue

Say "=== PyInstaller build ==="
$rc = Invoke-Native "python -m PyInstaller packaging\engstudio.spec --noconfirm --clean --distpath dist --workpath build"
if ($rc -ne 0) { Say "PyInstaller FAILED (exit $rc)"; exit 1 }
foreach ($exe in "EngineeringStudio.exe", "engstudio-console.exe") {
  if (-not (Test-Path "dist\EngineeringStudio\$exe")) { Say "$exe not found after build"; exit 1 }
}

$bytes = (Get-ChildItem "dist\EngineeringStudio" -Recurse -File | Measure-Object Length -Sum).Sum
Say ("App folder size: {0:N0} MB" -f ($bytes / 1MB))

Push-Location "dist\EngineeringStudio"
try {
  Say "=== --version ==="
  $c0 = Invoke-Native ".\engstudio-console.exe --version"

  Say "=== --selftest (minimal PATH, no Python variables: like a PC without Python) ==="
  $oldPath = $env:PATH; $oldHome = $env:PYTHONHOME; $oldPP = $env:PYTHONPATH
  try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    Remove-Item Env:\PYTHONHOME -ErrorAction SilentlyContinue
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $c1 = Invoke-Native ".\engstudio-console.exe --selftest"
    Say ("wall time: {0:N1} s" -f $sw.Elapsed.TotalSeconds)
  } finally {
    $env:PATH = $oldPath
    if ($oldHome) { $env:PYTHONHOME = $oldHome }
    if ($oldPP) { $env:PYTHONPATH = $oldPP }
  }

  Say "=== Real scripts in the frozen app: examples\full_feature_test.m (--run) ==="
  $work = Join-Path $env:TEMP "es_frozen_run"
  New-Item -ItemType Directory -Force $work | Out-Null
  Push-Location $work
  try {
    $exe = Join-Path (Split-Path (Split-Path $log)) "dist\EngineeringStudio\engstudio-console.exe"
    $ff = Join-Path (Split-Path (Split-Path $log)) "examples\full_feature_test.m"
    $out = cmd /c "`"$exe`" --run `"$ff`" 2>&1"
    $c3 = $LASTEXITCODE
    $out | Select-Object -Last 3 | ForEach-Object { Say $_ }
    if (-not ($out | Select-String -SimpleMatch " 0 failed")) { $c3 = 1 }
  } finally { Pop-Location }

  Say "=== GUI smoke: windowed app opens and quits (--smoke) ==="
  $p = Start-Process ".\EngineeringStudio.exe" -ArgumentList "--smoke" -PassThru -Wait
  $c2 = $p.ExitCode
  $err = Join-Path $env:LOCALAPPDATA "EngineeringStudio\startup_error.txt"
  if ((Test-Path $err) -and ((Get-Item $err).LastWriteTime -gt (Get-Date).AddMinutes(-2))) {
    Say "startup_error.txt:"; Get-Content $err | ForEach-Object { Say $_ }; $c2 = 1
  }
} finally {
  Pop-Location
}

Say "SUMMARY: version=$c0 selftest=$c1 scripts=$c3 gui-smoke=$c2 (0 = pass)"
if ($c0 -ne 0 -or $c1 -ne 0 -or $c2 -ne 0 -or $c3 -ne 0) { Say "BUILD CHECKS FAILED"; exit 1 }
Say "BUILD CHECKS PASSED on this machine (dist\EngineeringStudio)."
