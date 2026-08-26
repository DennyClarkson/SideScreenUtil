use std::fs;
use std::path::{Path, PathBuf};

use winreg::RegKey;
use winreg::enums::HKEY_CURRENT_USER;

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
    let current_user = RegKey::predef(HKEY_CURRENT_USER);
    let (run_key, _) = current_user
        .create_subkey("Software\\Microsoft\\Windows\\CurrentVersion\\Run")
        .map_err(|error| error.to_string())?;
    if enabled {
        run_key
            .set_value("SideScreenUtil Native", &startup_command_for(executable))
            .map_err(|error| error.to_string())
    } else {
        match run_key.delete_value("SideScreenUtil Native") {
            Ok(()) => Ok(()),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(error) => Err(error.to_string()),
        }
    }
}

fn startup_command_for(executable: &Path) -> String {
    format!("\"{}\" --startup", executable.to_string_lossy())
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
