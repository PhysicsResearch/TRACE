[Setup]
AppId={{1234ABCD-TRACE-GUI}}
AppName=TRACE
AppVersion=1.0.0
AppPublisher=TRACE Developer
DefaultDirName={autopf}\TRACE
DefaultGroupName=TRACE
OutputDir=Output
OutputBaseFilename=TRACE-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\app_icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\TRACE\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\TRACE"; Filename: "{app}\Launch_ImGUI.exe"; IconFilename: "{app}\assets\app_icon.ico"
Name: "{autodesktop}\TRACE"; Filename: "{app}\Launch_ImGUI.exe"; Tasks: desktopicon; IconFilename: "{app}\assets\app_icon.ico"

[Run]
Filename: "{app}\Launch_ImGUI.exe"; Description: "{cm:LaunchProgram,TRACE}"; Flags: nowait postinstall skipifsilent
