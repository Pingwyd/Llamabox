# Llamabox Desktop Wrapper

A minimal native Windows desktop wrapper for llama.cpp using pywebview.
Displays the llama-server web interface in a clean window with no browser
chrome. Includes server process management, system tray with minimize-to-tray,
and live CPU/RAM stats in the tray tooltip.

## Prerequisites

- Python 3.11+ installed and on PATH
- `pip` (Python package installer)
- llama.cpp installed somewhere on your machine

## Setup

Install Python dependencies:

```
pip install -r requirements.txt
```

## Configuration (config.json)

All server settings are stored in `config.json`, which is created
automatically the first time you run the app.  It is placed in
`%APPDATA%\Llamabox\` -- press Win+R and type `%APPDATA%\Llamabox` to
find it quickly.

Just run the app once:

```
python wrapper.py
```

It will create a default `config.json` and exit.  Open it in any text
editor.  It looks like this:

```json
{
  "llama_server_path": "C:\\llama.cpp\\llama-server.exe",
  "llama_server_args": [
    "-hf", "unsloth/gemma-4-E2B-it-GGUF:UD-Q4_K_XL",
    "-ngl", "999",
    "-c", "16384",
    "--jinja",
    "--tools", "write_file,read_file",
    "--webui-mcp-proxy",
    "--webui-config-file", "C:\\Program Files\\llama.cpp\\webui.json"
  ],
  "server_url": "http://127.0.0.1:8080"
}
```

| Field | What to put |
|-------|-------------|
| `llama_server_path` | Full path to your `llama-server.exe` |
| `llama_server_args` | Command-line arguments (model file, flags, etc.) |
| `server_url` | The URL the server will serve on (usually unchanged) |

Save the file and run the app again.  You only need to edit this file
when you change your model or server settings -- the script itself never
needs editing.

Once the app is running, you can also open `config.json` from the tray
menu: right-click the tray icon and choose **Edit Config**.

## Logging (app.log)

All application status messages and errors are written to `app.log`, which
is created in `%APPDATA%\Llamabox\`.  The log file is capped at 5 MB with
one backup (app.log.1) so it does not grow forever.

Each log line includes a timestamp and severity level:

```
2026-07-21 14:32:01 [INFO] Launching: C:\llama.cpp\llama-server.exe ...
2026-07-21 14:32:15 [INFO] Server ready, launching window...
2026-07-21 15:10:42 [ERROR] Server did not start within 60 seconds
```

If the app crashes, a native Windows message box will appear telling you
something went wrong and where to find `app.log` for the full traceback.
This is critical for the packaged `.exe` version, where there is no
visible terminal to show errors.

You can open the log file directly from the tray menu: right-click the
tray icon and choose **View Logs**.

### Where to find the files

| File | Location | Purpose |
|------|----------|---------|
| `config.json` | `%APPDATA%\Llamabox\` | Server settings (path, model, args) |
| `app.log` | `%APPDATA%\Llamabox\` | Application log (startup, errors, shutdown) |
| `server.log` | `%APPDATA%\Llamabox\` | llama-server stdout/stderr output |

To open `%APPDATA%\Llamabox\` quickly, press Win+R, type `%APPDATA%\Llamabox`,
and press Enter.

### For the packaged .exe version

When running the packaged `.exe` (no console window), there is no terminal
output visible.  If something goes wrong:

1. Press Win+R, type `%APPDATA%\Llamabox`, and look for `app.log`.
2. Right-click the tray icon and choose **View Logs** to open it.
3. If the app crashes before the tray appears, check for a Windows message
   box that says "Something went wrong" and tells you where the log file is.
4. The log contains timestamps, error messages, and full tracebacks for
   every issue the app encountered.

## Running Directly (for testing)

```
python wrapper.py
```

The script will:
1.  Configure logging to `app.log` in `%APPDATA%\Llamabox\`.
2.  Load settings from `config.json` (create it first if missing).
3.  Kill any leftover `llama-server.exe` from previous runs.
4.  Launch a fresh `llama-server.exe` with your configured arguments.
 5.  Poll `http://127.0.0.1:8080` every 2 seconds until the server responds
     (60 second timeout).
 6.  Show the pywebview window pointed at the local `shell.html` file,
     which contains a thin toolbar at the top and an iframe embedding the
     actual server UI.  The toolbar shows live CPU, RAM, battery status,
     and the active model name.
 7.  Add a system tray icon.  Closing the window hides it to the tray;
     use "Show Window" / "Edit Config" / "View Logs" / "Restart Server" /
     "Quit" from the tray menu.
 8.  Chat history and UI customizations you make in the web UI (model
     selection, dark mode, etc.) are saved in a persistent WebView2
     profile folder at `%APPDATA%\Llamabox\WebView2Data\` (see below).
 9.  If running on battery below 30% charge, a one-time native message
     box suggests using a lighter model profile (configurable via the
     `BATTERY_WARNING_THRESHOLD` constant in `wrapper.py`).

## WebView2 Profile (Chat History & UI Settings)

The llama-server web UI stores its settings and chat history in the
browser's localStorage API.  A plain WebView2/Edge window would normally
use a temporary profile folder, meaning everything would be lost every
time the window was recreated or the app restarted.

This wrapper configures the underlying WebView2 engine to use a fixed,
persistent profile folder at `%APPDATA%\Llamabox\WebView2Data\`.  This
folder contains all the data the web UI persists locally:

| Data | What it holds |
|------|---------------|
| Chat history | Saved conversations from the web UI |
| UI preferences | Dark mode, theme, layout settings |
| Model configuration | Any model/parameter selections made in the UI |

**This is separate from `config.json`.**  `config.json` only controls how
the server is launched (executable path, model file, command-line flags).
Everything you change inside the web UI (chat history, themes, etc.) lives
in the WebView2 profile folder instead.

If you ever want to reset the web UI to factory defaults (e.g. clear chat
history, reset preferences), simply **delete the `WebView2Data` folder**
while the app is not running.  The folder will be recreated automatically
the next time you launch the app.

## Battery Awareness

On startup, if the machine has a battery and is running unplugged below
a configurable threshold (default 30%), a one-time native message box
suggests switching to a lighter model profile to conserve power.

The toolbar at the top of the window also shows live battery status:

- `64% (on battery)` when unplugged
- `87% (plugged in)` when charging

If no battery is detected at all (desktop PC, VM), the battery segment
is omitted entirely from the toolbar.

The threshold is controlled by the `BATTERY_WARNING_THRESHOLD` constant
at the top of `wrapper.py`.  Set it to `0` to disable the startup
warning entirely.

This is an informational feature only -- no automatic model-switching
or CPU-only mode is implemented based on battery state.

## Update Checking

The toolbar includes a **Check for Updates** button that queries the GitHub
releases API and compares the latest published tag against the built-in
`CURRENT_VERSION` constant in `wrapper.py`.

### Behavior

- **Manual check**: Clicking the button queries GitHub and shows either
  "Update available" (button turns blue) or an "up to date" message box.
- **Auto check**: The app silently checks for updates 15 seconds after
  launch.  If an update is found, the button automatically changes to
  "Update available" on the next stats poll cycle.
- **Once available**: Clicking the "Update available" button opens the
  GitHub releases page in your default browser so you can download the
  new version.

### Configuration

| Constant | File | Purpose |
|----------|------|---------|
| `CURRENT_VERSION` | `wrapper.py` | Bump this before each release (semver, e.g. `"1.0.0"`). |
| `GITHUB_REPO` | `wrapper.py` | Set to `"owner/repo"` for your GitHub repository. |
| `AUTO_UPDATE_CHECK_DELAY` | `wrapper.py` | Seconds to wait after launch before the silent background check (default 15). |

The comparison uses simple semver tuple parsing (`major.minor.patch`) so
both `"1.2.3"` and `"v1.2.3"` tag formats are supported.

## Toolbar & shell.html

Instead of pointing pywebview directly at the llama-server web UI, the
app loads a local `shell.html` file (bundled alongside `wrapper.py`).
This file contains:

- A thin toolbar (~38 px) at the top with live stats: CPU, RAM, battery
  status (if a battery is detected), and the active model name.  These
  are updated every 3 seconds via the pywebview JavaScript bridge
  (`window.pywebview.api`).
- A **Check for Updates** button on the right side that queries the GitHub
  releases API.  It changes appearance when an update is available and
  opens the releases page in your browser.
- An iframe below the toolbar that fills the remaining window height and
  embeds the actual llama-server web UI.

The toolbar replaces the battery status that was previously shown in the
tray icon tooltip (which now only shows CPU and RAM, keeping the tray
area clean since Windows already shows battery status natively).

This approach avoids fragile frameless-window hacks and avoids injecting
code into llama.cpp's own pages, which could break across updates.

## Start with Windows

You can tell Llamabox to launch automatically when you log into Windows
by checking **Start with Windows** in the tray menu.  Uncheck it to
disable auto-start.

This uses the standard per-user registry key at:

```
HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
```

with a value named `Llamabox` containing the full path to the executable
(or the Python interpreter + script path when running in development
mode).  This is the same mechanism used by countless Windows applications
-- no admin rights are required since it is per-user, and you can verify
or remove it manually at any time with `regedit.exe` by navigating to the
key above.

If the toggle action fails (e.g. permissions issue), a native error
message will appear and the failure is logged to `app.log`.

## Building a Standalone .exe

Install PyInstaller:

```
pip install pyinstaller
```

Run this command from the project folder:

```
pyinstaller --onefile --windowed --icon=llamabox.ico --name "Llamabox" ^
  --hidden-import webview.platforms.win32_edge ^
  --hidden-import webview.platforms.winforms ^
  --hidden-import pystray._win32 ^
  --collect-all PIL ^
  wrapper.py
```

The resulting `.exe` will be at `dist\Llamabox.exe`.

### What the flags do

| Flag | Purpose |
|------|---------|
| `--onefile` | Bundle everything into a single .exe (no supporting folders). |
| `--windowed` | No console window -- required for a GUI app. |
| `--name "Llamabox"` | Name of the output .exe. |
| `--icon=llamabox.ico` | Custom icon for the .exe and its taskbar/titlebar. |
| `--hidden-import` | Force PyInstaller to include modules it might miss during scanning. |
| `--collect-all PIL` | Bundle all Pillow image format plugins (needed for the tray icon). |

## PyInstaller Notes

- **Hidden imports**: pywebview's platform backends (`win32_edge`,
  `winforms`) and `pystray._win32` are dynamically loaded at runtime,
  so PyInstaller's scanner won't find them automatically.  They must be
  listed with `--hidden-import` or the packaged .exe will crash on launch.
- **Pillow plugins**: `--collect-all PIL` ensures all image format handlers
  are bundled -- without this, the tray icon generation may fail.
- **config.json**, **app.log**, and **server.log** are written in
  `%APPDATA%\Llamabox\`, not next to the .exe.  This is because the .exe
  may be installed in a write-protected location (e.g. Program Files),
  so a user-writable directory is used instead.  The directory is created
  automatically the first time the app runs.
- **Migration from older versions**: If you had files from a previous
  version stored next to the script/exe, or from the old `%APPDATA%\LocalAI\`
  directory (before the rename), they are automatically copied to
  `%APPDATA%\Llamabox\` on first launch.  The old copies are left in place
  and can be removed once you have confirmed the new location works.
- **After packaging**, configuration works the same way: run the .exe
  once, it creates `config.json` in `%APPDATA%\Llamabox\`, edit that file,
  and restart.  No need to rebuild the .exe when you change models or paths.
- **Finding files manually**: Press Win+R, type `%APPDATA%\Llamabox`, and
  press Enter to open the folder in File Explorer.
