import json

from sidescreen.models import AppSettings
from sidescreen.settings_store import SettingsStore


def test_settings_are_clamped() -> None:
    settings = AppSettings(
        preview_scale=5,
        move_seconds=1,
        size_variation=2,
        capture_fps=200,
        blank_every_minutes=-1,
        blank_seconds=1,
        edge_thickness=99,
    ).normalized()
    assert settings.preview_scale == 0.9
    assert settings.move_seconds == 30
    assert settings.size_variation == 0.1
    assert settings.capture_fps == 30
    assert settings.blank_every_minutes == 0
    assert settings.blank_seconds == 5
    assert settings.edge_thickness == 4


def test_settings_round_trip(tmp_path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    expected = AppSettings(
        screen_id="display-2",
        capture_fps=12,
        limit_capture_resolution=False,
    )
    store.save(expected)
    assert store.load() == expected
    assert json.loads(path.read_text(encoding="utf-8"))["screen_id"] == "display-2"
    assert json.loads(path.read_text(encoding="utf-8"))["limit_capture_resolution"] is False


def test_invalid_settings_fall_back_to_defaults(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("not json", encoding="utf-8")
    assert SettingsStore(path).load() == AppSettings()
