use std::mem::{size_of, zeroed};
use std::ptr;

use native_windows_gui::ControlHandle;
use winapi::shared::minwindef::{BOOL, DWORD, LPARAM, TRUE};
use winapi::shared::windef::{HDC, HMONITOR, HWND, LPRECT, POINT};
use winapi::um::dwmapi::DwmSetWindowAttribute;
use winapi::um::libloaderapi::{FreeLibrary, GetProcAddress, LoadLibraryW};
use winapi::um::uxtheme::SetWindowTheme;
use winapi::um::wingdi::DISPLAY_DEVICEW;
use winapi::um::winuser::{
    EnumChildWindows, EnumDisplayDevicesW, EnumDisplayMonitors, GWL_EXSTYLE, GetClassNameW,
    GetCursorPos, GetMonitorInfoW, GetWindowLongPtrW, HWND_TOPMOST, IsWindow, LWA_ALPHA, MOD_ALT,
    MOD_CONTROL, MONITORINFO, MONITORINFOEXW, MONITORINFOF_PRIMARY, RDW_ALLCHILDREN, RDW_ERASE,
    RDW_FRAME, RDW_INVALIDATE, RedrawWindow, SW_HIDE, SW_RESTORE, SW_SHOWNOACTIVATE,
    SWP_FRAMECHANGED, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, SetForegroundWindow,
    SetLayeredWindowAttributes, SetProcessDpiAwarenessContext, SetWindowLongPtrW, SetWindowPos,
    ShowWindow, WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW,
};
use windows_capture::window::Window;

use crate::model::{MonitorInfo, WindowInfo};

pub const HOTKEY_ID: i32 = 0x5343;
pub const HOTKEY_MODIFIERS: u32 = MOD_CONTROL as u32 | MOD_ALT as u32;

pub fn enable_dpi_awareness() {
    unsafe {
        SetProcessDpiAwarenessContext(-4_isize as _);
    }
}

/// Opt classic Win32 controls into the process-wide dark palette before any
/// controls are created. The uxtheme entry point is undocumented but has been
/// stable since Windows 10 1809; every call is guarded so older systems retain
/// their normal theme instead of failing to start.
pub fn enable_native_dark_mode() {
    unsafe {
        let library_name: Vec<u16> = "uxtheme.dll\0".encode_utf16().collect();
        let library = LoadLibraryW(library_name.as_ptr());
        if library.is_null() {
            return;
        }
        let address = GetProcAddress(library, 135_usize as *const i8);
        if !address.is_null() {
            type SetPreferredAppMode = unsafe extern "system" fn(i32) -> i32;
            let set_preferred: SetPreferredAppMode = std::mem::transmute(address);
            set_preferred(1); // AllowDark
        }
        FreeLibrary(library);
    }
}

pub fn hwnd(handle: &ControlHandle) -> HWND {
    handle.hwnd().unwrap_or(ptr::null_mut())
}

pub fn enumerate_windows() -> Vec<WindowInfo> {
    let own_pid = std::process::id();
    let mut result: Vec<_> = Window::enumerate()
        .unwrap_or_default()
        .into_iter()
        .filter_map(|window| {
            let title = window.title().ok()?.trim().to_owned();
            if title.is_empty() || window.process_id().ok() == Some(own_pid) {
                return None;
            }
            let rect = window.rect().ok()?;
            if rect.right - rect.left < 160 || rect.bottom - rect.top < 90 {
                return None;
            }
            Some(WindowInfo {
                hwnd: window.as_raw_hwnd() as isize,
                title,
                process_name: window.process_name().unwrap_or_default(),
                rect: [rect.left, rect.top, rect.right, rect.bottom],
            })
        })
        .collect();
    result.sort_by_cached_key(|item| (item.process_name.to_lowercase(), item.title.to_lowercase()));
    result
}

pub fn enumerate_monitors() -> Vec<MonitorInfo> {
    unsafe extern "system" fn callback(
        monitor: HMONITOR,
        _dc: HDC,
        _rect: LPRECT,
        data: LPARAM,
    ) -> BOOL {
        let monitors = unsafe { &mut *(data as *mut Vec<MonitorInfo>) };
        let mut info: MONITORINFOEXW = unsafe { zeroed() };
        info.cbSize = size_of::<MONITORINFOEXW>() as DWORD;
        let ok = unsafe {
            GetMonitorInfoW(
                monitor,
                &mut info as *mut MONITORINFOEXW as *mut MONITORINFO,
            )
        };
        if ok != 0 {
            let device = wide_string(&info.szDevice);
            let mut adapter: DISPLAY_DEVICEW = unsafe { zeroed() };
            adapter.cb = size_of::<DISPLAY_DEVICEW>() as DWORD;
            let display_name = if unsafe {
                EnumDisplayDevicesW(info.szDevice.as_ptr(), 0, &mut adapter, 0)
            } != 0
            {
                wide_string(&adapter.DeviceString)
            } else {
                String::new()
            };
            let name = if display_name.trim().is_empty() {
                device.clone()
            } else {
                display_name
            };
            monitors.push(MonitorInfo {
                device,
                name,
                rect: [
                    info.rcMonitor.left,
                    info.rcMonitor.top,
                    info.rcMonitor.right,
                    info.rcMonitor.bottom,
                ],
                primary: info.dwFlags & MONITORINFOF_PRIMARY != 0,
            });
        }
        TRUE
    }

    let mut monitors: Vec<MonitorInfo> = Vec::new();
    unsafe {
        EnumDisplayMonitors(
            ptr::null_mut(),
            ptr::null(),
            Some(callback),
            &mut monitors as *mut Vec<MonitorInfo> as LPARAM,
        );
    }
    monitors.sort_by_key(|monitor| (!monitor.primary, monitor.rect[0], monitor.rect[1]));
    monitors
}

fn wide_string(buffer: &[u16]) -> String {
    let length = buffer
        .iter()
        .position(|value| *value == 0)
        .unwrap_or(buffer.len());
    String::from_utf16_lossy(&buffer[..length])
}

pub fn window_exists(hwnd: isize) -> bool {
    unsafe { IsWindow(hwnd as HWND) != 0 }
}

pub fn cursor_position() -> [i32; 2] {
    let mut point = POINT { x: 0, y: 0 };
    unsafe {
        GetCursorPos(&mut point);
    }
    [point.x, point.y]
}

pub fn point_in_rect(point: [i32; 2], rect: [i32; 4]) -> bool {
    point[0] >= rect[0] && point[0] < rect[2] && point[1] >= rect[1] && point[1] < rect[3]
}

pub fn apply_dark_title_bar(hwnd: HWND) {
    let enabled: i32 = 1;
    let corner_preference: i32 = 2;
    unsafe {
        DwmSetWindowAttribute(
            hwnd,
            20,
            &enabled as *const i32 as *const _,
            size_of::<i32>() as u32,
        );
        DwmSetWindowAttribute(
            hwnd,
            33,
            &corner_preference as *const i32 as *const _,
            size_of::<i32>() as u32,
        );
    }
}

fn apply_modern_theme_hwnd(hwnd: HWND) {
    let mut class_buffer = [0_u16; 64];
    let class_length =
        unsafe { GetClassNameW(hwnd, class_buffer.as_mut_ptr(), 64) }.max(0) as usize;
    let class_name = String::from_utf16_lossy(&class_buffer[..class_length]);
    let theme_name = if class_name.eq_ignore_ascii_case("ComboBox") {
        "DarkMode_CFD\0"
    } else {
        "DarkMode_Explorer\0"
    };
    let theme: Vec<u16> = theme_name.encode_utf16().collect();
    unsafe {
        let library_name: Vec<u16> = "uxtheme.dll\0".encode_utf16().collect();
        let library = LoadLibraryW(library_name.as_ptr());
        if !library.is_null() {
            let address = GetProcAddress(library, 133_usize as *const i8);
            if !address.is_null() {
                type AllowDarkModeForWindow = unsafe extern "system" fn(HWND, BOOL) -> BOOL;
                let allow_dark: AllowDarkModeForWindow = std::mem::transmute(address);
                allow_dark(hwnd, TRUE);
            }
            FreeLibrary(library);
        }
        SetWindowTheme(hwnd, theme.as_ptr(), ptr::null());
    }
}

pub fn apply_modern_theme_tree(root: HWND) {
    unsafe extern "system" fn callback(hwnd: HWND, _data: LPARAM) -> BOOL {
        apply_modern_theme_hwnd(hwnd);
        TRUE
    }
    apply_modern_theme_hwnd(root);
    unsafe {
        EnumChildWindows(root, Some(callback), 0);
        RedrawWindow(
            root,
            ptr::null(),
            ptr::null_mut(),
            RDW_INVALIDATE | RDW_ERASE | RDW_FRAME | RDW_ALLCHILDREN,
        );
    }
}

pub fn configure_overlay(hwnd: HWND) {
    unsafe {
        let style = GetWindowLongPtrW(hwnd, GWL_EXSTYLE);
        SetWindowLongPtrW(
            hwnd,
            GWL_EXSTYLE,
            style | WS_EX_NOACTIVATE as isize | WS_EX_TOOLWINDOW as isize | WS_EX_LAYERED as isize,
        );
        SetLayeredWindowAttributes(hwnd, 0, 0, LWA_ALPHA);
        SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        );
    }
}

pub fn set_overlay_alpha(hwnd: HWND, alpha: u8) {
    unsafe {
        SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA);
    }
}

pub fn show_overlay(hwnd: HWND, visible: bool) {
    unsafe {
        ShowWindow(hwnd, if visible { SW_SHOWNOACTIVATE } else { SW_HIDE });
    }
}

pub fn show_main_window(hwnd: HWND) {
    unsafe {
        ShowWindow(hwnd, SW_RESTORE);
        SetForegroundWindow(hwnd);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn point_hit_test_uses_half_open_bounds() {
        assert!(point_in_rect([10, 10], [0, 0, 20, 20]));
        assert!(!point_in_rect([20, 10], [0, 0, 20, 20]));
    }
}
