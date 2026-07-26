from __future__ import annotations

import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

from config import APP_DIR, APP_VERSION
from controller import AppController

# Brand palette (matches app icon)
TEAL = "#0F766E"
TEAL_DARK = "#0B5F59"
TEAL_SOFT = "#E6F4F2"
BG = "#F4F8F7"
TEXT = "#1F2937"
MUTED = "#6B7280"
OK = "#15803D"
OK_BG = "#DCFCE7"
OFF = "#6B7280"
OFF_BG = "#E5E7EB"
WARN = "#B45309"
WARN_BG = "#FEF3C7"
ACCENT = "#0F766E"


class MainWindow:
    def __init__(self, root: tk.Tk, controller: AppController) -> None:
        self.root = root
        self.controller = controller
        self._busy = False
        self._photo = None

        self.root.title(f"Zapret Manager {APP_VERSION}")
        self.root.geometry("460x560")
        self.root.minsize(420, 520)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self._set_window_icon()
        self._setup_styles()

        # Header
        header = tk.Frame(self.root, bg=TEAL, height=64)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        head_inner = tk.Frame(header, bg=TEAL)
        head_inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        left = tk.Frame(head_inner, bg=TEAL)
        left.pack(side=tk.LEFT, fill=tk.Y)

        self._load_header_icon(left)

        titles = tk.Frame(left, bg=TEAL)
        titles.pack(side=tk.LEFT, padx=(10, 0))
        tk.Label(
            titles,
            text="Zapret Manager",
            bg=TEAL,
            fg="white",
            font=("Segoe UI Semibold", 13),
        ).pack(anchor=tk.W)
        tk.Label(
            titles,
            text="Discord · YouTube",
            bg=TEAL,
            fg="#B6E2DE",
            font=("Segoe UI", 9),
        ).pack(anchor=tk.W)

        self.badge = tk.Label(
            head_inner,
            text=" OFF ",
            bg=OFF_BG,
            fg=OFF,
            font=("Segoe UI Semibold", 10),
            padx=10,
            pady=4,
        )
        self.badge.pack(side=tk.RIGHT, anchor=tk.CENTER)

        # Body
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

        # First-run / missing zapret banner
        self.setup_card = tk.Frame(
            body, bg=WARN_BG, highlightbackground="#F6D89C", highlightthickness=1
        )
        setup_inner = tk.Frame(self.setup_card, bg=WARN_BG)
        setup_inner.pack(fill=tk.X, padx=12, pady=10)
        tk.Label(
            setup_inner,
            text="Zapret ещё не скачан",
            bg=WARN_BG,
            fg=WARN,
            font=("Segoe UI Semibold", 10),
            anchor=tk.W,
        ).pack(fill=tk.X)
        self.setup_path_var = tk.StringVar(value="")
        tk.Label(
            setup_inner,
            textvariable=self.setup_path_var,
            bg=WARN_BG,
            fg="#92400E",
            font=("Segoe UI", 8),
            anchor=tk.W,
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(2, 8))
        self.btn_download = tk.Button(
            setup_inner,
            text="Скачать zapret",
            command=self._on_download_zapret,
            bg="#065F46",
            fg="white",
            activebackground="#064E3B",
            activeforeground="white",
            relief=tk.FLAT,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
            pady=7,
        )
        self.btn_download.pack(fill=tk.X)
        self.setup_card.pack(fill=tk.X, pady=(0, 12))

        # Status card
        self.status_card = tk.Frame(
            body, bg="white", highlightbackground="#D5E5E2", highlightthickness=1
        )
        self.status_card.pack(fill=tk.X, pady=(0, 12))

        card_inner = tk.Frame(self.status_card, bg="white")
        card_inner.pack(fill=tk.X, padx=14, pady=12)

        self.status_var = tk.StringVar(value="…")
        self.status_label = tk.Label(
            card_inner,
            textvariable=self.status_var,
            bg="white",
            fg=TEXT,
            font=("Segoe UI Semibold", 12),
            anchor=tk.W,
        )
        self.status_label.pack(fill=tk.X)

        self.hint_var = tk.StringVar(value="")
        tk.Label(
            card_inner,
            textvariable=self.hint_var,
            bg="white",
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(4, 0))

        # Main actions
        btns = tk.Frame(body, bg=BG)
        btns.pack(fill=tk.X, pady=(0, 12))

        self.btn_start = tk.Button(
            btns,
            text="Запустить",
            command=self._on_start,
            bg="#065F46",
            fg="white",
            activebackground="#064E3B",
            activeforeground="white",
            disabledforeground="#A7F3D0",
            relief=tk.FLAT,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
            padx=8,
            pady=8,
        )
        self.btn_stop = tk.Button(
            btns,
            text="Остановить",
            command=self._on_stop,
            bg="#EEF2F0",
            fg="#3F3F46",
            activebackground="#E4E4E7",
            activeforeground="#18181B",
            disabledforeground="#A1A1AA",
            relief=tk.FLAT,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
            padx=8,
            pady=8,
        )
        self.btn_restart = tk.Button(
            btns,
            text="Перезапустить",
            command=self._on_restart,
            bg="white",
            fg=TEAL_DARK,
            activebackground="#F8FAFC",
            activeforeground=TEAL_DARK,
            disabledforeground="#A1A1AA",
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=0,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
            padx=8,
            pady=8,
        )
        self.btn_start.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        self.btn_stop.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.btn_restart.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(6, 0))

        # Settings — strategy only (always newest zapret)
        form_card = tk.Frame(body, bg="white", highlightbackground="#D5E5E2", highlightthickness=1)
        form_card.pack(fill=tk.X, pady=(0, 12))
        form = tk.Frame(form_card, bg="white")
        form.pack(fill=tk.X, padx=14, pady=12)

        tk.Label(form, text="Стратегия", bg="white", fg=MUTED, font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 6)
        )
        self.strategy_var = tk.StringVar()
        self.strategy_combo = ttk.Combobox(
            form, textvariable=self.strategy_var, state="readonly", style="App.TCombobox"
        )
        self.strategy_combo.grid(row=1, column=0, sticky=tk.EW)
        self.strategy_combo.bind("<<ComboboxSelected>>", self._on_strategy_selected)
        form.columnconfigure(0, weight=1)

        # Updates
        upd_card = tk.Frame(body, bg="white", highlightbackground="#D5E5E2", highlightthickness=1)
        upd_card.pack(fill=tk.X, pady=(0, 12))
        upd = tk.Frame(upd_card, bg="white")
        upd.pack(fill=tk.X, padx=14, pady=12)

        tk.Label(
            upd, text="Обновления", bg="white", fg=TEXT, font=("Segoe UI Semibold", 10)
        ).pack(anchor=tk.W)
        self.update_var = tk.StringVar(value="Нажмите «Проверить» или «Скачать zapret»")
        self.update_label = tk.Label(
            upd,
            textvariable=self.update_var,
            bg="white",
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor=tk.W,
            wraplength=400,
            justify=tk.LEFT,
        )
        self.update_label.pack(fill=tk.X, pady=(4, 8))

        upd_btns = tk.Frame(upd, bg="white")
        upd_btns.pack(fill=tk.X)
        self.btn_check = tk.Button(
            upd_btns,
            text="Проверить",
            command=self._on_check_updates,
            bg=TEAL_SOFT,
            fg=TEAL_DARK,
            activebackground="#D0EBE8",
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            cursor="hand2",
            pady=6,
        )
        self.btn_install = tk.Button(
            upd_btns,
            text="Скачать / обновить",
            command=self._on_install_update,
            bg=TEAL,
            fg="white",
            activebackground=TEAL_DARK,
            activeforeground="white",
            relief=tk.FLAT,
            font=("Segoe UI Semibold", 9),
            cursor="hand2",
            pady=6,
        )
        self.btn_check.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        self.btn_install.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # Autostart — compact, two checkboxes only
        auto_card = tk.Frame(
            body, bg="white", highlightbackground="#D5E5E2", highlightthickness=1
        )
        auto_card.pack(fill=tk.X, pady=(0, 12))
        auto_inner = tk.Frame(auto_card, bg="white")
        auto_inner.pack(fill=tk.X, padx=14, pady=10)

        self.var_autostart_windows = tk.BooleanVar(
            value=bool(self.controller.config.get("autostart_windows"))
        )
        self.var_autostart_strategy = tk.BooleanVar(
            value=bool(self.controller.config.get("autostart_strategy"))
        )
        tk.Checkbutton(
            auto_inner,
            text="Запускать с Windows (без UAC каждый раз)",
            variable=self.var_autostart_windows,
            command=self._on_toggle_autostart_windows,
            bg="white",
            fg=TEXT,
            activebackground="white",
            selectcolor="white",
            font=("Segoe UI", 9),
            anchor=tk.W,
        ).pack(fill=tk.X)
        tk.Checkbutton(
            auto_inner,
            text="При старте включать обход",
            variable=self.var_autostart_strategy,
            command=self._on_toggle_autostart_strategy,
            bg="white",
            fg=TEXT,
            activebackground="white",
            selectcolor="white",
            font=("Segoe UI", 9),
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(4, 0))

        # Bottom
        bottom = tk.Frame(body, bg=BG)
        bottom.pack(fill=tk.X, pady=(2, 0))
        tk.Button(
            bottom,
            text="Открыть папку",
            command=self.controller.open_folder,
            bg=BG,
            fg=TEAL,
            activebackground=TEAL_SOFT,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            cursor="hand2",
        ).pack(side=tk.LEFT)
        tk.Label(
            bottom,
            text=f"v{APP_VERSION}",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(side=tk.RIGHT, padx=(8, 0))
        tk.Button(
            bottom,
            text="В трей",
            command=self.hide_to_tray,
            bg=BG,
            fg=MUTED,
            activebackground=OFF_BG,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        self._toast_var = tk.StringVar(value="")
        self.toast_label = tk.Label(
            body,
            textvariable=self._toast_var,
            bg=BG,
            fg=TEAL,
            font=("Segoe UI", 9),
            anchor=tk.W,
        )
        self.toast_label.pack(fill=tk.X, pady=(10, 0))

        self.controller.add_listener(self._schedule_refresh)
        self._lists_loaded = False
        self.refresh(full=True)
        self.root.after(4000, self._poll_status)

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "App.TCombobox",
            fieldbackground="white",
            background="white",
            foreground=TEXT,
            arrowcolor=TEAL,
            padding=4,
        )

    def _load_header_icon(self, parent: tk.Frame) -> None:
        try:
            from PIL import Image, ImageTk

            if getattr(sys, "frozen", False):
                base = Path(getattr(sys, "_MEIPASS", APP_DIR))
            else:
                base = APP_DIR
            png = base / "assets" / "icon.png"
            if not png.exists():
                return
            img = Image.open(png).convert("RGBA").resize((36, 36), Image.Resampling.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)
            tk.Label(parent, image=self._photo, bg=TEAL).pack(side=tk.LEFT)
        except Exception:
            pass

    def _set_window_icon(self) -> None:
        try:
            if getattr(sys, "frozen", False):
                base = Path(getattr(sys, "_MEIPASS", APP_DIR))
            else:
                base = APP_DIR
            ico = base / "assets" / "icon.ico"
            png = base / "assets" / "icon.png"
            if ico.exists():
                self.root.iconbitmap(default=str(ico))
            elif png.exists():
                self.root.iconphoto(True, tk.PhotoImage(file=str(png)))
        except Exception:
            pass

    def _schedule_refresh(self) -> None:
        try:
            self.root.after(0, lambda: self.refresh(full=True))
        except tk.TclError:
            pass

    def _poll_status(self) -> None:
        try:
            self.refresh(full=False)
            self.root.after(4000, self._poll_status)
        except tk.TclError:
            pass

    def _set_btn_state(self, btn: tk.Button, enabled: bool) -> None:
        btn.configure(state=(tk.NORMAL if enabled else tk.DISABLED))

    def refresh(self, full: bool = True) -> None:
        s = self.controller.status_dict()
        has_zapret = self.controller.has_zapret()
        state = "ON" if s["running"] else "OFF"
        self.status_var.set(f"Статус: {state}  ·  v{s['version']}")
        self.hint_var.set(f"Стратегия: {s['strategy'] or '—'}")

        # First-run banner
        self.setup_path_var.set(
            f"Скачается сюда:\n{self.controller.root}"
        )
        if has_zapret:
            self.setup_card.pack_forget()
        else:
            try:
                self.setup_card.pack(fill=tk.X, pady=(0, 12), before=self.status_card)
            except tk.TclError:
                self.setup_card.pack(fill=tk.X, pady=(0, 12))

        if s["running"]:
            self.badge.configure(text=" ON ", bg=OK_BG, fg=OK)
            self.status_label.configure(fg=OK)
        else:
            self.badge.configure(text=" OFF ", bg=OFF_BG, fg=OFF)
            self.status_label.configure(fg=TEXT)

        if full or not self._lists_loaded:
            strategies = self.controller.strategies()
            self.strategy_combo["values"] = strategies
            self._lists_loaded = True

        if s["strategy"]:
            self.strategy_var.set(s["strategy"])

        upd_text = self.controller.update_status_label()
        if not has_zapret:
            upd_text = "Zapret не найден — нажмите «Скачать zapret» выше"
        self.update_var.set(upd_text)
        if s["available_update"] or not has_zapret:
            self.update_label.configure(fg=WARN, bg="white")
        else:
            self.update_label.configure(fg=MUTED, bg="white")

        busy = self._busy or s["updating"]
        self._set_btn_state(self.btn_start, has_zapret and not s["running"] and not busy)
        self._set_btn_state(self.btn_stop, s["running"] and not busy)
        self._set_btn_state(self.btn_restart, has_zapret and not busy)
        self._set_btn_state(self.btn_check, not busy)
        self._set_btn_state(self.btn_install, not busy)
        self._set_btn_state(self.btn_download, not busy)
        self.strategy_combo.configure(state=("disabled" if busy else "readonly"))
        # Keep checkboxes in sync
        self.var_autostart_windows.set(bool(self.controller.config.get("autostart_windows")))
        self.var_autostart_strategy.set(bool(self.controller.config.get("autostart_strategy")))

    def show(self) -> None:
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(200, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except tk.TclError:
            pass

    def hide_to_tray(self) -> None:
        self.root.withdraw()
        self._toast("Свёрнуто в трей")

    def _toast(self, text: str) -> None:
        self._toast_var.set(text)

        def clear():
            if self._toast_var.get() == text:
                self._toast_var.set("")

        self.root.after(3500, clear)

    def _run_bg(self, fn, ok_toast: bool = True) -> None:
        if self._busy:
            return
        self._busy = True
        self.refresh(full=False)

        def work():
            try:
                msg = fn()
            except Exception as exc:
                msg = str(exc)
            finally:
                self._busy = False

            def done():
                self.refresh(full=True)
                if msg:
                    self._toast(msg)
                    if msg.startswith("Ошибка"):
                        messagebox.showerror("Zapret Manager", msg, parent=self.root)

            try:
                self.root.after(0, done)
            except tk.TclError:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _on_start(self) -> None:
        self._run_bg(self.controller.start)

    def _on_stop(self) -> None:
        self._run_bg(self.controller.stop)

    def _on_restart(self) -> None:
        self._run_bg(self.controller.restart)

    def _on_download_zapret(self) -> None:
        self._run_bg(self.controller.download_latest)

    def _on_check_updates(self) -> None:
        self._run_bg(lambda: self.controller.check_updates(quiet_if_ok=False))

    def _on_install_update(self) -> None:
        has = self.controller.has_zapret()
        title = "Скачать zapret" if not has else "Обновление"
        text = (
            "Скачать последнюю версию zapret с GitHub?\n"
            f"Папка: {self.controller.root}"
            if not has
            else "Скачать и установить обновление?\nОбход будет перезапущен, если он включён."
        )
        if not messagebox.askyesno(title, text, parent=self.root):
            return
        self._run_bg(self.controller.download_latest)

    def _on_strategy_selected(self, _event=None) -> None:
        name = self.strategy_var.get()
        if not name:
            return
        if name == self.controller.config.get("strategy"):
            return
        was_running = self.controller.status_dict()["running"]
        if was_running:
            self.controller.config["strategy"] = name
            from config import save_config

            save_config(self.controller.config)
            self._run_bg(self.controller.restart)
        else:
            self.controller.set_strategy(name, restart_if_running=False)
            self._toast(f"Стратегия: {name}")

    def _on_toggle_autostart_windows(self) -> None:
        enabled = bool(self.var_autostart_windows.get())

        def work():
            return self.controller.set_autostart_windows(enabled)

        self._run_bg(work)

    def _on_toggle_autostart_strategy(self) -> None:
        enabled = bool(self.var_autostart_strategy.get())
        self.controller.set_autostart_strategy(enabled)
        self._toast(
            "При старте обход будет включаться"
            if enabled
            else "При старте обход не включается"
        )
