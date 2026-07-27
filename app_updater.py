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

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


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
    Current process exits; a hidden PowerShell helper replaces the exe and relaunches.

    Must not be a child of the old PyInstaller onefile bootloader (avoids _MEI DLL error).
    """
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Самообновление работает только из собранного .exe")

    _validate_exe(new_exe)

    current = Path(sys.executable).resolve()
    staged = current.with_name(current.stem + ".update.exe")
    backup = current.with_suffix(current.suffix + ".bak")
    try:
        if staged.exists():
            staged.unlink()
    except OSError:
        pass

    import shutil

    shutil.copy2(new_exe, staged)

    pid = os.getpid()
    proc_name = current.stem  # ZapretManager
    ps1 = current.parent / "zapret_manager_update.ps1"

    # Hidden updater: wait for PID (timeout), wait until process name is gone,
    # swap files, start new exe, clean up.
    ps1.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'SilentlyContinue'",
                f"$oldPid = {pid}",
                f"$target = '{str(current).replace(chr(39), chr(39)+chr(39))}'",
                f"$staged = '{str(staged).replace(chr(39), chr(39)+chr(39))}'",
                f"$backup = '{str(backup).replace(chr(39), chr(39)+chr(39))}'",
                f"$procName = '{proc_name.replace(chr(39), chr(39)+chr(39))}'",
                "try { Wait-Process -Id $oldPid -Timeout 90 } catch {}",
                "$deadline = (Get-Date).AddSeconds(45)",
                "while ((Get-Date) -lt $deadline) {",
                "  $left = @(Get-Process -Name $procName -ErrorAction SilentlyContinue)",
                "  if ($left.Count -eq 0) { break }",
                "  Start-Sleep -Milliseconds 400",
                "}",
                "Start-Sleep -Seconds 2",
                "if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }",
                "if (Test-Path -LiteralPath $target) { Move-Item -LiteralPath $target -Destination $backup -Force }",
                "Move-Item -LiteralPath $staged -Destination $target -Force",
                "if (-not (Test-Path -LiteralPath $target)) {",
                "  if (Test-Path -LiteralPath $backup) { Move-Item -LiteralPath $backup -Destination $target -Force }",
                "  exit 1",
                "}",
                "if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }",
                "$env:PYINSTALLER_RESET_ENVIRONMENT = '1'",
                "Start-Process -FilePath $target",
                "Start-Sleep -Milliseconds 500",
                "Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force",
                "",
            ]
        ),
        encoding="utf-8",
        errors="replace",
    )

    flags = (
        CREATE_NO_WINDOW
        | DETACHED_PROCESS
        | CREATE_NEW_PROCESS_GROUP
        | CREATE_BREAKAWAY_FROM_JOB
    )
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(ps1),
        ],
        cwd=str(current.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
        env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"},
    )
