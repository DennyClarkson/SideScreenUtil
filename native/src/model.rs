use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct RectF {
    pub x: f32,
    pub y: f32,
    pub width: f32,
    pub height: f32,
}

impl RectF {
    pub fn normalized(self) -> Self {
        let width = self.width.clamp(0.08, 1.0);
        let height = self.height.clamp(0.08, 1.0);
        Self {
            x: self.x.clamp(0.0, 1.0 - width),
            y: self.y.clamp(0.0, 1.0 - height),
            width,
            height,
        }
    }
}

#[derive(Clone, Copy, Debug, Default, Deserialize, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum LayoutMode {
    #[default]
    Source,
    Grid,
    Horizontal,
    Vertical,
    Manual,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FilterStyle {
    #[default]
    Original,
    Grayscale,
    Mono,
    MonoCycle,
    Edge,
    EdgeCycle,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(default)]
pub struct AppSettings {
    pub language: String,
    pub start_with_windows: bool,
    pub silent_start: bool,
    pub monitor_device: String,
    pub preview_scale: f32,
    pub move_seconds: u32,
    pub size_variation: f32,
    pub capture_fps: u32,
    pub limit_capture_resolution: bool,
    pub blank_every_minutes: u32,
    pub blank_seconds: u32,
    pub layout_mode: LayoutMode,
    pub filter_style: FilterStyle,
    pub brightness: f32,
    pub accent_color: u32,
    pub hue_cycle_seconds: u32,
    pub edge_threshold: u8,
    pub edge_thickness: u8,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            language: "zh_CN".to_owned(),
            start_with_windows: false,
            silent_start: false,
            monitor_device: String::new(),
            preview_scale: 0.72,
            move_seconds: 180,
            size_variation: 0.03,
            capture_fps: 12,
            limit_capture_resolution: true,
            blank_every_minutes: 30,
            blank_seconds: 30,
            layout_mode: LayoutMode::Source,
            filter_style: FilterStyle::Original,
            brightness: 0.65,
            accent_color: 0x22d3ee,
            hue_cycle_seconds: 120,
            edge_threshold: 18,
            edge_thickness: 2,
        }
    }
}

impl AppSettings {
    pub fn normalize(&mut self) {
        self.preview_scale = self.preview_scale.clamp(0.20, 0.90);
        self.move_seconds = self.move_seconds.clamp(30, 900);
        self.size_variation = self.size_variation.clamp(0.0, 0.10);
        self.capture_fps = self.capture_fps.clamp(5, 30);
        self.blank_every_minutes = self.blank_every_minutes.min(240);
        self.blank_seconds = self.blank_seconds.clamp(5, 300);
        self.brightness = self.brightness.clamp(0.10, 1.0);
        self.hue_cycle_seconds = self.hue_cycle_seconds.clamp(10, 600);
        self.edge_threshold = self.edge_threshold.clamp(4, 120);
        self.edge_thickness = self.edge_thickness.clamp(1, 4);
    }
}

#[derive(Clone, Debug)]
pub struct WindowInfo {
    pub hwnd: isize,
    pub title: String,
    pub process_name: String,
    pub rect: [i32; 4],
}

impl WindowInfo {
    pub fn display_name(&self) -> String {
        if self.process_name.is_empty() {
            self.title.clone()
        } else {
            format!("{} — {}", self.title, self.process_name)
        }
    }
}

#[derive(Clone, Debug)]
pub struct MonitorInfo {
    pub device: String,
    pub name: String,
    pub rect: [i32; 4],
    pub primary: bool,
}

impl MonitorInfo {
    pub fn width(&self) -> i32 {
        self.rect[2] - self.rect[0]
    }

    pub fn height(&self) -> i32 {
        self.rect[3] - self.rect[1]
    }
}

#[derive(Clone, Debug)]
pub struct FrameData {
    pub width: u32,
    pub height: u32,
    pub pixels: Vec<u8>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn older_settings_default_new_startup_preferences_to_disabled() {
        let settings: AppSettings =
            serde_json::from_str(r#"{"language":"en_US"}"#).expect("valid settings");
        assert!(!settings.start_with_windows);
        assert!(!settings.silent_start);
    }

    #[test]
    fn startup_preferences_round_trip() {
        let settings = AppSettings {
            start_with_windows: true,
            silent_start: true,
            ..AppSettings::default()
        };
        let raw = serde_json::to_string(&settings).expect("serialize settings");
        let restored: AppSettings = serde_json::from_str(&raw).expect("deserialize settings");
        assert!(restored.start_with_windows);
        assert!(restored.silent_start);
    }
}
