from __future__ import annotations

import logging

from PySide6.QtCore import QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QColor, QCursor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sidescreen.controls import ValueSlider
from sidescreen.displays import screen_id, screen_label
from sidescreen.filters import FILTER_LABEL_KEYS, FilterConfig
from sidescreen.hotkeys import GlobalLayoutHotkey
from sidescreen.i18n import available_languages, current_language, set_language, tr
from sidescreen.layout_editor import LayoutEditor
from sidescreen.layouts import grid_layout, source_relative_layout, strip_layout
from sidescreen.memory import trim_unused_working_set
from sidescreen.models import AppSettings, WindowInfo
from sidescreen.multi_capture import MultiCaptureManager
from sidescreen.overlay import MonitorOverlay
from sidescreen.resources import asset_path
from sidescreen.settings_store import SettingsStore
from sidescreen.win32_api import enumerate_windows, get_window_rect

LOGGER = logging.getLogger(__name__)
WINDOW_ROLE = Qt.ItemDataRole.UserRole


APP_STYLE = """
QMainWindow, QWidget#root { background: #070b14; color: #dce8f7; }
QWidget { font-family: "Segoe UI", "Microsoft YaHei UI"; font-size: 13px; }
QFrame#header, QFrame#card { background: #0d1422; border: 1px solid #1b2a40; border-radius: 14px; }
QLabel#title { font-size: 24px; font-weight: 700; color: #f4fbff; }
QLabel#subtitle, QLabel[class="muted"] { color: #7f91aa; }
QLabel#section { color: #7dd3fc; font-size: 12px; font-weight: 700; }
QComboBox, QSpinBox, QDoubleSpinBox, QListWidget {
  background: #080e19; border: 1px solid #25344d; border-radius: 8px;
  padding: 7px; color: #e6f2ff; selection-background-color: #164e63;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QListWidget:hover { border-color: #3a5978; }
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #22d3ee; }
QListWidget::item { padding: 7px 4px; border-radius: 6px; }
QListWidget::item:hover { background: #111d2e; }
QListWidget::item:selected { background: #123349; color: white; }
QPushButton {
  background: #132238; border: 1px solid #29415f; border-radius: 8px;
  padding: 8px 13px; color: #dbeafe;
}
QPushButton:hover { background: #19304b; border-color: #3b82a0; }
QPushButton:pressed { background: #0f1b2d; }
QPushButton#primary { background: #0891b2; border-color: #22d3ee; color: white; font-weight: 700; }
QPushButton#primary:hover { background: #06a7c8; }
QPushButton:disabled { color: #526177; background: #0d1420; border-color: #1b2839; }
QTabWidget::pane { border: 1px solid #1b2a40; border-radius: 10px; background: #0b111d; top: -1px; }
QTabBar::tab {
  background: #0b111d; color: #71839d; padding: 9px 18px;
  border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: #67e8f9; border-bottom-color: #22d3ee; }
QLabel#status {
  background: #091827; border: 1px solid #164e63; border-radius: 9px;
  padding: 10px; color: #a5f3fc;
}
QToolTip { background: #111827; color: white; border: 1px solid #334155; padding: 5px; }
QCheckBox { color: #dbeafe; spacing: 9px; }
QCheckBox::indicator { width: 34px; height: 18px; border-radius: 9px; background: #25344d; }
QCheckBox::indicator:checked { background: #22d3ee; border: 1px solid #67e8f9; }
QSlider::groove:horizontal { height: 5px; background: #1d2c42; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #22d3ee; border-radius: 2px; }
QSlider::handle:horizontal {
  background: #f8fafc; border: 2px solid #22d3ee; width: 16px; height: 16px;
  margin: -7px 0; border-radius: 9px;
}
QSlider::handle:horizontal:hover { background: #cffafe; }
QLabel[class="sliderValue"] { color: #a5f3fc; font-family: "Cascadia Mono", "Consolas"; }
"""


class MainWindow(QMainWindow):
    def __init__(self, store: SettingsStore | None = None) -> None:
        super().__init__()
        self.setObjectName("main")
        self.setMinimumSize(940, 650)
        self.resize(1040, 730)
        self.setStyleSheet(APP_STYLE)
        self._store = store or SettingsStore()
        self._settings = self._store.load()
        set_language(self._settings.language)
        self.setWindowTitle(tr("app.window_title"))
        self._overlay = MonitorOverlay()
        self._captures = MultiCaptureManager()
        self._active_screen = None
        self._active = False
        self._paused = False
        self._quitting = False
        self._loading = True
        self._layout: dict[int, QRectF] = {}
        self._accent_color = QColor(self._settings.accent_color)

        self._selection_debounce = QTimer(self)
        self._selection_debounce.setSingleShot(True)
        self._selection_debounce.setInterval(80)
        self._selection_debounce.timeout.connect(self._apply_window_selection)

        self._build_ui()
        self._build_tray()
        self._layout_hotkey = GlobalLayoutHotkey(self)
        self._connect_signals()
        self._load_controls()
        self.refresh_screens()
        self.refresh_windows()
        self._loading = False

        self._pointer_timer = QTimer(self)
        self._pointer_timer.setInterval(16)
        self._pointer_timer.timeout.connect(self._check_pointer)
        self._pointer_timer.start()

        self._source_layout_timer = QTimer(self)
        self._source_layout_timer.setInterval(1000)
        self._source_layout_timer.timeout.connect(self._refresh_source_layout)
        self._source_layout_timer.start()

        self._filter_animation_timer = QTimer(self)
        self._filter_animation_timer.setInterval(1000)
        self._filter_animation_timer.timeout.connect(self._captures.refresh_animated_filters)
        self._filter_animation_timer.start()

        self._memory_timer = QTimer(self)
        self._memory_timer.setInterval(90_000)
        self._memory_timer.timeout.connect(trim_unused_working_set)
        self._memory_timer.start()
        QTimer.singleShot(4_000, trim_unused_working_set)

    def _build_ui(self) -> None:
        root_widget = QWidget(self)
        root_widget.setObjectName("root")
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(13)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        logo = QLabel()
        logo.setPixmap(
            QPixmap(str(asset_path("sidescreen-logo-app.png"))).scaled(
                52,
                52,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        heading = QVBoxLayout()
        title = QLabel("SideScreenUtil")
        title.setObjectName("title")
        subtitle = QLabel(tr("app.subtitle"))
        subtitle.setObjectName("subtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header_layout.addWidget(logo)
        header_layout.addLayout(heading)
        header_layout.addStretch()
        language_label = QLabel(tr("header.language"))
        language_label.setProperty("class", "muted")
        self.language_combo = QComboBox()
        self.language_combo.setMinimumWidth(130)
        for language in available_languages():
            self.language_combo.addItem(language.name, language.code)
        self._set_combo_data(self.language_combo, current_language())
        header_layout.addWidget(language_label)
        header_layout.addWidget(self.language_combo)
        self.header_state = QLabel(tr("state.idle"))
        self.header_state.setStyleSheet("color: #64748b; font-weight: 600;")
        header_layout.addWidget(self.header_state)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(13)
        source_card = QFrame()
        source_card.setObjectName("card")
        source_card.setFixedWidth(350)
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(15, 15, 15, 15)
        source_layout.setSpacing(10)
        source_title = QLabel(tr("source.section"))
        source_title.setObjectName("section")
        source_layout.addWidget(source_title)
        screen_row = QHBoxLayout()
        self.screen_combo = QComboBox()
        refresh_screens = QPushButton(tr("common.refresh"))
        refresh_screens.setToolTip(tr("source.refresh_screens_tip"))
        screen_row.addWidget(self.screen_combo, 1)
        screen_row.addWidget(refresh_screens)
        source_layout.addLayout(screen_row)
        hint = QLabel(tr("source.hint"))
        hint.setWordWrap(True)
        hint.setProperty("class", "muted")
        source_layout.addWidget(hint)
        self.window_list = QListWidget()
        self.window_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.window_list.setAlternatingRowColors(False)
        self.window_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.window_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        source_layout.addWidget(self.window_list, 1)
        source_buttons = QHBoxLayout()
        refresh_windows = QPushButton(tr("source.refresh_windows"))
        select_all = QPushButton(tr("source.select_all"))
        clear_all = QPushButton(tr("source.clear"))
        source_buttons.addWidget(refresh_windows, 1)
        source_buttons.addWidget(select_all)
        source_buttons.addWidget(clear_all)
        source_layout.addLayout(source_buttons)
        body.addWidget(source_card)

        workspace = QFrame()
        workspace.setObjectName("card")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(14, 14, 14, 14)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_layout_tab(), tr("tabs.layout"))
        self.tabs.addTab(self._build_filter_tab(), tr("tabs.filters"))
        self.tabs.addTab(self._build_protection_tab(), tr("tabs.protection"))
        workspace_layout.addWidget(self.tabs)
        body.addWidget(workspace, 1)
        root.addLayout(body, 1)

        controls = QHBoxLayout()
        self.start_button = QPushButton(tr("action.start"))
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumHeight(44)
        self.pause_button = QPushButton(tr("action.pause"))
        self.pause_button.setMinimumHeight(44)
        self.pause_button.setEnabled(False)
        controls.addWidget(self.start_button, 1)
        controls.addWidget(self.pause_button)
        root.addLayout(controls)
        self.status_label = QLabel(tr("status.ready"))
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.setCentralWidget(root_widget)

        refresh_screens.clicked.connect(self.refresh_screens)
        refresh_windows.clicked.connect(self.refresh_windows)
        select_all.clicked.connect(lambda: self._set_all_windows(Qt.CheckState.Checked))
        clear_all.clicked.connect(lambda: self._set_all_windows(Qt.CheckState.Unchecked))

    def _build_layout_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("layout.type")))
        self.layout_combo = QComboBox()
        for key, label in (
            ("source", tr("layout.source")),
            ("grid", tr("layout.grid")),
            ("horizontal", tr("layout.horizontal")),
            ("vertical", tr("layout.vertical")),
            ("manual", tr("layout.manual")),
        ):
            self.layout_combo.addItem(label, key)
        regenerate = QPushButton(tr("layout.regenerate"))
        row.addWidget(self.layout_combo, 1)
        row.addWidget(regenerate)
        layout.addLayout(row)
        self.layout_editor = LayoutEditor()
        self.layout_editor.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.layout_editor, 1)
        self.layout_edit_button = QPushButton(tr("layout.edit"))
        self.layout_edit_button.setEnabled(False)
        layout.addWidget(self.layout_edit_button)
        help_label = QLabel(tr("layout.help"))
        help_label.setWordWrap(True)
        help_label.setProperty("class", "muted")
        layout.addWidget(help_label)
        regenerate.clicked.connect(self._regenerate_layout)
        return tab

    def _build_filter_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(14)
        self.filter_combo = QComboBox()
        for key, label_key in FILTER_LABEL_KEYS.items():
            self.filter_combo.addItem(tr(label_key), key)
        self.brightness_spin = ValueSlider(
            10, 100, lambda value: tr("common.percent", value=value)
        )
        self.accent_button = QPushButton(tr("filter.choose_color"))
        self.hue_cycle_spin = ValueSlider(
            10, 600, lambda value: tr("filter.cycle_seconds", value=value)
        )
        self.edge_spin = ValueSlider(4, 120, lambda value: str(value))
        self.edge_spin.setToolTip(tr("filter.edge_tip"))
        self.edge_thickness_spin = ValueSlider(1, 4, lambda value: f"{value} px")
        form.addRow(tr("filter.visual"), self.filter_combo)
        form.addRow(tr("filter.brightness"), self.brightness_spin)
        form.addRow(tr("filter.fixed_color"), self.accent_button)
        form.addRow(tr("filter.hue_speed"), self.hue_cycle_spin)
        form.addRow(tr("filter.edge_sensitivity"), self.edge_spin)
        form.addRow(tr("filter.edge_width"), self.edge_thickness_spin)
        explanation = QLabel(tr("filter.explanation"))
        explanation.setWordWrap(True)
        explanation.setProperty("class", "muted")
        form.addRow("", explanation)
        return tab

    def _build_protection_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(14)
        self.scale_spin = ValueSlider(
            20, 92, lambda value: tr("common.percent", value=value)
        )
        self.move_spin = ValueSlider(
            30, 900, lambda value: tr("protection.segment_seconds", value=value)
        )
        self.variation_spin = ValueSlider(
            0, 10, lambda value: tr("common.percent", value=value)
        )
        self.blank_every_spin = ValueSlider(
            0,
            240,
            lambda value: tr("common.close")
            if value == 0
            else tr("common.minutes", value=value),
        )
        self.blank_seconds_spin = ValueSlider(
            5, 300, lambda value: tr("common.seconds", value=value)
        )
        self.fps_spin = ValueSlider(
            5, 30, lambda value: tr("protection.fps_value", value=value)
        )
        self.limit_resolution_check = QCheckBox()
        self.limit_resolution_check.setToolTip(
            tr("protection.resolution_tip")
        )
        form.addRow(tr("protection.canvas_size"), self.scale_spin)
        form.addRow(tr("protection.drift_speed"), self.move_spin)
        form.addRow(tr("protection.size_variation"), self.variation_spin)
        form.addRow(tr("protection.blank_interval"), self.blank_every_spin)
        form.addRow(tr("protection.blank_duration"), self.blank_seconds_spin)
        form.addRow(tr("protection.fps"), self.fps_spin)
        form.addRow(tr("protection.resolution_limit"), self.limit_resolution_check)
        return tab

    def _build_tray(self) -> None:
        icon = QIcon(str(asset_path("sidescreen.ico")))
        self.setWindowIcon(icon)
        self._tray = QSystemTrayIcon(icon, self)
        menu = QMenu()
        show_action = QAction(tr("tray.show"), self)
        self._tray_pause_action = QAction(tr("tray.pause"), self)
        self._tray_pause_action.setEnabled(False)
        quit_action = QAction(tr("tray.quit"), self)
        show_action.triggered.connect(self._show_settings)
        self._tray_pause_action.triggered.connect(self.toggle_pause)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(show_action)
        menu.addAction(self._tray_pause_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self.toggle_active)
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.layout_edit_button.clicked.connect(self.toggle_layout_editing)
        self._layout_hotkey.activated.connect(self.toggle_layout_editing)
        self.window_list.itemChanged.connect(lambda _item: self._selection_changed())
        self.layout_combo.currentIndexChanged.connect(lambda _index: self._regenerate_layout())
        self._overlay.layout_edited.connect(self._overlay_layout_edited)
        self.filter_combo.currentIndexChanged.connect(self._filter_controls_changed)
        self.brightness_spin.valueChanged.connect(self._filter_controls_changed)
        self.hue_cycle_spin.valueChanged.connect(self._filter_controls_changed)
        self.edge_spin.valueChanged.connect(self._filter_controls_changed)
        self.edge_thickness_spin.valueChanged.connect(self._filter_controls_changed)
        self.accent_button.clicked.connect(self._choose_accent)
        for control in (
            self.scale_spin,
            self.move_spin,
            self.variation_spin,
            self.blank_every_spin,
            self.blank_seconds_spin,
        ):
            control.valueChanged.connect(self._protection_changed)
        self.fps_spin.valueChanged.connect(lambda _value: self._selection_changed())
        self.limit_resolution_check.stateChanged.connect(self._resolution_limit_changed)
        self._captures.frame_ready.connect(self._overlay.set_frame)
        self._captures.backends_changed.connect(self._backends_changed)
        self._captures.warning.connect(self._capture_warning)
        self._captures.source_closed.connect(self._source_closed)
        app = QApplication.instance()
        app.screenAdded.connect(lambda _screen: self.refresh_screens())
        app.screenRemoved.connect(self._screen_removed)

    def _load_controls(self) -> None:
        settings = self._settings
        self.scale_spin.setValue(settings.preview_scale * 100)
        self.move_spin.setValue(settings.move_seconds)
        self.variation_spin.setValue(settings.size_variation * 100)
        self.blank_every_spin.setValue(settings.blank_every_minutes)
        self.blank_seconds_spin.setValue(settings.blank_seconds)
        self.fps_spin.setValue(settings.capture_fps)
        self.limit_resolution_check.setChecked(settings.limit_capture_resolution)
        self._update_resolution_limit_text()
        self.brightness_spin.setValue(settings.brightness * 100)
        self.hue_cycle_spin.setValue(settings.hue_cycle_seconds)
        self.edge_spin.setValue(settings.edge_threshold)
        self.edge_thickness_spin.setValue(settings.edge_thickness)
        self._set_combo_data(self.layout_combo, settings.layout_mode)
        self._set_combo_data(self.filter_combo, settings.filter_style)
        self._update_accent_button()
        self._update_filter_visibility()

    @staticmethod
    def _set_combo_data(combo: QComboBox, data: object) -> None:
        index = combo.findData(data)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _settings_from_controls(self) -> AppSettings:
        screen = self.screen_combo.currentData()
        return AppSettings(
            language=str(self.language_combo.currentData() or current_language()),
            screen_id=screen_id(screen) if screen is not None else "",
            preview_scale=self.scale_spin.value() / 100,
            move_seconds=self.move_spin.value(),
            size_variation=self.variation_spin.value() / 100,
            capture_fps=self.fps_spin.value(),
            limit_capture_resolution=self.limit_resolution_check.isChecked(),
            blank_every_minutes=self.blank_every_spin.value(),
            blank_seconds=self.blank_seconds_spin.value(),
            layout_mode=str(self.layout_combo.currentData()),
            filter_style=str(self.filter_combo.currentData()),
            brightness=self.brightness_spin.value() / 100,
            accent_color=self._accent_color.name(),
            hue_cycle_seconds=self.hue_cycle_spin.value(),
            edge_threshold=self.edge_spin.value(),
            edge_thickness=self.edge_thickness_spin.value(),
        ).normalized()

    def _filter_config(self) -> FilterConfig:
        settings = self._settings_from_controls()
        return FilterConfig(
            style=settings.filter_style,
            brightness=settings.brightness,
            accent_color=settings.accent_color,
            hue_cycle_seconds=settings.hue_cycle_seconds,
            edge_threshold=settings.edge_threshold,
            edge_thickness=settings.edge_thickness,
        )

    def refresh_screens(self) -> None:
        current_id = self._settings.screen_id
        current_screen = self.screen_combo.currentData() if self.screen_combo.count() else None
        if current_screen is not None:
            current_id = screen_id(current_screen)
        self.screen_combo.clear()
        selected = -1
        for index, screen in enumerate(QApplication.screens()):
            self.screen_combo.addItem(screen_label(screen, index), screen)
            if screen_id(screen) == current_id:
                selected = index
        if selected >= 0:
            self.screen_combo.setCurrentIndex(selected)
        elif self.screen_combo.count() > 1:
            primary = QApplication.primaryScreen()
            for index in range(self.screen_combo.count()):
                if self.screen_combo.itemData(index) is not primary:
                    self.screen_combo.setCurrentIndex(index)
                    break

    def refresh_windows(self) -> None:
        checked = {window.hwnd for window in self._selected_windows()} | self._captures.window_ids
        self.window_list.blockSignals(True)
        self.window_list.clear()
        for window in enumerate_windows():
            item = QListWidgetItem(window.display_name)
            item.setData(WINDOW_ROLE, window)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if window.hwnd in checked else Qt.CheckState.Unchecked
            )
            item.setToolTip(window.title)
            self.window_list.addItem(item)
        self.window_list.blockSignals(False)
        self._sync_layout_editor()

    def _selected_windows(self) -> list[WindowInfo]:
        result: list[WindowInfo] = []
        for index in range(self.window_list.count()):
            item = self.window_list.item(index)
            window = item.data(WINDOW_ROLE)
            if item.checkState() == Qt.CheckState.Checked and isinstance(window, WindowInfo):
                result.append(window)
        return result

    def _set_all_windows(self, state: Qt.CheckState) -> None:
        self.window_list.blockSignals(True)
        for index in range(self.window_list.count()):
            self.window_list.item(index).setCheckState(state)
        self.window_list.blockSignals(False)
        self._selection_changed()

    def _selection_changed(self) -> None:
        self._selection_debounce.start()
        self._sync_layout_editor()

    def _apply_window_selection(self) -> None:
        windows = self._selected_windows()
        if self._active:
            self._captures.sync_windows(
                windows,
                self.fps_spin.value(),
                self._filter_config(),
                self.limit_resolution_check.isChecked(),
            )
            self._overlay.set_sources([window.hwnd for window in windows])
            self._overlay.set_source_titles({window.hwnd: window.title for window in windows})
        self._regenerate_layout(selection_changed=True)
        if self._active:
            self.status_label.setText(tr("status.live_switch", count=len(windows)))

    def _generate_layout(self, mode: str, windows: list[WindowInfo]) -> dict[int, QRectF]:
        keys = [window.hwnd for window in windows]
        if mode == "horizontal":
            return strip_layout(keys)
        if mode == "vertical":
            return strip_layout(keys, vertical=True)
        if mode == "source":
            rectangles: dict[int, QRect] = {}
            for window in windows:
                raw = get_window_rect(window.hwnd)
                if raw is not None:
                    left, top, right, bottom = raw
                    rectangles[window.hwnd] = QRect(left, top, right - left, bottom - top)
            return source_relative_layout(rectangles) if rectangles else grid_layout(keys)
        return grid_layout(keys)

    def _regenerate_layout(self, selection_changed: bool = False) -> None:
        if not hasattr(self, "layout_editor"):
            return
        windows = self._selected_windows()
        mode = str(self.layout_combo.currentData())
        keys = {window.hwnd for window in windows}
        if mode == "manual" and not selection_changed and set(self._layout) == keys:
            layout = self._layout
        elif mode == "manual" and set(self._layout) == keys:
            layout = self._layout
        else:
            layout = self._generate_layout(mode, windows)
        self._set_layout(layout)

    def _set_layout(self, layout: dict[int, QRectF], animate: bool = True) -> None:
        self._layout = {key: QRectF(value) for key, value in layout.items()}
        self._sync_layout_editor()
        if self._active:
            self._overlay.set_layout(self._layout, animate=animate)

    def _sync_layout_editor(self) -> None:
        if not hasattr(self, "layout_editor"):
            return
        windows = self._selected_windows()
        titles = {window.hwnd: window.title for window in windows}
        valid_layout = {key: value for key, value in self._layout.items() if key in titles}
        if set(valid_layout) != set(titles):
            valid_layout = self._generate_layout(str(self.layout_combo.currentData()), windows)
            self._layout = valid_layout
        self.layout_editor.set_items(titles, valid_layout)

    def _manual_layout_changed(self, layout: dict[int, QRectF]) -> None:
        self.layout_combo.blockSignals(True)
        self._set_combo_data(self.layout_combo, "manual")
        self.layout_combo.blockSignals(False)
        self._set_layout(layout)

    def _overlay_layout_edited(self, layout: dict[int, QRectF]) -> None:
        self._manual_layout_changed(layout)
        self.layout_edit_button.setText(tr("layout.edit"))
        self.header_state.setText(
            tr("state.running", count=len(self._selected_windows()))
        )
        self.status_label.setText(tr("status.layout_saved"))
        self._persist_current_settings()
        QTimer.singleShot(0, self._check_pointer)

    def toggle_layout_editing(self) -> None:
        if not self._active:
            self.status_label.setText(tr("status.start_before_edit"))
            return
        if self._paused:
            self._paused = False
            self.pause_button.setText(tr("action.pause"))
            self._tray_pause_action.setText(tr("tray.pause"))
        editing = self._overlay.toggle_layout_editing()
        if editing:
            self.layout_edit_button.setText(tr("layout.finish"))
            self.header_state.setText(tr("state.editing"))
            self.status_label.setText(tr("status.layout_editing"))
        else:
            self.layout_edit_button.setText(tr("layout.edit"))

    def _refresh_source_layout(self) -> None:
        if not self._active or self.layout_combo.currentData() != "source":
            return
        updated = self._generate_layout("source", self._selected_windows())
        if not self._layouts_equal(updated, self._layout):
            self._set_layout(updated)

    @staticmethod
    def _layouts_equal(first: dict[int, QRectF], second: dict[int, QRectF]) -> bool:
        if set(first) != set(second):
            return False
        return all(
            abs(first[key].x() - second[key].x()) < 0.002
            and abs(first[key].y() - second[key].y()) < 0.002
            and abs(first[key].width() - second[key].width()) < 0.002
            and abs(first[key].height() - second[key].height()) < 0.002
            for key in first
        )

    def _choose_accent(self) -> None:
        color = QColorDialog.getColor(
            self._accent_color, self, tr("dialog.choose_filter_color")
        )
        if color.isValid():
            self._accent_color = color
            self._update_accent_button()
            self._filter_controls_changed()

    def _update_accent_button(self) -> None:
        foreground = "#061018" if self._accent_color.lightness() > 150 else "white"
        self.accent_button.setText(self._accent_color.name().upper())
        self.accent_button.setStyleSheet(
            f"background: {self._accent_color.name()}; color: {foreground}; font-weight: 700;"
        )

    def _update_filter_visibility(self) -> None:
        style = str(self.filter_combo.currentData())
        self.accent_button.setEnabled(style in {"mono", "edge"})
        self.hue_cycle_spin.setEnabled(style in {"mono_cycle", "edge_cycle"})
        self.edge_spin.setEnabled(style in {"edge", "edge_cycle"})
        self.edge_thickness_spin.setEnabled(style in {"edge", "edge_cycle"})

    def _filter_controls_changed(self, _value: object = None) -> None:
        self._update_filter_visibility()
        if self._active:
            self._captures.set_filter(self._filter_config())
        self._persist_current_settings()

    def _protection_changed(self, _value: object = None) -> None:
        if self._active:
            self._overlay.update_settings(self._settings_from_controls())
        self._persist_current_settings()

    def _update_resolution_limit_text(self) -> None:
        if self.limit_resolution_check.isChecked():
            self.limit_resolution_check.setText(tr("protection.resolution_limited"))
        else:
            self.limit_resolution_check.setText(tr("protection.resolution_full"))

    def _resolution_limit_changed(self, _state: object = None) -> None:
        self._update_resolution_limit_text()
        self._captures.set_resolution_limit(self.limit_resolution_check.isChecked())
        if self._active:
            mode = tr(
                "status.resolution_limited"
                if self.limit_resolution_check.isChecked()
                else "status.resolution_full"
            )
            self.status_label.setText(tr("status.resolution_changed", mode=mode))
        self._persist_current_settings()

    def _language_changed(self, _index: int = -1) -> None:
        if self._loading:
            return
        code = str(self.language_combo.currentData() or "")
        if not code or code == current_language():
            return
        set_language(code)
        self._persist_current_settings()
        QMessageBox.information(
            self,
            tr("language.changed_title"),
            tr("language.changed_body"),
        )

    def _persist_current_settings(self) -> None:
        if self._loading:
            return
        try:
            self._settings = self._settings_from_controls()
            self._store.save(self._settings)
        except OSError:
            LOGGER.exception("Unable to save settings")

    def toggle_active(self) -> None:
        if self._active:
            self.stop_mode()
        else:
            self.start_mode()

    def start_mode(self) -> None:
        screen = self.screen_combo.currentData()
        windows = self._selected_windows()
        if screen is None:
            QMessageBox.warning(
                self, tr("dialog.cannot_start"), tr("dialog.select_screen")
            )
            return
        if not windows:
            QMessageBox.warning(
                self, tr("dialog.cannot_start"), tr("dialog.select_window")
            )
            return
        settings = self._settings_from_controls()
        self._settings = settings
        self._persist_current_settings()
        self._active_screen = screen
        self._active = True
        self._paused = False
        self._overlay.set_sources([window.hwnd for window in windows])
        self._overlay.set_source_titles({window.hwnd: window.title for window in windows})
        starting_layout = self._layout or grid_layout(window.hwnd for window in windows)
        self._overlay.set_layout(starting_layout, False)
        self._overlay.activate(screen, settings)
        self._captures.sync_windows(
            windows,
            settings.capture_fps,
            self._filter_config(),
            settings.limit_capture_resolution,
        )
        self.start_button.setText(tr("action.stop"))
        self.pause_button.setEnabled(True)
        self.layout_edit_button.setEnabled(True)
        self.pause_button.setText(tr("action.pause"))
        self._tray_pause_action.setEnabled(True)
        self._tray_pause_action.setText(tr("tray.pause"))
        self.header_state.setText(tr("state.running", count=len(windows)))
        self.header_state.setStyleSheet("color: #22d3ee; font-weight: 700;")
        self.status_label.setText(tr("status.starting"))
        self._check_pointer()

    def stop_mode(self, status: str | None = None) -> None:
        self._captures.stop_all()
        self._overlay.deactivate(animated=not self._quitting)
        self._active = False
        self._paused = False
        self._active_screen = None
        self.start_button.setText(tr("action.start"))
        self.pause_button.setEnabled(False)
        self.layout_edit_button.setEnabled(False)
        self.layout_edit_button.setText(tr("layout.edit"))
        self.pause_button.setText(tr("action.pause"))
        self._tray_pause_action.setEnabled(False)
        self._tray_pause_action.setText(tr("tray.pause"))
        self.header_state.setText(tr("state.idle"))
        self.header_state.setStyleSheet("color: #64748b; font-weight: 600;")
        self.status_label.setText(status or tr("status.stopped"))
        QTimer.singleShot(500, trim_unused_working_set)

    def toggle_pause(self) -> None:
        if not self._active:
            return
        if self._overlay.layout_editing:
            self._overlay.finish_layout_editing()
        self._paused = not self._paused
        if self._paused:
            self._overlay.suppress_for_pointer()
            self.pause_button.setText(tr("common.resume"))
            self._tray_pause_action.setText(tr("tray.resume"))
            self.header_state.setText(tr("state.paused"))
            self.status_label.setText(tr("status.paused"))
        else:
            self.pause_button.setText(tr("action.pause"))
            self._tray_pause_action.setText(tr("tray.pause"))
            self.header_state.setText(
                tr("state.running", count=len(self._selected_windows()))
            )
            self._check_pointer()

    def _check_pointer(self) -> None:
        if (
            not self._active
            or self._active_screen is None
            or self._paused
            or self._overlay.layout_editing
        ):
            return
        inside = self._active_screen.geometry().contains(QCursor.pos())
        if inside:
            self._overlay.suppress_for_pointer()
        elif self._overlay.pointer_suppressed:
            self._overlay.reveal()

    def _backends_changed(self, summary: str) -> None:
        if self._active:
            count = len(self._captures.window_ids)
            self.status_label.setText(
                tr("status.backends", count=count, summary=summary)
            )
            self.header_state.setText(tr("state.running", count=count))

    def _capture_warning(self, message: str) -> None:
        self.status_label.setText(message)

    def _source_closed(self, hwnd: int) -> None:
        self.window_list.blockSignals(True)
        for index in range(self.window_list.count()):
            item = self.window_list.item(index)
            window = item.data(WINDOW_ROLE)
            if isinstance(window, WindowInfo) and window.hwnd == hwnd:
                item.setCheckState(Qt.CheckState.Unchecked)
                break
        self.window_list.blockSignals(False)
        self._apply_window_selection()
        self.status_label.setText(tr("status.source_closed"))

    def _screen_removed(self, removed: object) -> None:
        if self._active_screen is removed:
            self.stop_mode(tr("status.screen_removed"))
        self.refresh_screens()

    def _show_settings(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_settings()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.hide()
        self._tray.showMessage(
            tr("tray.still_running_title"),
            tr("tray.still_running_body"),
            QSystemTrayIcon.MessageIcon.Information,
            2200,
        )

    def quit_application(self) -> None:
        self._quitting = True
        self.stop_mode()
        self._tray.hide()
        QApplication.quit()
