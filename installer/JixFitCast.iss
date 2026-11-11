#define AppVersion "1.0.0"
#define ProductName "肌智 JixFit 演示投屏"

[Setup]
AppId={{B92188A7-B762-4EEC-BF2B-94ADAF7426D8}
AppName={#ProductName}
AppVersion={#AppVersion}
AppPublisher=肌智 JixFit
DefaultDirName={localappdata}\Programs\JixFitCast
DefaultGroupName={#ProductName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\release
OutputBaseFilename=JixFit-Cast-Setup-{#AppVersion}-x64
SetupIconFile=app.ico
UninstallDisplayIcon={app}\MirrorStage.exe
UninstallDisplayName={#ProductName}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
InfoAfterFile=quick-start.txt

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式"

[Files]
Source: "..\dist\MirrorStage\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "quick-start.txt"; DestDir: "{app}"; DestName: "使用说明.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\{#ProductName}"; Filename: "{app}\MirrorStage.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\肌智 JixFit 投屏"; Filename: "{app}\MirrorStage.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\MirrorStage.exe"; Description: "启动肌智 JixFit 演示投屏"; Flags: nowait postinstall skipifsilent
