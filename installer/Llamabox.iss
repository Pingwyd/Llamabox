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
// InitializeSetup: Called once when the installer first launches.
// Uses taskkill (built into Windows) to close any running Llamabox instance.
// Return False to abort installation, True to continue.
// ---------------------------------------------------------------------------
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;

  // taskkill returns 0 if the process was found and terminated.
  // It returns 128 if no matching process was found (not running).
  // We only show a prompt if the process is actually running.
  if Exec('taskkill', '/f /im Llamabox.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      // Process was running and was killed — give it a moment
      Sleep(500);
    end;
  end;
end;

// ---------------------------------------------------------------------------
// InitializeUninstall: Called before uninstallation begins.
// Does the same taskkill to ensure files can be removed cleanly.
// ---------------------------------------------------------------------------
function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  Exec('taskkill', '/f /im Llamabox.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

[Run]
; -- Launch after install (finish-page checkbox) --
Filename: "{app}\{#ExeName}.exe"; \
    Description: "Launch {#AppName}"; \
    Flags: nowait postinstall skipifdoesntexist unchecked

; The "Flags: unchecked" means the launch checkbox starts unchecked on
; the finish page. The user can check it to launch immediately after install.
