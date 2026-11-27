# Engineering Studio - desktop integration for the development install (no admin rights).
#   Creates: Desktop shortcut, Start menu shortcut, and "Open with > Engineering Studio" for
#   .m files (current user only, HKCU). Double-click still opens .m files with your default app
#   (e.g. MATLAB); this only adds Engineering Studio to the "Open with" list.
#   Run from the project root:   powershell -ExecutionPolicy Bypass -File packaging\install_desktop.ps1
#   Remove everything again:     powershell -ExecutionPolicy Bypass -File packaging\install_desktop.ps1 -Uninstall
param([switch]$Uninstall)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
$icon = Join-Path $root "src\engstudio\gui\engstudio.ico"
$name = "Engineering Studio"
$progId = "EngineeringStudio.MFile"
$desktopLnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "$name.lnk"
$startLnk = Join-Path ([Environment]::GetFolderPath("Programs")) "$name.lnk"
$classes = "HKCU:\Software\Classes"

if ($Uninstall) {
    foreach ($p in $desktopLnk, $startLnk) { if (Test-Path $p) { Remove-Item $p -Force } }
    if (Test-Path "$classes\$progId") { Remove-Item "$classes\$progId" -Recurse -Force }
    $owp = "$classes\.m\OpenWithProgids"
    if (Test-Path $owp) { Remove-ItemProperty -Path $owp -Name $progId -ErrorAction SilentlyContinue }
    Write-Output "Removed shortcuts and the Open with entry."
    exit 0
}

if (-not (Test-Path $pythonw)) { throw "Not found: $pythonw (create the .venv first)" }

# Shortcuts: pythonw = no console window.
$shell = New-Object -ComObject WScript.Shell
foreach ($lnkPath in $desktopLnk, $startLnk) {
    $lnk = $shell.CreateShortcut($lnkPath)
    $lnk.TargetPath = $pythonw
    $lnk.Arguments = "-m engstudio.gui"
    $lnk.WorkingDirectory = [Environment]::GetFolderPath("MyDocuments")
    $lnk.IconLocation = "$icon,0"
    $lnk.Description = "Engineering Studio (MATLAB-style engineering environment)"
    $lnk.Save()
}

# "Open with" for .m files (per user).
$cmd = "`"$pythonw`" -m engstudio.gui `"%1`""
New-Item -Path "$classes\$progId" -Force | Out-Null
Set-Item -Path "$classes\$progId" -Value "MATLAB script"
New-Item -Path "$classes\$progId\DefaultIcon" -Force | Out-Null
Set-Item -Path "$classes\$progId\DefaultIcon" -Value "$icon,0"
New-Item -Path "$classes\$progId\shell\open\command" -Force | Out-Null
Set-Item -Path "$classes\$progId\shell\open" -Value "Open in $name"
New-ItemProperty -Path "$classes\$progId\shell\open" -Name "FriendlyAppName" -Value $name -Force | Out-Null
Set-Item -Path "$classes\$progId\shell\open\command" -Value $cmd
New-Item -Path "$classes\.m\OpenWithProgids" -Force | Out-Null
New-ItemProperty -Path "$classes\.m\OpenWithProgids" -Name $progId -Value "" -PropertyType String -Force | Out-Null

# Ask Explorer to refresh file associations and icons.
Add-Type -Namespace ES -Name Shell -MemberDefinition '[DllImport("shell32.dll")] public static extern void SHChangeNotify(int e, int f, System.IntPtr a, System.IntPtr b);'
[ES.Shell]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)

Write-Output "Desktop shortcut: $desktopLnk"
Write-Output "Start menu:       $startLnk"
Write-Output "Open with:        right-click a .m file > Open with > $name"
