from __future__ import annotations

import sys
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
    silent_start = "--autostart" in sys.argv

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

    if silent_start:
        # Start in tray only — no window flash on Windows logon
        root.withdraw()

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

        def start_bypass_if_needed():
            if not controller.config.get("autostart_strategy"):
                return
            if not controller.has_zapret():
                return
            if controller.status_dict()["running"]:
                return
            msg = controller.start()
            root.after(0, lambda m=msg: notify(m))

        def background_jobs():
            # 0) First-run strategy pick (once), before enabling bypass
            try:
                if (
                    controller.has_zapret()
                    and controller.needs_strategy_pick()
                    and not controller.picking
                ):
                    msg = controller.pick_strategy()
                    if msg:
                        root.after(0, lambda m=msg: notify(m))
            except Exception as exc:
                _log(f"strategy pick error: {exc}")

            # 1) Silent zapret auto-update
            try:
                if controller.config.get("auto_update_zapret", True):
                    msg = controller.auto_update_zapret_silent()
                    if msg:
                        root.after(0, lambda m=msg: notify(m))
            except Exception as exc:
                _log(f"zapret auto-update error: {exc}")

            # 2) Enable bypass on start (after possible update / pick)
            try:
                start_bypass_if_needed()
            except Exception as exc:
                _log(f"autostart strategy error: {exc}")

            # 3) App self-update: modal only for manual launches
            try:
                available, remote_ver, prompt = controller.check_app_update()
                if not available or not prompt:
                    return
                if silent_start:
                    root.after(
                        0,
                        lambda: notify(
                            f"Доступна новая версия приложения: {remote_ver}"
                        ),
                    )
                    return

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

                            def done():
                                notify(msg)
                                # Must schedule exit on the Tk main thread
                                root.after(600, os_exit)

                            root.after(0, done)
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

        delay = 1500 if silent_start else (2000 if not controller.has_zapret() else 4000)
        root.after(delay, kick)

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
    _log(f"ui started v{APP_VERSION} silent={silent_start}")
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
