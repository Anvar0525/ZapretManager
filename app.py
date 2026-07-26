from __future__ import annotations

import threading
import tkinter as tk
import traceback
from tkinter import messagebox

from config import APP_DIR, APP_VERSION
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
    window = MainWindow(root, controller)
    tray_holder: dict = {}

    def start_tray():
        tray = TrayController(controller, window)
        tray.run_detached()
        tray_holder["tray"] = tray

        def notify(msg: str) -> None:
            if not msg:
                return
            try:
                tray._notify(msg)
            except Exception:
                pass

        def background_jobs():
            # 1) Silent zapret auto-update
            try:
                if controller.config.get("auto_update_zapret", True):
                    msg = controller.auto_update_zapret_silent()
                    if msg:
                        root.after(0, lambda m=msg: notify(m))
            except Exception as exc:
                _log(f"zapret auto-update error: {exc}")

            # 2) App self-update prompt
            try:
                available, remote_ver, prompt = controller.check_app_update()
                if available and prompt:

                    def ask():
                        ok = messagebox.askyesno(
                            "Обновление Zapret Manager",
                            prompt,
                            parent=root,
                        )
                        if not ok:
                            controller.skip_app_update(remote_ver)
                            return

                        def work():
                            try:
                                msg = controller.apply_app_update(remote_ver)
                                root.after(0, lambda: notify(msg))
                                # Exit so bat can replace exe
                                root.after(800, lambda: os_exit())
                            except Exception as exc:
                                err = f"Ошибка обновления приложения: {exc}"
                                _log(err)
                                root.after(
                                    0,
                                    lambda: messagebox.showerror(
                                        "Обновление", err, parent=root
                                    ),
                                )

                        threading.Thread(target=work, daemon=True).start()

                    root.after(0, ask)
            except Exception as exc:
                _log(f"app update check error: {exc}")

        def os_exit():
            try:
                root.quit()
                root.destroy()
            except Exception:
                pass
            import os

            os._exit(0)

        def kick():
            threading.Thread(target=background_jobs, daemon=True).start()

        # First-run without zapret: sooner. Otherwise give UI a moment.
        delay = 2000 if not controller.has_zapret() else 5000
        root.after(delay, kick)

        # Periodic silent zapret check every 6 hours
        def loop_zapret():
            def job():
                try:
                    msg = controller.auto_update_zapret_silent()
                    if msg:
                        root.after(0, lambda m=msg: notify(m))
                except Exception as exc:
                    _log(f"periodic zapret update: {exc}")
                root.after(6 * 60 * 60 * 1000, loop_zapret)

            threading.Thread(target=job, daemon=True).start()

        root.after(6 * 60 * 60 * 1000, loop_zapret)

    root.after(150, start_tray)
    _log(f"ui started v{APP_VERSION}")
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
