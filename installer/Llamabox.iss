; =============================================================================
; LlamaBox Inno Setup Script
; =============================================================================
;
; This script packages the LlamaBox desktop wrapper into a Windows installer
; using Inno Setup (https://jrsoftware.org/isinfo.php).
;
; Before compiling, make sure:
;   1. The PyInstaller-built "Llamabox.exe" exists in the installer\exe\ folder
;      (or update the Source paths below to point to your dist\ folder).
;   2. shell.html, config.json, and llamabox.ico are in the same directory
;      as this .iss file (or update the Source paths accordingly).
;   3. You fill in the #define values below (AppName, AppVersion, Publisher).
;
; To compile:
;   Open this file in Inno Setup Compiler and click Build > Compile,
;   or run: ISCC.exe installer\Llamabox.iss
;
; Output goes to: installer\Output\LlamaboxSetup.exe
; =============================================================================

; -----------------------------------------------------------------------------
; CONFIGURATION — Fill these in before each release
; -----------------------------------------------------------------------------

#define AppName        "Llamabox"
#define AppVersion     "0.1.0"       ; Must match CURRENT_VERSION in wrapper.py
#define AppPublisher   "Your Name"   ; Replace with your name or org
#define AppURL         "https://github.com/Pingwyd/Llamabox"
#define ExeName        "Llamabox"    ; Base name of the .exe (no extension)

; -----------------------------------------------------------------------------
; PATHS — Where to find the files to package
;
; Default layout expects:
;   installer/
;     Llamabox.iss          (this script)
;     exe/
;       Llamabox.exe        (PyInstaller output, copied from dist\)
;     shell.html
;     config.json
;     llamabox.ico
;
; Adjust these if your layout differs.
; -----------------------------------------------------------------------------

#define ExeDir         "exe"
#define ExePath        ExeDir + "\Llamabox.exe"

; -----------------------------------------------------------------------------
; INSTALLER METADATA
; -----------------------------------------------------------------------------

[Setup]
; Unique identifier for this app — do not change across versions.
; Generated once; keep it stable so Windows tracks upgrades correctly.
AppId={{B1A2C3D4-E5F6-7890-ABCD-EF1234567890}

AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}

; Default install directory under %LOCALAPPDATA% (no admin rights needed).
; The trailing {#AppName} creates a subfolder: %LOCALAPPDATA%\Llamabox\
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}

; Output settings
OutputDir=Output
OutputBaseFilename=LlamaboxSetup
Compression=lzma2
SolidCompression=yes

; Visual settings
SetupIconFile=llamabox.ico
UninstallDisplayIcon={app}\llamabox.ico
WizardStyle=modern

; Require Windows 10+ (WebView2 needs it)
MinVersion=10.0.17763

; Do not prompt for admin rights — we install to %LOCALAPPDATA%
PrivilegesRequired=lowest

; Uncomment the line below if you want a license agreement screen:
; LicenseFile=LICENSE

; -----------------------------------------------------------------------------
; FILES — What gets installed
; -----------------------------------------------------------------------------

[Files]
; The main executable
Source: "{#ExePath}"; DestDir: "{app}"; Flags: ignoreversion

; The HTML toolbar that pywebview loads
Source: "shell.html"; DestDir: "{app}"; Flags: ignoreversion

; The .ico file used for the tray icon and window icon
Source: "llamabox.ico"; DestDir: "{app}"; Flags: ignoreversion

; config.json — only install if it does not already exist.
; This prevents overwriting a user's existing config during updates/reinstalls.
; The "onlyifdoesntexist" flag means: skip this file if {app}\config.json
; already exists on disk. The " uninsneveruninstall" flag means: even if we
; did install it on first setup, never delete it during uninstall (user data).
Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist uninsneveruninstall

; -----------------------------------------------------------------------------
; ICONS — Start Menu and Desktop shortcuts
; -----------------------------------------------------------------------------

[Icons]
; Start Menu shortcut (always created)
; "Group" puts it in a folder named after the app in the Start Menu.
; Parameters: none needed — the exe handles everything.
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}.exe"; IconFilename: "{app}\llamabox.ico"

; Desktop shortcut (created only if the user checks the box during install)
; The "Tasks" reference ties this to the [Tasks] section below.
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#ExeName}.exe"; IconFilename: "{app}\llamabox.ico"; Tasks: desktopicon

; -----------------------------------------------------------------------------
; TASKS — Optional actions the user can choose during installation
; -----------------------------------------------------------------------------

[Tasks]
; Desktop shortcut checkbox — appears during install, default unchecked.
; "Flags: unchecked" means the checkbox starts unchecked.
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

; Start with Windows checkbox — appears during install, default unchecked.
; When checked, writes to the same HKCU\...\Run key that the app's tray
; toggle uses, so both stay in sync.
Name: "autostart"; Description: "Launch {#AppName} when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

; -----------------------------------------------------------------------------
; REGISTRY — Write the autostart key if the user checked the box
; -----------------------------------------------------------------------------

[Registry]
; Write to HKCU (current user) so no admin rights are needed.
; The value name "Llamabox" matches what the app's own tray toggle uses
; (see _is_startup_enabled / _set_startup in wrapper.py).
; The "Tasks: autostart" link means this only writes if the task is checked.
; ValueType: string — a REG_SZ string value.
; ValueData: the full path to the exe, quoted for spaces.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "Llamabox"; ValueData: """{app}\{#ExeName}.exe"""; \
    Tasks: autostart; Flags: uninsdeletevalue

; The "Flags: uninsdeletevalue" above means: during uninstall, delete just
; this one registry value (not the entire Run key). This ensures uninstalling
; Llamabox cleans up the startup entry if it was created by the installer.

; -----------------------------------------------------------------------------
; CODE — Pascal Script for pre-install checks and post-install actions
; -----------------------------------------------------------------------------

[Code]
// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type
  // PROCESSENTRY32 structure for CreateToolhelp32Snapshot API.
  // Must be defined manually because Inno Setup 6.7.1 doesn't ship
  // TProcessEntry32 or TProcessEntry32 as built-in types.
  TProcessEntry32 = record
    dwSize: LongWord;
    cntUsage: LongWord;
    th32ProcessID: LongWord;
    th32DefaultHeapID: LongWord;
    th32ModuleID: LongWord;
    cntThreads: LongWord;
    th32ParentProcessID: LongWord;
    pcPriClassBase: LongInt;
    dwFlags: LongWord;
    szExeFile: array[0..259] of Char;
  end;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const
  // The process name to look for (without .exe extension).
  // If the user has Llamabox running, we need to close it before installing.
  ProcessName = 'Llamabox';

// ---------------------------------------------------------------------------
// Win32 API imports — needed for process detection / termination.
// These are not built into Inno Setup's Pascal Script so we declare them
// explicitly from kernel32.dll.
// ---------------------------------------------------------------------------
function CreateToolhelp32Snapshot(dwFlags: LongWord; th32ProcessID: LongWord): THandle;
external 'CreateToolhelp32Snapshot@kernel32.dll stdcall';
function Process32First(hSnapshot: THandle; var lppe: TProcessEntry32): Boolean;
external 'Process32First@kernel32.dll stdcall';
function Process32Next(hSnapshot: THandle; var lppe: TProcessEntry32): Boolean;
external 'Process32Next@kernel32.dll stdcall';
function OpenProcess(dwDesiredAccess: LongWord; bInheritHandle: Boolean; dwProcessId: LongWord): THandle;
external 'OpenProcess@kernel32.dll stdcall';
function TerminateProcess(hProcess: THandle; uExitCode: LongWord): Boolean;
external 'TerminateProcess@kernel32.dll stdcall';
function CloseHandle(hObject: THandle): Boolean;
external 'CloseHandle@kernel32.dll stdcall';

// ---------------------------------------------------------------------------
// CheckIfRunning: Detect if Llamabox is currently running.
// Returns True if the process is found, False otherwise.
// Uses the Windows CreateToolhelp32Snapshot API to enumerate processes.
// ---------------------------------------------------------------------------
function CheckIfRunning(): Boolean;
var
  hSnapshot: THandle;
  pe: TProcessEntry32;
  Found: Boolean;
begin
  Result := False;

  // Take a snapshot of all running processes
  hSnapshot := CreateToolhelp32Snapshot($00000002  { TH32CS_SNAPPROCESS }, 0);
  if hSnapshot = LongWord(-1)  { INVALID_HANDLE_VALUE } then
    Exit;

  // Initialize the structure size
  pe.dwSize := SizeOf(pe);

  // Walk the process list
  Found := Process32First(hSnapshot, pe);
  while Found do
  begin
    // Compare process names (case-insensitive)
    if CompareText(ChangeFileExt(pe.szExeFile, ''), ProcessName) = 0 then
    begin
      Result := True;
      Break;
    end;
    Found := Process32Next(hSnapshot, pe);
  end;

  CloseHandle(hSnapshot);
end;

// ---------------------------------------------------------------------------
// KillProcess: Terminate a running process by name.
// Uses TerminateProcess after finding the PID via CreateToolhelp32Snapshot.
// Returns True if the process was found and terminated.
// ---------------------------------------------------------------------------
function KillProcess(const AName: string): Boolean;
var
  hSnapshot: THandle;
  pe: TProcessEntry32;
  hProcess: THandle;
  Found: Boolean;
begin
  Result := False;

  hSnapshot := CreateToolhelp32Snapshot($00000002  { TH32CS_SNAPPROCESS }, 0);
  if hSnapshot = LongWord(-1)  { INVALID_HANDLE_VALUE } then
    Exit;

  pe.dwSize := SizeOf(pe);
  Found := Process32First(hSnapshot, pe);

  while Found do
  begin
    if CompareText(ChangeFileExt(pe.szExeFile, ''), AName) = 0 then
    begin
      // Open the process with terminate rights
      hProcess := OpenProcess($00000001  { PROCESS_TERMINATE }, False, pe.th32ProcessID);
      if hProcess <> 0 then
      begin
        TerminateProcess(hProcess, 0);
        CloseHandle(hProcess);
        Result := True;
      end;
    end;
    Found := Process32Next(hSnapshot, pe);
  end;

  CloseHandle(hSnapshot);
end;

// ---------------------------------------------------------------------------
// InitializeSetup: Called once when the installer first launches.
// Checks if Llamabox is running and offers to close it.
// Return False to abort installation, True to continue.
// ---------------------------------------------------------------------------
function InitializeSetup(): Boolean;
begin
  Result := True;

  if CheckIfRunning() then
  begin
    // Ask the user if we should close the running instance
    if MsgBox(
      'LlamaBox is currently running.'#13#10#13#10 +
      'The installer needs to close it before proceeding.'#13#10 +
      'Any unsaved changes in the server will be lost.'#13#10#13#10 +
      'Close LlamaBox now?',
      mbConfirmation,
      MB_YESNO
    ) = IDYES then
    begin
      // Give the process a moment to shut down gracefully
      // (the app handles WM_CLOSE / tray quit cleanly)
      KillProcess(ProcessName);

      // Wait up to 5 seconds for the process to exit
      Sleep(5000);

      // If it's still running, warn the user
      if CheckIfRunning() then
      begin
        if MsgBox(
          'LlamaBox is still running. Force close it?',
          mbConfirmation,
          MB_YESNO
        ) = IDYES then
        begin
          KillProcess(ProcessName);
          Sleep(2000);
        end
        else
        begin
          // User declined — abort the installation
          MsgBox(
            'Installation cancelled. Please close LlamaBox manually and try again.',
            mbError,
            MB_OK
          );
          Result := False;
        end;
      end;
    end
    else
    begin
      // User chose not to close — abort
      MsgBox(
        'Installation cancelled. Please close LlamaBox manually and try again.',
        mbError,
        MB_OK
      );
      Result := False;
    end;
  end;
end;

// ---------------------------------------------------------------------------
// CurStepChanged: Called after each step of the installation finishes.
// We use PostInstall (step = ssPostInstall) to offer launching the app.
// ---------------------------------------------------------------------------
procedure CurStepChanged(CurStep: TSetupStep);
begin
  // ssPostInstall = 3, meaning the installation just finished
  if CurStep = ssPostInstall then
  begin
    // The finish page checkbox "Launch LlamaBox" is handled automatically
    // by Inno Setup via the [Run] section below. No extra code needed here.
  end;
end;

// ---------------------------------------------------------------------------
// InitializeUninstall: Called before uninstallation begins.
// Closes Llamabox if it's running, so files can be removed cleanly.
// ---------------------------------------------------------------------------
function InitializeUninstall(): Boolean;
begin
  Result := True;

  if CheckIfRunning() then
  begin
    if MsgBox(
      'LlamaBox is currently running. Close it now?',
      mbConfirmation,
      MB_YESNO
    ) = IDYES then
    begin
      KillProcess(ProcessName);
      Sleep(3000);
    end;
  end;
end;

// ---------------------------------------------------------------------------
// UninstallNeedRestart: Tells Inno Setup whether a restart is needed.
// We don't need one — just returning False.
// ---------------------------------------------------------------------------
function UninstallNeedRestart(): Boolean;
begin
  Result := False;
end;

; -----------------------------------------------------------------------------
; RUN — Actions to perform after installation completes
; -----------------------------------------------------------------------------

[Run]
; "Filename" is the app exe. The "Tasks: launchapp" reference ties this
; to the finish-page checkbox. "Flags: nowait" means the installer doesn't
; wait for the app to exit before showing the final page.
Filename: "{app}\{#ExeName}.exe"; \
    Description: "Launch {#AppName}"; \
    Flags: nowait postinstall skipifdoesntexist unchecked

; The "Flags: unchecked" means the launch checkbox starts unchecked on
; the finish page. The user can check it to launch immediately after install.
