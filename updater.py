from __future__ import annotations

import json
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from core import VERSION_PREFIX, version_key

VERSION_URL = (
    "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/"
    "main/.service/version.txt"
)
RELEASE_API_URL = (
    "https://api.github.com/repos/Flowseal/zapret-discord-youtube/releases/tags/{tag}"
)
LATEST_API_URL = (
    "https://api.github.com/repos/Flowseal/zapret-discord-youtube/releases/latest"
)

USER_FILES = (
    "lists/list-general-user.txt",
    "lists/list-exclude-user.txt",
    "lists/ipset-exclude-user.txt",
    "utils/game_filter.enabled",
)

UA = "ZapretManager/1.0 (+https://github.com/Flowseal/zapret-discord-youtube)"


@dataclass
class RemoteRelease:
    version: str
    zip_url: str
    html_url: str


def _http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_latest_version_string() -> str:
    text = _http_get(VERSION_URL, timeout=10).decode("utf-8", errors="ignore").strip()
    if not text:
        raise RuntimeError("Пустой version.txt с GitHub")
    return text.splitlines()[0].strip()


def fetch_release(version: str | None = None) -> RemoteRelease:
    if version:
        url = RELEASE_API_URL.format(tag=version)
    else:
        url = LATEST_API_URL
    data = json.loads(_http_get(url).decode("utf-8"))
    tag = str(data.get("tag_name") or version or "").strip()
    if not tag:
        raise RuntimeError("Не удалось определить версию релиза")

    assets = data.get("assets") or []
    zip_url = ""
    preferred = f"zapret-discord-youtube-{tag}.zip"
    for asset in assets:
        name = asset.get("name") or ""
        if name == preferred:
            zip_url = asset.get("browser_download_url") or ""
            break
    if not zip_url:
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name.endswith(".zip") and "zapret-discord-youtube" in name:
                zip_url = asset.get("browser_download_url") or ""
                break
    if not zip_url:
        raise RuntimeError(f"В релизе {tag} нет zip-архива")

    return RemoteRelease(
        version=tag,
        zip_url=zip_url,
        html_url=str(data.get("html_url") or ""),
    )


def is_newer(remote: str, local: str) -> bool:
    if not remote:
        return False
    if not local:
        return True
    return version_key(remote) > version_key(local)


def local_has_version(root: Path, version: str) -> bool:
    return (root / f"{VERSION_PREFIX}{version}").is_dir()


def copy_user_data(src: Path, dst: Path) -> None:
    for rel in USER_FILES:
        s = src / rel
        d = dst / rel
        if not s.exists():
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)


def _normalize_extracted_dir(extract_root: Path, version: str) -> Path:
    expected = extract_root / f"{VERSION_PREFIX}{version}"
    if expected.is_dir():
        return expected

    # zip may contain a single top-level folder with any name
    children = [p for p in extract_root.iterdir() if p.name not in (".", "..")]
    dirs = [p for p in children if p.is_dir()]
    if len(dirs) == 1 and (dirs[0] / "bin" / "winws.exe").exists():
        return dirs[0]
    if (extract_root / "bin" / "winws.exe").exists():
        return extract_root
    raise RuntimeError("Не удалось найти winws.exe в архиве")


def download_and_install(
    root: Path,
    release: RemoteRelease,
    previous: Path | None = None,
    progress=None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{VERSION_PREFIX}{release.version}"
    if target.exists() and (target / "bin" / "winws.exe").exists():
        if previous and previous != target:
            copy_user_data(previous, target)
        return target

    if progress:
        progress("Скачивание…")

    with tempfile.TemporaryDirectory(prefix="zapret_upd_") as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / f"{VERSION_PREFIX}{release.version}.zip"
        req = urllib.request.Request(
            release.zip_url,
            headers={"User-Agent": UA},
        )
        with urllib.request.urlopen(req, timeout=120) as resp, archive.open("wb") as out:
            shutil.copyfileobj(resp, out)

        if progress:
            progress("Распаковка…")

        extract_to = tmp_path / "extract"
        extract_to.mkdir()
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(extract_to)

        extracted = _normalize_extracted_dir(extract_to, release.version)
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(extracted), str(target))

    if previous and previous.exists() and previous != target:
        copy_user_data(previous, target)

    if not (target / "bin" / "winws.exe").exists():
        raise RuntimeError("После установки не найден bin\\winws.exe")

    return target


def check_for_update(local_version: str) -> tuple[bool, RemoteRelease | None, str]:
    """
    Returns (update_available, release_or_none, message).
    """
    try:
        remote_ver = fetch_latest_version_string()
        if not is_newer(remote_ver, local_version):
            return False, None, f"У вас актуальная версия: {local_version or '?'}"
        release = fetch_release(remote_ver)
        return True, release, f"Доступно обновление: {release.version}"
    except urllib.error.URLError as exc:
        return False, None, f"Нет сети / GitHub недоступен: {exc}"
    except Exception as exc:
        return False, None, f"Ошибка проверки: {exc}"
