# Make installer_output\EngineeringStudio-Setup-<version>.exe from dist\EngineeringStudio.
# Usage (venv active, after packaging\build.ps1 passed):  .\packaging\make_installer.ps1
# Needs Inno Setup 6 or 7 (ISCC.exe), installed per user or for all users.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path "dist\EngineeringStudio\EngineeringStudio.exe")) {
  throw "dist\EngineeringStudio not found: run packaging\build.ps1 first"
}
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 7\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup (ISCC.exe) not found" }

$version = (python -c "from engstudio.version import __version__; print(__version__)").Trim()
python tools\third_party_notices.py dist\EngineeringStudio\THIRD_PARTY_NOTICES.txt
Copy-Item packaging\INSTALL_NOTICE.txt dist\EngineeringStudio\README.txt -Force

cmd /c "`"$iscc`" /Q /DAppVersion=$version packaging\installer.iss 2>&1"
if ($LASTEXITCODE -ne 0) { throw "ISCC failed ($LASTEXITCODE)" }
$out = Get-Item "installer_output\EngineeringStudio-Setup-$version.exe"
"{0}  {1:N0} MB" -f $out.FullName, ($out.Length / 1MB)
(Get-FileHash $out.FullName -Algorithm SHA256).Hash | Set-Content "$($out.FullName).sha256" -Encoding ascii
"SHA-256 written to $($out.Name).sha256"
