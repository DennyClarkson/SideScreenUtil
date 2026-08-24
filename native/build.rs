use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    let manifest = PathBuf::from(env::var_os("CARGO_MANIFEST_DIR").unwrap());
    let translations = manifest.join("..").join("assets").join("i18n");
    println!("cargo:rerun-if-changed={}", translations.display());

    let mut files: Vec<PathBuf> = fs::read_dir(&translations)
        .expect("assets/i18n is required")
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.extension().and_then(|value| value.to_str()) == Some("json"))
        .collect();
    files.sort();

    let mut generated = String::from("pub const EMBEDDED_LANGUAGE_FILES: &[(&str, &str)] = &[\n");
    for path in files {
        let code = path.file_stem().unwrap().to_string_lossy();
        let normalized = path.to_string_lossy().replace('\\', "/");
        generated.push_str(&format!(
            "    ({code:?}, include_str!(r#{normalized:?}#)),\n"
        ));
    }
    generated.push_str("];\n");
    let output = PathBuf::from(env::var_os("OUT_DIR").unwrap()).join("embedded_i18n.rs");
    fs::write(output, generated).expect("failed to generate embedded translations");

    println!("cargo:rerun-if-changed=app.rc");
    println!("cargo:rerun-if-changed=../assets/sidescreen.ico");
    embed_resource::compile("app.rc", embed_resource::NONE)
        .manifest_optional()
        .expect("failed to embed native Windows resources");
}
