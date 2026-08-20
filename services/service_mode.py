import os
import subprocess
import sys
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None

from services.credential_store import has_credentials

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE = "SolarEconomy"
_MODE_FILE = "background_mode"

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008


def _state_dir() -> Path | None:
    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        return None
    path = Path(local_app_data) / "SolarEconomy"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None
    return path


def _mode_path() -> Path | None:
    directory = _state_dir()
    return directory / _MODE_FILE if directory else None


def is_background_mode() -> bool:
    path = _mode_path()
    if path is None:
        return False
    try:
        return path.exists() and path.read_text(encoding="utf-8").strip() == "1"
    except Exception:
        return False


def set_background_mode(enabled: bool) -> bool:
    path = _mode_path()
    if path is None:
        return False
    try:
        path.write_text("1" if enabled else "0", encoding="utf-8")
        return True
    except Exception:
        return False


def launch_command() -> list[str] | None:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    script = Path(__file__).parent.parent / "index.py"
    if not script.exists():
        return None
    interpreter = sys.executable
    pythonw = Path(interpreter).parent / "pythonw.exe"
    if pythonw.exists():
        interpreter = str(pythonw)
    return [interpreter, str(script)]


def relaunch_detached() -> bool:
    command = launch_command()
    if not command:
        return False
    try:
        subprocess.Popen(
            command,
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
            close_fds=True,
            cwd=str(Path(__file__).parent.parent),
        )
        return True
    except Exception:
        return False


def relaunch_with_console() -> bool:
    command = launch_command()
    if not command:
        return False
    if not getattr(sys, "frozen", False):
        interpreter = Path(command[0])
        if interpreter.name.lower() == "pythonw.exe":
            console = interpreter.parent / "python.exe"
            if console.exists():
                command[0] = str(console)
    try:
        subprocess.Popen(
            command,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            close_fds=True,
            cwd=str(Path(__file__).parent.parent),
        )
        return True
    except Exception:
        return False


def is_autostart_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, _RUN_VALUE)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable_autostart() -> tuple[bool, str]:
    if winreg is None:
        return False, "Autostart is only supported on Windows."
    if not has_credentials():
        return False, "Saved credentials are required before autostart can be enabled. Run 'login save' first."
    command = launch_command()
    if not command:
        return False, "Could not determine how to relaunch the bot."
    quoted = " ".join(f'"{part}"' for part in command)
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _RUN_VALUE, 0, winreg.REG_SZ, quoted)
        return True, "Autostart enabled. The bot will start when you sign in to Windows."
    except OSError as e:
        return False, f"Failed to write the autostart entry: {e}"


def disable_autostart() -> tuple[bool, str]:
    if winreg is None:
        return False, "Autostart is only supported on Windows."
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _RUN_VALUE)
        return True, "Autostart disabled."
    except FileNotFoundError:
        return True, "Autostart was not enabled."
    except OSError as e:
        return False, f"Failed to remove the autostart entry: {e}"


def service_status() -> dict:
    return {
        "background_mode": is_background_mode(),
        "autostart": is_autostart_enabled(),
        "has_credentials": has_credentials(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "console_attached": sys.stdin is not None and sys.stdin.isatty(),
    }
