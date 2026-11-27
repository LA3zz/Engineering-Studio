; Inno Setup script for Engineering Studio. Built by packaging\make_installer.ps1, which passes
; /DAppVersion=x.y.z and expects the app folder in dist\EngineeringStudio (packaging\build.ps1).
; Per-user install (no administrator rights); upgrades in place because AppId never changes.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Engineering Studio"
#define AppExe "EngineeringStudio.exe"
#define ProgId "EngineeringStudio.MFile"

[Setup]
AppId={{6C1F2B8E-4E7A-4B5D-9C3E-2A8F7D6E5B41}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=LA3zz
AppPublisherURL=https://github.com/LA3zz/Engineering-Studio
AppSupportURL=https://github.com/LA3zz/Engineering-Studio/issues
AppUpdatesURL=https://github.com/LA3zz/Engineering-Studio/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\installer_output
OutputBaseFilename=EngineeringStudio-Setup-{#AppVersion}
SetupIconFile=..\src\engstudio\gui\engstudio.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
ChangesAssociations=yes
LicenseFile=..\packaging\INSTALL_NOTICE.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "openwith"; Description: "Add Engineering Studio to ""Open with"" for .m files"; GroupDescription: "File types:"

[Files]
Source: "..\dist\EngineeringStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Example scripts"; Filename: "{app}\_internal\examples"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; "Open with" entry for .m files; double-click keeps the user's default program (e.g. MATLAB).
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueData: "MATLAB script"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueData: """{app}\{#AppExe}"",0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent
; One-click update from Help > Check for Updates runs this installer with /SILENT /UPDATE:
; start the program again when the update is finished.
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: IsUpdate

[Code]
function IsUpdate: Boolean;
begin
  Result := Pos('/UPDATE', UpperCase(GetCmdTail)) > 0;
end;
