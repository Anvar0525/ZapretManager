from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable

from config import APP_DIR, APP_VERSION, load_config, save_config
from core import (
    list_strategies,
    pick_version,
    start_strategy,
    stop_winws,
    winws_running,
)
from updater import check_for_update, download_and_install, fetch_release, local_has_version
from app_updater import (
    download_app_exe,
    fetch_latest_app_release,
    is_app_update_available,
    schedule_replace_and_restart,
)
from autostart import is_autostart_enabled, set_autostart

Listener = Callable[[], None]


class AppController:
    def __init__(self) -> None:
        self.config = load_config()
        self._lock = threading.Lock()
        self._updating = False
        self._listeners: list[Listener] = []
        self._strategies_cache: list[str] | None = None
        self._bootstrap_selection()

    def add_listener(self, callback: Listener) -> None:
        self._listeners.append(callback)

    def notify(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:
                pass

    @property
    def updating(self) -> bool:
        return self._updating

    @property
    def root(self) -> Path:
        return Path(self.config["zapret_root"])

    def selected_version(self):
        # Always use the newest local zapret folder
        return pick_version(self.root, "")

    def strategies(self) -> list[str]:
        if self._strategies_cache is None:
            version = self.selected_version()
            self._strategies_cache = list_strategies(version.path) if version else []
        return self._strategies_cache

    def invalidate_lists(self) -> None:
        self._strategies_cache = None

    def status_dict(self) -> dict:
        running = winws_running()
        version = self.selected_version()
        return {
            "running": running,
            "version": version.version if version else "?",
            "version_folder": version.name if version else "",
            "strategy": self.config.get("strategy", ""),
            "available_update": self.config.get("available_update") or "",
            "updating": self._updating,
            "app_version": APP_VERSION,
        }

    def status_text(self) -> str:
        s = self.status_dict()
        upd = f" · ↑{s['available_update']}" if s["available_update"] else ""
        state = "ON" if s["running"] else "OFF"
        return f"Zapret {state} · v{s['version']} · {s['strategy']}{upd}"

    def update_status_label(self) -> str:
        if self._updating:
            return "Обновление: выполняется…"
        avail = self.config.get("available_update") or ""
        if avail:
            return f"Доступно zapret: {avail}"
        version = self.selected_version()
        local = version.version if version else "?"
        return f"Zapret актуален (v{local})"

    def _bootstrap_selection(self) -> None:
        latest = self.selected_version()
        if latest:
            self.config["version_folder"] = latest.name
            strategies = list_strategies(latest.path)
            if self.config.get("strategy") not in strategies and strategies:
                self.config["strategy"] = strategies[0]
        # Sync checkbox with real scheduled task; refresh task path if enabled
        try:
            enabled = is_autostart_enabled()
            self.config["autostart_windows"] = enabled
            if enabled:
                # Keep TR pointing at current exe/script after updates
                set_autostart(True)
        except Exception:
            pass
        save_config(self.config)

    def set_autostart_windows(self, enabled: bool) -> str:
        try:
            set_autostart(enabled)
            self.config["autostart_windows"] = enabled
            save_config(self.config)
            self.notify()
            return "Автозапуск с Windows включён" if enabled else "Автозапуск выключен"
        except Exception as exc:
            # Revert UI expectation
            self.config["autostart_windows"] = is_autostart_enabled()
            save_config(self.config)
            self.notify()
            return f"Ошибка автозапуска: {exc}"

    def set_autostart_strategy(self, enabled: bool) -> None:
        self.config["autostart_strategy"] = bool(enabled)
        save_config(self.config)
        self.notify()

    def set_strategy(self, name: str, restart_if_running: bool = True) -> None:
        self.config["strategy"] = name
        save_config(self.config)
        if restart_if_running and winws_running():
            self.start()
        else:
            self.notify()

    def start(self) -> str:
        with self._lock:
            version = self.selected_version()
            if not version:
                msg = "Не найдена папка zapret-discord-youtube-*"
                self.notify()
                return msg
            strategy = self.config.get("strategy") or "general.bat"
            try:
                start_strategy(version.path, strategy)
                self.config["version_folder"] = version.name
                self.config["strategy"] = strategy
                save_config(self.config)
                msg = f"Запущено: {strategy}"
            except Exception as exc:
                msg = f"Ошибка запуска: {exc}"
            self.notify()
            return msg

    def stop(self) -> str:
        stop_winws()
        self.notify()
        return "Остановлено"

    def restart(self) -> str:
        stop_winws()
        return self.start()

    def check_updates(self, quiet_if_ok: bool = False) -> str:
        version = self.selected_version()
        local = version.version if version else ""
        # No local install → always treat latest as downloadable
        if not local:
            try:
                release = fetch_release()
                self.config["available_update"] = release.version
                save_config(self.config)
                self.notify()
                msg = (
                    f"Zapret не найден. Можно скачать {release.version} "
                    f"в папку:\n{self.root}"
                )
                return msg if not quiet_if_ok else msg
            except Exception as exc:
                self.notify()
                return f"Не удалось проверить GitHub: {exc}"

        available, release, message = check_for_update(local)
        if available and release:
            self.config["available_update"] = release.version
            if local_has_version(self.root, release.version) and local == release.version:
                self.config["available_update"] = ""
                message = f"У вас актуальная версия: {local}"
                available = False
        else:
            self.config["available_update"] = ""
        save_config(self.config)
        self.notify()
        if available or not quiet_if_ok:
            return message
        return ""

    def download_latest(self) -> str:
        """Download latest zapret even if 'available_update' is empty."""
        if self._updating:
            return "Загрузка уже выполняется"
        self._updating = True
        self.notify()
        was_running = winws_running()
        previous = self.selected_version()
        strategy = self.config.get("strategy") or "general.bat"
        try:
            # Ensure download target is next to exe for fresh users
            if not list(self.root.glob("zapret-discord-youtube-*")):
                self.config["zapret_root"] = str(APP_DIR)
                save_config(self.config)

            target_ver = self.config.get("available_update") or ""
            release = fetch_release(target_ver or None)
            if was_running:
                stop_winws()
            new_path = download_and_install(
                self.root,
                release,
                previous=previous.path if previous else None,
            )
            self.config["version_folder"] = new_path.name
            self.config["available_update"] = ""
            self.invalidate_lists()
            strategies = self.strategies()
            if strategy not in strategies:
                strategy = strategies[0] if strategies else strategy
            self.config["strategy"] = strategy
            save_config(self.config)
            if was_running:
                start_strategy(new_path, strategy)
                msg = f"Zapret обновлён до {release.version} (перезапущен)"
            else:
                msg = (
                    f"Скачан zapret {release.version}\n"
                    f"Папка: {new_path}\n"
                    f"Теперь нажмите «Запустить»."
                )
        except Exception as exc:
            msg = f"Ошибка загрузки: {exc}"
        finally:
            self._updating = False
            self.notify()
        return msg

    def install_update(self) -> str:
        # Same pipeline as download_latest (works for first install too)
        return self.download_latest()

    def auto_update_zapret_silent(self) -> str:
        """
        Background zapret update: download+install without asking.
        Restarts bypass if it was running (brief blink is OK).
        """
        if not self.config.get("auto_update_zapret", True):
            return ""
        if self._updating:
            return ""

        version = self.selected_version()
        local = version.version if version else ""
        if not local:
            # First install: also silent — download latest without asking
            try:
                release = fetch_release()
                self.config["available_update"] = release.version
                save_config(self.config)
                result = self.download_latest()
                if result.startswith("Ошибка"):
                    return result
                return f"Zapret скачан: {release.version}"
            except Exception as exc:
                return f"Не удалось скачать zapret: {exc}"

        available, release, message = check_for_update(local)
        if not available or not release:
            self.config["available_update"] = ""
            save_config(self.config)
            self.notify()
            return ""

        self.config["available_update"] = release.version
        save_config(self.config)
        self.notify()
        result = self.download_latest()
        if result.startswith("Ошибка"):
            return result
        return f"Zapret обновлён до {release.version}"

    def check_app_update(self) -> tuple[bool, str, str]:
        """
        Returns (available, remote_version, message).
        Honors skip_app_version for 'No' on this release.
        """
        try:
            release = fetch_latest_app_release()
        except Exception as exc:
            return False, "", f"Не удалось проверить обновление приложения: {exc}"
        if not release:
            return False, "", ""
        skipped = self.config.get("skip_app_version") or ""
        if skipped == release.version:
            return False, release.version, ""
        if not is_app_update_available(release.version, APP_VERSION):
            return False, release.version, ""
        return (
            True,
            release.version,
            f"Доступна новая версия приложения: {release.version}\n"
            f"(сейчас {APP_VERSION})\n\nСкачать и установить?",
        )

    def skip_app_update(self, version: str) -> None:
        self.config["skip_app_version"] = version
        save_config(self.config)

    def apply_app_update(self, version: str | None = None) -> str:
        """Download new exe and schedule replace+restart. Raises/returns error text."""
        release = fetch_latest_app_release()
        if not release:
            return "Не найден exe в релизе на GitHub"
        if version and release.version != version:
            # Still install whatever is latest
            pass
        if not is_app_update_available(release.version, APP_VERSION):
            return "Уже установлена актуальная версия приложения"

        import tempfile
        from pathlib import Path

        dest = Path(tempfile.gettempdir()) / f"ZapretManager_{release.version}.exe"
        download_app_exe(release.exe_url, dest)
        schedule_replace_and_restart(dest)
        return f"Скачано {release.version}. Перезапуск…"

    def open_folder(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.root))

    def has_zapret(self) -> bool:
        return self.selected_version() is not None
