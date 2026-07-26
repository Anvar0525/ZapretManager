from __future__ import annotations

import re
import time
import urllib.error
import urllib.request

from core import list_strategies, start_strategy, stop_winws


YOUTUBE_URLS = (
    "https://www.youtube.com",
    "https://i.ytimg.com",
    "https://youtu.be",
)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ZapretManager/StrategyPick"


def _alt_sort_key(name: str) -> tuple:
    match = re.search(r"ALT\s*(\d+)", name, re.I)
    num = int(match.group(1)) if match else 0
    return (num, name.lower())


def ordered_strategies(names: list[str]) -> list[str]:
    """ALT* first, then general.bat, then the rest."""
    alts = [n for n in names if "ALT" in n.upper()]
    general = [n for n in names if n.lower() == "general.bat"]
    rest = [n for n in names if n not in alts and n not in general]
    alts_sorted = sorted(alts, key=_alt_sort_key)
    rest_sorted = sorted(rest, key=lambda n: n.lower())
    return alts_sorted + general + rest_sorted


def youtube_reachable(timeout: float = 4.0) -> bool:
    for url in YOUTUBE_URLS:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": UA, "Accept": "*/*"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                # Any non-5xx means path is usable enough for our purpose
                if 200 <= getattr(resp, "status", 200) < 500:
                    return True
        except urllib.error.HTTPError as exc:
            if 200 <= exc.code < 500:
                return True
        except Exception:
            continue
    return False


def find_working_strategy(
    version_path,
    strategies: list[str] | None = None,
    settle_seconds: float = 2.5,
    on_progress=None,
) -> tuple[str | None, str]:
    """
    Try strategies in order, return (strategy_name, message).
    Leaves winws running on success with the chosen strategy.
    """
    names = ordered_strategies(strategies or list_strategies(version_path))
    if not names:
        return None, "Нет файлов стратегий (.bat)"

    if on_progress:
        on_progress("Идет подбор стратегии")

    # If YouTube already works without zapret — keep a sensible default
    stop_winws()
    time.sleep(0.5)
    if youtube_reachable():
        chosen = "general.bat" if "general.bat" in names else names[0]
        start_strategy(version_path, chosen)
        return chosen, f"YouTube уже доступен. Выбрано: {chosen}"

    for name in names:
        if on_progress:
            on_progress("Идет подбор стратегии")
        try:
            stop_winws()
            time.sleep(0.4)
            start_strategy(version_path, name)
            time.sleep(settle_seconds)
            if youtube_reachable():
                return name, f"Подобрана стратегия: {name}"
        except Exception:
            continue

    stop_winws()
    return None, "Не удалось подобрать рабочую стратегию для YouTube"
