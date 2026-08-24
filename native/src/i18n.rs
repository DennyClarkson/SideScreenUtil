use std::collections::HashMap;

use serde::Deserialize;

include!(concat!(env!("OUT_DIR"), "/embedded_i18n.rs"));

#[derive(Deserialize)]
struct LanguageMeta {
    code: String,
    name: String,
}

#[derive(Deserialize)]
struct LanguageFile {
    meta: LanguageMeta,
    strings: HashMap<String, String>,
}

pub struct Translations {
    files: Vec<LanguageFile>,
    active: usize,
}

impl Translations {
    pub fn load(language: &str) -> Self {
        let files: Vec<LanguageFile> = EMBEDDED_LANGUAGE_FILES
            .iter()
            .filter_map(|(_, raw)| serde_json::from_str(raw).ok())
            .collect();
        let active = files
            .iter()
            .position(|file| file.meta.code == language)
            .or_else(|| files.iter().position(|file| file.meta.code == "en_US"))
            .unwrap_or(0);
        Self { files, active }
    }

    pub fn select(&mut self, index: usize) {
        if index < self.files.len() {
            self.active = index;
        }
    }

    pub fn language_code(&self) -> &str {
        &self.files[self.active].meta.code
    }

    pub fn language_names(&self) -> Vec<String> {
        self.files
            .iter()
            .map(|file| file.meta.name.clone())
            .collect()
    }

    pub fn active_index(&self) -> usize {
        self.active
    }

    pub fn text(&self, key: &str) -> String {
        self.files[self.active]
            .strings
            .get(key)
            .or_else(|| {
                self.files
                    .iter()
                    .find(|file| file.meta.code == "en_US")
                    .and_then(|file| file.strings.get(key))
            })
            .cloned()
            .unwrap_or_else(|| key.to_owned())
    }
}
