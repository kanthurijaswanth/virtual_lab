; ================== MMT Virtual Lab (Qt) ==================
; - Installs your launcher and .grc experiments
; - Bundles GNU Radio 3.9.4 installer
; - Verifies SHA-256 before running
; - Automatically runs the GNU Radio installer DURING SETUP if not already installed
; - Keeps a copy of the EXE under {app}\third_party for manual use

#define MyAppName "MMT Virtual Lab"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MakeMyTechnology"
#define MyAppExeName "virtual_lab_launcher.exe"

; GNU Radio bundle (you verified this hash earlier; recompute if your file differs)
#define GnuExe    "gnuradio_3.9.4-0_win64_release.exe"
#define GnuSha256 "e1e6c67834a1f6a887c6f7432fb1ed4114c49a850dd1bae09cf8c2f122c0ff57"

[Setup]
AppId={{A45C5F53-45E9-44F2-8F0B-5AB1F3E34E8C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={pf}\MMT\VirtualLab
DefaultGroupName={#MyAppName}
OutputBaseFilename=MMT-Virtual-Lab-Setup-QT
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
DisableDirPage=no
DisableProgramGroupPage=no
; Show “preparing to install” details so you can see component selection etc.
DisableReadyMemo=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full"; Description: "Full installation"
Name: "minimal"; Description: "Minimal (without GNU Radio)"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "app"; Description: "MMT Virtual Lab Application"; Types: full minimal custom; Flags: fixed
Name: "gnuradio"; Description: "Install bundled GNU Radio (recommended if not already installed)"; Types: full custom

[Files]
; App
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion; Components: app

; Experiments
Source: "..\experiments\*"; DestDir: "{app}\experiments"; Flags: recursesubdirs ignoreversion; Components: app

; Bundle GNU Radio EXE – copy to {app}\third_party (kept) and {tmp} (optional)
Source: "..\third_party\{#GnuExe}"; DestDir: "{app}\third_party"; Flags: ignoreversion skipifsourcedoesntexist; Components: gnuradio
Source: "..\third_party\{#GnuExe}"; DestDir: "{tmp}";          Flags: ignoreversion skipifsourcedoesntexist; Components: gnuradio

[Icons]
Name: "{group}\MMT Virtual Lab"; Filename: "{app}\{#MyAppExeName}"; Components: app
Name: "{commondesktop}\MMT Virtual Lab"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Components: app

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
; 1) If needed, install GNU Radio from the copy we just placed (wait for it to finish)
Filename: "{app}\third_party\{#GnuExe}"; \
  Parameters: "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-"; \
  StatusMsg: "Installing GNU Radio..."; \
  Flags: waituntilterminated; \
  Check: NeedInstallGnuRadio

; 2) Launch your app afterwards
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent; Components: app

[Code]
// ---------- Utility: detect GNU Radio ----------
function IsGnuRadioInstalled(): Boolean;
var
  ResultCode: Integer;
  FR: TFindRec;
  Root, Candidate: string;
begin
  Result := False;

  // PATH
  if Exec(ExpandConstant('{cmd}'), '/C where gnuradio-companion', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    if ResultCode = 0 then
    begin
      Result := True;
      exit;
    end;

  // Common fixed locations
  if FileExists('C:\Program Files\GNURadio\bin\gnuradio-companion.exe') then begin Result := True; exit; end;
  if FileExists('C:\Program Files\GNURadio 3.10\bin\gnuradio-companion.exe') then begin Result := True; exit; end;
  if FileExists('C:\Program Files\GNURadio-3.10\bin\gnuradio-companion.exe') then begin Result := True; exit; end;
  if FileExists('C:\Program Files\GNURadio 3.9\bin\gnuradio-companion.exe') then begin Result := True; exit; end;
  if FileExists('C:\Program Files\GNURadio-3.9\bin\gnuradio-companion.exe') then begin Result := True; exit; end;

  // Deep scan: C:\Program Files\GNURadio*\bin\gnuradio-companion.exe
  Root := 'C:\Program Files\GNURadio*';
  if FindFirst(Root, FR) then
  try
    repeat
      if (FR.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
      begin
        Candidate := 'C:\Program Files\' + FR.Name + '\bin\gnuradio-companion.exe';
        if FileExists(Candidate) then
        begin
          Result := True;
          exit;
        end;
      end;
    until not FindNext(FR);
  finally
    FindClose(FR);
  end;
end;

// ---------- Utility: checksum ----------
function VerifyFileSha256(const FullPath, Expected: string): Boolean;
var
  Actual: string;
begin
  Result := False;
  if not FileExists(FullPath) then exit;

  if Length(Expected) < 64 then  // no hash set -> accept
  begin
    Result := True;
    exit;
  end;

  Actual := GetSHA256OfFile(FullPath);
  Result := CompareText(Actual, Expected) = 0;
end;

// ---------- Run-time check used by [Run] ----------
function NeedInstallGnuRadio(): Boolean;
var
  FullPath: string;
begin
  // If the user unchecked the component, skip.
  if not WizardIsComponentSelected('gnuradio') then
  begin
    Result := False;
    exit;
  end;

  // If already installed, skip.
  if IsGnuRadioInstalled() then
  begin
    Result := False;
    exit;
  end;

  // Prefer the copy under {app}\third_party (we just installed it there)
  FullPath := ExpandConstant('{app}\third_party\{#GnuExe}');
  if not FileExists(FullPath) then
    FullPath := ExpandConstant('{tmp}\{#GnuExe}');
  if not FileExists(FullPath) then
  begin
    Result := False;  // nothing to run
    exit;
  end;

  // Verify checksum; if mismatch, skip to avoid running a tampered file
  if not VerifyFileSha256(FullPath, '{#GnuSha256}') then
  begin
    MsgBox('Bundled GNU Radio installer checksum mismatch. GNU Radio will not be installed.', mbCriticalError, MB_OK);
    Result := False;
    exit;
  end;

  // We need to install
  Result := True;
end;
