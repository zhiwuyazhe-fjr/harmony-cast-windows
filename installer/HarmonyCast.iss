#define AppVersion "1.0.0"
#define ProductName "鸿蒙手机连接助手"

[Setup]
AppId={{108A0F8B-AD65-4C98-9B41-62AF4647D012}
AppName={#ProductName}
AppVersion={#AppVersion}
AppPublisher=HarmonyCast
DefaultDirName={localappdata}\Programs\HarmonyCast
DefaultGroupName={#ProductName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\release
OutputBaseFilename=HarmonyCast-Setup-{#AppVersion}-x64
SetupIconFile=harmony-cast.ico
UninstallDisplayIcon={app}\HarmonyCast.exe
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
Source: "..\dist\HarmonyCast\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "quick-start.txt"; DestDir: "{app}"; DestName: "使用说明.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\{#ProductName}"; Filename: "{app}\HarmonyCast.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#ProductName}"; Filename: "{app}\HarmonyCast.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\HarmonyCast.exe"; Description: "启动{#ProductName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure StopOwnedHdc;
var
  Locator, Services, Processes, Process: Variant;
  Index, ResultCode: Integer;
  ExecutablePath, OwnedPath: String;
begin
  OwnedPath := ExpandConstant('{app}\_internal\vendor\hdc\hdc.exe');
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Services := Locator.ConnectServer('.', 'root\CIMV2');
    Processes := Services.ExecQuery('SELECT ExecutablePath, ProcessId FROM Win32_Process WHERE Name = ''hdc.exe''');
    for Index := 0 to Processes.Count - 1 do
    begin
      Process := Processes.ItemIndex(Index);
      if not VarIsNull(Process.ExecutablePath) then
      begin
        ExecutablePath := Process.ExecutablePath;
        if CompareText(ExecutablePath, OwnedPath) = 0 then
        begin
          ResultCode := Process.Terminate(0);
          Log(Format('Stopped bundled HDC, result %d', [ResultCode]));
          Sleep(500);
        end;
      end;
    end;
  except
    Log('Bundled HDC cleanup failed: ' + GetExceptionMessage);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    StopOwnedHdc;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopOwnedHdc;
end;
