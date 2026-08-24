use std::cell::RefCell;
use std::collections::HashMap;
use std::f32::consts::TAU;
use std::mem::{size_of, zeroed};
use std::rc::{Rc, Weak};
use std::sync::Arc;
use std::time::Instant;

use native_windows_gui as nwg;
use winapi::shared::minwindef::DWORD;
use winapi::shared::windef::{HBITMAP, HBRUSH, HDC, HGDIOBJ, HWND, POINT, RECT};
use winapi::um::wingdi::{
    BI_RGB, BITMAPINFO, BITMAPINFOHEADER, BitBlt, CreateCompatibleBitmap, CreateCompatibleDC,
    CreatePen, CreateSolidBrush, DIB_RGB_COLORS, DeleteDC, DeleteObject, HALFTONE, PS_SOLID,
    Rectangle, SRCCOPY, SelectObject, SetBkMode, SetStretchBltMode, SetTextColor, StretchDIBits,
    TRANSPARENT,
};
use winapi::um::winuser::{
    DT_CENTER, DT_SINGLELINE, DT_VCENTER, DrawTextW, FillRect, GetClientRect, GetCursorPos,
    HWND_TOPMOST, InvalidateRect, ReleaseCapture, SWP_NOACTIVATE, SWP_SHOWWINDOW, ScreenToClient,
    SetCapture, SetWindowPos, WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW,
};

use crate::capture::SharedCaptureState;
use crate::model::{AppSettings, MonitorInfo, RectF};
use crate::platform;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum EditAction {
    None,
    Move,
    Resize,
}

#[derive(Default)]
struct BackBuffer {
    dc: HDC,
    bitmap: HBITMAP,
    previous: HGDIOBJ,
    width: i32,
    height: i32,
}

impl BackBuffer {
    fn prepare(&mut self, target: HDC, width: i32, height: i32) -> Option<HDC> {
        if width <= 0 || height <= 0 {
            return None;
        }
        if self.dc.is_null() || self.width != width || self.height != height {
            self.release();
            unsafe {
                self.dc = CreateCompatibleDC(target);
                if self.dc.is_null() {
                    return None;
                }
                self.bitmap = CreateCompatibleBitmap(target, width, height);
                if self.bitmap.is_null() {
                    DeleteDC(self.dc);
                    self.dc = std::ptr::null_mut();
                    return None;
                }
                self.previous = SelectObject(self.dc, self.bitmap as _);
            }
            self.width = width;
            self.height = height;
        }
        Some(self.dc)
    }

    fn release(&mut self) {
        unsafe {
            if !self.dc.is_null() {
                if !self.previous.is_null() {
                    SelectObject(self.dc, self.previous);
                }
                if !self.bitmap.is_null() {
                    DeleteObject(self.bitmap as _);
                }
                DeleteDC(self.dc);
            }
        }
        self.dc = std::ptr::null_mut();
        self.bitmap = std::ptr::null_mut();
        self.previous = std::ptr::null_mut();
        self.width = 0;
        self.height = 0;
    }
}

impl Drop for BackBuffer {
    fn drop(&mut self) {
        self.release();
    }
}

pub struct Overlay {
    pub window: nwg::Window,
    shared: Arc<SharedCaptureState>,
    settings: AppSettings,
    monitor: Option<MonitorInfo>,
    layout: HashMap<isize, RectF>,
    titles: HashMap<isize, String>,
    active: bool,
    pointer_suppressed: bool,
    editing: bool,
    selected: Option<isize>,
    edit_action: EditAction,
    drag_offset: [f32; 2],
    alpha: u8,
    target_alpha: u8,
    session_started: Instant,
    back_buffer: BackBuffer,
    event_handler: Option<nwg::EventHandler>,
}

impl Overlay {
    pub fn build(shared: Arc<SharedCaptureState>) -> Result<Rc<RefCell<Self>>, nwg::NwgError> {
        let mut window = nwg::Window::default();
        nwg::Window::builder()
            .size((800, 600))
            .position((0, 0))
            .title("SideScreenUtil Overlay")
            .flags(nwg::WindowFlags::POPUP)
            .ex_flags(WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_LAYERED)
            .topmost(true)
            .build(&mut window)?;
        let overlay = Rc::new(RefCell::new(Self {
            window,
            shared,
            settings: AppSettings::default(),
            monitor: None,
            layout: HashMap::new(),
            titles: HashMap::new(),
            active: false,
            pointer_suppressed: false,
            editing: false,
            selected: None,
            edit_action: EditAction::None,
            drag_offset: [0.0, 0.0],
            alpha: 0,
            target_alpha: 0,
            session_started: Instant::now(),
            back_buffer: BackBuffer::default(),
            event_handler: None,
        }));
        let weak: Weak<RefCell<Self>> = Rc::downgrade(&overlay);
        let handle = overlay.borrow().window.handle;
        let handler = nwg::full_bind_event_handler(&handle, move |event, data, event_handle| {
            let Some(overlay) = weak.upgrade() else {
                return;
            };
            let Ok(mut overlay) = overlay.try_borrow_mut() else {
                return;
            };
            if event_handle != overlay.window.handle {
                return;
            }
            match event {
                nwg::Event::OnPaint => overlay.paint(data.on_paint()),
                nwg::Event::OnMousePress(mouse) => overlay.mouse_press(mouse),
                nwg::Event::OnMouseMove => overlay.mouse_move(),
                _ => {}
            }
        });
        overlay.borrow_mut().event_handler = Some(handler);
        let hwnd = platform::hwnd(&overlay.borrow().window.handle);
        platform::configure_overlay(hwnd);
        Ok(overlay)
    }

    pub fn hwnd(&self) -> HWND {
        platform::hwnd(&self.window.handle)
    }

    pub fn activate(&mut self, monitor: MonitorInfo, settings: AppSettings) {
        self.monitor = Some(monitor.clone());
        self.settings = settings;
        self.session_started = Instant::now();
        self.active = true;
        self.pointer_suppressed = false;
        self.editing = false;
        self.alpha = 0;
        self.target_alpha = 255;
        unsafe {
            SetWindowPos(
                self.hwnd(),
                HWND_TOPMOST,
                monitor.rect[0],
                monitor.rect[1],
                monitor.width(),
                monitor.height(),
                SWP_NOACTIVATE | SWP_SHOWWINDOW,
            );
            InvalidateRect(self.hwnd(), std::ptr::null(), 0);
        }
        platform::set_overlay_alpha(self.hwnd(), 0);
    }

    pub fn deactivate(&mut self) {
        self.active = false;
        self.editing = false;
        self.pointer_suppressed = false;
        self.target_alpha = 0;
    }

    pub fn set_settings(&mut self, settings: AppSettings) {
        self.settings = settings;
        unsafe {
            InvalidateRect(self.hwnd(), std::ptr::null(), 0);
        }
    }

    pub fn set_layout(&mut self, layout: HashMap<isize, RectF>) {
        self.layout = layout
            .into_iter()
            .map(|(hwnd, rect)| (hwnd, rect.normalized()))
            .collect();
        unsafe {
            InvalidateRect(self.hwnd(), std::ptr::null(), 0);
        }
    }

    pub fn layout(&self) -> HashMap<isize, RectF> {
        self.layout.clone()
    }

    pub fn set_titles(&mut self, titles: HashMap<isize, String>) {
        self.titles = titles;
    }

    pub fn is_active(&self) -> bool {
        self.active
    }

    pub fn toggle_editing(&mut self) -> bool {
        if !self.active || self.layout.is_empty() {
            return false;
        }
        self.editing = !self.editing;
        self.selected = None;
        self.edit_action = EditAction::None;
        if self.editing && self.pointer_suppressed {
            self.reveal();
        }
        unsafe {
            InvalidateRect(self.hwnd(), std::ptr::null(), 0);
        }
        self.editing
    }

    pub fn tick(&mut self) {
        if self.alpha != self.target_alpha {
            let step = if self.target_alpha > self.alpha {
                24
            } else {
                32
            };
            self.alpha = if self.target_alpha > self.alpha {
                self.alpha.saturating_add(step).min(self.target_alpha)
            } else {
                self.alpha.saturating_sub(step).max(self.target_alpha)
            };
            platform::set_overlay_alpha(self.hwnd(), self.alpha);
            if self.alpha == 0 && (self.pointer_suppressed || !self.active) {
                platform::show_overlay(self.hwnd(), false);
            }
        }
        if !self.active || self.editing {
            return;
        }
        let Some(monitor) = &self.monitor else {
            return;
        };
        let inside = platform::point_in_rect(platform::cursor_position(), monitor.rect);
        if inside && !self.pointer_suppressed {
            self.pointer_suppressed = true;
            self.target_alpha = 0;
        } else if !inside && self.pointer_suppressed {
            self.reveal();
        }
        unsafe {
            InvalidateRect(self.hwnd(), std::ptr::null(), 0);
        }
    }

    fn reveal(&mut self) {
        self.pointer_suppressed = false;
        self.alpha = 0;
        self.target_alpha = 255;
        platform::show_overlay(self.hwnd(), true);
        platform::set_overlay_alpha(self.hwnd(), 0);
    }

    fn periodic_blank(&self) -> bool {
        let every = self.settings.blank_every_minutes * 60;
        if every == 0 || self.settings.blank_seconds == 0 {
            return false;
        }
        let elapsed = self.session_started.elapsed().as_secs() as u32;
        elapsed % (every + self.settings.blank_seconds) >= every
    }

    fn composition_rect(&self, width: i32, height: i32) -> [f32; 4] {
        let margin = (width.min(height) as f32 * 0.035).max(16.0);
        let available_width = (width as f32 - margin * 2.0).max(1.0);
        let available_height = (height as f32 - margin * 2.0).max(1.0);
        let elapsed = self.session_started.elapsed().as_secs_f32();
        let phase = elapsed / self.settings.move_seconds.max(30) as f32 * TAU;
        let motion_x = 0.5 + 0.5 * phase.sin();
        let motion_y = 0.5 + 0.5 * (phase * 0.73 + 1.2).sin();
        let scale_variation = 1.0 + self.settings.size_variation * (phase * 0.41).sin();
        let scale = (self.settings.preview_scale * scale_variation).clamp(0.18, 0.94);
        let content_width = available_width * scale;
        let content_height = available_height * scale;
        [
            margin + (available_width - content_width) * motion_x,
            margin + (available_height - content_height) * motion_y,
            content_width,
            content_height,
        ]
    }

    fn cell_rect(composition: [f32; 4], rect: RectF) -> [i32; 4] {
        let left = composition[0] + rect.x * composition[2];
        let top = composition[1] + rect.y * composition[3];
        [
            left.round() as i32,
            top.round() as i32,
            (left + rect.width * composition[2]).round() as i32,
            (top + rect.height * composition[3]).round() as i32,
        ]
    }

    fn paint(&mut self, paint_data: &nwg::PaintData) {
        let paint = paint_data.begin_paint();
        let target_dc = paint.hdc;
        let mut client = RECT {
            left: 0,
            top: 0,
            right: 1,
            bottom: 1,
        };
        unsafe {
            GetClientRect(self.hwnd(), &mut client);
        }
        let width = client.right.max(1);
        let height = client.bottom.max(1);
        let dc = self
            .back_buffer
            .prepare(target_dc, width, height)
            .unwrap_or(target_dc);
        unsafe {
            let black = CreateSolidBrush(0);
            FillRect(dc, &client, black);
            DeleteObject(black as _);
        }
        if !self.periodic_blank() || self.editing {
            let composition = self.composition_rect(client.right, client.bottom);
            let frames: HashMap<_, _> = self
                .shared
                .frames
                .lock()
                .unwrap_or_else(|error| error.into_inner())
                .iter()
                .map(|(hwnd, frame)| (*hwnd, frame.clone()))
                .collect();
            unsafe {
                SetStretchBltMode(dc, HALFTONE);
            }
            for (hwnd, normalized) in &self.layout {
                let Some(frame) = frames.get(hwnd) else {
                    continue;
                };
                let cell = Self::cell_rect(composition, *normalized);
                let destination = fit_frame(cell, frame.width, frame.height);
                let bitmap_info = bitmap_info(frame.width, frame.height);
                unsafe {
                    StretchDIBits(
                        dc,
                        destination[0],
                        destination[1],
                        destination[2] - destination[0],
                        destination[3] - destination[1],
                        0,
                        0,
                        frame.width as i32,
                        frame.height as i32,
                        frame.pixels.as_ptr() as _,
                        &bitmap_info,
                        DIB_RGB_COLORS,
                        winapi::um::wingdi::SRCCOPY,
                    );
                }
                if self.editing {
                    self.paint_edit_frame(dc, *hwnd, cell);
                }
            }
            if self.editing {
                self.paint_banner(dc, client.right);
            }
        }
        if dc != target_dc {
            unsafe {
                BitBlt(target_dc, 0, 0, width, height, dc, 0, 0, SRCCOPY);
            }
        }
        paint_data.end_paint(&paint);
    }

    fn paint_edit_frame(&self, dc: winapi::shared::windef::HDC, hwnd: isize, cell: [i32; 4]) {
        let selected = self.selected == Some(hwnd);
        let color = if selected { 0x00ffffff } else { 0x00b0b0b0 };
        unsafe {
            let pen = CreatePen(PS_SOLID as i32, if selected { 3 } else { 1 }, color);
            let old_pen = SelectObject(dc, pen as _);
            let hollow =
                winapi::um::wingdi::GetStockObject(winapi::um::wingdi::HOLLOW_BRUSH as i32);
            let old_brush = SelectObject(dc, hollow);
            Rectangle(dc, cell[0], cell[1], cell[2], cell[3]);
            SelectObject(dc, old_brush);
            SelectObject(dc, old_pen);
            DeleteObject(pen as _);
            let handle = CreateSolidBrush(0x00ffffff);
            let grip = RECT {
                left: cell[2] - 15,
                top: cell[3] - 15,
                right: cell[2] - 2,
                bottom: cell[3] - 2,
            };
            FillRect(dc, &grip, handle);
            DeleteObject(handle as _);
        }
    }

    fn paint_banner(&self, dc: winapi::shared::windef::HDC, width: i32) {
        let mut banner = RECT {
            left: (width / 2 - 285).max(18),
            top: 18,
            right: (width / 2 + 285).min(width - 18),
            bottom: 62,
        };
        unsafe {
            let brush: HBRUSH = CreateSolidBrush(0x00202020);
            FillRect(dc, &banner, brush);
            DeleteObject(brush as _);
            SetBkMode(dc, TRANSPARENT as i32);
            SetTextColor(dc, 0x00ffffff);
            let text = wide("EDIT LAYOUT  ·  Drag / resize bottom-right  ·  Ctrl+Alt+L to save");
            DrawTextW(
                dc,
                text.as_ptr(),
                -1,
                &mut banner,
                DT_CENTER | DT_VCENTER | DT_SINGLELINE,
            );
        }
    }

    fn mouse_press(&mut self, event: nwg::MousePressEvent) {
        if !self.editing {
            return;
        }
        match event {
            nwg::MousePressEvent::MousePressLeftDown => self.begin_drag(),
            nwg::MousePressEvent::MousePressLeftUp => {
                self.edit_action = EditAction::None;
                unsafe {
                    ReleaseCapture();
                }
            }
            _ => {}
        }
    }

    fn begin_drag(&mut self) {
        let Some((point, composition)) = self.pointer_in_composition() else {
            return;
        };
        self.selected = None;
        for (hwnd, rect) in &self.layout {
            let cell = Self::cell_rect(composition, *rect);
            if point[0] >= cell[0] - 3
                && point[0] <= cell[2] + 3
                && point[1] >= cell[1] - 3
                && point[1] <= cell[3] + 3
            {
                self.selected = Some(*hwnd);
                self.edit_action = if point[0] >= cell[2] - 24 && point[1] >= cell[3] - 24 {
                    EditAction::Resize
                } else {
                    EditAction::Move
                };
                let nx = (point[0] as f32 - composition[0]) / composition[2];
                let ny = (point[1] as f32 - composition[1]) / composition[3];
                self.drag_offset = [nx - rect.x, ny - rect.y];
                unsafe {
                    SetCapture(self.hwnd());
                }
                break;
            }
        }
    }

    fn mouse_move(&mut self) {
        if !self.editing || self.edit_action == EditAction::None {
            return;
        }
        let Some(selected) = self.selected else {
            return;
        };
        let Some((point, composition)) = self.pointer_in_composition() else {
            return;
        };
        let nx = (point[0] as f32 - composition[0]) / composition[2];
        let ny = (point[1] as f32 - composition[1]) / composition[3];
        let Some(rect) = self.layout.get(&selected).copied() else {
            return;
        };
        let updated = match self.edit_action {
            EditAction::Move => RectF {
                x: nx - self.drag_offset[0],
                y: ny - self.drag_offset[1],
                ..rect
            },
            EditAction::Resize => RectF {
                width: (nx - rect.x).max(0.08),
                height: (ny - rect.y).max(0.08),
                ..rect
            },
            EditAction::None => rect,
        }
        .normalized();
        self.layout.insert(selected, updated);
        unsafe {
            InvalidateRect(self.hwnd(), std::ptr::null(), 0);
        }
    }

    fn pointer_in_composition(&self) -> Option<([i32; 2], [f32; 4])> {
        let mut point = POINT { x: 0, y: 0 };
        let mut client = RECT {
            left: 0,
            top: 0,
            right: 1,
            bottom: 1,
        };
        unsafe {
            GetCursorPos(&mut point);
            ScreenToClient(self.hwnd(), &mut point);
            GetClientRect(self.hwnd(), &mut client);
        }
        Some((
            [point.x, point.y],
            self.composition_rect(client.right, client.bottom),
        ))
    }
}

fn bitmap_info(width: u32, height: u32) -> BITMAPINFO {
    let mut info: BITMAPINFO = unsafe { zeroed() };
    info.bmiHeader = BITMAPINFOHEADER {
        biSize: size_of::<BITMAPINFOHEADER>() as DWORD,
        biWidth: width as i32,
        biHeight: -(height as i32),
        biPlanes: 1,
        biBitCount: 32,
        biCompression: BI_RGB,
        biSizeImage: width * height * 4,
        biXPelsPerMeter: 0,
        biYPelsPerMeter: 0,
        biClrUsed: 0,
        biClrImportant: 0,
    };
    info
}

fn fit_frame(cell: [i32; 4], width: u32, height: u32) -> [i32; 4] {
    let cell_width = (cell[2] - cell[0]).max(1) as f32;
    let cell_height = (cell[3] - cell[1]).max(1) as f32;
    let image_ratio = width as f32 / height.max(1) as f32;
    let cell_ratio = cell_width / cell_height;
    let (target_width, target_height) = if image_ratio > cell_ratio {
        (cell_width, cell_width / image_ratio)
    } else {
        (cell_height * image_ratio, cell_height)
    };
    let left = cell[0] as f32 + (cell_width - target_width) / 2.0;
    let top = cell[1] as f32 + (cell_height - target_height) / 2.0;
    [
        left.round() as i32,
        top.round() as i32,
        (left + target_width).round() as i32,
        (top + target_height).round() as i32,
    ]
}

fn wide(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(std::iter::once(0)).collect()
}
