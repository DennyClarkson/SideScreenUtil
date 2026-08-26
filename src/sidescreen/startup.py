from __future__ import annotations

import subprocess
import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
FULL_STARTUP_ENTRY = "SideScreenUtil"


def startup_command(executable: Path | None = None) -> str:
    path = executable or Path(sys.executable)
    return subprocess.list2cmdline([str(path), "--startup"])


def set_start_with_windows(enabled: bool, executable: Path | None = None) -> None:
    if enabled:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(
                key,
                FULL_STARTUP_ENTRY,
                0,
                winreg.REG_SZ,
                startup_command(executable),
            )
        return
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, FULL_STARTUP_ENTRY)
    except FileNotFoundError:
        pass
