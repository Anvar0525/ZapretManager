from __future__ import annotations

import threading
import tkinter as tk
import traceback

from config import APP_DIR
from controller import AppController
from core import ensure_admin
from tray import TrayController, acquire_single_instance
from window import MainWindow

LOG_PATH = APP_DIR / "zapret_manager.log"


def _log(message: str) -> None:
    try:
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(message + "\n")
    except OSError:
        pass


def main() -> None:
    if not acquire_single_instance():
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                "Zapret Manager уже запущен.\nСмотрите окно или иконку в трее.",
                "Zapret Manager",
                0x40,
            )
        except Exception:
            pass
        return

    controller = AppController()
    root = tk.Tk()
    # Show window ASAP, start tray a moment later so first paint isn't blocked
    window = MainWindow(root, controller)
    tray_holder: dict = {}

    def start_tray():
        tray = TrayController(controller, window)
        tray.run_detached()
        tray_holder["tray"] = tray

        if controller.config.get("auto_check_updates", True):
            def delayed_check():
                # Always try: for empty install this unlocks download flow
                msg = controller.check_updates(quiet_if_ok=controller.has_zapret())
                tray_obj = tray_holder.get("tray")
                if msg and tray_obj:
                    try:
                        tray_obj._notify(msg)
                    except Exception:
                        pass

            def kick():
                threading.Thread(target=delayed_check, daemon=True).start()

            # Faster first-run check
            root.after(1500 if not controller.has_zapret() else 8000, kick)

    root.after(150, start_tray)
    _log("ui started")
    root.mainloop()


if __name__ == "__main__":
    try:
        ensure_admin()
        _log("started")
        main()
    except Exception:
        _log(traceback.format_exc())
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                f"Ошибка Zapret Manager.\nПодробности: {LOG_PATH}",
                "Zapret Manager",
                0x10,
            )
        except Exception:
            pass
        raise
