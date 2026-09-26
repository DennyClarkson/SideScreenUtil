import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from sidescreen.main_window import MainWindow  # noqa: E402
from sidescreen.models import AppSettings  # noqa: E402
from sidescreen.settings_store import SettingsStore  # noqa: E402


def test_mode_can_start_without_selected_windows(tmp_path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr("sidescreen.main_window.enumerate_windows", lambda: [])
    warning = Mock()
    monkeypatch.setattr(QMessageBox, "warning", warning)
    window = MainWindow(SettingsStore(tmp_path / "settings.json"))
    window._overlay.activate = Mock()
    window._overlay.set_sources = Mock()
    window._overlay.set_source_titles = Mock()
    window._overlay.set_layout = Mock()
    window._captures.sync_windows = Mock()

    window.start_mode()

    assert window._active
    assert window._active_screen is window.screen_combo.currentData()
    assert not window.layout_edit_button.isEnabled()
    window._overlay.set_sources.assert_called_once_with([])
    window._captures.sync_windows.assert_called_once()
    assert window._captures.sync_windows.call_args.args[0] == []
    warning.assert_not_called()

    window._quitting = True
    window._tray.hide()
    window.close()
    application.processEvents()


def test_settings_page_persists_startup_preferences(tmp_path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path / "settings.json")
    store.save(AppSettings())
    startup_updates: list[bool] = []
    monkeypatch.setattr(
        "sidescreen.main_window.set_start_with_windows",
        lambda enabled: startup_updates.append(enabled),
    )
    window = MainWindow(store)

    assert window.navigation.count() == 5
    assert window.pages.count() == 5
    assert not window.start_with_windows_check.isChecked()
    assert not window.silent_start_check.isChecked()

    window.start_with_windows_check.click()
    window.silent_start_check.click()

    saved = store.load()
    assert startup_updates == [True]
    assert saved.start_with_windows
    assert saved.silent_start
    assert window.silent_start

    window._quitting = True
    window._tray.hide()
    window.close()
    application.processEvents()


def test_window_pointer_reveal_only_covers_region_and_pause_ends_positioning(tmp_path, monkeypatch):
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr("sidescreen.main_window.enumerate_windows", lambda: [])
    store = SettingsStore(tmp_path / "settings.json")
    store.save(AppSettings(windowed=True, window_rect=[0.25, 0.25, 0.5, 0.5]))
    window = MainWindow(store)
    window.start_mode()
    region = window._overlay.geometry()
    monkeypatch.setattr("sidescreen.main_window.QCursor.pos", lambda: region.center())
    window._check_pointer()
    assert window._overlay.pointer_suppressed
    monkeypatch.setattr(
        "sidescreen.main_window.QCursor.pos", lambda: region.topLeft() - QPoint(2, 2)
    )
    window._check_pointer()
    assert not window._overlay.pointer_suppressed
    assert window._overlay.geometry() == region
    window.toggle_positioning()
    assert window._overlay.positioning
    window.toggle_pause()
    assert window._paused and not window._overlay.positioning
    assert window._overlay.pointer_suppressed
    window.toggle_pause()
    assert not window._overlay.pointer_suppressed
    window.output_combo.setCurrentIndex(0)
    assert not store.load().windowed
    assert window._overlay.geometry() == window._active_screen.geometry()
    window._quitting = True
    window.stop_mode()
    window._tray.hide()
    window.close()
    application.processEvents()
