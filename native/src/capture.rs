use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, RwLock};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use std::mem::{size_of, zeroed};
use winapi::shared::windef::RECT;
use winapi::um::wingdi::{
    BI_RGB, BITMAPINFO, BITMAPINFOHEADER, BitBlt, CreateCompatibleBitmap, CreateCompatibleDC,
    DIB_RGB_COLORS, DeleteDC, DeleteObject, GetDIBits, SRCCOPY, SelectObject,
};
use winapi::um::winuser::{GetWindowDC, GetWindowRect, PrintWindow, ReleaseDC};
use windows_capture::capture::{CaptureControl, Context, GraphicsCaptureApiHandler};
use windows_capture::frame::Frame;
use windows_capture::graphics_capture_api::InternalCaptureControl;
use windows_capture::settings::{
    ColorFormat, CursorCaptureSettings, DirtyRegionSettings, DrawBorderSettings,
    MinimumUpdateIntervalSettings, SecondaryWindowSettings, Settings,
};
use windows_capture::window::Window;

use crate::filter::compact_and_filter;
use crate::model::{AppSettings, FrameData};

pub struct SharedCaptureState {
    pub frames: Mutex<HashMap<isize, Arc<FrameData>>>,
    pub settings: RwLock<AppSettings>,
    pub closed_windows: Mutex<Vec<isize>>,
    started_at: Instant,
}

impl SharedCaptureState {
    pub fn new(settings: AppSettings) -> Arc<Self> {
        Arc::new(Self {
            frames: Mutex::new(HashMap::new()),
            settings: RwLock::new(settings),
            closed_windows: Mutex::new(Vec::new()),
            started_at: Instant::now(),
        })
    }

    pub fn update_settings(&self, settings: AppSettings) {
        *self
            .settings
            .write()
            .unwrap_or_else(|error| error.into_inner()) = settings;
    }

    pub fn retain_frames(&self, handles: &[isize]) {
        self.frames
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .retain(|hwnd, _| handles.contains(hwnd));
    }

    pub fn clear(&self) {
        self.frames
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .clear();
    }
}

#[derive(Clone)]
pub struct CaptureFlags {
    hwnd: isize,
    shared: Arc<SharedCaptureState>,
    minimum_interval: Duration,
}

pub struct CaptureHandler {
    flags: CaptureFlags,
    last_frame_at: Instant,
}

impl GraphicsCaptureApiHandler for CaptureHandler {
    type Flags = CaptureFlags;
    type Error = String;

    fn new(context: Context<Self::Flags>) -> Result<Self, Self::Error> {
        let last_frame_at = Instant::now()
            .checked_sub(context.flags.minimum_interval)
            .unwrap_or_else(Instant::now);
        Ok(Self {
            flags: context.flags,
            last_frame_at,
        })
    }

    fn on_frame_arrived(
        &mut self,
        frame: &mut Frame,
        _capture_control: InternalCaptureControl,
    ) -> Result<(), Self::Error> {
        let now = Instant::now();
        if now.duration_since(self.last_frame_at) < self.flags.minimum_interval.mul_f32(0.8) {
            return Ok(());
        }
        self.last_frame_at = now;
        let mut buffer = frame.buffer().map_err(|error| error.to_string())?;
        let width = buffer.width();
        let height = buffer.height();
        let row_pitch = buffer.row_pitch();
        let settings = self
            .flags
            .shared
            .settings
            .read()
            .unwrap_or_else(|error| error.into_inner())
            .clone();
        let elapsed = now
            .duration_since(self.flags.shared.started_at)
            .as_secs_f64();
        let result = compact_and_filter(
            buffer.as_raw_buffer(),
            width,
            height,
            row_pitch,
            &settings,
            elapsed,
        );
        self.flags
            .shared
            .frames
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .insert(self.flags.hwnd, Arc::new(result));
        Ok(())
    }

    fn on_closed(&mut self) -> Result<(), Self::Error> {
        self.flags
            .shared
            .closed_windows
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .push(self.flags.hwnd);
        Ok(())
    }
}

pub enum NativeCaptureControl {
    Wgc(CaptureControl<CaptureHandler, String>),
    Gdi(GdiCaptureControl),
}

impl NativeCaptureControl {
    pub fn stop(self) -> Result<(), String> {
        match self {
            Self::Wgc(control) => control.stop().map_err(|error| error.to_string()),
            Self::Gdi(control) => control.stop(),
        }
    }
}

pub struct GdiCaptureControl {
    stopping: Arc<AtomicBool>,
    thread: Option<JoinHandle<()>>,
}

impl GdiCaptureControl {
    fn start(hwnd: isize, shared: Arc<SharedCaptureState>, fps: u32) -> Self {
        let stopping = Arc::new(AtomicBool::new(false));
        let worker_stop = stopping.clone();
        let interval = Duration::from_secs_f64(1.0 / fps.clamp(1, 30) as f64);
        let thread = thread::spawn(move || {
            let started = Instant::now();
            while !worker_stop.load(Ordering::Relaxed) && crate::platform::window_exists(hwnd) {
                let frame_started = Instant::now();
                if let Some((raw, width, height)) = capture_window_gdi(hwnd) {
                    let settings = shared
                        .settings
                        .read()
                        .unwrap_or_else(|error| error.into_inner())
                        .clone();
                    let frame = compact_and_filter(
                        &raw,
                        width,
                        height,
                        width * 4,
                        &settings,
                        started.elapsed().as_secs_f64(),
                    );
                    shared
                        .frames
                        .lock()
                        .unwrap_or_else(|error| error.into_inner())
                        .insert(hwnd, Arc::new(frame));
                }
                if let Some(remaining) = interval.checked_sub(frame_started.elapsed()) {
                    thread::sleep(remaining);
                }
            }
            if !worker_stop.load(Ordering::Relaxed) {
                shared
                    .closed_windows
                    .lock()
                    .unwrap_or_else(|error| error.into_inner())
                    .push(hwnd);
            }
        });
        Self {
            stopping,
            thread: Some(thread),
        }
    }

    fn stop(mut self) -> Result<(), String> {
        self.stopping.store(true, Ordering::Relaxed);
        if let Some(worker) = self.thread.take() {
            worker
                .join()
                .map_err(|_| "PrintWindow capture worker panicked".to_owned())?;
        }
        Ok(())
    }
}

pub fn start(
    hwnd: isize,
    shared: Arc<SharedCaptureState>,
    frames_per_second: u32,
) -> Result<NativeCaptureControl, String> {
    let interval = Duration::from_secs_f64(1.0 / frames_per_second.clamp(1, 60) as f64);
    let flags = CaptureFlags {
        hwnd,
        shared: shared.clone(),
        minimum_interval: interval,
    };
    let settings = Settings::new(
        Window::from_raw_hwnd(hwnd as _),
        CursorCaptureSettings::WithoutCursor,
        DrawBorderSettings::WithoutBorder,
        SecondaryWindowSettings::Default,
        MinimumUpdateIntervalSettings::Custom(interval),
        DirtyRegionSettings::Default,
        ColorFormat::Bgra8,
        flags,
    );
    match CaptureHandler::start_free_threaded(settings) {
        Ok(control) => Ok(NativeCaptureControl::Wgc(control)),
        Err(_) => Ok(NativeCaptureControl::Gdi(GdiCaptureControl::start(
            hwnd,
            shared,
            frames_per_second,
        ))),
    }
}

pub fn stop_all(controls: &mut HashMap<isize, NativeCaptureControl>) {
    for (_, control) in controls.drain() {
        let _ = control.stop();
    }
}

fn capture_window_gdi(hwnd: isize) -> Option<(Vec<u8>, u32, u32)> {
    unsafe {
        let mut rect: RECT = zeroed();
        if GetWindowRect(hwnd as _, &mut rect) == 0 {
            return None;
        }
        let width = (rect.right - rect.left).max(1) as u32;
        let height = (rect.bottom - rect.top).max(1) as u32;
        let source = GetWindowDC(hwnd as _);
        if source.is_null() {
            return None;
        }
        let memory = CreateCompatibleDC(source);
        let bitmap = CreateCompatibleBitmap(source, width as i32, height as i32);
        if memory.is_null() || bitmap.is_null() {
            if !memory.is_null() {
                DeleteDC(memory);
            }
            if !bitmap.is_null() {
                DeleteObject(bitmap as _);
            }
            ReleaseDC(hwnd as _, source);
            return None;
        }
        let old = SelectObject(memory, bitmap as _);
        if PrintWindow(hwnd as _, memory, 2) == 0 {
            BitBlt(
                memory,
                0,
                0,
                width as i32,
                height as i32,
                source,
                0,
                0,
                SRCCOPY,
            );
        }
        let mut info: BITMAPINFO = zeroed();
        info.bmiHeader = BITMAPINFOHEADER {
            biSize: size_of::<BITMAPINFOHEADER>() as u32,
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
        let mut pixels = vec![0_u8; width as usize * height as usize * 4];
        let copied = GetDIBits(
            memory,
            bitmap,
            0,
            height,
            pixels.as_mut_ptr() as _,
            &mut info,
            DIB_RGB_COLORS,
        );
        SelectObject(memory, old);
        DeleteObject(bitmap as _);
        DeleteDC(memory);
        ReleaseDC(hwnd as _, source);
        if copied == 0 {
            None
        } else {
            Some((pixels, width, height))
        }
    }
}

pub fn capture_smoke_test() -> Result<(), String> {
    let sources: Vec<_> = crate::platform::enumerate_windows()
        .into_iter()
        .take(2)
        .collect();
    if sources.is_empty() {
        return Err("No capturable window is available".to_owned());
    }
    let shared = SharedCaptureState::new(AppSettings::default());
    let mut controls = Vec::new();
    for source in &sources {
        controls.push(start(source.hwnd, shared.clone(), 8)?);
    }
    let deadline = Instant::now() + Duration::from_secs(4);
    let captured = loop {
        let frames = shared
            .frames
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        if sources
            .iter()
            .all(|source| frames.contains_key(&source.hwnd))
        {
            break true;
        }
        drop(frames);
        if Instant::now() >= deadline {
            break false;
        }
        std::thread::sleep(Duration::from_millis(40));
    };
    for control in controls {
        let _ = control.stop();
    }
    if captured {
        Ok(())
    } else {
        Err("Timed out waiting for multi-window capture frames".to_owned())
    }
}
