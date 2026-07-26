from __future__ import annotations

import json
import sys
from pathlib import Path


def get_app_dir() -> Path:
    """Directory with the exe (frozen) or project folder (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = get_app_dir()
CONFIG_PATH = APP_DIR / "config.json"
APP_VERSION = "1.3.0"


def _default_zapret_root() -> Path:
    # Prefer folder that already contains zapret-discord-youtube-*
    for candidate in (APP_DIR, APP_DIR.parent):
        try:
            if any(candidate.glob("zapret-discord-youtube-*")):
                return candidate
        except OSError:
            continue
    # Fresh install: keep everything next to the .exe (e.g. Desktop)
    return APP_DIR


DEFAULT_ZAPRET_ROOT = _default_zapret_root()

DEFAULTS = {
    "zapret_root": str(DEFAULT_ZAPRET_ROOT),
    "version_folder": "",
    "strategy": "general.bat",
    "autostart_windows": False,
    "autostart_strategy": False,
    "available_update": "",
    "auto_check_updates": True,
    "auto_update_zapret": True,
    "skip_app_version": "",
}


def load_config() -> dict:
    data = dict(DEFAULTS)
    # Re-evaluate default root each load if missing from file
    data["zapret_root"] = str(_default_zapret_root())
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update({k: loaded[k] for k in DEFAULTS if k in loaded})
        except (OSError, json.JSONDecodeError):
            pass
    return data


def save_config(data: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
