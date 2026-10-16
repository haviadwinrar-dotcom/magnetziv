; Inno Setup script - Magnetoti
#define AppName "Magnetoti"
#define AppVersion "1.0"

[Setup]
AppId={{B7E2A6F4-5C1D-4E8A-9F3B-2D6A1C7E9B10}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=installer_output
OutputBaseFilename=Magnetoti_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\Magnetoti.exe

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\Magnetoti.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Magnetoti.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Magnetoti.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Magnetoti.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
