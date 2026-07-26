from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TASK_NAME = "ZapretManager"


def _launch_command() -> str:
    if getattr(sys, "frozen", False):
        exe = str(Path(sys.executable).resolve())
        return f'"{exe}" --autostart'
    # Dev: prefer pythonw next to python
    py = Path(sys.executable)
    pythonw = py.with_name("pythonw.exe")
    runner = str(pythonw if pythonw.exists() else py)
    script = str(Path(__file__).resolve().with_name("app.py"))
    return f'"{runner}" "{script}" --autostart'


def is_autostart_enabled() -> bool:
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def enable_autostart() -> None:
    # /RL HIGHEST — runs elevated at logon without UAC prompt each time
    cmd = [
        "schtasks",
        "/Create",
        "/TN",
        TASK_NAME,
        "/TR",
        _launch_command(),
        "/SC",
        "ONLOGON",
        "/RL",
        "HIGHEST",
        "/F",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        timeout=20,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or b"").decode("cp866", errors="ignore").strip()
        raise RuntimeError(err or "Не удалось создать задачу автозапуска")


def disable_autostart() -> None:
    if not is_autostart_enabled():
        return
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        timeout=15,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or b"").decode("cp866", errors="ignore").strip()
        raise RuntimeError(err or "Не удалось удалить задачу автозапуска")


def set_autostart(enabled: bool) -> None:
    if enabled:
        enable_autostart()
    else:
        disable_autostart()
