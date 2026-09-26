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
        start_with_windows=True,
        silent_start=True,
        screen_id="display-2",
        capture_fps=12,
        limit_capture_resolution=False,
        windowed=True,
        window_rect=[0.1, 0.2, 0.5, 0.4],
    )
    store.save(expected)
    assert store.load() == expected
    assert json.loads(path.read_text(encoding="utf-8"))["screen_id"] == "display-2"
    assert json.loads(path.read_text(encoding="utf-8"))["limit_capture_resolution"] is False
    assert json.loads(path.read_text(encoding="utf-8"))["start_with_windows"] is True
    assert json.loads(path.read_text(encoding="utf-8"))["silent_start"] is True


def test_invalid_settings_fall_back_to_defaults(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("not json", encoding="utf-8")
    assert SettingsStore(path).load() == AppSettings()


def test_window_region_defaults_and_normalization():
    assert not AppSettings.from_dict({"brightness": 0.4}).windowed
    assert AppSettings(window_rect=[-2, 3, 9, -4]).normalized().window_rect == [0, 0.9, 1, 0.1]
    for invalid in (None, [], [1], [0, 0, float("nan"), 1]):
        assert AppSettings(window_rect=invalid).normalized().window_rect == [0.15, 0.15, 0.7, 0.7]
