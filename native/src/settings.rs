use std::fs;
use std::path::{Path, PathBuf};

use winapi::shared::minwindef::HKEY;
use winapi::shared::winerror::{ERROR_FILE_NOT_FOUND, ERROR_SUCCESS};
use winapi::um::winnt::{KEY_SET_VALUE, REG_SZ};
use winapi::um::winreg::{
    HKEY_CURRENT_USER, RegCloseKey, RegCreateKeyExW, RegDeleteValueW, RegSetValueExW,
};

use crate::model::AppSettings;

fn settings_path() -> PathBuf {
    let root = std::env::var_os("APPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir);
    root.join("SideScreenUtil").join("settings-native.json")
}

pub fn load() -> AppSettings {
    let path = settings_path();
    let mut settings = fs::read_to_string(path)
        .ok()
        .and_then(|raw| serde_json::from_str::<AppSettings>(&raw).ok())
        .unwrap_or_default();
    settings.normalize();
    settings
}

pub fn save(settings: &AppSettings) -> Result<(), String> {
    let path = settings_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let raw = serde_json::to_string_pretty(settings).map_err(|error| error.to_string())?;
    fs::write(path, raw).map_err(|error| error.to_string())
}

pub fn sync_start_with_windows(enabled: bool) -> Result<(), String> {
    let executable = std::env::current_exe().map_err(|error| error.to_string())?;
    set_start_with_windows_for(enabled, &executable)
}

fn set_start_with_windows_for(enabled: bool, executable: &Path) -> Result<(), String> {
    let key_path = wide("Software\\Microsoft\\Windows\\CurrentVersion\\Run");
    let value_name = wide("SideScreenUtil Native");
    let mut key: HKEY = std::ptr::null_mut();
    let opened = unsafe {
        RegCreateKeyExW(
            HKEY_CURRENT_USER,
            key_path.as_ptr(),
            0,
            std::ptr::null_mut(),
            0,
            KEY_SET_VALUE,
            std::ptr::null_mut(),
            &mut key,
            std::ptr::null_mut(),
        )
    };
    if opened != ERROR_SUCCESS as i32 {
        return Err(format!("RegCreateKeyExW failed with status {opened}"));
    }
    let result = if enabled {
        let command = wide(&startup_command_for(executable));
        unsafe {
            RegSetValueExW(
                key,
                value_name.as_ptr(),
                0,
                REG_SZ,
                command.as_ptr() as *const u8,
                (command.len() * std::mem::size_of::<u16>()) as u32,
            )
        }
    } else {
        let deleted = unsafe { RegDeleteValueW(key, value_name.as_ptr()) };
        if deleted == ERROR_FILE_NOT_FOUND as i32 {
            ERROR_SUCCESS as i32
        } else {
            deleted
        }
    };
    unsafe {
        RegCloseKey(key);
    }
    if result == ERROR_SUCCESS as i32 {
        Ok(())
    } else {
        Err(format!(
            "Windows registry update failed with status {result}"
        ))
    }
}

fn startup_command_for(executable: &Path) -> String {
    format!("\"{}\" --startup", executable.to_string_lossy())
}

fn wide(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(std::iter::once(0)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn startup_command_quotes_the_executable_and_adds_the_flag() {
        let executable = Path::new(r"C:\Program Files\SideScreenUtil\SideScreenUtil-native.exe");
        assert_eq!(
            startup_command_for(executable),
            r#""C:\Program Files\SideScreenUtil\SideScreenUtil-native.exe" --startup"#
        );
    }
}
