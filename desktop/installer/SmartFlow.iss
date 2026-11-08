; SmartFlow per-user installer. Build with scripts/build-desktop.ps1 (needs Inno Setup 6).
; Development build: unsigned, not LGU-ready until clean-profile acceptance passes.
#ifndef SourceDir
  #error Pass /DSourceDir=<path to the SmartFlowPrototype folder>
#endif
#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#ifndef WebView2Installer
  #define WebView2Installer ""
#endif

[Setup]
AppId={{6F1D2A58-3B7E-4C0A-9E52-5A1F0C7B9D31}
AppName=SmartFlow
AppVersion={#AppVersion}
AppPublisher=SmartFlow capstone team
DefaultDirName={localappdata}\Programs\SmartFlow
DefaultGroupName=SmartFlow
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
; The running app holds this mutex (desktop/launcher.py); setup stops rather than replace live binaries.
AppMutex=SmartFlowDesktopRunning
CloseApplications=no
SetupIconFile=..\smartflow.ico
UninstallDisplayIcon={app}\SmartFlow.exe
OutputBaseFilename=SmartFlow-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
LicenseFile=..\..\docs\DESKTOP_LICENSES.md

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs
Source: "..\..\docs\DESKTOP_LICENSES.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\..\docs\DESKTOP_INSTALLATION.md"; DestDir: "{app}\docs"; Flags: ignoreversion
#if WebView2Installer != ""
Source: "{#WebView2Installer}"; DestDir: "{tmp}"; DestName: "webview2-setup.exe"; Flags: deleteafterinstall; Check: NeedsWebView2
#endif

[Icons]
Name: "{group}\SmartFlow"; Filename: "{app}\SmartFlow.exe"
Name: "{userdesktop}\SmartFlow"; Filename: "{app}\SmartFlow.exe"; Tasks: desktopicon

[Run]
#if WebView2Installer != ""
Filename: "{tmp}\webview2-setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft WebView2 runtime..."; Check: NeedsWebView2; Flags: waituntilterminated
#endif
Filename: "{app}\SmartFlow.exe"; Description: "Start SmartFlow"; Flags: nowait postinstall skipifsilent

; No [UninstallDelete] for user data: %LOCALAPPDATA%\SmartFlow (database, models, recordings, evidence) is kept on uninstall.

[Code]
const WebView2Guid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function WebView2Present: Boolean;
var Version: String;
begin
  Result := RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WebView2Guid, 'pv', Version)
         or RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\' + WebView2Guid, 'pv', Version);
  if Result then Result := (Version <> '') and (Version <> '0.0.0.0');
end;

function NeedsWebView2: Boolean;
begin
  Result := not WebView2Present;
end;

function InitializeSetup: Boolean;
begin
  Result := True;
#if WebView2Installer == ""
  if not WebView2Present then
    Result := MsgBox('The Microsoft WebView2 runtime was not found, and this installer was built without it. ' +
      'SmartFlow will not open until WebView2 is installed (Windows 11 normally includes it). Continue anyway?',
      mbConfirmation, MB_YESNO) = IDYES;
#endif
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    MsgBox('SmartFlow was removed. Your data in ' + ExpandConstant('{localappdata}') + '\SmartFlow was kept. ' +
      'Delete that folder yourself only if you no longer need the records.', mbInformation, MB_OK);
end;
