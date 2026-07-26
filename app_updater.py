from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from config import APP_DIR, APP_VERSION
from core import version_key

MANAGER_RELEASES_API = (
    "https://api.github.com/repos/Anvar0525/ZapretManager/releases/latest"
)
UA = f"ZapretManager/{APP_VERSION}"

# Onefile PyInstaller builds are typically > 8 MB; HTML error pages are tiny
_MIN_EXE_BYTES = 5 * 1024 * 1024


@dataclass
class AppRelease:
    version: str
    exe_url: str
    html_url: str


def _normalize_tag(tag: str) -> str:
    tag = (tag or "").strip()
    if tag.lower().startswith("v"):
        tag = tag[1:]
    return tag


def fetch_latest_app_release() -> AppRelease | None:
    req = urllib.request.Request(
        MANAGER_RELEASES_API,
        headers={"User-Agent": UA, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    version = _normalize_tag(str(data.get("tag_name") or ""))
    if not version:
        return None
    exe_url = ""
    for asset in data.get("assets") or []:
        name = (asset.get("name") or "").lower()
        if name == "zapretmanager.exe" or (
            name.endswith(".exe") and "zapretmanager" in name
        ):
            exe_url = asset.get("browser_download_url") or ""
            break
    if not exe_url:
        for asset in data.get("assets") or []:
            if (asset.get("name") or "").lower().endswith(".exe"):
                exe_url = asset.get("browser_download_url") or ""
                break
    if not exe_url:
        return None
    return AppRelease(
        version=version,
        exe_url=exe_url,
        html_url=str(data.get("html_url") or ""),
    )


def is_app_update_available(remote: str, local: str = APP_VERSION) -> bool:
    return bool(remote) and version_key(remote) > version_key(local)


def download_app_exe(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        try:
            tmp.unlink()
        except OSError:
            pass
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as resp, tmp.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
    _validate_exe(tmp)
    tmp.replace(dest)


def _validate_exe(path: Path) -> None:
    size = path.stat().st_size
    if size < _MIN_EXE_BYTES:
        raise RuntimeError(
            f"Скачанный файл слишком маленький ({size} байт) — похоже, не exe"
        )
    with path.open("rb") as fh:
        magic = fh.read(2)
    if magic != b"MZ":
        raise RuntimeError("Скачанный файл не является Windows .exe")


def schedule_replace_and_restart(new_exe: Path) -> None:
    """
    Current process exits; a detached helper bat replaces the exe and relaunches it.

    Important for PyInstaller --onefile: the new process must NOT be a child of the
    old bootloader, otherwise the old process deletes _MEI* and the new launch fails
    with "Failed to load Python DLL".
    """
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Самообновление работает только из собранного .exe")

    _validate_exe(new_exe)

    current = Path(sys.executable).resolve()
    # Keep the new binary next to the app (not only in Temp) for a safer swap
    staged = current.with_name(current.stem + ".update.exe")
    try:
        if staged.exists():
            staged.unlink()
    except OSError:
        pass
    # copy2 via read/write — shutil.copy2 also fine
    import shutil

    shutil.copy2(new_exe, staged)

    bat = current.parent / "zapret_manager_update.bat"
    pid = os.getpid()
    # Use ping instead of timeout (timeout breaks under CREATE_NO_WINDOW).
    # Breakaway + extra delay so old _MEI* cleanup finishes before new extract.
    bat.write_text(
        "\r\n".join(
            [
                "@echo off",
                "setlocal",
                "set PYINSTALLER_RESET_ENVIRONMENT=1",
                f'set "TARGET={current}"',
                f'set "STAGED={staged}"',
                f'set "BACKUP={current.with_suffix(current.suffix + ".bak")}"',
                f":wait",
                f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul',
                "if not errorlevel 1 (",
                "  ping 127.0.0.1 -n 2 >nul",
                "  goto wait",
                ")",
                "REM let old onefile bootloader finish deleting its _MEI folder",
                "ping 127.0.0.1 -n 4 >nul",
                'if exist "%BACKUP%" del /F /Q "%BACKUP%" >nul 2>&1',
                'if exist "%TARGET%" move /Y "%TARGET%" "%BACKUP%" >nul',
                'move /Y "%STAGED%" "%TARGET%" >nul',
                "if not exist \"%TARGET%\" (",
                '  if exist "%BACKUP%" move /Y "%BACKUP%" "%TARGET%" >nul',
                "  exit /b 1",
                ")",
                'del /F /Q "%BACKUP%" >nul 2>&1',
                "REM new console session — not a child of the old onefile bootloader",
                'start "" "%TARGET%"',
                'del /F /Q "%~f0" >nul 2>&1',
                "endlocal",
                "",
            ]
        ),
        encoding="utf-8",
        errors="replace",
    )

    # Fully detach helper from this PyInstaller process tree
    flags = (
        getattr(subprocess, "DETACHED_PROCESS", 0x8)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
        | 0x01000000  # CREATE_BREAKAWAY_FROM_JOB
    )
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat)],
        cwd=str(current.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
        env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"},
    )
