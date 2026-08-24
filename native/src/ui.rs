#![allow(deprecated)]

use std::cell::RefCell;
use std::collections::{HashMap, HashSet};
use std::rc::{Rc, Weak};
use std::sync::Arc;

use native_windows_gui as nwg;
use winapi::shared::windef::RECT;
use winapi::um::wingdi::{CreateSolidBrush, SetBkColor, SetTextColor};
use winapi::um::winuser::{
    FillRect, GetClientRect, MF_BYCOMMAND, MF_STRING, ModifyMenuW, RegisterHotKey,
    UnregisterHotKey, WM_CTLCOLORBTN, WM_CTLCOLORDLG, WM_CTLCOLOREDIT, WM_CTLCOLORLISTBOX,
    WM_CTLCOLORSTATIC, WM_ERASEBKGND, WM_HOTKEY,
};

use crate::capture::{self, NativeCaptureControl, SharedCaptureState};
use crate::i18n::Translations;
use crate::layout;
use crate::model::{AppSettings, FilterStyle, LayoutMode, MonitorInfo, RectF, WindowInfo};
use crate::overlay::Overlay;
use crate::platform;
use crate::settings;

const BG: [u8; 3] = [28, 28, 28];
const TEXT: [u8; 3] = [245, 245, 245];
const MUTED: [u8; 3] = [178, 178, 178];

#[derive(Default)]
struct MonitorPage {
    frame: nwg::Frame,
    title: nwg::Label,
    description: nwg::Label,
    monitor_label: nwg::Label,
    monitor_combo: nwg::ComboBox<String>,
    refresh_monitors: nwg::Button,
    windows_label: nwg::Label,
    windows_list: nwg::ListBox<String>,
    refresh_windows: nwg::Button,
    select_all: nwg::Button,
    clear: nwg::Button,
    hint: nwg::Label,
}

#[derive(Default)]
struct LayoutPage {
    frame: nwg::Frame,
    title: nwg::Label,
    description: nwg::Label,
    kind_label: nwg::Label,
    kind_combo: nwg::ComboBox<String>,
    regenerate: nwg::Button,
    edit: nwg::Button,
    help: nwg::Label,
}

#[derive(Default)]
struct FilterPage {
    frame: nwg::Frame,
    title: nwg::Label,
    description: nwg::Label,
    kind_label: nwg::Label,
    kind_combo: nwg::ComboBox<String>,
    brightness_label: nwg::Label,
    brightness_value: nwg::Label,
    brightness: nwg::TrackBar,
    color_label: nwg::Label,
    choose_color: nwg::Button,
    hue_label: nwg::Label,
    hue_value: nwg::Label,
    hue: nwg::TrackBar,
    edge_threshold_label: nwg::Label,
    edge_threshold_value: nwg::Label,
    edge_threshold: nwg::TrackBar,
    edge_width_label: nwg::Label,
    edge_width_value: nwg::Label,
    edge_width: nwg::TrackBar,
    explanation: nwg::Label,
}

#[derive(Default)]
struct ProtectionPage {
    frame: nwg::Frame,
    title: nwg::Label,
    description: nwg::Label,
    scale_label: nwg::Label,
    scale_value: nwg::Label,
    scale: nwg::TrackBar,
    drift_label: nwg::Label,
    drift_value: nwg::Label,
    drift: nwg::TrackBar,
    variation_label: nwg::Label,
    variation_value: nwg::Label,
    variation: nwg::TrackBar,
    blank_interval_label: nwg::Label,
    blank_interval_value: nwg::Label,
    blank_interval: nwg::TrackBar,
    blank_duration_label: nwg::Label,
    blank_duration_value: nwg::Label,
    blank_duration: nwg::TrackBar,
    fps_label: nwg::Label,
    fps_value: nwg::Label,
    fps: nwg::TrackBar,
    resolution_limit: nwg::CheckBox,
    resolution_tip: nwg::Label,
}

pub struct App {
    window: nwg::Window,
    heading: nwg::Label,
    subtitle: nwg::Label,
    language_label: nwg::Label,
    language: nwg::ComboBox<String>,
    state: nwg::Label,
    nav_monitor: nwg::Button,
    nav_layout: nwg::Button,
    nav_filters: nwg::Button,
    nav_protection: nwg::Button,
    monitor_page: MonitorPage,
    layout_page: LayoutPage,
    filter_page: FilterPage,
    protection_page: ProtectionPage,
    start_stop: nwg::Button,
    pause_resume: nwg::Button,
    status: nwg::Label,
    resources: nwg::EmbedResource,
    icon: nwg::Icon,
    tray: nwg::TrayNotification,
    tray_menu: nwg::Menu,
    tray_show: nwg::MenuItem,
    tray_pause: nwg::MenuItem,
    tray_separator: nwg::MenuSeparator,
    tray_quit: nwg::MenuItem,
    timer: nwg::Timer,
    color_dialog: nwg::ColorDialog,
    heading_font: nwg::Font,
    page_font: nwg::Font,
    settings: AppSettings,
    translations: Translations,
    monitors: Vec<MonitorInfo>,
    windows: Vec<WindowInfo>,
    shared: Arc<SharedCaptureState>,
    overlay: Rc<RefCell<Overlay>>,
    captures: HashMap<isize, NativeCaptureControl>,
    active: bool,
    paused: bool,
    page: usize,
    event_handler: Option<nwg::EventHandler>,
    raw_handler: Option<nwg::RawEventHandler>,
    color_handlers: Vec<nwg::RawEventHandler>,
}

impl App {
    pub fn build() -> Result<Rc<RefCell<Self>>, nwg::NwgError> {
        let mut loaded = settings::load();
        loaded.normalize();
        let translations = Translations::load(&loaded.language);
        let shared = SharedCaptureState::new(loaded.clone());
        let overlay = Overlay::build(shared.clone())?;
        let mut app = Self {
            window: Default::default(),
            heading: Default::default(),
            subtitle: Default::default(),
            language_label: Default::default(),
            language: Default::default(),
            state: Default::default(),
            nav_monitor: Default::default(),
            nav_layout: Default::default(),
            nav_filters: Default::default(),
            nav_protection: Default::default(),
            monitor_page: Default::default(),
            layout_page: Default::default(),
            filter_page: Default::default(),
            protection_page: Default::default(),
            start_stop: Default::default(),
            pause_resume: Default::default(),
            status: Default::default(),
            resources: Default::default(),
            icon: Default::default(),
            tray: Default::default(),
            tray_menu: Default::default(),
            tray_show: Default::default(),
            tray_pause: Default::default(),
            tray_separator: Default::default(),
            tray_quit: Default::default(),
            timer: Default::default(),
            color_dialog: Default::default(),
            heading_font: Default::default(),
            page_font: Default::default(),
            settings: loaded,
            translations,
            monitors: Vec::new(),
            windows: Vec::new(),
            shared,
            overlay,
            captures: HashMap::new(),
            active: false,
            paused: false,
            page: 0,
            event_handler: None,
            raw_handler: None,
            color_handlers: Vec::new(),
        };
        app.build_controls()?;
        let app = Rc::new(RefCell::new(app));
        Self::bind_events(&app)?;
        {
            let mut value = app.borrow_mut();
            value.refresh_monitors();
            value.refresh_windows(HashSet::new());
            value.apply_language();
            value.show_page(0);
            value.update_value_labels();
            value.apply_themes();
            let hwnd = platform::hwnd(&value.window.handle);
            platform::apply_dark_title_bar(hwnd);
            unsafe {
                RegisterHotKey(
                    hwnd,
                    platform::HOTKEY_ID,
                    platform::HOTKEY_MODIFIERS,
                    b'L' as u32,
                );
            }
        }
        Ok(app)
    }

    fn t(&self, key: &str) -> String {
        self.translations.text(key)
    }

    fn build_controls(&mut self) -> Result<(), nwg::NwgError> {
        nwg::Font::builder()
            .family("Segoe UI Variable Display")
            .size(25)
            .weight(600)
            .build(&mut self.heading_font)?;
        nwg::Font::builder()
            .family("Segoe UI Variable Text")
            .size(18)
            .weight(600)
            .build(&mut self.page_font)?;
        self.resources = nwg::EmbedResource::load(None)?;
        nwg::Icon::builder()
            .source_embed(Some(&self.resources))
            .source_embed_id(1)
            .build(&mut self.icon)?;
        nwg::Window::builder()
            .size((1040, 760))
            .center(true)
            .title("SideScreenUtil")
            .icon(Some(&self.icon))
            .flags(nwg::WindowFlags::WINDOW | nwg::WindowFlags::VISIBLE)
            .build(&mut self.window)?;
        label(
            &mut self.heading,
            "SideScreenUtil",
            (28, 22),
            (390, 42),
            &self.window,
            Some(&self.heading_font),
            TEXT,
        )?;
        label(
            &mut self.subtitle,
            "",
            (30, 64),
            (610, 24),
            &self.window,
            None,
            MUTED,
        )?;
        label(
            &mut self.language_label,
            "",
            (735, 24),
            (85, 24),
            &self.window,
            None,
            MUTED,
        )?;
        nwg::ComboBox::builder()
            .position((818, 20))
            .size((190, 34))
            .collection(self.translations.language_names())
            .selected_index(Some(self.translations.active_index()))
            .parent(&self.window)
            .build(&mut self.language)?;
        label(
            &mut self.state,
            "",
            (735, 61),
            (270, 24),
            &self.window,
            None,
            [76, 201, 240],
        )?;
        button(
            &mut self.nav_monitor,
            "",
            (24, 115),
            (202, 44),
            &self.window,
        )?;
        button(&mut self.nav_layout, "", (24, 165), (202, 44), &self.window)?;
        button(
            &mut self.nav_filters,
            "",
            (24, 215),
            (202, 44),
            &self.window,
        )?;
        button(
            &mut self.nav_protection,
            "",
            (24, 265),
            (202, 44),
            &self.window,
        )?;
        self.build_monitor_page()?;
        self.build_layout_page()?;
        self.build_filter_page()?;
        self.build_protection_page()?;
        button(
            &mut self.start_stop,
            "",
            (252, 676),
            (580, 44),
            &self.window,
        )?;
        button(
            &mut self.pause_resume,
            "",
            (844, 676),
            (164, 44),
            &self.window,
        )?;
        label(
            &mut self.status,
            "",
            (253, 724),
            (755, 24),
            &self.window,
            None,
            MUTED,
        )?;
        nwg::TrayNotification::builder()
            .parent(&self.window)
            .icon(Some(&self.icon))
            .tip(Some("SideScreenUtil"))
            .build(&mut self.tray)?;
        nwg::Menu::builder()
            .popup(true)
            .parent(&self.window)
            .build(&mut self.tray_menu)?;
        nwg::MenuItem::builder()
            .text("")
            .parent(&self.tray_menu)
            .build(&mut self.tray_show)?;
        nwg::MenuItem::builder()
            .text("")
            .parent(&self.tray_menu)
            .build(&mut self.tray_pause)?;
        nwg::MenuSeparator::builder()
            .parent(&self.tray_menu)
            .build(&mut self.tray_separator)?;
        nwg::MenuItem::builder()
            .text("")
            .parent(&self.tray_menu)
            .build(&mut self.tray_quit)?;
        nwg::Timer::builder()
            .parent(&self.window)
            .interval(30)
            .stopped(false)
            .build(&mut self.timer)?;
        nwg::ColorDialog::builder().build(&mut self.color_dialog)?;
        Ok(())
    }

    fn build_monitor_page(&mut self) -> Result<(), nwg::NwgError> {
        frame(&mut self.monitor_page.frame, &self.window)?;
        let p = &self.monitor_page.frame;
        label(
            &mut self.monitor_page.title,
            "",
            (28, 22),
            (500, 32),
            p,
            Some(&self.page_font),
            TEXT,
        )?;
        label(
            &mut self.monitor_page.description,
            "",
            (28, 54),
            (690, 24),
            p,
            None,
            MUTED,
        )?;
        label(
            &mut self.monitor_page.monitor_label,
            "",
            (28, 98),
            (200, 24),
            p,
            None,
            TEXT,
        )?;
        nwg::ComboBox::builder()
            .position((28, 126))
            .size((610, 34))
            .parent(p)
            .build(&mut self.monitor_page.monitor_combo)?;
        button(
            &mut self.monitor_page.refresh_monitors,
            "",
            (650, 126),
            (108, 34),
            p,
        )?;
        label(
            &mut self.monitor_page.windows_label,
            "",
            (28, 180),
            (250, 24),
            p,
            None,
            TEXT,
        )?;
        nwg::ListBox::builder()
            .flags(
                nwg::ListBoxFlags::VISIBLE
                    | nwg::ListBoxFlags::MULTI_SELECT
                    | nwg::ListBoxFlags::TAB_STOP,
            )
            .position((28, 208))
            .size((730, 220))
            .parent(p)
            .build(&mut self.monitor_page.windows_list)?;
        button(
            &mut self.monitor_page.refresh_windows,
            "",
            (28, 440),
            (150, 34),
            p,
        )?;
        button(
            &mut self.monitor_page.select_all,
            "",
            (188, 440),
            (120, 34),
            p,
        )?;
        button(&mut self.monitor_page.clear, "", (318, 440), (120, 34), p)?;
        label(
            &mut self.monitor_page.hint,
            "",
            (28, 492),
            (730, 44),
            p,
            None,
            MUTED,
        )?;
        Ok(())
    }

    fn build_layout_page(&mut self) -> Result<(), nwg::NwgError> {
        frame(&mut self.layout_page.frame, &self.window)?;
        let p = &self.layout_page.frame;
        label(
            &mut self.layout_page.title,
            "",
            (28, 22),
            (500, 32),
            p,
            Some(&self.page_font),
            TEXT,
        )?;
        label(
            &mut self.layout_page.description,
            "",
            (28, 54),
            (700, 24),
            p,
            None,
            MUTED,
        )?;
        label(
            &mut self.layout_page.kind_label,
            "",
            (28, 108),
            (220, 24),
            p,
            None,
            TEXT,
        )?;
        nwg::ComboBox::builder()
            .position((28, 138))
            .size((500, 34))
            .selected_index(Some(layout_index(self.settings.layout_mode)))
            .parent(p)
            .build(&mut self.layout_page.kind_combo)?;
        button(
            &mut self.layout_page.regenerate,
            "",
            (540, 138),
            (160, 34),
            p,
        )?;
        button(&mut self.layout_page.edit, "", (28, 210), (672, 44), p)?;
        label(
            &mut self.layout_page.help,
            "",
            (28, 282),
            (700, 120),
            p,
            None,
            MUTED,
        )?;
        Ok(())
    }

    fn build_filter_page(&mut self) -> Result<(), nwg::NwgError> {
        frame(&mut self.filter_page.frame, &self.window)?;
        let p = &self.filter_page.frame;
        label(
            &mut self.filter_page.title,
            "",
            (28, 22),
            (500, 32),
            p,
            Some(&self.page_font),
            TEXT,
        )?;
        label(
            &mut self.filter_page.description,
            "",
            (28, 54),
            (700, 24),
            p,
            None,
            MUTED,
        )?;
        label(
            &mut self.filter_page.kind_label,
            "",
            (28, 92),
            (220, 24),
            p,
            None,
            TEXT,
        )?;
        nwg::ComboBox::builder()
            .position((260, 88))
            .size((438, 34))
            .selected_index(Some(filter_index(self.settings.filter_style)))
            .parent(p)
            .build(&mut self.filter_page.kind_combo)?;
        slider_row(
            &mut self.filter_page.brightness_label,
            &mut self.filter_page.brightness_value,
            &mut self.filter_page.brightness,
            142,
            10..101,
            (self.settings.brightness * 100.0) as usize,
            p,
        )?;
        label(
            &mut self.filter_page.color_label,
            "",
            (28, 202),
            (220, 24),
            p,
            None,
            TEXT,
        )?;
        button(
            &mut self.filter_page.choose_color,
            "",
            (260, 198),
            (438, 34),
            p,
        )?;
        slider_row(
            &mut self.filter_page.hue_label,
            &mut self.filter_page.hue_value,
            &mut self.filter_page.hue,
            252,
            10..601,
            self.settings.hue_cycle_seconds as usize,
            p,
        )?;
        slider_row(
            &mut self.filter_page.edge_threshold_label,
            &mut self.filter_page.edge_threshold_value,
            &mut self.filter_page.edge_threshold,
            312,
            4..121,
            self.settings.edge_threshold as usize,
            p,
        )?;
        slider_row(
            &mut self.filter_page.edge_width_label,
            &mut self.filter_page.edge_width_value,
            &mut self.filter_page.edge_width,
            372,
            1..5,
            self.settings.edge_thickness as usize,
            p,
        )?;
        label(
            &mut self.filter_page.explanation,
            "",
            (28, 438),
            (700, 92),
            p,
            None,
            MUTED,
        )?;
        Ok(())
    }

    fn build_protection_page(&mut self) -> Result<(), nwg::NwgError> {
        frame(&mut self.protection_page.frame, &self.window)?;
        let p = &self.protection_page.frame;
        label(
            &mut self.protection_page.title,
            "",
            (28, 22),
            (500, 32),
            p,
            Some(&self.page_font),
            TEXT,
        )?;
        label(
            &mut self.protection_page.description,
            "",
            (28, 54),
            (700, 24),
            p,
            None,
            MUTED,
        )?;
        slider_row(
            &mut self.protection_page.scale_label,
            &mut self.protection_page.scale_value,
            &mut self.protection_page.scale,
            90,
            20..91,
            (self.settings.preview_scale * 100.0) as usize,
            p,
        )?;
        slider_row(
            &mut self.protection_page.drift_label,
            &mut self.protection_page.drift_value,
            &mut self.protection_page.drift,
            150,
            30..901,
            self.settings.move_seconds as usize,
            p,
        )?;
        slider_row(
            &mut self.protection_page.variation_label,
            &mut self.protection_page.variation_value,
            &mut self.protection_page.variation,
            210,
            0..11,
            (self.settings.size_variation * 100.0) as usize,
            p,
        )?;
        slider_row(
            &mut self.protection_page.blank_interval_label,
            &mut self.protection_page.blank_interval_value,
            &mut self.protection_page.blank_interval,
            270,
            0..241,
            self.settings.blank_every_minutes as usize,
            p,
        )?;
        slider_row(
            &mut self.protection_page.blank_duration_label,
            &mut self.protection_page.blank_duration_value,
            &mut self.protection_page.blank_duration,
            330,
            5..301,
            self.settings.blank_seconds as usize,
            p,
        )?;
        slider_row(
            &mut self.protection_page.fps_label,
            &mut self.protection_page.fps_value,
            &mut self.protection_page.fps,
            390,
            5..31,
            self.settings.capture_fps as usize,
            p,
        )?;
        nwg::CheckBox::builder()
            .text("")
            .position((28, 458))
            .size((670, 30))
            .background_color(Some(BG))
            .parent(p)
            .build(&mut self.protection_page.resolution_limit)?;
        self.protection_page.resolution_limit.set_check_state(
            if self.settings.limit_capture_resolution {
                nwg::CheckBoxState::Checked
            } else {
                nwg::CheckBoxState::Unchecked
            },
        );
        label(
            &mut self.protection_page.resolution_tip,
            "",
            (52, 493),
            (646, 46),
            p,
            None,
            MUTED,
        )?;
        Ok(())
    }

    fn bind_events(app: &Rc<RefCell<Self>>) -> Result<(), nwg::NwgError> {
        let weak: Weak<RefCell<Self>> = Rc::downgrade(app);
        let window_handle = app.borrow().window.handle;
        let handler = nwg::full_bind_event_handler(&window_handle, move |event, _, handle| {
            let Some(app) = weak.upgrade() else {
                return;
            };
            let Ok(mut app) = app.try_borrow_mut() else {
                return;
            };
            app.handle_event(event, handle);
        });
        app.borrow_mut().event_handler = Some(handler);
        let weak: Weak<RefCell<Self>> = Rc::downgrade(app);
        let background_brush = unsafe { CreateSolidBrush(0x001c1c1c) } as isize;
        let raw = nwg::bind_raw_event_handler(&window_handle, 0x1_5343, move |hwnd, msg, w, _| {
            if msg == WM_HOTKEY && w == platform::HOTKEY_ID as usize {
                if let Some(app) = weak.upgrade() {
                    if let Ok(mut app) = app.try_borrow_mut() {
                        app.toggle_layout_edit();
                    }
                }
            } else if msg == WM_ERASEBKGND {
                let mut rect = RECT {
                    left: 0,
                    top: 0,
                    right: 0,
                    bottom: 0,
                };
                unsafe {
                    GetClientRect(hwnd, &mut rect);
                    FillRect(w as _, &rect, background_brush as _);
                }
                return Some(1);
            } else if matches!(
                msg,
                WM_CTLCOLORSTATIC
                    | WM_CTLCOLORBTN
                    | WM_CTLCOLORDLG
                    | WM_CTLCOLOREDIT
                    | WM_CTLCOLORLISTBOX
            ) {
                unsafe {
                    SetBkColor(w as _, 0x001c1c1c);
                    SetTextColor(w as _, 0x00f5f5f5);
                }
                return Some(background_brush);
            }
            None
        })?;
        app.borrow_mut().raw_handler = Some(raw);
        let frame_handles = {
            let app = app.borrow();
            [
                app.monitor_page.frame.handle,
                app.layout_page.frame.handle,
                app.filter_page.frame.handle,
                app.protection_page.frame.handle,
            ]
        };
        for (index, handle) in frame_handles.into_iter().enumerate() {
            let handler = bind_dark_container(&handle, 0x1_5400 + index)?;
            app.borrow_mut().color_handlers.push(handler);
        }
        Ok(())
    }

    fn handle_event(&mut self, event: nwg::Event, handle: nwg::ControlHandle) {
        if event == nwg::Event::OnWindowClose && handle == self.window.handle {
            self.window.set_visible(false);
            self.tray.show(
                &self.t("tray.still_running_body"),
                Some(&self.t("tray.still_running_title")),
                Some(nwg::TrayNotificationFlags::INFO_ICON),
                None,
            );
        } else if event == nwg::Event::OnContextMenu && handle == self.tray.handle {
            let (x, y) = nwg::GlobalCursor::position();
            self.tray_menu.popup(x, y);
        } else if event == nwg::Event::OnMousePress(nwg::MousePressEvent::MousePressLeftUp)
            && handle == self.tray.handle
        {
            self.show_main();
        } else if event == nwg::Event::OnMenuItemSelected {
            if handle == self.tray_show.handle {
                self.show_main();
            } else if handle == self.tray_pause.handle {
                self.toggle_pause();
            } else if handle == self.tray_quit.handle {
                self.shutdown();
                nwg::stop_thread_dispatch();
            }
        } else if event == nwg::Event::OnButtonClick {
            if handle == self.nav_monitor.handle {
                self.show_page(0);
            } else if handle == self.nav_layout.handle {
                self.show_page(1);
            } else if handle == self.nav_filters.handle {
                self.show_page(2);
            } else if handle == self.nav_protection.handle {
                self.show_page(3);
            } else if handle == self.monitor_page.refresh_monitors.handle {
                self.refresh_monitors();
            } else if handle == self.monitor_page.refresh_windows.handle {
                let s = self.selected_handles();
                self.refresh_windows(s);
            } else if handle == self.monitor_page.select_all.handle {
                self.monitor_page.windows_list.select_all();
                self.windows_changed();
            } else if handle == self.monitor_page.clear.handle {
                self.monitor_page.windows_list.unselect_all();
                self.windows_changed();
            } else if handle == self.layout_page.regenerate.handle {
                self.regenerate_layout(false);
            } else if handle == self.layout_page.edit.handle {
                self.toggle_layout_edit();
            } else if handle == self.filter_page.choose_color.handle {
                self.choose_color();
            } else if handle == self.start_stop.handle {
                if self.active {
                    self.stop();
                } else {
                    self.start();
                }
            } else if handle == self.pause_resume.handle {
                self.toggle_pause();
            } else if handle == self.protection_page.resolution_limit.handle {
                self.controls_changed(false);
            }
        } else if event == nwg::Event::OnComboxBoxSelection {
            if handle == self.language.handle {
                self.language_changed();
            } else if handle == self.monitor_page.monitor_combo.handle {
                self.monitor_changed();
            } else if handle == self.layout_page.kind_combo.handle {
                self.layout_changed();
            } else if handle == self.filter_page.kind_combo.handle {
                self.controls_changed(false);
            }
        } else if event == nwg::Event::OnListBoxSelect
            && handle == self.monitor_page.windows_list.handle
        {
            self.windows_changed();
        } else if event == nwg::Event::OnHorizontalScroll {
            self.controls_changed(handle == self.protection_page.fps.handle);
        } else if event == nwg::Event::OnTimerTick && handle == self.timer.handle {
            self.tick();
        }
    }

    fn start(&mut self) {
        let Some(monitor) = self.selected_monitor().cloned() else {
            nwg::error_message(
                "SideScreenUtil",
                if self.is_zh() {
                    "没有可用的目标显示器"
                } else {
                    "No target display is available"
                },
            );
            return;
        };
        self.pull_settings();
        self.active = true;
        self.paused = false;
        self.synchronize_captures(true);
        self.regenerate_layout(true);
        self.overlay
            .borrow_mut()
            .activate(monitor, self.settings.clone());
        self.update_state();
    }

    fn stop(&mut self) {
        self.overlay.borrow_mut().deactivate();
        capture::stop_all(&mut self.captures);
        self.shared.clear();
        self.active = false;
        self.paused = false;
        self.update_state();
        let _ = settings::save(&self.settings);
    }

    fn toggle_pause(&mut self) {
        if !self.active {
            return;
        }
        self.paused = !self.paused;
        if self.paused {
            self.overlay.borrow_mut().deactivate();
        } else if let Some(monitor) = self.selected_monitor().cloned() {
            self.overlay
                .borrow_mut()
                .activate(monitor, self.settings.clone());
        }
        self.update_state();
    }

    fn synchronize_captures(&mut self, force_restart: bool) {
        if !self.active {
            return;
        }
        let selected: Vec<isize> = self.selected_handles().into_iter().collect();
        if force_restart {
            capture::stop_all(&mut self.captures);
        }
        let wanted: HashSet<isize> = selected.iter().copied().collect();
        let removed: Vec<isize> = self
            .captures
            .keys()
            .filter(|hwnd| !wanted.contains(hwnd))
            .copied()
            .collect();
        for hwnd in removed {
            if let Some(control) = self.captures.remove(&hwnd) {
                let _ = control.stop();
            }
        }
        for hwnd in &selected {
            if !self.captures.contains_key(hwnd) {
                match capture::start(*hwnd, self.shared.clone(), self.settings.capture_fps) {
                    Ok(control) => {
                        self.captures.insert(*hwnd, control);
                    }
                    Err(error) => self.status.set_text(&format!("Capture failed: {error}")),
                }
            }
        }
        self.shared.retain_frames(&selected);
        self.regenerate_layout(true);
    }

    fn regenerate_layout(&mut self, preserve_manual: bool) {
        let handles: Vec<isize> = self.selected_handles().into_iter().collect();
        let chosen: Vec<WindowInfo> = handles
            .iter()
            .filter_map(|hwnd| {
                self.windows
                    .iter()
                    .find(|window| window.hwnd == *hwnd)
                    .cloned()
            })
            .collect();
        let result = match self.settings.layout_mode {
            LayoutMode::Source => layout::source_relative(&chosen),
            LayoutMode::Grid => layout::grid(&handles),
            LayoutMode::Horizontal => layout::strip(&handles, false),
            LayoutMode::Vertical => layout::strip(&handles, true),
            LayoutMode::Manual if preserve_manual => {
                let current = self.overlay.borrow().layout();
                let fallback = layout::grid(&handles);
                handles
                    .iter()
                    .map(|hwnd| {
                        (
                            *hwnd,
                            current
                                .get(hwnd)
                                .or_else(|| fallback.get(hwnd))
                                .copied()
                                .unwrap_or(RectF {
                                    x: 0.1,
                                    y: 0.1,
                                    width: 0.8,
                                    height: 0.8,
                                }),
                        )
                    })
                    .collect()
            }
            LayoutMode::Manual => layout::grid(&handles),
        };
        let titles = chosen
            .into_iter()
            .map(|window| (window.hwnd, window.title))
            .collect();
        let mut overlay = self.overlay.borrow_mut();
        overlay.set_layout(result);
        overlay.set_titles(titles);
    }

    fn windows_changed(&mut self) {
        self.pull_settings();
        self.synchronize_captures(false);
        self.update_state();
    }
    fn monitor_changed(&mut self) {
        self.pull_settings();
        if self.active && !self.paused {
            if let Some(monitor) = self.selected_monitor().cloned() {
                self.overlay
                    .borrow_mut()
                    .activate(monitor, self.settings.clone());
            }
        }
        let _ = settings::save(&self.settings);
    }
    fn layout_changed(&mut self) {
        self.settings.layout_mode =
            layout_from_index(self.layout_page.kind_combo.selection().unwrap_or(0));
        self.regenerate_layout(false);
        let _ = settings::save(&self.settings);
    }
    fn controls_changed(&mut self, restart_capture: bool) {
        self.pull_settings();
        self.shared.update_settings(self.settings.clone());
        self.overlay
            .borrow_mut()
            .set_settings(self.settings.clone());
        if restart_capture {
            self.synchronize_captures(true);
        }
        self.update_value_labels();
        let _ = settings::save(&self.settings);
    }

    fn pull_settings(&mut self) {
        self.settings.monitor_device = self
            .selected_monitor()
            .map(|m| m.device.clone())
            .unwrap_or_default();
        self.settings.layout_mode =
            layout_from_index(self.layout_page.kind_combo.selection().unwrap_or(0));
        self.settings.filter_style =
            filter_from_index(self.filter_page.kind_combo.selection().unwrap_or(0));
        self.settings.brightness = self.filter_page.brightness.pos() as f32 / 100.0;
        self.settings.hue_cycle_seconds = self.filter_page.hue.pos() as u32;
        self.settings.edge_threshold = self.filter_page.edge_threshold.pos() as u8;
        self.settings.edge_thickness = self.filter_page.edge_width.pos() as u8;
        self.settings.preview_scale = self.protection_page.scale.pos() as f32 / 100.0;
        self.settings.move_seconds = self.protection_page.drift.pos() as u32;
        self.settings.size_variation = self.protection_page.variation.pos() as f32 / 100.0;
        self.settings.blank_every_minutes = self.protection_page.blank_interval.pos() as u32;
        self.settings.blank_seconds = self.protection_page.blank_duration.pos() as u32;
        self.settings.capture_fps = self.protection_page.fps.pos() as u32;
        self.settings.limit_capture_resolution =
            self.protection_page.resolution_limit.check_state() == nwg::CheckBoxState::Checked;
        self.settings.normalize();
    }

    fn choose_color(&mut self) {
        if self.color_dialog.run(Some(&self.window)) {
            let [r, g, b] = self.color_dialog.color();
            self.settings.accent_color = ((r as u32) << 16) | ((g as u32) << 8) | b as u32;
            self.controls_changed(false);
        }
    }

    fn toggle_layout_edit(&mut self) {
        let editing = self.overlay.borrow_mut().toggle_editing();
        if editing {
            self.state.set_text(&self.t("state.editing"));
            self.layout_page.edit.set_text(&self.t("layout.finish"));
        } else {
            if self.active && !self.overlay.borrow().layout().is_empty() {
                self.settings.layout_mode = LayoutMode::Manual;
                self.layout_page
                    .kind_combo
                    .set_selection(Some(layout_index(LayoutMode::Manual)));
            }
            self.layout_page.edit.set_text(&self.t("layout.edit"));
            self.update_state();
        }
    }

    fn tick(&mut self) {
        self.overlay.borrow_mut().tick();
        let closed: Vec<isize> = self
            .shared
            .closed_windows
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .drain(..)
            .collect();
        if !closed.is_empty() {
            let closed: HashSet<isize> = closed.into_iter().collect();
            let selected: HashSet<isize> = self
                .selected_handles()
                .difference(&closed)
                .copied()
                .collect();
            self.refresh_windows(selected);
            self.synchronize_captures(false);
        }
    }

    fn selected_monitor(&self) -> Option<&MonitorInfo> {
        self.monitor_page
            .monitor_combo
            .selection()
            .and_then(|index| self.monitors.get(index))
    }
    fn selected_handles(&self) -> HashSet<isize> {
        self.monitor_page
            .windows_list
            .multi_selection()
            .into_iter()
            .filter_map(|index| self.windows.get(index).map(|window| window.hwnd))
            .collect()
    }

    fn refresh_monitors(&mut self) {
        let previous = self.settings.monitor_device.clone();
        self.monitors = platform::enumerate_monitors();
        let zh = self.is_zh();
        let items = self
            .monitors
            .iter()
            .enumerate()
            .map(|(index, monitor)| {
                let primary = if monitor.primary {
                    if zh { " · 主屏" } else { " · Primary" }
                } else {
                    ""
                };
                format!(
                    "{}. {} — {}×{} ({}, {}){}",
                    index + 1,
                    monitor.name,
                    monitor.width(),
                    monitor.height(),
                    monitor.rect[0],
                    monitor.rect[1],
                    primary
                )
            })
            .collect();
        self.monitor_page.monitor_combo.set_collection(items);
        let selected = self
            .monitors
            .iter()
            .position(|m| m.device == previous)
            .or_else(|| self.monitors.iter().position(|m| !m.primary))
            .or(if self.monitors.is_empty() {
                None
            } else {
                Some(0)
            });
        self.monitor_page.monitor_combo.set_selection(selected);
        if let Some(monitor) = selected.and_then(|index| self.monitors.get(index)) {
            self.settings.monitor_device = monitor.device.clone();
        }
    }

    fn refresh_windows(&mut self, selected: HashSet<isize>) {
        self.windows = platform::enumerate_windows();
        self.monitor_page
            .windows_list
            .set_collection(self.windows.iter().map(WindowInfo::display_name).collect());
        for (index, window) in self.windows.iter().enumerate() {
            if selected.contains(&window.hwnd) {
                self.monitor_page.windows_list.multi_add_selection(index);
            }
        }
    }

    fn language_changed(&mut self) {
        self.translations
            .select(self.language.selection().unwrap_or(0));
        self.settings.language = self.translations.language_code().to_owned();
        let selected = self.selected_handles();
        self.apply_language();
        self.refresh_monitors();
        self.refresh_windows(selected);
        self.update_state();
        self.update_value_labels();
        let _ = settings::save(&self.settings);
    }

    fn apply_language(&mut self) {
        self.window.set_text(&self.t("app.window_title"));
        self.subtitle.set_text(&self.t("app.subtitle"));
        self.language_label.set_text(&self.t("header.language"));
        self.nav_monitor.set_text(&self.t("tabs.monitor"));
        self.nav_layout.set_text(&self.t("tabs.layout"));
        self.nav_filters.set_text(&self.t("tabs.filters"));
        self.nav_protection.set_text(&self.t("tabs.protection"));
        self.monitor_page.title.set_text(&self.t("source.section"));
        self.monitor_page
            .description
            .set_text(&self.t("page.monitor_description"));
        self.monitor_page
            .monitor_label
            .set_text(&self.t("source.target_display"));
        self.monitor_page
            .refresh_monitors
            .set_text(&self.t("common.refresh"));
        self.monitor_page
            .windows_label
            .set_text(&self.t("source.windows"));
        self.monitor_page
            .refresh_windows
            .set_text(&self.t("source.refresh_windows"));
        self.monitor_page
            .select_all
            .set_text(&self.t("source.select_all"));
        self.monitor_page.clear.set_text(&self.t("source.clear"));
        self.monitor_page.hint.set_text(&self.t("source.hint"));
        self.layout_page.title.set_text(&self.t("tabs.layout"));
        self.layout_page
            .description
            .set_text(&self.t("page.layout_description"));
        self.layout_page.kind_label.set_text(&self.t("layout.type"));
        self.layout_page.kind_combo.set_collection(vec![
            self.t("layout.source"),
            self.t("layout.grid"),
            self.t("layout.horizontal"),
            self.t("layout.vertical"),
            self.t("layout.manual"),
        ]);
        self.layout_page
            .kind_combo
            .set_selection(Some(layout_index(self.settings.layout_mode)));
        self.layout_page
            .regenerate
            .set_text(&self.t("layout.regenerate"));
        self.layout_page.edit.set_text(&self.t("layout.edit"));
        self.layout_page.help.set_text(&self.t("layout.help"));
        self.filter_page.title.set_text(&self.t("tabs.filters"));
        self.filter_page
            .description
            .set_text(&self.t("page.filters_description"));
        self.filter_page
            .kind_label
            .set_text(&self.t("filter.visual"));
        self.filter_page.kind_combo.set_collection(vec![
            self.t("filter.original"),
            self.t("filter.grayscale"),
            self.t("filter.mono"),
            self.t("filter.mono_cycle"),
            self.t("filter.edge"),
            self.t("filter.edge_cycle"),
        ]);
        self.filter_page
            .kind_combo
            .set_selection(Some(filter_index(self.settings.filter_style)));
        self.filter_page
            .brightness_label
            .set_text(&self.t("filter.brightness"));
        self.filter_page
            .color_label
            .set_text(&self.t("filter.fixed_color"));
        self.filter_page
            .choose_color
            .set_text(&self.t("filter.choose_color"));
        self.filter_page
            .hue_label
            .set_text(&self.t("filter.hue_speed"));
        self.filter_page
            .edge_threshold_label
            .set_text(&self.t("filter.edge_sensitivity"));
        self.filter_page
            .edge_width_label
            .set_text(&self.t("filter.edge_width"));
        self.filter_page.explanation.set_text(&format!(
            "{}\r\n{}",
            self.t("filter.edge_tip"),
            self.t("filter.explanation")
        ));
        self.protection_page
            .title
            .set_text(&self.t("tabs.protection"));
        self.protection_page
            .description
            .set_text(&self.t("page.protection_description"));
        self.protection_page
            .scale_label
            .set_text(&self.t("protection.canvas_size"));
        self.protection_page
            .drift_label
            .set_text(&self.t("protection.drift_speed"));
        self.protection_page
            .variation_label
            .set_text(&self.t("protection.size_variation"));
        self.protection_page
            .blank_interval_label
            .set_text(&self.t("protection.blank_interval"));
        self.protection_page
            .blank_duration_label
            .set_text(&self.t("protection.blank_duration"));
        self.protection_page
            .fps_label
            .set_text(&self.t("protection.fps"));
        self.protection_page
            .resolution_limit
            .set_text(&self.t("protection.resolution_limit"));
        self.protection_page
            .resolution_tip
            .set_text(&self.t("protection.resolution_tip"));
        set_menu_text(&self.tray_show, &self.t("tray.show"));
        set_menu_text(
            &self.tray_pause,
            &self.t(if self.paused {
                "tray.resume"
            } else {
                "tray.pause"
            }),
        );
        set_menu_text(&self.tray_quit, &self.t("tray.quit"));
        self.update_state();
    }

    fn update_state(&self) {
        if !self.active {
            self.state.set_text(&self.t("state.idle"));
            self.start_stop.set_text(&self.t("action.start"));
            self.pause_resume.set_text(&self.t("action.pause"));
            self.pause_resume.set_enabled(false);
            set_menu_text(&self.tray_pause, &self.t("tray.pause"));
            self.tray_pause.set_enabled(false);
            self.status.set_text(&self.t("status.ready"));
        } else {
            let count = self.selected_handles().len();
            let state = if self.paused {
                self.t("state.paused")
            } else if count == 0 {
                self.t("state.black_only")
            } else {
                self.t("state.running")
                    .replace("{count}", &count.to_string())
            };
            self.state.set_text(&state);
            self.start_stop.set_text(&self.t("action.stop"));
            self.pause_resume.set_text(&self.t(if self.paused {
                "common.resume"
            } else {
                "common.pause"
            }));
            self.pause_resume.set_enabled(true);
            set_menu_text(
                &self.tray_pause,
                &self.t(if self.paused {
                    "tray.resume"
                } else {
                    "tray.pause"
                }),
            );
            self.tray_pause.set_enabled(true);
            self.status.set_text(if self.is_zh() {
                "运行中 · 鼠标移入目标屏幕会立即显示原桌面"
            } else {
                "Active · Move the pointer onto the target display to reveal the desktop"
            });
        }
    }

    fn update_value_labels(&self) {
        self.filter_page
            .brightness_value
            .set_text(&format!("{}%", self.filter_page.brightness.pos()));
        self.filter_page
            .hue_value
            .set_text(&format!("{} s", self.filter_page.hue.pos()));
        self.filter_page
            .edge_threshold_value
            .set_text(&self.filter_page.edge_threshold.pos().to_string());
        self.filter_page
            .edge_width_value
            .set_text(&format!("{} px", self.filter_page.edge_width.pos()));
        self.protection_page
            .scale_value
            .set_text(&format!("{}%", self.protection_page.scale.pos()));
        self.protection_page
            .drift_value
            .set_text(&format!("{} s", self.protection_page.drift.pos()));
        self.protection_page
            .variation_value
            .set_text(&format!("{}%", self.protection_page.variation.pos()));
        self.protection_page.blank_interval_value.set_text(&format!(
            "{} min",
            self.protection_page.blank_interval.pos()
        ));
        self.protection_page
            .blank_duration_value
            .set_text(&format!("{} s", self.protection_page.blank_duration.pos()));
        self.protection_page
            .fps_value
            .set_text(&format!("{} FPS", self.protection_page.fps.pos()));
    }

    fn show_page(&mut self, page: usize) {
        self.page = page;
        self.monitor_page.frame.set_visible(page == 0);
        self.layout_page.frame.set_visible(page == 1);
        self.filter_page.frame.set_visible(page == 2);
        self.protection_page.frame.set_visible(page == 3);
    }
    fn apply_themes(&self) {
        for handle in [
            &self.language.handle,
            &self.monitor_page.monitor_combo.handle,
            &self.monitor_page.windows_list.handle,
            &self.layout_page.kind_combo.handle,
            &self.filter_page.kind_combo.handle,
            &self.start_stop.handle,
            &self.pause_resume.handle,
        ] {
            platform::apply_modern_theme(handle);
        }
    }
    fn is_zh(&self) -> bool {
        self.settings.language.starts_with("zh")
    }
    fn show_main(&self) {
        self.window.set_visible(true);
        platform::show_main_window(platform::hwnd(&self.window.handle));
    }
    fn shutdown(&mut self) {
        capture::stop_all(&mut self.captures);
        self.overlay.borrow_mut().deactivate();
        let _ = settings::save(&self.settings);
        unsafe {
            UnregisterHotKey(platform::hwnd(&self.window.handle), platform::HOTKEY_ID);
        }
    }
}

fn frame(out: &mut nwg::Frame, parent: &nwg::Window) -> Result<(), nwg::NwgError> {
    nwg::Frame::builder()
        .flags(nwg::FrameFlags::VISIBLE)
        .position((246, 104))
        .size((786, 550))
        .parent(parent)
        .build(out)
}
fn label<C: Into<nwg::ControlHandle> + Copy>(
    out: &mut nwg::Label,
    text: &str,
    position: (i32, i32),
    size: (i32, i32),
    parent: C,
    font: Option<&nwg::Font>,
    color: [u8; 3],
) -> Result<(), nwg::NwgError> {
    let mut builder = nwg::Label::builder()
        .text(text)
        .position(position)
        .size(size)
        .background_color(Some(BG))
        .parent(parent);
    if let Some(font) = font {
        builder = builder.font(Some(font));
    }
    builder.build(out)?;
    set_text_color(&out.handle, color);
    Ok(())
}
fn button<C: Into<nwg::ControlHandle> + Copy>(
    out: &mut nwg::Button,
    text: &str,
    position: (i32, i32),
    size: (i32, i32),
    parent: C,
) -> Result<(), nwg::NwgError> {
    nwg::Button::builder()
        .text(text)
        .position(position)
        .size(size)
        .parent(parent)
        .build(out)
}
fn slider_row<C: Into<nwg::ControlHandle> + Copy>(
    title: &mut nwg::Label,
    value: &mut nwg::Label,
    slider: &mut nwg::TrackBar,
    y: i32,
    range: std::ops::Range<usize>,
    position: usize,
    parent: C,
) -> Result<(), nwg::NwgError> {
    label(title, "", (28, y), (220, 24), parent, None, TEXT)?;
    label(value, "", (610, y), (88, 24), parent, None, MUTED)?;
    nwg::TrackBar::builder()
        .flags(
            nwg::TrackBarFlags::VISIBLE
                | nwg::TrackBarFlags::NO_TICK
                | nwg::TrackBarFlags::TAB_STOP,
        )
        .position((260, y - 4))
        .size((338, 30))
        .range(Some(range))
        .pos(Some(position))
        .background_color(Some(BG))
        .parent(parent)
        .build(slider)
}
fn set_text_color(_handle: &nwg::ControlHandle, _color: [u8; 3]) {}
fn bind_dark_container(
    handle: &nwg::ControlHandle,
    id: usize,
) -> Result<nwg::RawEventHandler, nwg::NwgError> {
    let background_brush = unsafe { CreateSolidBrush(0x001c1c1c) } as isize;
    nwg::bind_raw_event_handler(handle, id, move |hwnd, msg, w, _| {
        if msg == WM_ERASEBKGND {
            let mut rect = RECT {
                left: 0,
                top: 0,
                right: 0,
                bottom: 0,
            };
            unsafe {
                GetClientRect(hwnd, &mut rect);
                FillRect(w as _, &rect, background_brush as _);
            }
            return Some(1);
        }
        if matches!(
            msg,
            WM_CTLCOLORSTATIC
                | WM_CTLCOLORBTN
                | WM_CTLCOLORDLG
                | WM_CTLCOLOREDIT
                | WM_CTLCOLORLISTBOX
        ) {
            unsafe {
                SetBkColor(w as _, 0x001c1c1c);
                SetTextColor(w as _, 0x00f5f5f5);
            }
            return Some(background_brush);
        }
        None
    })
}
fn set_menu_text(item: &nwg::MenuItem, text: &str) {
    let Some((menu, id)) = item.handle.hmenu_item() else {
        return;
    };
    let wide: Vec<u16> = text.encode_utf16().chain(std::iter::once(0)).collect();
    unsafe {
        ModifyMenuW(
            menu,
            id,
            MF_BYCOMMAND | MF_STRING,
            id as usize,
            wide.as_ptr(),
        );
    }
}
fn layout_index(value: LayoutMode) -> usize {
    match value {
        LayoutMode::Source => 0,
        LayoutMode::Grid => 1,
        LayoutMode::Horizontal => 2,
        LayoutMode::Vertical => 3,
        LayoutMode::Manual => 4,
    }
}
fn layout_from_index(value: usize) -> LayoutMode {
    match value {
        1 => LayoutMode::Grid,
        2 => LayoutMode::Horizontal,
        3 => LayoutMode::Vertical,
        4 => LayoutMode::Manual,
        _ => LayoutMode::Source,
    }
}
fn filter_index(value: FilterStyle) -> usize {
    match value {
        FilterStyle::Original => 0,
        FilterStyle::Grayscale => 1,
        FilterStyle::Mono => 2,
        FilterStyle::MonoCycle => 3,
        FilterStyle::Edge => 4,
        FilterStyle::EdgeCycle => 5,
    }
}
fn filter_from_index(value: usize) -> FilterStyle {
    match value {
        1 => FilterStyle::Grayscale,
        2 => FilterStyle::Mono,
        3 => FilterStyle::MonoCycle,
        4 => FilterStyle::Edge,
        5 => FilterStyle::EdgeCycle,
        _ => FilterStyle::Original,
    }
}

pub fn run() -> Result<(), nwg::NwgError> {
    let _app = App::build()?;
    nwg::dispatch_thread_events();
    Ok(())
}

pub fn smoke_test() -> Result<(), String> {
    let original = settings::load();
    let app = App::build().map_err(|error| error.to_string())?;
    {
        let mut app = app.borrow_mut();
        app.window.set_visible(false);
        if app.monitors.is_empty() {
            return Err("No monitor was enumerated by the native UI".to_owned());
        }
        app.show_page(1);
        app.show_page(2);
        app.show_page(3);
        app.show_page(0);
        app.monitor_page.windows_list.unselect_all();
        app.start();
        if !app.active || !app.overlay.borrow().is_active() {
            return Err("Black-only secondary-screen mode did not activate".to_owned());
        }
        app.toggle_pause();
        if !app.paused {
            return Err("Pause transition failed".to_owned());
        }
        app.stop();
        app.shutdown();
    }
    settings::save(&original)?;
    Ok(())
}
