<div align="center">

<img src="llamabox_256.png" width="96" alt="Llamabox icon" />

# Llamabox

**A lightweight native desktop wrapper for llama.cpp — no browser tab, no bloat, just your local model.**

[![CI](https://github.com/Pingwyd/Llamabox/actions/workflows/ci.yml/badge.svg)](https://github.com/Pingwyd/Llamabox/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Latest Release](https://img.shields.io/github/v/release/Pingwyd/Llamabox)](https://github.com/Pingwyd/Llamabox/releases)
[![Platform](https://img.shields.io/badge/platform-Windows-blue)](#platform-support)

</div>

---

### Why this exists

Running a local model with `llama-server` gives you a web UI — but opening
it in a normal browser tab means paying for an entire browser process just
to display one page. Llamabox replaces that tab with a real, native,
single-purpose window: it launches the server for you, waits until it's
actually ready, and shows it in a clean window that lives quietly in your
system tray. No tabs, no bookmarks bar, no browser overhead sitting between
you and your model.

### What you get

- 🪶 **Genuinely lightweight** — ~45-90 MB of wrapper overhead, not the
  300-500 MB an Electron-based chat app costs before you've even loaded a
  model
- 🚀 **One-click launch** — starts `llama-server` for you, waits for it to
  be ready, then opens the window automatically
- 🗂️ **System tray native** — minimizes to tray instead of quitting, with
  live CPU/RAM/battery stats in the toolbar
- 🔄 **Model switching** — swap between configured model profiles without
  touching a terminal
- 🔋 **Battery-aware** — a heads-up when you're running low and unplugged
- ⚙️ **Fully configurable, no rebuild required** — everything lives in a
  plain `config.json`
- 🔒 **Zero telemetry** — no analytics, no phone-home, nothing beyond
  talking to your own local server and (optionally) checking GitHub for
  updates

### Screenshots

<!--
  Add 2-3 screenshots or a short GIF here once available, e.g.:
  ![Tray menu](docs/screenshot-tray.png)
  ![Toolbar + chat window](docs/screenshot-window.png)
  A short screen recording showing launch -> tray minimize -> restore
  works especially well for a tool like this.
-->

### Quick start

```bash
git clone https://github.com/Pingwyd/Llamabox.git
cd Llamabox
pip install -r requirements.txt
python wrapper.py
```

On first run, Llamabox creates a `config.json` for you to point at your
own `llama-server` install and model — see [Configuration](#configuration-configjson)
below. Prefer not to install Python at all? Grab the prebuilt `.exe` or
installer from [Releases](https://github.com/Pingwyd/Llamabox/releases)
instead.

---

## Platform Support

| Platform | Status |
|----------|--------|
| **Windows** | Fully tested and supported. All features work. |
| **Linux** | Experimental. Code paths exist but have NOT been tested on a real Linux system. |
| **macOS** | Not supported. No code paths exist. |

**Windows is the only tested and supported platform for v1.0.** The codebase
includes cross-platform logic for Linux (XDG directories, zenity dialogs,
WebKitGTK, `.desktop` autostart files, `fcntl` file locking) that was written
to be correct in principle, but has never been run on an actual Linux machine.
If you try it on Linux and hit issues, bug reports and contributions are
welcome.

## Lightweight by Design

Llamabox is built to stay out of your way. The entire wrapper adds just
**45-90 MB of RAM** on top of whatever the llama-server process itself
needs. There is no heavy Electron runtime, no bundled Chromium, and no
background services -- just a single Python process, a tiny HTML toolbar,
and the native WebView (Windows WebView2 or Linux WebKitGTK) that is
already installed on your machine.

For comparison, a typical Electron-based chat app uses 300-500 MB before
you even load a model. Llamabox keeps the overhead low so more of your
RAM stays available for the model weights where it actually matters.

## Prerequisites

- Python 3.11+ installed and on PATH
- `pip` (Python package installer)
- llama.cpp installed somewhere on your machine

### Linux-specific (experimental)

On Linux, you also need:

- `zenity` or `notify-send` for native notification dialogs
- `xdg-utils` for opening files in the default application (usually pre-installed)
- A desktop environment with system tray support (GNOME, KDE, XFCE, etc.)
- WebKitGTK (usually pre-installed on GNOME-based distros)

Install on Debian/Ubuntu:

```
sudo apt install python3-pip zenity xdg-utils
```

Install on Fedora:

```
sudo dnf install python3-pip zenity xdg-utils
```

## Setup

Install Python dependencies:

```
pip install -r requirements.txt
```

## Configuration (config.json)

All server settings are stored in `config.json`, which is created
automatically the first time you run the app.  The location depends on
your OS:

- **Windows**: `%APPDATA%\Llamabox\`
- **Linux** (experimental): `~/.local/share/Llamabox/`

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
    "-ngl", "999",
    "-c", "16384",
    "--jinja",
    "--tools", "all"
  ],
  "server_url": "http://127.0.0.1:8080"
}
```

On Linux the default server path is `~/llama.cpp/llama-server` (without
the `.exe` suffix).

| Field | What to put |
|-------|-------------|
| `llama_server_path` | Full path to your `llama-server` executable |
| `llama_server_args` | Command-line arguments as a JSON array (model file, flags, etc.) |
| `server_url` | The URL the server will serve on (usually unchanged) |

Save the file and run the app again.  You only need to edit this file
when you change your model or server settings -- the script itself never
needs editing.

You can also edit config from within the app: click the gear icon in the
toolbar to open the **Settings** modal, or right-click the tray icon and
choose **Edit Config**.

## Logging (app.log)

All application status messages and errors are written to `app.log`,
which is created in the same data directory as `config.json`:

- **Windows**: `%APPDATA%\Llamabox\`
- **Linux** (experimental): `~/.local/share/Llamabox/`

The log file is capped at 5 MB with one backup (app.log.1) so it does
not grow forever.

Each log line includes a timestamp and severity level:

```
2026-07-21 14:32:01 [INFO] Launching: C:\llama.cpp\llama-server.exe ...
2026-07-21 14:32:15 [INFO] Server ready, launching window...
2026-07-21 15:10:42 [ERROR] Server did not start within 60 seconds
```

If the app crashes, a native message box will appear telling you
something went wrong and where to find `app.log` for the full traceback.
On Windows this is a standard Win32 MessageBox; on Linux it uses zenity
(or notify-send as a fallback).

You can open the log file directly from the tray menu: right-click the
tray icon and choose **View Logs**.

### Where to find the files

| File | Windows | Linux (experimental) | Purpose |
|------|---------|-------|---------|
| `config.json` | `%APPDATA%\Llamabox\` | `~/.local/share/Llamabox/` | Server settings (path, model, args) |
| `app.log` | `%APPDATA%\Llamabox\` | `~/.local/share/Llamabox/` | Application log (startup, errors, shutdown) |
| `server.log` | `%APPDATA%\Llamabox\` | `~/.local/share/Llamabox/` | llama-server stdout/stderr output |

To open the data directory quickly:

- **Windows**: Press Win+R, type `%APPDATA%\Llamabox`, and press Enter.
- **Linux**: Run `xdg-open ~/.local/share/Llamabox` in a terminal.

### For the packaged .exe version (Windows)

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

1.  Configure logging to `app.log` in the data directory.
2.  Load settings from `config.json` (create it first if missing).
3.  Kill any leftover `llama-server` process from previous runs.
4.  Launch a fresh `llama-server` with your configured arguments.
5.  Poll the server URL every 2 seconds until the server responds
    (60 second timeout).  If the server exits immediately (bad args,
    missing file), the error is captured and displayed in the settings
    modal with an option to revert.
6.  Show the pywebview window pointed at the local `shell.html` file,
    which contains a thin toolbar at the top and an iframe embedding the
    actual server UI.  The toolbar shows live CPU, RAM, and battery status
    (if a battery is detected).
7.  Add a system tray icon.  Closing the window hides it to the tray;
    use "Show Window" / "Edit Config" / "View Logs" / "Restart Server" /
    "Quit" from the tray menu.
8.  Chat history and UI customizations you make in the web UI (model
    selection, dark mode, etc.) are saved in a persistent browser profile
    folder at `WebView2Data` (Windows) or the WebKitGTK data directory
    (Linux), both inside the data directory.
9.  If running on battery below 30% charge, a one-time native message
    box suggests using a lighter model profile (configurable via the
    `BATTERY_WARNING_THRESHOLD` constant in `wrapper.py`).

## Settings Modal

Click the gear icon (&#9881;) in the toolbar to open the Settings modal.
It has two tabs:

### General

- **Start with Windows** -- Apple-style toggle that enables automatic
  launch at login.  See the
  [Start with Windows / Linux](#start-with-windows--linux) section for
  details.

### Server

- **Server Path** -- Full path to the `llama-server` executable.
  Shows a "requires restart" badge.
- **Server Arguments** -- JSON array of command-line arguments for the
  server.  Must be a valid JSON array, e.g. `["-ngl", "999", "-c", "16384"]`.
  Shows a "requires restart" badge.
- **Server URL** -- The URL the server is expected to serve on.
  Shows a "requires restart" badge.

### Saving and Restarting

When you click **Save**:

1. The button shows a spinner with "Saving..." text.
2. If any server fields changed, the server is automatically restarted.
3. The button shows "Restarting..." while polling for the server to come
   back up.
4. On success, the button shows "Done" briefly before resetting.

### Error Recovery

If the server fails to start after saving (e.g. bad arguments, missing
executable), the error message is displayed in the modal footer along
with a **Revert** link.  Clicking Revert restores the previous
`config.json` values and restarts the server, so you are never stuck
with broken settings.

### Restart Server Button

The **Restart Server** button in the modal footer manually restarts the
llama-server process without changing any settings.  Useful after
updating models or changing server-side configuration.

## WebView2 / WebKit Profile (Chat History & UI Settings)

The llama-server web UI stores its settings and chat history in the
browser's localStorage API.  A plain pywebview window would normally use
a temporary profile folder, meaning everything would be lost every time
the window was recreated or the app restarted.

This wrapper configures the underlying browser engine to use a fixed,
persistent profile folder inside the data directory:

- **Windows**: `%APPDATA%\Llamabox\WebView2Data\` (WebView2 / Edge)
- **Linux** (experimental): `~/.local/share/Llamabox/WebKitData/` (WebKitGTK)

This folder contains all the data the web UI persists locally:

| Data | What it holds |
|------|---------------|
| Chat history | Saved conversations from the web UI |
| UI preferences | Dark mode, theme, layout settings |
| Model configuration | Any model/parameter selections made in the UI |

**This is separate from `config.json`.**  `config.json` only controls how
the server is launched (executable path, model file, command-line flags).
Everything you change inside the web UI (chat history, themes, etc.) lives
in the browser profile folder instead.

If you ever want to reset the web UI to factory defaults (e.g. clear chat
history, reset preferences), simply **delete the profile folder** while
the app is not running.  The folder will be recreated automatically the
next time you launch the app.

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

## Error Handling

### Server Crash Detection

If the llama-server process crashes while running (e.g. out of memory,
segfault), the tray icon tooltip updates to show "Server not running" and
a native notification is shown.  The app keeps running so you can restart
the server from the tray menu or settings modal.

### Fast-Failure Detection

When starting the server, if the process exits within the first few
seconds (e.g. bad arguments, missing executable), the error is captured
immediately rather than waiting for the full 60-second timeout.  The
error includes the server's exit code and the last few lines from
`server.log`.

### Config Revert

When you save new server settings in the settings modal, the previous
config is stored in memory.  If the server fails to start with the new
settings, a **Revert** link appears in the error message.  Clicking it
restores the previous `config.json` and restarts the server, so you can
always get back to a working state.

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

- A thin toolbar (~38 px) at the top with live stats: CPU, RAM, and
  battery status (if a battery is detected).  These are updated every
  3 seconds via the pywebview JavaScript bridge (`window.pywebview.api`).
- A **Check for Updates** button on the right side that queries the GitHub
  releases API.  It changes appearance when an update is available and
  opens the releases page in your browser.
- A **Settings** gear icon (&#9881;) that opens the settings modal for
  managing server config and startup options.
- An iframe below the toolbar that fills the remaining window height and
  embeds the actual llama-server web UI.

This approach avoids fragile frameless-window hacks and avoids injecting
code into llama.cpp's own pages, which could break across updates.

## Start with Windows / Linux

You can tell Llamabox to launch automatically when you log in.

- **Windows**: Check **Start with Windows** in the settings modal or tray
  menu.  This uses the standard per-user registry key at:
  ```
  HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
  ```
  with a value named `Llamabox`.  No admin rights are required since it
  is per-user.

- **Linux** (experimental): Check **Start with Windows** in the settings
  modal or tray menu (the label stays the same for consistency).  This
  creates a `.desktop` file at `~/.config/autostart/llamabox.desktop`
  which GNOME, KDE, XFCE, and other freedesktop-compatible desktop
  environments recognize automatically.

If the toggle action fails (e.g. permissions issue), a native error
message will appear and the failure is logged to `app.log`.

## Running Tests

LlamaBox includes a minimal smoke test suite covering the core deterministic
logic: version comparison, config parsing/migration, and battery status
formatting.  These tests run without launching a server or opening windows.

### Install test dependencies

```
pip install -r requirements-dev.txt
```

This installs everything in `requirements.txt` plus `pytest`.

### Run the tests

From the project root:

```
pytest
```

Or with verbose output:

```
pytest -v
```

To run a specific test file:

```
pytest tests/test_parse_version.py
pytest tests/test_config.py
pytest tests/test_battery.py
```

### What is tested

| Test file | Covers |
|-----------|--------|
| `test_parse_version.py` | Semver string parsing and comparison for update checking |
| `test_config.py` | Config validation, v1-to-v2 migration, profile extraction, malformed input handling |
| `test_battery.py` | Battery status formatting for the tray tooltip |

### What is NOT tested

These are integration/manual tests that require a running server or OS
interaction:

- Server process lifecycle (start/stop/restart)
- pywebview window creation and JS bridge
- System tray icon and menu
- Actual file I/O (config.json read/write on disk)
- Registry/autostart operations
- Real battery detection via psutil

## Releasing a new version

This project uses a GitHub Actions release workflow that automatically builds
and publishes the portable `.exe` and the Inno Setup installer whenever you
push a version tag.

### Manual steps (you must do these)

The release workflow does everything automatically **except** these two
things, which you must do manually before tagging:

1. **Bump `CURRENT_VERSION` in `wrapper.py`** — the workflow checks that
   this constant matches the tag version and fails if they differ.

   ```python
   CURRENT_VERSION = "1.0.1"  # Must match the tag you're about to push
   ```

2. **Update `AppVersion` in `installer\Llamabox.iss`** — the Inno Setup
   script has its own version constant.  Keep it in sync with the app.

   ```
   #define AppVersion     "1.0.1"      ; Must match CURRENT_VERSION in wrapper.py
   ```

3. **Update `AppPublisher` in `installer\Llamabox.iss`** — set this to your
   name or organization the first time, then leave it alone.

### Release process

```
# 1. Make sure you're on main with all changes committed
git checkout main
git pull

# 2. Update CURRENT_VERSION in wrapper.py
#    (edit the file, then save)

# 3. Update AppVersion in installer\Llamabox.iss
#    (edit the file, then save)

# 4. Commit the version bump
git add wrapper.py installer\Llamabox.iss
git commit -m "chore: bump version to 1.0.1"

# 5. Tag the release
git tag v1.0.1

# 6. Push — the tag triggers the release workflow
git push origin main --tags
```

After pushing, go to **Actions** tab on GitHub to watch the workflow run.
When it finishes, a new Release will appear under **Releases** with both
assets attached (portable `.exe` and installer `Setup.exe`).

### What the workflow does

1. Validates that `CURRENT_VERSION` in `wrapper.py` matches the tag version
2. Runs the smoke test suite — if tests fail, the release is cancelled
3. Builds the portable `.exe` with PyInstaller
4. Installs Inno Setup and compiles the installer `.iss` script
5. Names the assets `LlamaBox-1.0.1-portable.exe` and
   `LlamaBox-1.0.1-Setup.exe` (using the version from the tag)
6. Creates a GitHub Release with auto-generated release notes

## Building a Standalone .exe (Windows)

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

## Building on Linux (experimental)

To create a distributable package on Linux, you can use PyInstaller
with similar flags (adjust hidden imports for Linux backends):

```
pyinstaller --onefile --windowed --name "llamabox" ^
  --hidden-import webview.platforms.gtk ^
  --hidden-import pystray._appindicator ^
  --collect-all PIL ^
  wrapper.py
```

The resulting binary will be at `dist/llamabox`.

On Linux you may also package the app as a `.deb`, `.rpm`, or AppImage
using standard Linux packaging tools.  Make sure to include `zenity` and
`xdg-utils` as dependencies.

**Note**: This has not been tested. Contributions from Linux users are
welcome.

## PyInstaller Notes

- **Hidden imports**: pywebview's platform backends (`win32_edge`,
  `winforms` on Windows; `gtk` on Linux) and `pystray` backends
  (`_win32` on Windows; `_appindicator` on Linux) are dynamically loaded
  at runtime, so PyInstaller's scanner won't find them automatically.
  They must be listed with `--hidden-import` or the packaged binary will
  crash on launch.
- **Pillow plugins**: `--collect-all PIL` ensures all image format handlers
  are bundled -- without this, the tray icon generation may fail.
- **config.json**, **app.log**, and **server.log** are written in the
  platform-specific data directory (`%APPDATA%\Llamabox\` on Windows,
  `~/.local/share/Llamabox/` on Linux), not next to the executable.
  This is because the executable may be installed in a write-protected
  location (e.g. Program Files), so a user-writable directory is used
  instead.  The directory is created automatically the first time the
  app runs.
- **Migration from older versions**: If you had files from a previous
  version stored next to the script/exe, or from the old `%APPDATA%\LocalAI\`
  directory (before the rename), they are automatically copied to the
  new data directory on first launch.  The old copies are left in place
  and can be removed once you have confirmed the new location works.
- **After packaging**, configuration works the same way: run the binary
  once, it creates `config.json` in the data directory, edit that file,
  and restart.  No need to rebuild when you change models or paths.
- **Finding files manually**:
  - Windows: Press Win+R, type `%APPDATA%\Llamabox`, and press Enter.
  - Linux: Run `xdg-open ~/.local/share/Llamabox` in a terminal.
