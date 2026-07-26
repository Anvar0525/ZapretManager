from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import psutil

VERSION_PREFIX = "zapret-discord-youtube-"


@dataclass
class ZapretVersion:
    name: str
    path: Path

    @property
    def version(self) -> str:
        return self.name[len(VERSION_PREFIX) :]


def is_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _pythonw_path() -> str:
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    if candidate.exists():
        return str(candidate)
    # Fallback if somehow started via py.exe / python.exe from another dir
    local = Path.home() / "AppData/Local/Programs/Python"
    for version in ("Python313", "Python312", "Python311"):
        path = local / version / "pythonw.exe"
        if path.exists():
            return str(path)
    return str(exe)


def ensure_admin() -> None:
    if is_admin():
        return
    import ctypes

    if getattr(sys, "frozen", False):
        exe = str(Path(sys.executable).resolve())
        params = " ".join(
            f'"{a}"' if " " in a else a for a in sys.argv[1:]
        )
        workdir = str(Path(exe).parent)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            exe,
            params,
            workdir,
            1,  # show window (GUI app)
        )
    else:
        script = str(Path(sys.argv[0]).resolve())
        args = [f'"{script}"'] + [
            f'"{a}"' if " " in a else a for a in sys.argv[1:]
        ]
        params = " ".join(args)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            _pythonw_path(),
            params,
            str(Path(script).parent),
            0,
        )
    if rc <= 32:
        raise RuntimeError("Не удалось запросить права администратора")
    sys.exit(0)


def version_key(name: str) -> tuple:
    raw = name[len(VERSION_PREFIX) :] if name.startswith(VERSION_PREFIX) else name
    parts: list = []
    for chunk in re.findall(r"\d+|[A-Za-z]+", raw):
        if chunk.isdigit():
            parts.append((0, int(chunk)))
        else:
            parts.append((1, chunk.lower()))
    return tuple(parts)


def discover_versions(root: Path) -> list[ZapretVersion]:
    if not root.exists():
        return []
    versions = [
        ZapretVersion(name=p.name, path=p)
        for p in root.iterdir()
        if p.is_dir() and p.name.startswith(VERSION_PREFIX)
    ]
    versions.sort(key=lambda v: version_key(v.name))
    return versions


def pick_version(root: Path, preferred: str = "") -> ZapretVersion | None:
    versions = discover_versions(root)
    if not versions:
        return None
    if preferred:
        for v in versions:
            if v.name == preferred or v.version == preferred:
                return v
    return versions[-1]


def list_strategies(version_path: Path) -> list[str]:
    bats = [
        p.name
        for p in version_path.glob("*.bat")
        if not p.name.lower().startswith("service")
    ]

    def sort_key(name: str):
        stem = Path(name).stem.lower()
        if stem == "general":
            return (0, name.lower())
        return (1, name.lower())

    return sorted(bats, key=sort_key)


def ensure_user_lists(version_path: Path) -> None:
    lists = version_path / "lists"
    lists.mkdir(exist_ok=True)
    defaults = {
        "ipset-exclude-user.txt": "203.0.113.113/32\n",
        "list-exclude-user.txt": "example.com\n",
        "list-general-user.txt": "\n",
    }
    for name, content in defaults.items():
        path = lists / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")


def game_filter_ports(version_path: Path) -> tuple[str, str]:
    flag = version_path / "utils" / "game_filter.enabled"
    if not flag.exists():
        return "12", "12"
    mode = flag.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
    mode_value = (mode[0] if mode else "").strip().lower()
    if mode_value == "all":
        return "1024-65535", "1024-65535"
    if mode_value == "tcp":
        return "1024-65535", "12"
    return "12", "1024-65535"


def parse_strategy_args(strategy_path: Path) -> list[str]:
    text = strategy_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    collecting = False
    chunks: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not collecting:
            if "winws.exe" not in line.lower():
                continue
            collecting = True
            idx = line.lower().find("winws.exe")
            after = line[idx + len("winws.exe") :]
            after = after.lstrip("\"' ")
            if after.endswith("^"):
                after = after[:-1].rstrip()
            if after:
                chunks.append(after)
            continue

        if line.endswith("^"):
            chunks.append(line[:-1].rstrip())
        else:
            if line.strip():
                chunks.append(line.strip())
            break

    joined = " ".join(chunks)
    joined = joined.replace("^=", "=")
    return _split_args(joined)


def _split_args(command: str) -> list[str]:
    args: list[str] = []
    current: list[str] = []
    in_quotes = False
    for ch in command:
        if ch == '"':
            in_quotes = not in_quotes
            continue
        if ch.isspace() and not in_quotes:
            if current:
                args.append("".join(current))
                current = []
            continue
        current.append(ch)
    if current:
        args.append("".join(current))
    return [a for a in args if a and a != "^"]


def expand_args(args: list[str], version_path: Path) -> list[str]:
    bin_dir = str(version_path / "bin") + "\\"
    lists_dir = str(version_path / "lists") + "\\"
    tcp, udp = game_filter_ports(version_path)
    root = str(version_path) + "\\"

    expanded: list[str] = []
    for arg in args:
        value = (
            arg.replace("%BIN%", bin_dir)
            .replace("%LISTS%", lists_dir)
            .replace("%~dp0", root)
            .replace("%GameFilterTCP%", tcp)
            .replace("%GameFilterUDP%", udp)
            .replace("%GameFilter%", tcp)
        )
        expanded.append(value)
    return expanded


_winws_cache: tuple[float, bool] | None = None


def winws_running(force: bool = False) -> bool:
    """Fast check with short cache — process scan is relatively expensive."""
    global _winws_cache
    import time

    now = time.monotonic()
    if not force and _winws_cache is not None:
        cached_at, value = _winws_cache
        if now - cached_at < 0.8:
            return value

    found = False
    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info["name"] or "").lower() == "winws.exe":
                found = True
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _winws_cache = (now, found)
    return found


def current_strategy_hint() -> str:
    # Intentionally lightweight: window-title scanning caused UI freezes.
    return ""


def invalidate_winws_cache() -> None:
    global _winws_cache
    _winws_cache = None


def stop_winws() -> None:
    invalidate_winws_cache()
    targets = []
    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info["name"] or "").lower() == "winws.exe":
                targets.append(proc)
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _gone, alive = psutil.wait_procs(targets, timeout=2)
    for proc in alive:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    invalidate_winws_cache()


def start_strategy(version_path: Path, strategy_name: str) -> None:
    strategy_path = version_path / strategy_name
    if not strategy_path.exists():
        raise FileNotFoundError(f"Стратегия не найдена: {strategy_name}")

    winws = version_path / "bin" / "winws.exe"
    if not winws.exists():
        raise FileNotFoundError(f"Не найден winws.exe: {winws}")

    ensure_user_lists(version_path)
    args = expand_args(parse_strategy_args(strategy_path), version_path)

    stop_winws()

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    subprocess.Popen(
        [str(winws), *args],
        cwd=str(version_path / "bin"),
        creationflags=creationflags,
        close_fds=True,
    )
    invalidate_winws_cache()
