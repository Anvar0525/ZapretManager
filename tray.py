from __future__ import annotations

import atexit
import os
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import pystray
from PIL import Image, ImageDraw, ImageEnhance

from config import APP_DIR

if TYPE_CHECKING:
    from controller import AppController
    from window import MainWindow

LOCK_PATH = APP_DIR / "zapret_manager.lock"
_ICON_ON = None
_ICON_OFF = None


def _assets_dir() -> Path:
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", APP_DIR))
        bundled = meipass / "assets"
        if bundled.exists():
            return bundled
    return APP_DIR / "assets"


def make_icon(active: bool) -> Image.Image:
    global _ICON_ON, _ICON_OFF
    if active:
        if _ICON_ON is None:
            _ICON_ON = _build_icon(True)
        return _ICON_ON
    if _ICON_OFF is None:
        _ICON_OFF = _build_icon(False)
    return _ICON_OFF


def _build_icon(active: bool) -> Image.Image:
    path = _assets_dir() / "icon.png"
    if path.exists():
        img = Image.open(path).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        if active:
            # small green status dot
            draw = ImageDraw.Draw(img)
            draw.ellipse((46, 46, 60, 60), fill=(46, 160, 67, 255), outline=(255, 255, 255, 220))
            return img
        faded = ImageEnhance.Brightness(img).enhance(0.85)
        faded = ImageEnhance.Color(faded).enhance(0.25)
        draw = ImageDraw.Draw(faded)
        draw.ellipse((46, 46, 60, 60), fill=(120, 120, 120, 255), outline=(255, 255, 255, 200))
        return faded

    # fallback geometric icon
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fill = (15, 118, 110, 255) if active else (120, 120, 120, 255)
    draw.rounded_rectangle((4, 4, 60, 60), radius=14, fill=(248, 250, 252, 255))
    draw.ellipse((12, 12, 52, 52), fill=fill)
    return img


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_single_instance() -> bool:
    if LOCK_PATH.exists():
        try:
            old_pid = int(LOCK_PATH.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            old_pid = 0
        if _pid_alive(old_pid):
            return False
    LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8")

    def _cleanup() -> None:
        try:
            if LOCK_PATH.exists():
                text = LOCK_PATH.read_text(encoding="utf-8").strip()
                if text == str(os.getpid()):
                    LOCK_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    atexit.register(_cleanup)
    return True


class TrayController:
    def __init__(self, controller: AppController, window: MainWindow) -> None:
        self.controller = controller
        self.window = window
        self.icon: pystray.Icon | None = None
        self._last_running: bool | None = None
        self.controller.add_listener(self._on_controller_change)

    def _on_controller_change(self) -> None:
        if not self.icon:
            return
        try:
            running = self.controller.status_dict()["running"]
            if running != self._last_running:
                self._last_running = running
                self.icon.icon = make_icon(running)
            self.icon.title = self.controller.status_text()
            # Do NOT rebuild/update_menu here — it freezes the UI on Windows.
        except Exception:
            pass

    def _menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Открыть окно", self.on_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Запустить",
                self.on_start,
                enabled=lambda item: (
                    not self.controller.status_dict()["running"]
                    and not self.controller.updating
                ),
            ),
            pystray.MenuItem(
                "Остановить",
                self.on_stop,
                enabled=lambda item: (
                    self.controller.status_dict()["running"]
                    and not self.controller.updating
                ),
            ),
            pystray.MenuItem(
                "Перезапустить",
                self.on_restart,
                enabled=lambda item: not self.controller.updating,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self.on_exit),
        )

    def _notify(self, message: str) -> None:
        if self.icon and message:
            try:
                self.icon.notify(message, "Zapret Manager")
            except Exception:
                pass

    def on_show(self, icon=None, item=None) -> None:
        self.window.root.after(0, self.window.show)

    def on_start(self, icon=None, item=None) -> None:
        def work():
            msg = self.controller.start()
            self._notify(msg)

        threading.Thread(target=work, daemon=True).start()

    def on_stop(self, icon=None, item=None) -> None:
        def work():
            msg = self.controller.stop()
            self._notify(msg)

        threading.Thread(target=work, daemon=True).start()

    def on_restart(self, icon=None, item=None) -> None:
        def work():
            msg = self.controller.restart()
            self._notify(msg)

        threading.Thread(target=work, daemon=True).start()

    def on_exit(self, icon=None, item=None) -> None:
        try:
            if self.icon:
                self.icon.visible = False
                self.icon.stop()
        except Exception:
            pass

        def quit_app():
            try:
                self.window.root.quit()
                self.window.root.destroy()
            except Exception:
                pass
            os._exit(0)

        try:
            self.window.root.after(0, quit_app)
        except Exception:
            os._exit(0)

    def run_detached(self) -> None:
        running = self.controller.status_dict()["running"]
        self._last_running = running
        self.icon = pystray.Icon(
            "ZapretManager",
            make_icon(running),
            self.controller.status_text(),
            self._menu(),
        )
        threading.Thread(target=self.icon.run, daemon=True).start()
