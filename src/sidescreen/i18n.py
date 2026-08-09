from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sidescreen.resources import asset_path

LOGGER = logging.getLogger(__name__)
DEFAULT_LANGUAGE = "zh_CN"


@dataclass(frozen=True, slots=True)
class LanguageInfo:
    code: str
    name: str
    path: Path


_catalogs: dict[str, dict[str, str]] = {}
_languages: list[LanguageInfo] | None = None
_current_language = DEFAULT_LANGUAGE


def _read_language(path: Path) -> tuple[LanguageInfo, dict[str, str]] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        meta = raw.get("meta", {})
        strings = raw.get("strings", {})
        code = str(meta.get("code", path.stem)).strip()
        name = str(meta.get("name", code)).strip()
        if not code or not name or not isinstance(strings, dict):
            raise ValueError("invalid language metadata")
        catalog = {str(key): str(value) for key, value in strings.items()}
        return LanguageInfo(code, name, path), catalog
    except (OSError, ValueError, json.JSONDecodeError, AttributeError):
        LOGGER.warning("Ignoring invalid language pack: %s", path, exc_info=True)
        return None


def available_languages(refresh: bool = False) -> list[LanguageInfo]:
    global _languages
    if _languages is not None and not refresh:
        return list(_languages)
    _catalogs.clear()
    discovered: list[LanguageInfo] = []
    directory = asset_path("i18n")
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        loaded = _read_language(path)
        if loaded is None:
            continue
        info, catalog = loaded
        discovered.append(info)
        _catalogs[info.code] = catalog
    _languages = sorted(discovered, key=lambda item: (item.code != DEFAULT_LANGUAGE, item.name))
    return list(_languages)


def set_language(code: str) -> str:
    global _current_language
    available_languages()
    _current_language = code if code in _catalogs else DEFAULT_LANGUAGE
    return _current_language


def current_language() -> str:
    return _current_language


def tr(key: str, **values: object) -> str:
    available_languages()
    text = _catalogs.get(_current_language, {}).get(key)
    if text is None:
        text = _catalogs.get(DEFAULT_LANGUAGE, {}).get(key, key)
    try:
        return text.format(**values)
    except (KeyError, ValueError):
        LOGGER.warning("Invalid placeholders for translation key %s", key)
        return text
