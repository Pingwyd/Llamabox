"""
Llamabox Desktop Wrapper -- Phase 6

Phase 1: Minimal pywebview window that displays a local server.
Phase 2: Server process lifecycle management (start/stop/restart).
Phase 3: System tray icon with minimize-to-tray behavior.
Phase 4: Live CPU and RAM usage for the server process in the tray tooltip.
Phase 5: External config.json instead of hardcoded settings; PyInstaller packaging.
Phase 6: Persistent WebView2 user-data folder so localStorage (chat history,
         UI settings) survives window recreation and app restarts.
Phase 7: Battery-awareness: startup warning when running on battery below a
         configurable threshold, battery status in the toolbar.
Phase 8: "Start with Windows" tray toggle using the standard HKCU Run key.
Phase 9: Custom toolbar via local shell.html + iframe embedding the llama-server
         UI; JS bridge exposes live CPU/RAM/battery/model to the toolbar.
Phase 10: Cross-platform support -- Linux alongside Windows.
"""

import time
import sys
import subprocess
import os
import json
import threading
import queue
import logging
import traceback
from logging.handlers import RotatingFileHandler
import requests
import webview
import psutil
from PIL import Image
import pystray
from pystray import MenuItem as Item
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socket

# ---------------------------------------------------------------------------
# PLATFORM DETECTION
# ---------------------------------------------------------------------------

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

# Guard Windows-only imports so the file parses cleanly on Linux.
if IS_WINDOWS:
    import ctypes


# ---------------------------------------------------------------------------
# CROSS-PLATFORM HELPERS
# ---------------------------------------------------------------------------

# Windows MB_* constants
_MB_OK = 0x00
_MB_ICONINFO = 0x40
_MB_ICONWARNING = 0x30
_MB_ICONERROR = 0x10


def _show_messagebox(title, text, flags=0):
    """
    Show a native message box on Windows, or a zenity dialog on Linux.

    Args:
        title: Window title.
        text:  Body text.
        flags: Windows-style flags (MB_ICONINFO, etc.).  On Linux this is
               mapped to the closest zenity icon type.
    """
    if IS_WINDOWS:
        ctypes.windll.user32.MessageBoxW(0, text, title, flags)
    elif IS_LINUX:
        icon = "info"
        if flags & _MB_ICONERROR:
            icon = "error"
        elif flags & _MB_ICONWARNING:
            icon = "warning"
        try:
            subprocess.run(
                ["zenity", "--info", f"--title={title}", f"--text={text}",
                 f"--icon-name={icon}-symbolic"],
                timeout=30, capture_output=True,
            )
        except FileNotFoundError:
            # zenity not installed -- fall back to notify-send (fire-and-forget).
            try:
                subprocess.run(
                    ["notify-send", title, text],
                    timeout=10, capture_output=True,
                )
            except FileNotFoundError:
                logging.warning("No zenity or notify-send found; message: %s: %s", title, text)


def _open_file(path):
    """Open a file with the OS default handler (os.startfile / xdg-open)."""
    if IS_WINDOWS:
        os.startfile(path)
    elif IS_LINUX:
        subprocess.Popen(["xdg-open", path])


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

# These values are loaded from config.json at startup (see load_config()).
# The defaults here are used only to generate config.json on the first run;
# after that, config.json is the source of truth.
_DEFAULT_SERVER_PATH = (
    "C:\\llama.cpp\\llama-server.exe" if IS_WINDOWS
    else os.path.expanduser("~/llama.cpp/llama-server")
)
_DEFAULT_SERVER_ARGS = [
    "-hf", "unsloth/gemma-4-E2B-it-GGUF:UD-Q4_K_XL",
    "-ngl", "999",
    "-c", "16384",
    "--jinja",
    "--tools", "all",
    "--webui-mcp-proxy",
    "--webui-config-file",
    "C:\\Program Files\\llama.cpp\\webui.json"
]
_DEFAULT_SERVER_URL = "http://127.0.0.1:8080"

# Set to the local proxy HTTP port once the server starts, so the JS bridge
# can return a same-origin URL for the iframe.
_http_port = None

# Populated from config.json by load_config().
LLAMA_SERVER_PATH = None
LLAMA_SERVER_ARGS = None
SERVER_URL = None

# Config format version — bumped when the schema changes.
_CONFIG_VERSION = 2

# How many seconds to wait between checking if the server is up.
POLL_INTERVAL = 2

# Maximum total seconds to wait before giving up.
TIMEOUT_SECONDS = 60

# Window title shown in the title bar.
WINDOW_TITLE = "Llamabox"

# Window dimensions (width x height) in pixels.
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800

# Battery: percentage below which the startup warning fires (only when
# running on battery).  Set to 0 to disable the warning entirely.
BATTERY_WARNING_THRESHOLD = 30

# Filename of the local shell HTML loaded by pywebview (toolbar + iframe).
SHELL_HTML_FILENAME = "shell.html"

# App version -- bumped manually before each release.
CURRENT_VERSION = "0.1.0"

# GitHub repository path for update checks ("owner/repo").
# Set to the real value once the repo is published.
GITHUB_REPO = "Pingwyd/Llamabox"

# How many seconds after launch to perform a silent background update check.
AUTO_UPDATE_CHECK_DELAY = 15


# ---------------------------------------------------------------------------
# UPDATE CHECKING (GitHub releases API)
# ---------------------------------------------------------------------------

_update_state = {
    "status": "idle",       # idle | checking | available | uptodate | error
    "latest_version": None,
    "release_url": None,
}


def _parse_version(v):
    """
    Parse a semver string ("1.2.3" or "v1.2.3") into a tuple of ints for
    comparison.  Built-in only -- no extra dependencies needed.
    """
    try:
        return tuple(int(p) for p in v.lstrip("v").split("."))
    except (ValueError, AttributeError):
        return (0,)


def _check_for_updates(notify_on_current=False, notify_on_error=False):
    """
    Query the GitHub releases API for the latest release, compare its
    tag_name to CURRENT_VERSION, and update _update_state.

    Parameters control whether message boxes are shown when already on the
    latest version or when the network call fails (pass False for silent
    background checks so the user isn't interrupted by a check they didn't
    ask for).
    """
    if GITHUB_REPO == "username/llamabox":
        logging.warning(
            "GITHUB_REPO is still the placeholder value. "
            "Set it to the real owner/repo in wrapper.py before releases."
        )
        _update_state["status"] = "error"
        if notify_on_error:
            _show_messagebox(
                "Llamabox - Updates",
                "Update checking has not been configured yet.\n\n"
                "Set GITHUB_REPO in wrapper.py to your repository path.",
                _MB_ICONINFO,
            )
        return

    _update_state["status"] = "checking"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        latest = data.get("tag_name", "")
        release_url = data.get("html_url", "")
    except Exception as exc:
        _update_state["status"] = "error"
        logging.warning("Update check failed: %s", exc)
        if notify_on_error:
            _show_messagebox(
                "Llamabox - Updates",
                "Could not check for updates.\n\n"
                "Check your internet connection and try again later.",
                _MB_ICONERROR,
            )
        return

    try:
        current_ver = _parse_version(CURRENT_VERSION)
        latest_ver = _parse_version(latest)
    except Exception:
        _update_state["status"] = "error"
        logging.warning("Update check: could not parse versions (current=%s, latest=%s)", CURRENT_VERSION, latest)
        if notify_on_error:
            _show_messagebox(
                "Llamabox - Updates",
                "Could not compare version numbers.\n\n"
                f"Current: {CURRENT_VERSION}, Latest: {latest}",
                _MB_ICONERROR,
            )
        return

    _update_state["release_url"] = release_url

    if latest_ver > current_ver:
        _update_state["status"] = "available"
        _update_state["latest_version"] = latest
        logging.info("Update available: %s (current: %s)", latest, CURRENT_VERSION)
    else:
        _update_state["status"] = "uptodate"
        _update_state["latest_version"] = CURRENT_VERSION
        logging.info("Already on latest version %s", CURRENT_VERSION)
        if notify_on_current:
            _show_messagebox(
                "Llamabox - Updates",
                f"You are running the latest version ({CURRENT_VERSION}).",
                _MB_ICONINFO,
            )


# ---------------------------------------------------------------------------
# THREAD-SAFE COMMAND QUEUE
# ---------------------------------------------------------------------------

# pystray and pywebview run on different threads.  The tray callbacks
# cannot directly control the window, so they post string commands into
# this thread-safe queue.  The main thread reads and processes them.
_command_queue = queue.Queue()


# ---------------------------------------------------------------------------
# HELPER: DATA DIRECTORY (%APPDATA%\Llamabox)
# ---------------------------------------------------------------------------

_DATA_DIR = None


def _get_data_dir():
    """
    Return the directory for application data files (config, logs).

    On Windows, uses %APPDATA%\\Llamabox.  On Linux, uses
    ~/.local/share/Llamabox (XDG_DATA_HOME).

    The directory is created on first call if it does not exist.
    """
    global _DATA_DIR
    if _DATA_DIR is not None:
        return _DATA_DIR
    if IS_LINUX:
        path = os.path.join(
            os.environ.get("XDG_DATA_HOME",
                           os.path.join(os.path.expanduser("~"), ".local", "share")),
            "Llamabox",
        )
    else:
        path = os.path.join(os.environ["APPDATA"], "Llamabox")
    os.makedirs(path, exist_ok=True)
    _DATA_DIR = path
    return path


def _get_base_path():
    """
    Return the directory containing the executable or script (used only
    for migrating files from the old location).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


_MIGRATED_FILES = ("config.json", "app.log", "server.log")

_OLD_APPDATA_DIR = (
    os.path.join(os.environ["APPDATA"], "LocalAI") if IS_WINDOWS else None
)


def _migrate_old_files():
    """
    Copy config / log files from old locations to the current data dir on
    first run.  Sources checked (in order, least-recent first):

      1. Old script/exe directory (from very early versions).
      2. Old %APPDATA%\\LocalAI directory (before the Llamabox rename).

    Files are only copied if the target does not already have them, so
    existing user data is never overwritten.
    """
    import shutil

    new_dir = _get_data_dir()

    # Source 1: old script/exe directory
    script_dir = _get_base_path()
    if script_dir != new_dir:
        for name in _MIGRATED_FILES:
            _maybe_copy(shutil, os.path.join(script_dir, name), new_dir)

    # Source 2: old %APPDATA%\LocalAI\ directory (prior app name, Windows only)
    if _OLD_APPDATA_DIR and _OLD_APPDATA_DIR != new_dir and os.path.isdir(_OLD_APPDATA_DIR):
        for name in _MIGRATED_FILES:
            _maybe_copy(shutil, os.path.join(_OLD_APPDATA_DIR, name), new_dir)


def _maybe_copy(shutil_mod, src_path, dst_dir):
    """Copy src_path to dst_dir if src exists and the destination doesn't."""
    if not os.path.isfile(src_path):
        return
    dst_path = os.path.join(dst_dir, os.path.basename(src_path))
    if os.path.isfile(dst_path):
        return
    try:
        shutil_mod.copy2(src_path, dst_path)
        logging.info("Migrated %s to %s", os.path.basename(src_path), dst_dir)
    except Exception as exc:
        logging.warning("Could not migrate %s: %s", os.path.basename(src_path), exc)


# ---------------------------------------------------------------------------
# BATTERY STATUS
# ---------------------------------------------------------------------------

_BATTERY_CHECK_DONE = False


def _get_battery_status():
    """
    Query power status via psutil.sensors_battery().

    Returns a dict with keys:
      "present"   — bool (True if a battery was detected, False on
                     desktops / VMs without a battery).
      "percent"   — int (0-100, only meaningful when present=True).
      "plugged_in" — bool (True if charging, False on battery, None when
                     psutil returns None for this field).
    """
    try:
        bat = psutil.sensors_battery()
    except Exception:
        bat = None

    if bat is None:
        return {"present": False, "percent": 0, "plugged_in": None}

    return {
        "present": True,
        "percent": int(bat.percent),
        "plugged_in": bat.power_plugged,
    }


def _format_battery_tooltip(status):
    """
    Format a battery status dict into a short tooltip string.

    Args:
        status: dict with keys "present" (bool), "percent" (int),
                "plugged_in" (bool or None).

    Returns:
        A string like " | Battery: 64% (on battery)" or "" if no battery.
    """
    if not status["present"]:
        return ""

    if status["plugged_in"]:
        return f" | Battery: {status['percent']}% (plugged in)"
    else:
        return f" | Battery: {status['percent']}% (on battery)"


def _battery_tooltip_suffix():
    """
    Return a short battery string for the tray tooltip, e.g.
    " | Battery: 64% (on battery)"  or  " | Battery: plugged in".

    Returns "" (empty string) when no battery is detected so the
    tooltip simply omits the battery segment on desktop systems.
    """
    return _format_battery_tooltip(_get_battery_status())


def _check_battery_on_startup():
    """
    Show a one-time native message box if the machine is running on
    battery and the charge is below BATTERY_WARNING_THRESHOLD.

    Uses a module-level flag so the warning fires only once per process
    lifetime, even if the caller checks multiple times.
    """
    global _BATTERY_CHECK_DONE
    if _BATTERY_CHECK_DONE:
        return
    _BATTERY_CHECK_DONE = True

    if BATTERY_WARNING_THRESHOLD <= 0:
        return

    status = _get_battery_status()
    if not status["present"] or status["plugged_in"]:
        return

    if status["percent"] >= BATTERY_WARNING_THRESHOLD:
        return

    logging.info(
        "Running on battery (%s%% remaining, threshold %s%%).",
        status["percent"],
        BATTERY_WARNING_THRESHOLD,
    )

    _show_messagebox(
        "Llamabox - Battery Notice",
        (
            f"Running on battery ({status['percent']}% remaining).\n\n"
            "Consider using a lighter model profile or enabling "
            "CPU-only mode for better battery life."
        ),
        _MB_ICONINFO,
    )


# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

APP_LOG_FILENAME = "app.log"
_logger_configured = False


def _init_logging():
    """
    Configure the root logger to write to a rotating app.log next to the
    script/exe, and also echo to stderr (visible in the terminal when
    running as a script, invisible when packaged as a windowed .exe).

    The log file is capped at 5 MB with one backup.  Only configures the
    root logger once; subsequent calls are no-ops.
    """
    global _logger_configured
    if _logger_configured:
        return

    log_path = os.path.join(_get_data_dir(), APP_LOG_FILENAME)

    # File handler: RotatingFileHandler, 5 MB max, 1 backup.
    fh = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=1,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)

    # Console handler: stderr, so it shows in the terminal when running
    # as a script but is invisible when packaged as a windowed .exe.
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.DEBUG)

    # Common format: "2026-07-21 14:32:01 [INFO] Message..."
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)
    root.addHandler(ch)

    _logger_configured = True
    logging.info("Log initialized: %s", log_path)


# ---------------------------------------------------------------------------
# CONFIG FILE (config.json)
# ---------------------------------------------------------------------------

CONFIG_FILENAME = "config.json"


def _migrate_config(config):
    """
    Migrate an old flat config to the new profiles format.

    Old format (v1):
      { "llama_server_path": "...", "llama_server_args": [...], "server_url": "..." }

    New format (v2):
      {
        "config_version": 2,
        "active_profile": "Default",
        "profiles": {
          "Default": {
            "llama_server_path": "...",
            "llama_server_args": [...],
            "server_url": "..."
          }
        }
      }

    If the config is already v2 or has a profiles key, it is returned unchanged.
    """
    if config.get("config_version", 1) >= 2 and "profiles" in config:
        return config

    # Old flat format — migrate to profiles
    profile = {}
    for key in ("llama_server_path", "llama_server_args", "server_url"):
        if key in config:
            profile[key] = config[key]

    return {
        "config_version": 2,
        "active_profile": "Default",
        "profiles": {"Default": profile},
    }


def _get_active_profile(config):
    """
    Return the active profile dict from a v2 config.

    Raises ValueError if the config structure is invalid.
    """
    if "profiles" not in config:
        raise ValueError("Config missing 'profiles' key")
    if "active_profile" not in config:
        raise ValueError("Config missing 'active_profile' key")

    name = config["active_profile"]
    if name not in config["profiles"]:
        raise ValueError(f"Active profile '{name}' not found in profiles")

    return config["profiles"][name]


def _parse_config(config):
    """
    Validate and normalize a config dict.  Raises ValueError on invalid input.

    Handles both old flat format (v1) and new profiles format (v2).
    Migrates v1 to v2 automatically.

    This is the pure-logic core of load_config(), separated so it can be
    tested without file I/O or sys.exit() calls.

    Args:
        config: dict loaded from config.json.

    Returns:
        The validated config dict in v2 format.

    Raises:
        ValueError: with a descriptive message if the config is invalid.
    """
    if not isinstance(config, dict):
        raise ValueError("Config must be a JSON object (dict), got " + type(config).__name__)

    # Migrate old format to profiles format
    config = _migrate_config(config)

    # Validate profiles structure
    if not isinstance(config.get("profiles"), dict):
        raise ValueError("'profiles' must be a dict")
    if not config["profiles"]:
        raise ValueError("'profiles' must contain at least one profile")
    if not isinstance(config.get("active_profile"), str):
        raise ValueError("'active_profile' must be a string")

    # Validate the active profile exists and has required fields
    profile = _get_active_profile(config)
    required = ["llama_server_path", "llama_server_args", "server_url"]
    missing = [f for f in required if f not in profile]
    if missing:
        raise ValueError(f"Active profile missing required field(s): {', '.join(missing)}")

    if not isinstance(profile["llama_server_path"], str):
        raise ValueError("'llama_server_path' must be a string")
    if not isinstance(profile["llama_server_args"], list):
        raise ValueError("'llama_server_args' must be a list of strings")
    if not isinstance(profile["server_url"], str):
        raise ValueError("'server_url' must be a string")

    return config


def load_config():
    """
    Load settings from config.json next to the executable/script.

    If config.json does not exist, create it from the hardcoded defaults,
    print an instructive message, and exit cleanly.  If config.json exists
    but is malformed or missing required fields, print a specific error
    and exit so the user knows what to fix.
    """
    config_path = os.path.join(_get_data_dir(), CONFIG_FILENAME)

    if not os.path.exists(config_path):
        _create_default_config(config_path)
        logging.info("Created %s", config_path)
        logging.info("Edit it with your server path and model settings, then restart the app.")
        sys.exit(0)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as exc:
        logging.error(
            "%s contains invalid JSON at line %s, column %s: %s",
            CONFIG_FILENAME, exc.lineno, exc.colno, exc.msg,
        )
        sys.exit(1)

    try:
        config = _parse_config(config)
    except ValueError as exc:
        logging.error("%s: %s", CONFIG_FILENAME, exc)
        sys.exit(1)

    return config


def _create_default_config(config_path):
    """Write a config.json with placeholder values so the user can edit it."""
    default = {
        "config_version": 2,
        "active_profile": "Default",
        "profiles": {
            "Default": {
                "llama_server_path": _DEFAULT_SERVER_PATH,
                "llama_server_args": _DEFAULT_SERVER_ARGS,
                "server_url": _DEFAULT_SERVER_URL,
            }
        },
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(default, f, indent=2)


# ---------------------------------------------------------------------------
# SERVER PROCESS MANAGEMENT
# ---------------------------------------------------------------------------

# Reference to the current pywebview Window object, used by the tray's
# Quit callback to destroy the window and unblock the main thread.
_window = None

# Holds the subprocess.Popen object for the running llama-server instance.
# Used by terminate_server() and restart_server() to control the process.
_server_process = None

# File handle for server.log, kept open while the server is running.
_server_log_file = None

# Flag set by terminate_server() so the stats monitor can distinguish
# an intentional stop (restart / quit) from an unexpected crash.
_server_stop_intentional = False

# Stores the last server error message so the UI can display it.
_last_server_error = None

# Stores the previous config so we can revert if the server fails to start.
_previous_config = None


def terminate_existing_servers():
    """
    Find and terminate any llama-server.exe processes left running from
    previous sessions.  This prevents port conflicts and orphaned processes.
    """
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = proc.info["name"]
            if name and "llama-server.exe" in name.lower():
                logging.info("Killing leftover llama-server.exe (PID %s)...", proc.info["pid"])
                proc.terminate()
                proc.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process died before we could act, or we lack permission -- skip.
            pass
        except psutil.TimeoutExpired:
            # Graceful terminate timed out -- force kill.
            logging.warning("Force-killing unresponsive llama-server.exe (PID %s)...", proc.info["pid"])
            proc.kill()
            proc.wait()


def _read_server_log_tail(lines=10):
    """Read the last N lines of server.log for error display."""
    log_path = os.path.join(_get_data_dir(), "server.log")
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:]).strip()
    except Exception:
        return "(could not read server.log)"


def launch_server():
    """
    Start llama-server.exe as a subprocess with the configured arguments.
    stdout and stderr are merged and written to server.log in the same
    directory as this script.
    """
    global _server_process, _server_log_file

    # Path to the log file (written next to the .exe / script).
    log_path = os.path.join(_get_data_dir(), "server.log")

    # Truncate server.log on each launch so it only contains output from
    # the current session.  Historical launches are recorded in app.log.
    _server_log_file = open(log_path, "w", encoding="utf-8")

    # Build the full command line from path + args.
    cmd = [LLAMA_SERVER_PATH] + LLAMA_SERVER_ARGS

    logging.info("Launching: %s", " ".join(cmd))
    logging.info("Server log (stdout/stderr): %s", log_path)

    # Hide the console window on Windows — llama-server.exe is a console-mode
    # binary and would otherwise pop a visible terminal on every launch.
    kwargs = {}
    if sys.platform == "win32":
        kwargs["startupinfo"] = subprocess.STARTUPINFO(
            dwFlags=subprocess.STARTF_USESHOWWINDOW,
            wShowWindow=subprocess.SW_HIDE,
        )

    _server_process = subprocess.Popen(
        cmd,
        stdout=_server_log_file,
        stderr=subprocess.STDOUT,
        **kwargs,
    )


def terminate_server():
    """
    Gracefully shut down the running llama-server subprocess.  Sends a
    terminate signal first; if the process does not exit within 5 seconds,
    force-kill it.
    """
    global _server_process, _server_log_file, _server_stop_intentional

    if _server_process is None:
        return

    logging.info("Shutting down llama-server...")
    _server_stop_intentional = True

    # Try graceful termination first.
    _server_process.terminate()

    try:
        _server_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        # Graceful shutdown timed out -- escalate to force kill.
        logging.warning("Server did not respond to terminate signal, force-killing...")
        _server_process.kill()
        _server_process.wait()

    _server_process = None

    # Close the log file handle so all output is flushed to disk.
    if _server_log_file is not None:
        _server_log_file.close()
        _server_log_file = None


def restart_server():
    """
    Stop the currently running llama-server (if any) and start a fresh
    instance with the same configuration.  Runs in a background thread
    when called from the tray menu so the tray event loop is not blocked.
    """
    terminate_server()

    # Brief pause so the port is fully released before the new process binds.
    time.sleep(1)

    launch_server()


# ---------------------------------------------------------------------------
# STARTUP REGISTRY (HKCU Run key)
# ---------------------------------------------------------------------------

_STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_STARTUP_REG_VALUE = "LlamaBox"
_AUTOSTART_DESKTOP = os.path.expanduser("~/.config/autostart/llamabox.desktop")


def _get_startup_exe_path():
    """
    Return the full path of the currently running executable to store in
    the registry.  When frozen by PyInstaller, sys.executable points to
    the .exe; when running as a script, it points to python.exe, so we
    append the script path.
    """
    if getattr(sys, "frozen", False):
        return sys.executable
    script = os.path.abspath(__file__)
    return f'"{sys.executable}" "{script}"'


def _is_startup_enabled():
    """
    Check whether auto-start is enabled.
    Windows: looks for the value under HKCU Run key.
    Linux: checks for a .desktop file in ~/.config/autostart/.
    """
    if IS_WINDOWS:
        import winreg
        expected = _get_startup_exe_path()
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_READ
            ) as key:
                stored, _ = winreg.QueryValueEx(key, _STARTUP_REG_VALUE)
        except FileNotFoundError:
            return False
        except Exception:
            return False
        return stored == expected

    elif IS_LINUX:
        return os.path.isfile(_AUTOSTART_DESKTOP)

    return False


def _set_startup(enable):
    """
    Enable or disable auto-start.
    Windows: writes/deletes the HKCU Run registry value.
    Linux: creates/removes a .desktop file in ~/.config/autostart/.
    """
    if IS_WINDOWS:
        import winreg
        if enable:
            path = _get_startup_exe_path()
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, _STARTUP_REG_VALUE, 0, winreg.REG_SZ, path)
            logging.info("Startup registry entry added: %s", path)
        else:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, _STARTUP_REG_VALUE)
            logging.info("Startup registry entry removed.")

    elif IS_LINUX:
        if enable:
            exe_path = _get_startup_exe_path()
            desktop = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Llamabox\n"
                "Exec=" + exe_path + "\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            os.makedirs(os.path.dirname(_AUTOSTART_DESKTOP), exist_ok=True)
            with open(_AUTOSTART_DESKTOP, "w") as f:
                f.write(desktop)
            logging.info("Autostart .desktop file created: %s", _AUTOSTART_DESKTOP)
        else:
            if os.path.exists(_AUTOSTART_DESKTOP):
                os.remove(_AUTOSTART_DESKTOP)
                logging.info("Autostart .desktop file removed.")


def _on_tray_toggle_startup(icon, item):
    """
    Tray menu callback: toggle the startup registry entry on or off.
    Shows a native message box on failure.
    """
    current = _is_startup_enabled()
    try:
        _set_startup(not current)
    except Exception as exc:
        logging.error("Failed to toggle startup entry: %s", exc)
        _show_messagebox(
            "Llamabox - Error",
            f"Could not update the startup setting.\n\n{exc}",
            _MB_ICONERROR,
        )


def _is_startup_checked(item):
    """Return True if the startup entry currently exists (checked state)."""
    return _is_startup_enabled()


# ---------------------------------------------------------------------------
# SHARED STATS (written by _stats_monitor, read by JsApi bridge)
# ---------------------------------------------------------------------------

# Module-level dict holding the latest CPU / RAM snapshot so the toolbar
# HTML page can read it via the pywebview JS bridge without duplicating
# process-monitoring logic.  Updated by _stats_monitor every 3 seconds.
_latest_stats = {
    "cpu": None,
    "ram_mb": None,
    "cpu_measuring": False,
    "running": False,
}


def _get_model_display_name():
    """
    Extract a human-readable model name from the current server args.
    Looks for flags like -hf, --hf, --model, -m and cleans up the value.
    Falls back to 'default' if none can be identified.
    """
    args = LLAMA_SERVER_ARGS
    if not args:
        return "default"
    for i, arg in enumerate(args):
        if i + 1 < len(args) and arg in ("-hf", "--hf", "--model", "-m"):
            raw = args[i + 1]
            name = raw.replace("\\", "/").rstrip("/").split("/")[-1]
            name = name.split(":")[0]
            if name.lower().endswith(".gguf"):
                name = name[:-5]
            return name
    return "default"


# ---------------------------------------------------------------------------
# JS API BRIDGE (exposes stats to the shell.html toolbar)
# ---------------------------------------------------------------------------

class JsApi:
    """
    Methods exposed to JavaScript via window.pywebview.api.*.
    Called from the shell.html toolbar polling loop.
    """

    def copy_to_clipboard(self, text):
        """Copy text to the system clipboard.

        The llama-server UI runs inside an iframe where the Clipboard API
        may be blocked depending on the page origin.  This bridge method
        lets injected JS route copy requests through Python instead.
        """
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return True
        except Exception:
            logging.warning("Failed to copy to clipboard: %s", text[:80])
            return False

    def get_server_url(self):
        """Return the current server URL for the iframe to load.

        Returns a same-origin proxied URL so the Clipboard API works
        inside the iframe.  Falls back to the direct SERVER_URL if the
        proxy port is not yet set.
        """
        if _http_port is not None:
            return f"http://127.0.0.1:{_http_port}/"
        return SERVER_URL

    def get_stats(self):
        """Return a dict of current server stats + battery + model name
        plus the current update-check state."""
        s = _latest_stats
        bat = _get_battery_status()
        us = _update_state
        return {
            "cpu": s["cpu"],
            "ram_mb": s["ram_mb"],
            "cpu_measuring": s["cpu_measuring"],
            "running": s["running"],
            "battery_present": bat["present"],
            "battery_percent": bat["percent"] if bat["present"] else None,
            "battery_plugged_in": bat["plugged_in"] if bat["present"] else None,
            "model": _get_model_display_name(),
            "update_status": us["status"],
            "update_latest_version": us["latest_version"],
            "update_current_version": CURRENT_VERSION,
        }

    def check_for_updates(self):
        """Called from the toolbar button.  Runs the check in a background
        thread so the JS bridge call returns immediately; the result is
        picked up on the next stats poll."""
        threading.Thread(target=_check_for_updates, args=(True, True), daemon=True).start()

    def open_releases_page(self):
        """Open the GitHub releases page in the user's default browser."""
        url = _update_state.get("release_url")
        if not url and GITHUB_REPO != "username/llamabox":
            url = f"https://github.com/{GITHUB_REPO}/releases/latest"
        import webbrowser
        webbrowser.open(url or "https://github.com/username/llamabox/releases")

    def get_update_status(self):
        """Return the current update state for the toolbar to display."""
        s = _update_state
        return {
            "status": s["status"],
            "latest_version": s["latest_version"],
            "current_version": CURRENT_VERSION,
        }

    def get_config(self):
        """Return the current config values for the settings modal.

        Returns the active profile's values as a flat dict for backward
        compatibility with the settings modal UI.
        """
        config_path = os.path.join(_get_data_dir(), CONFIG_FILENAME)
        if not os.path.exists(config_path):
            return {"error": "Config file not found"}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as exc:
            return {"error": str(exc)}

        # Migrate if needed and return the active profile's values
        try:
            config = _parse_config(raw)
            profile = _get_active_profile(config)
            return profile
        except ValueError as exc:
            return {"error": str(exc)}

    def save_config(self, config):
        """Save config values to config.json and auto-restart if changed.

        Accepts flat config values from the settings modal and writes them
        into the active profile within the profiles structure.
        """
        global LLAMA_SERVER_PATH, LLAMA_SERVER_ARGS, SERVER_URL, _previous_config

        config_path = os.path.join(_get_data_dir(), CONFIG_FILENAME)

        # Read old config for comparison and store for potential revert.
        old_config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    old_config = json.load(f)
            except Exception:
                pass

        # Ensure llama_server_args is a list (pywebview bridge may stringify it).
        args = config.get("llama_server_args", [])
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
                args = parsed if isinstance(parsed, list) else [parsed]
            except (json.JSONDecodeError, TypeError):
                args = [a.strip().strip('"').strip(",") for a in args.split(",") if a.strip()]
        elif isinstance(args, list):
            # Clean up any leftover JSON artifacts from a bad parse.
            args = [a.strip().strip('"').strip(",") for a in args if isinstance(a, str)]
        config["llama_server_args"] = [a for a in args if a]

        # Build the new profiles config, writing into the active profile
        try:
            old_parsed = _parse_config(old_config) if old_config else None
        except ValueError:
            old_parsed = None

        active_name = config.get("active_profile", "Default")
        if old_parsed and "profiles" in old_parsed:
            active_name = old_parsed.get("active_profile", "Default")
            profiles = old_parsed.get("profiles", {})
        else:
            profiles = {}

        profiles[active_name] = {
            "llama_server_path": config.get("llama_server_path", ""),
            "llama_server_args": config.get("llama_server_args", []),
            "server_url": config.get("server_url", ""),
        }

        new_config = {
            "config_version": 2,
            "active_profile": active_name,
            "profiles": profiles,
        }

        # Compare old active profile with new values
        old_profile = profiles.get(active_name, {}) if old_parsed else {}
        changed = (
            old_profile.get("llama_server_path") != config.get("llama_server_path")
            or old_profile.get("llama_server_args") != config.get("llama_server_args")
            or old_profile.get("server_url") != config.get("server_url")
        )

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, indent=2)
        except Exception as exc:
            return {"error": str(exc)}

        if changed:
            # Store old config for revert, update in-memory globals, restart.
            _previous_config = old_config
            LLAMA_SERVER_PATH = config.get("llama_server_path", LLAMA_SERVER_PATH)
            LLAMA_SERVER_ARGS = config.get("llama_server_args", LLAMA_SERVER_ARGS)
            SERVER_URL = config.get("server_url", SERVER_URL)
            threading.Thread(target=restart_server, daemon=True).start()
            return {"success": True, "restarted": True}

        return {"success": True, "restarted": False}

    def revert_config(self):
        """Revert to the previous config and restart."""
        global LLAMA_SERVER_PATH, LLAMA_SERVER_ARGS, SERVER_URL, _previous_config

        if _previous_config is None:
            return {"error": "No previous config to revert to."}

        config_path = os.path.join(_get_data_dir(), CONFIG_FILENAME)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(_previous_config, f, indent=2)
        except Exception as exc:
            return {"error": str(exc)}

        LLAMA_SERVER_PATH = _previous_config.get("llama_server_path", LLAMA_SERVER_PATH)
        LLAMA_SERVER_ARGS = _previous_config.get("llama_server_args", LLAMA_SERVER_ARGS)
        SERVER_URL = _previous_config.get("server_url", SERVER_URL)
        _previous_config = None
        threading.Thread(target=restart_server, daemon=True).start()
        return {"success": True}

    def restart_server(self):
        """Manually restart the server (called from the settings modal)."""
        threading.Thread(target=restart_server, daemon=True).start()
        return {"success": True}

    def get_startup_enabled(self):
        """Return whether Start with Windows is currently enabled."""
        return _is_startup_enabled()

    def set_startup(self, enable):
        """Enable or disable Start with Windows. Returns success or error."""
        try:
            _set_startup(enable)
            return {"success": True, "enabled": enable}
        except Exception as exc:
            return {"error": str(exc)}

    def get_server_error(self):
        """Return the last server error message, if any."""
        return {"error": _last_server_error}


# ---------------------------------------------------------------------------
# TRAY ICON
# ---------------------------------------------------------------------------

def _create_tray_image():
    """
    Load the Llamabox .ico file from the executable / script directory.
    Falls back to a solid-blue circle if the file cannot be found.
    """
    ico_path = os.path.join(_get_base_path(), "llamabox.ico")
    if os.path.isfile(ico_path):
        return Image.open(ico_path)

    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return image


def _on_tray_show(icon, item):
    """Tray menu callback: signal the main thread to show the window."""
    _command_queue.put("show")


def _on_tray_edit_config(icon, item):
    """
    Open config.json in the user's default text editor so they can change
    server settings without hunting for the file manually.  Works both
    when running as a script and when frozen as a .exe.
    """
    config_path = os.path.join(_get_data_dir(), CONFIG_FILENAME)
    if os.path.exists(config_path):
        _open_file(config_path)


def _on_tray_view_logs(icon, item):
    """
    Open app.log in the user's default text editor, same convenience
    pattern as the Edit Config tray option.
    """
    log_path = os.path.join(_get_data_dir(), APP_LOG_FILENAME)
    if os.path.exists(log_path):
        _open_file(log_path)


def _on_tray_restart(icon, item):
    """
    Tray menu callback: restart the server in a background thread so the
    tray event loop is not blocked during shutdown.
    """
    threading.Thread(target=restart_server, daemon=True).start()


def _on_tray_quit(icon, item):
    """
    Tray menu callback: signal the main thread to shut down, destroy the
    window if open (so webview.start() unblocks), then remove the icon.
    The quit signal is sent FIRST because icon.stop() can hang when called
    from inside pystray's message loop on Windows.
    """
    _command_queue.put("quit")

    # If the pywebview window is open, destroy it so the main thread
    # unblocks from webview.start() and can process the quit command.
    if _window is not None:
        try:
            _window.destroy()
        except Exception:
            pass

    icon.stop()


def _run_tray():
    """
    Create and run the system tray icon.  This function blocks until
    icon.stop() is called (by the Quit menu item).  It runs in a
    background daemon thread so the main thread can manage pywebview.
    """
    image = _create_tray_image()

    settings_menu = pystray.Menu(
        Item("Edit Config", _on_tray_edit_config),
        Item("Start with Windows", _on_tray_toggle_startup, checked=_is_startup_checked),
        Item("View Logs", _on_tray_view_logs),
    )

    menu = pystray.Menu(
        Item("Show Window", _on_tray_show, default=True),
        Item("Restart Server", _on_tray_restart),
        pystray.Menu.SEPARATOR,
        Item("Settings", settings_menu),
        pystray.Menu.SEPARATOR,
        Item("Quit", _on_tray_quit),
    )

    icon = pystray.Icon("llamabox", image, "Llamabox", menu)

    # Start the live stats monitor in a background thread so the tooltip
    # auto-updates with CPU and RAM usage every 3 seconds.
    threading.Thread(target=_stats_monitor, args=(icon,), daemon=True).start()

    icon.run()


# ---------------------------------------------------------------------------
# LIVE STATS MONITOR (CPU / RAM)
# ---------------------------------------------------------------------------

def _stats_monitor(icon):
    """
    Background thread: every 3 seconds, read the llama-server process's
    current CPU usage (%) and RAM (MB), then update the tray icon tooltip.

    psutil.Process.cpu_percent() needs a baseline call before it returns
    meaningful values.  To avoid showing 0%, the first update cycle after
    creating a new psutil.Process object reports RAM only (with a
    "measuring..." label for CPU).  The next cycle includes both values.

    After a server restart (PID change), the old psutil.Process object is
    discarded and a fresh one is created for the new PID.

    Only logs when a meaningful state change occurs (server found,
    crashed, monitoring error) -- never logs individual samples.
    """
    global _server_stop_intentional

    psutil_proc = None
    last_pid = None
    skip_cpu = False
    was_running = False
    crash_alerted = False

    def _notify_crash(pid):
        """Log an ERROR and show a one-shot native message box."""
        nonlocal crash_alerted
        if crash_alerted:
            return
        crash_alerted = True

        logging.error(
            "llama-server.exe stopped unexpectedly (was PID %s) -- "
            "it may have crashed. Check server.log for details.",
            pid,
        )

        _show_messagebox(
            "Llamabox - Server Error",
            "The server stopped unexpectedly and may have crashed.\n\n"
            "Check server.log and app.log for details.",
            _MB_ICONERROR,
        )

    while True:
        time.sleep(3)

        try:
            current_pid = _server_process.pid if _server_process else None
        except (AttributeError, OSError):
            current_pid = None

        if current_pid is None:
            # No server PID available.
            if psutil_proc is not None:
                if was_running:
                    if _server_stop_intentional:
                        _server_stop_intentional = False
                    else:
                        _notify_crash(last_pid)
                    was_running = False
            psutil_proc = None
            last_pid = None
        elif current_pid != last_pid:
            # PID changed (new server or first discovery).
            last_pid = current_pid
            was_running = False
            crash_alerted = False
            try:
                psutil_proc = psutil.Process(current_pid)
                psutil_proc.cpu_percent()
                skip_cpu = True
                logging.info("Monitoring server PID %s", current_pid)
            except psutil.NoSuchProcess:
                psutil_proc = None

        # Build the tooltip string (CPU and RAM only -- battery moved to
        # the shell.html toolbar in Phase 9).

        if psutil_proc is not None:
            try:
                mem_bytes = psutil_proc.memory_info().rss
                mem_mb = mem_bytes / (1024 * 1024)

                if skip_cpu:
                    skip_cpu = False
                    tooltip = f"Llamabox - RAM: {int(mem_mb)} MB | CPU: measuring..."
                    _latest_stats.update({"ram_mb": int(mem_mb), "cpu": None, "cpu_measuring": True, "running": True})
                else:
                    cpu = psutil_proc.cpu_percent()
                    tooltip = f"Llamabox - CPU: {cpu:.1f}% | RAM: {int(mem_mb)} MB"
                    _latest_stats.update({"ram_mb": int(mem_mb), "cpu": cpu, "cpu_measuring": False, "running": True})

                was_running = True

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                if was_running:
                    if _server_stop_intentional:
                        _server_stop_intentional = False
                    else:
                        _notify_crash(last_pid)
                    was_running = False
                psutil_proc = None
                last_pid = None
                tooltip = "Llamabox - Server not running"
                _latest_stats.update({"cpu": None, "ram_mb": None, "cpu_measuring": False, "running": False})
        else:
            tooltip = "Llamabox - Server not running"
            _latest_stats.update({"cpu": None, "ram_mb": None, "cpu_measuring": False, "running": False})

        try:
            icon.title = tooltip
        except Exception:
            pass


# ---------------------------------------------------------------------------
# SERVER WAIT LOOP
# ---------------------------------------------------------------------------

class ServerTimeoutError(Exception):
    """Raised when the server does not start within the configured timeout."""
    pass


def wait_for_server(url, interval, timeout):
    """
    Poll the given URL every `interval` seconds until we get any HTTP
    response.  Any status code (even 404, 500, etc.) counts as "server
    is running".  Raises ServerTimeoutError if `timeout` seconds pass
    with no response.

    Also detects fast failure: if the server process exits within the
    first few seconds, it likely crashed due to bad args / missing file.
    """
    global _last_server_error
    start = time.time()

    while True:
        elapsed = time.time() - start
        if elapsed >= timeout:
            raise ServerTimeoutError("Server did not start within 60 seconds")

        # Fast-failure detection: if the server process already exited
        # (e.g. bad arguments, missing file), don't keep polling.
        if _server_process is not None and _server_process.poll() is not None:
            exit_code = _server_process.returncode
            error_msg = _read_server_log_tail(10)
            _last_server_error = (
                f"Server exited immediately (exit code {exit_code}).\n\n"
                f"Last output from server.log:\n{error_msg}"
            )
            logging.error("Server failed to start: %s", _last_server_error)
            raise ServerTimeoutError(_last_server_error)

        logging.info("Waiting for server...")

        try:
            # Attempt a GET request.  We use a short timeout so we do not
            # get stuck on a single attempt if the connection hangs.
            requests.get(url, timeout=5)

            # If we get here, the server responded (any status code counts).
            logging.info("Server ready, launching window...")
            return

        except requests.ConnectionError:
            # Server is not accepting connections yet -- keep polling.
            pass
        except requests.Timeout:
            # Request timed out -- also keep polling.
            pass

        time.sleep(interval)


# ---------------------------------------------------------------------------
# DARK TITLE BAR
# ---------------------------------------------------------------------------

# DWMWA_USE_IMMERSIVE_DARK_MODE tells Windows to render the title bar in
# dark mode (value 20 on Win10 1903+, value 19 on earlier builds).
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19


def _set_dark_title_bar(hwnd):
    """
    Apply a dark title bar to the given window handle using the Windows
    DWM API.  Returns True on success, False on failure.
    """
    if not hwnd:
        logging.warning("_set_dark_title_bar: hwnd is None, skipping")
        return False

    try:
        # Enable immersive dark mode (attribute 20).
        # This is the well-documented DWM attribute that toggles the
        # dark title bar on Windows 10 20H1+ and Windows 11.
        value = ctypes.c_int(1)
        hr = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value), ctypes.sizeof(value),
        )
        if hr != 0:
            logging.warning("DwmSetWindowAttribute(DWMWA_USE_IMMERSIVE_DARK_MODE) returned HRESULT %s", hr)

        # Also try the older attribute value for pre-20H1 builds.
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE_OLD,
            ctypes.byref(value), ctypes.sizeof(value),
        )

        # Flush changes so they take effect immediately.
        ctypes.windll.dwmapi.DwmFlush()

        logging.info("Applied dark mode title bar to HWND %s", hwnd)
        return True

    except AttributeError as exc:
        logging.warning("DWM API not available: %s", exc)
        return False
    except OSError as exc:
        logging.warning("DWM API call failed: %s", exc)
        return False


def _style_window():
    """
    Find the pywebview window's underlying WinForms form, apply the dark
    title bar via the DWM API, and set the window/taskbar icon.

    Polls for up to 15 seconds because the form is created inside
    webview.start() (the main thread blocks until the window closes).

    Accessing the form handle through pywebview's internal
    BrowserView.instances is more reliable than FindWindowW, which can
    miss the window if the title hasn't been set yet or if the window
    hasn't completed its initialisation when we look for it.
    """
    ico_path = os.path.join(_get_base_path(), "llamabox.ico")
    if not os.path.isfile(ico_path):
        ico_path = None

    for _ in range(30):
        try:
            from webview.platforms import winforms as wf
        except ImportError:
            time.sleep(0.5)
            continue

        instances = wf.BrowserView.instances
        if not instances:
            time.sleep(0.5)
            continue

        form = list(instances.values())[0]
        try:
            hwnd = form.Handle.ToInt32()
        except Exception:
            time.sleep(0.5)
            continue

        if hwnd:
            _set_dark_title_bar(hwnd)

        if hwnd and ico_path:
            try:
                import clr
                clr.AddReference('System.Drawing')
                from System.Drawing import Icon
                form.Icon = Icon(ico_path)
                logging.info("Set window icon from %s", ico_path)
            except Exception as exc:
                logging.warning("Could not set window icon: %s", exc)

        if hwnd:
            return

        time.sleep(0.5)


# ---------------------------------------------------------------------------
# WINDOW MANAGEMENT LOOP
# ---------------------------------------------------------------------------

def run_window_loop():
    """
    Main-thread loop: create a pywebview window and wait.  When the user
    closes the window (X button), drain any stale 'show' commands, then
    block waiting for a fresh command from the tray:

      "quit" -- exit the loop (terminate_server happens afterward in main())
      "show" -- loop back and create a fresh window

    The window is *not* hidden on close -- pywebview on Windows (WebView2 /
    WinForms) does not expose a Python-level hook to cancel the close
    event and hide the window instead.  The standard workaround (used here)
    is to let the window close normally and recreate it when the user
    clicks "Show Window" in the tray menu.  This means the page reloads
    when the window reappears, but it is reliable and simple.

    We pass storage_path and private_mode=False to webview.start() so the
    underlying WebView2 engine uses a fixed, persistent user-data folder
    at %APPDATA%\\Llamabox\\WebView2Data.  This ensures that the
    llama-server web UI's localStorage (chat history, UI settings) is
    preserved across window recreation and across app restarts.

    The window URL is our local shell.html (which contains a toolbar and
    an iframe embedding the actual server UI).  The iframe src is set
    dynamically via the JS bridge (JsApi.get_server_url).
    """
    from pathlib import Path

    webview2_data_dir = os.path.join(_get_data_dir(), "WebView2Data")

    shell_path = os.path.join(_get_base_path(), SHELL_HTML_FILENAME)
    shell_dir = os.path.dirname(shell_path)

    # Serve shell.html and proxy the llama-server through a single local
    # HTTP server.  This keeps the parent and iframe on the same origin
    # (same port), which is required for the Clipboard API to work inside
    # the iframe.  The llama-server gets every request by default; our
    # shell.html is served only at /__shell/ so the llama-server's
    # absolute paths (e.g. /style.css, /app.js) route through the proxy
    # and resolve correctly.
    class _ProxyHandler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=shell_dir, **kw)

        def do_GET(self):
            if self.path.startswith("/__shell"):
                # Serve shell.html and static assets from shell_dir
                self.path = self.path.replace("/__shell", "", 1) or f"/{SHELL_HTML_FILENAME}"
                super().do_GET()
            else:
                self._proxy(self.path)

        def do_POST(self):
            self._proxy(self.path, method="POST")

        def _proxy(self, path, method="GET"):
            # Extract host:port from the configured SERVER_URL at request time
            # so it picks up any config changes.
            from urllib.parse import urlparse
            parsed = urlparse(SERVER_URL)
            target = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}{path}"
            try:
                body = None
                if method == "POST":
                    length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(length) if length else None
                resp = requests.request(
                    method, target, data=body,
                    headers={"Content-Type": self.headers.get("Content-Type", "application/octet-stream")},
                    timeout=30, stream=True,
                )
                self.send_response(resp.status_code)
                for key, val in resp.headers.items():
                    if key.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(key, val)
                self.end_headers()
                for chunk in resp.iter_content(8192):
                    self.wfile.write(chunk)
            except Exception:
                self.send_error(502)

        def log_message(self, fmt, *a):
            pass  # suppress request logs

    httpd = HTTPServer(("127.0.0.1", 0), _ProxyHandler)
    http_port = httpd.server_address[1]
    global _http_port
    _http_port = http_port
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    shell_url = f"http://127.0.0.1:{http_port}/__shell/{SHELL_HTML_FILENAME}"

    while True:
        global _window
        _window = webview.create_window(
            title=WINDOW_TITLE,
            url=shell_url,
            js_api=JsApi(),
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            min_size=(600, 400),
            resizable=True,
        )

        # Start a background thread that polls for the window HWND and
        # applies the dark title bar once the window appears.  We do this
        # instead of using webview.start(func=...) because pywebview 4.x
        # does not expose a native_handle property on the Window object.
        # Only on Windows; Linux uses GTK/Qt and doesn't have DWM.
        if IS_WINDOWS:
            threading.Thread(target=_style_window, daemon=True).start()

        # webview.start() blocks until the window is closed (or destroyed
        # by the Quit callback).  After it returns, clear the reference.
        webview.start(
            storage_path=webview2_data_dir,
            private_mode=False,
        )
        _window = None
        httpd.shutdown()

        # At this point the window is gone, but the tray is still running.
        # Drain any stale "show" commands that were queued while the window
        # was visible (e.g. user clicked the menu item repeatedly).
        while True:
            try:
                cmd = _command_queue.get_nowait()
            except queue.Empty:
                break
            if cmd == "quit":
                return

        # Wait for a fresh command from the tray.
        cmd = _command_queue.get()

        if cmd == "quit":
            return

        # "show" -- loop back and create a new window.


# ---------------------------------------------------------------------------
# SINGLE-INSTANCE CHECK
# ---------------------------------------------------------------------------

# Named kernel mutex that enforces single-instance behaviour.  The handle
# is intentionally leaked so the kernel destroys the mutex object when
# the process exits (even on crash), preventing orphaned-lock issues.
_SINGLE_INSTANCE_MUTEX_NAME = "Llamabox_SingleInstance_Mutex"
_SINGLE_INSTANCE_LOCK_FILE = os.path.join(_get_data_dir(), ".lock")


def _check_single_instance():
    """
    Return True if this is the only instance running.
    Windows: uses CreateMutexW with bInitialOwner=TRUE.
    Linux: uses a lock file with fcntl.flock.
    """
    if IS_WINDOWS:
        handle = ctypes.windll.kernel32.CreateMutexW(
            None, True, _SINGLE_INSTANCE_MUTEX_NAME,
        )
        if ctypes.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            ctypes.windll.kernel32.CloseHandle(handle)
            return False
        return True

    elif IS_LINUX:
        import fcntl
        try:
            lock_fd = open(_SINGLE_INSTANCE_LOCK_FILE, "w")
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_fd.write(str(os.getpid()))
            lock_fd.flush()
            globals()["_lock_fd"] = lock_fd
            return True
        except OSError:
            return False

    return True


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def main():
    """
    0. Load configuration from config.json (create it on first run).
    1. Kill any leftover llama-server processes from previous runs.
    2. Launch a fresh llama-server subprocess.
    3. Wait for the server to respond on SERVER_URL.
    4. Start the system tray icon in a background thread.
    5. Enter the window management loop (create, close, recreate on demand).
    6. On quit (from tray menu), terminate the server and exit.
    """
    # Set up file logging before anything else so all messages are captured.
    _init_logging()

    # Migrate config and log files from the old script/exe directory or
    # from the old %APPDATA%\LocalAI data directory to %APPDATA%\Llamabox
    # (one-time, files only copied if absent at target).
    _migrate_old_files()

    # Exit early if another instance is already running.
    if not _check_single_instance():
        logging.info("Another instance is already running -- exiting.")
        _show_messagebox(
            "Llamabox",
            "Llamabox is already running.\nCheck your system tray.",
            _MB_ICONINFO,
        )
        sys.exit(0)

    # Load settings from config.json (auto-creates on first run, exits).
    global LLAMA_SERVER_PATH, LLAMA_SERVER_ARGS, SERVER_URL
    config = load_config()
    profile = _get_active_profile(config)
    LLAMA_SERVER_PATH = profile["llama_server_path"]
    LLAMA_SERVER_ARGS = profile["llama_server_args"]
    SERVER_URL = profile["server_url"]

    try:
        # Clean up any orphaned processes from prior runs.
        terminate_existing_servers()

        # Start the server.
        launch_server()

        # Block until the server responds (or we hit the timeout and exit).
        wait_for_server(SERVER_URL, POLL_INTERVAL, TIMEOUT_SECONDS)

        # One-time low-battery warning (only on initial launch).
        _check_battery_on_startup()

        # Start the tray icon in a daemon thread so it does not block
        # the main thread (which must own the pywebview GUI loop).
        tray_thread = threading.Thread(target=_run_tray, daemon=True)
        tray_thread.start()

        # Schedule a silent background update check a few seconds after
        # launch (daemon thread, won't block shutdown).
        threading.Thread(
            target=lambda: (time.sleep(AUTO_UPDATE_CHECK_DELAY), _check_for_updates())[0],
            daemon=True,
        ).start()

        # Enter the window management loop.  This returns only when the
        # user selects "Quit" from the tray menu.
        run_window_loop()

    except ServerTimeoutError as error:
        logging.error(error)
        sys.exit(1)

    finally:
        # Either the user quit from the tray (normal), or the script is
        # being killed (Ctrl+C).  Either way, shut down the server cleanly.
        terminate_server()
        # Force the process to exit.  Daemon threads (like the pystray
        # message loop) can otherwise prevent Python from terminating,
        # leaving the terminal stuck even after everything is cleaned up.
        os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Log the full traceback to app.log before showing the message box.
        logging.critical(
            "FATAL ERROR\n%s",
            traceback.format_exc(),
        )

        # Show a native message box so the user knows what happened.
        import ctypes
        msg = (
            "Something went wrong.\n\n"
            f"Check app.log in:\n{_get_data_dir()}\n\n"
            "for details."
        )
        _show_messagebox("Llamabox - Error", msg, _MB_ICONERROR)

        os._exit(1)