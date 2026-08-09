import json
from pathlib import Path
from string import Formatter

from sidescreen.i18n import available_languages, set_language, tr


def test_builtin_languages_are_discovered() -> None:
    languages = available_languages(refresh=True)
    assert {language.code for language in languages} >= {"zh_CN", "en_US"}


def test_english_translation_and_placeholders() -> None:
    try:
        assert set_language("en_US") == "en_US"
        assert tr("tabs.layout") == "Layout"
        assert tr("state.running", count=3) == "●  Active · 3 windows"
    finally:
        set_language("zh_CN")


def test_builtin_language_packs_have_matching_keys() -> None:
    directory = Path(__file__).resolve().parents[1] / "assets" / "i18n"
    chinese = json.loads((directory / "zh_CN.json").read_text(encoding="utf-8"))["strings"]
    english = json.loads((directory / "en_US.json").read_text(encoding="utf-8"))["strings"]
    assert set(english) == set(chinese)
    formatter = Formatter()
    for key in chinese:
        chinese_fields = {field for _, field, _, _ in formatter.parse(chinese[key]) if field}
        english_fields = {field for _, field, _, _ in formatter.parse(english[key]) if field}
        assert english_fields == chinese_fields, key
