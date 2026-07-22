# Building the LlamaBox Installer

This guide covers how to compile the LlamaBox Inno Setup installer into a
distributable `LlamaboxSetup.exe` for GitHub Releases.

## Prerequisites

### 1. Install Inno Setup

Inno Setup is a free, open-source Windows installer compiler.

- Download from: https://jrsoftware.org/isdl.php
- Choose the "Inno Setup 6.x" latest release (e.g. `isetup-6.3.3.exe`)
- Run the installer with default options
- Make sure "ISCC.exe" is added to your PATH (the installer offers this)

To verify it's installed, open a terminal and run:

```
ISCC.exe /?
```

If you get usage output, it's working. If not, add Inno Setup to your PATH:

```
set PATH=%PATH%;C:\Program Files (x86)\Inno Setup 6
```

### 2. Build the PyInstaller Executable

Before compiling the installer, you need the `.exe` from PyInstaller.

From the project root:

```
pip install pyinstaller
pyinstaller --onefile --windowed --icon=llamabox.ico --name "Llamabox" ^
  --hidden-import webview.platforms.win32_edge ^
  --hidden-import webview.platforms.winforms ^
  --hidden-import pystray._win32 ^
  --collect-all PIL ^
  wrapper.py
```

This creates `dist\Llamabox.exe`.

### 3. Copy the .exe to the installer directory

The Inno Setup script expects the `.exe` in `installer\exe\`:

```
mkdir installer\exe
copy dist\Llamabox.exe installer\exe\Llamabox.exe
```

## Project Layout

```
installer/
  Llamabox.iss              <-- Inno Setup script (the main file)
  README.md                 <-- This file
  exe/
    Llamabox.exe            <-- PyInstaller output (you must copy this here)
  shell.html                <-- Copy from project root
  config.json               <-- Copy from project root
  llamabox.ico              <-- Copy from project root
  Output/
    LlamaboxSetup.exe       <-- Generated after compilation (git-ignored)
```

The `.iss` script references `shell.html`, `config.json`, and `llamabox.ico`
relative to its own location. Make sure these files are in the `installer/`
directory alongside the script, or update the `Source:` paths in the `.iss`
file to point to the correct locations.

## Compiling the Installer

### Option A: Use the Inno Setup GUI

1. Open **Inno Setup Compiler** (the Start Menu shortcut)
2. Go to **File > Open** and select `installer\Llamabox.iss`
3. Click **Build > Compile** (or press Ctrl+F9)
4. Wait for compilation to finish — you'll see "Finished" in the log pane
5. The output is at `installer\Output\LlamaboxSetup.exe`

### Option B: Use the command line

```
ISCC.exe installer\Llamabox.iss
```

Output goes to `installer\Output\LlamaboxSetup.exe`.

## What the Installer Does

When a user runs `LlamaboxSetup.exe`:

1. **Pre-install check**: Detects if LlamaBox is currently running and
   offers to close it gracefully before proceeding.

2. **Install location**: Defaults to `%LOCALAPPDATA%\Llamabox\` (no admin
   rights required). The user can change this during install.

3. **Files installed**:
   - `Llamabox.exe` — the main application
   - `shell.html` — the toolbar UI
   - `llamabox.ico` — the app icon
   - `config.json` — **only if it doesn't already exist** (preserves user
     config during updates/reinstalls)

4. **Start Menu shortcut**: Created in a "Llamabox" folder.

5. **Desktop shortcut**: Optional checkbox during install (default unchecked).

6. **Start with Windows**: Optional checkbox during install (default unchecked).
   Writes to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` with value
   name "Llamabox" — the same key the app's tray toggle uses, so they stay
   in sync.

7. **Launch option**: Finish page offers to launch LlamaBox immediately.

## What the Uninstaller Does

- Removes all installed files from the install directory
- Removes the Start Menu shortcut
- Removes the Desktop shortcut (if it was created)
- Removes the "Llamabox" value from the `Run` registry key (if present),
  so no orphaned startup entry is left behind
- Does **not** delete `config.json` or other user data (those live in
  `%APPDATA%\Llamabox\`, which is managed by the app itself)

## Placeholder Values

The `.iss` script has two placeholders you must fill in before each release:

| Placeholder | Location in .iss | What to put |
|-------------|------------------|-------------|
| `AppVersion` | Line `#define AppVersion` | Must match `CURRENT_VERSION` in `wrapper.py` (e.g. `"1.0.0"`) |
| `AppPublisher` | Line `#define AppPublisher` | Your name or organization (shown in Windows "Programs and Features") |

Update these before compiling each release version.

## Versioning

The installer uses the same version number as the app (`CURRENT_VERSION`
in `wrapper.py`). When you bump the version in `wrapper.py` for a release,
also update `AppVersion` in the `.iss` script before recompiling the
installer.

Windows uses the `AppId` (the `{B1A2C3D4-...}` GUID in `[Setup]`) to
track installations. **Do not change the AppId** between versions — Windows
sees a changed AppId as a different app entirely, which would let users
install multiple copies side-by-side instead of upgrading.

## Troubleshooting

### "File not found" during compilation

Make sure `shell.html`, `config.json`, and `llamabox.ico` are in the same
directory as the `.iss` file, and that `Llamabox.exe` is in `installer\exe\`.

### Installer doesn't close the running app

The pre-install check uses `CreateToolhelp32Snapshot` to find the process.
Make sure the running process is named `Llamabox.exe` (case-insensitive).
If you renamed the exe, update the `ProcessName` constant in the `[Code]`
section of the `.iss` file.

### "Privileges required" error

The script sets `PrivilegesRequired=lowest` to avoid requiring admin rights.
If you see this error, make sure you're not running the compiler as a
different user than who will install the app, or remove the
`PrivilegesRequiredOverridingAllowed` line.

### Registry key not written

The autostart checkbox writes to `HKCU\...\Run`. This only works if the
installer runs with the same user privileges as the target user. If running
from an admin terminal, make sure UAC elevation isn't switching users.
