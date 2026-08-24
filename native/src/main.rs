#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use native_windows_gui as nwg;

mod capture;
mod filter;
mod i18n;
mod layout;
mod model;
mod overlay;
mod platform;
mod settings;
mod ui;

fn main() {
    platform::enable_dpi_awareness();
    if std::env::args().any(|argument| argument == "--binary-smoke-test") {
        let mut settings = settings::load();
        settings.normalize();
        let translations = i18n::Translations::load(&settings.language);
        if translations.text("action.start").is_empty() {
            std::process::exit(1);
        }
        let pixels = [32_u8, 64, 96, 255].repeat(16);
        let frame = filter::compact_and_filter(&pixels, 4, 4, 16, &settings, 0.0);
        if frame.width != 4 || frame.height != 4 || frame.pixels.len() != 64 {
            std::process::exit(1);
        }
        return;
    }
    if std::env::args().any(|argument| argument == "--capture-smoke-test") {
        if let Err(error) = capture::capture_smoke_test() {
            eprintln!("{error}");
            std::process::exit(1);
        }
        return;
    }
    if std::env::args().any(|argument| argument == "--smoke-test") {
        let mut settings = settings::load();
        settings.normalize();
        let _ = platform::enumerate_monitors();
        let _ = platform::enumerate_windows();
        return;
    }
    nwg::init().expect("Failed to initialize native Windows UI");
    nwg::Font::set_global_family("Segoe UI").expect("Failed to set UI font");
    if std::env::args().any(|argument| argument == "--ui-smoke-test") {
        if let Err(error) = ui::smoke_test() {
            eprintln!("{error}");
            std::process::exit(1);
        }
        return;
    }
    ui::run().expect("Failed to build main window");
}
