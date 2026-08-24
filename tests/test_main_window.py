import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from sidescreen.main_window import MainWindow  # noqa: E402
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
