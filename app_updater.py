from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from config import APP_DIR, APP_VERSION
from core import version_key

MANAGER_RELEASES_API = (
    "https://api.github.com/repos/Anvar0525/ZapretManager/releases/latest"
)
UA = f"ZapretManager/{APP_VERSION}"


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
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as resp, dest.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)


def schedule_replace_and_restart(new_exe: Path) -> None:
    """
    Current process exits; a helper bat replaces the exe and relaunches it.
    Only works when running as frozen .exe.
    """
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Самообновление работает только из собранного .exe")

    current = Path(sys.executable).resolve()
    bat = Path(tempfile.gettempdir()) / "zapret_manager_update.bat"
    pid = os.getpid()
    bat.write_text(
        "\r\n".join(
            [
                "@echo off",
                f":wait",
                f'tasklist /FI "PID eq {pid}" | find "{pid}" >nul',
                "if not errorlevel 1 (",
                "  timeout /t 1 /nobreak >nul",
                "  goto wait",
                ")",
                f'copy /Y "{new_exe}" "{current}" >nul',
                f'start "" "{current}"',
                f'del "%~f0"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat)],
        cwd=str(current.parent),
        creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        close_fds=True,
    )
