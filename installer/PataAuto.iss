; Instalador de PataAuto (Inno Setup 7).
; Antes: build.ps1 genera installer\out\PataAuto con PyInstaller.

#define AppName "PataAuto"
#define AppVersion "1.0.0"
; ViGEmMsi lo pasa build.ps1 (/DViGEmMsi=...), sacado de la instalación de vgamepad

[Setup]
AppId={{D680E807-2A10-400E-A59A-952A89C679C1}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\PataAuto.exe
OutputDir=out
OutputBaseFilename=PataAuto-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=yes
; la variable SDL va en HKCU a propósito: es del usuario que juega
UsedUserAreasWarning=no
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.VigemTask=Instalar ViGEmBus (driver del mando virtual; necesario para jugar en 2º plano)
english.VigemTask=Install ViGEmBus (virtual gamepad driver; needed to play in the background)
spanish.SdlTask=Permitir que el juego lea el mando en 2º plano (SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS)
english.SdlTask=Let the game read the gamepad in the background (SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS)

[Messages]
spanish.FinishedLabel=PataAuto quedó instalado.%n%nSi el juego estaba abierto, reinícialo para que lea el mando virtual en 2º plano. Juega en modo ventana o pantalla completa sin bordes.
english.FinishedLabel=PataAuto is installed.%n%nIf the game was open, restart it so it can read the virtual gamepad in the background. Play in windowed or borderless fullscreen mode.

[Tasks]
Name: "vigem"; Description: "{cm:VigemTask}"; Check: not ViGEmInstalled
Name: "sdlbg"; Description: "{cm:SdlTask}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "out\PataAuto\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ViGEmMsi}"; DestDir: "{tmp}"; Flags: deleteafterinstall; Tasks: vigem

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"; ValueData: "1"; Flags: uninsdeletevalue; Tasks: sdlbg

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\PataAuto.exe"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\PataAuto.exe"; Tasks: desktopicon

[Run]
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\ViGEmBusSetup_x64.msi"" /qb /norestart"; StatusMsg: "ViGEmBus…"; Flags: waituntilterminated; Tasks: vigem
Filename: "{app}\PataAuto.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
function ViGEmInstalled: Boolean;
begin
  Result := RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\ViGEmBus');
end;
