# SideScreenUtil Development Guide

## AI-assisted maintenance

The repository includes a project-scoped Codex skill at
`.agents/skills/sidescreenutil-maintainer/SKILL.md`. Codex discovers it automatically when opened
inside this repository, or it can be invoked explicitly as `$sidescreenutil-maintainer`. The skill
maps the Python and Rust implementations, preserves cross-edition product invariants, and routes
build and release work through the existing verified scripts.

## Architecture

SideScreenUtil has two Windows implementations that are released and maintained in parallel:

- the full compatibility edition, built with Python, PySide6 Essentials, NumPy, and pywin32;
- the compact native edition in `native`, built with Rust, Win32 controls, and Windows Graphics Capture.

The main components are:

- `src/sidescreen/app.py`: process startup, Qt application setup, logging, and packaged smoke-test entry points.
- `src/sidescreen/main_window.py`: control panel, settings, source selection, and orchestration.
- `src/sidescreen/overlay.py`: frameless target-display canvas, painting, transitions, pointer suppression, and direct layout editing.
- `src/sidescreen/capture.py`: one WGC or `PrintWindow` capture session.
- `src/sidescreen/multi_capture.py`: live synchronization of multiple capture sessions.
- `src/sidescreen/filters.py`: NumPy-based OLED-oriented visual filters.
- `src/sidescreen/layouts.py`: normalized grid, strip, source-relative, and clamping functions.
- `src/sidescreen/i18n.py`: JSON language discovery, fallback, and placeholder formatting.
- `src/sidescreen/models.py`: serializable application settings and window metadata.
- `src/sidescreen/startup.py`: current-user Windows startup registration for the full edition.

The overlay layout uses normalized rectangles in the `[0, 1]` coordinate space. The complete composition can drift to the physical screen edges, rebound, and scale without changing the relative geometry of its source windows.

Each edition owns a separate value under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
The stored command includes `--startup`, and the persisted `silent_start` setting decides whether
the control panel is initially visible. The tray remains available when the window starts hidden.

## Environment setup

```powershell
.\scripts\setup.ps1
```

The setup script creates `.venv`, installs the project in editable mode, and installs development dependencies.

Run the application:

```powershell
.\scripts\run.ps1
```

## Localization system

Language packs live in `assets/i18n`. At startup, `available_languages()` scans every `*.json` file in that directory. PyInstaller bundles the complete directory, so adding a valid file before building is sufficient to include it in the EXE.

The selected language code is stored in the `language` field of the user's settings file. A missing translation falls back to `zh_CN`; if it is also absent there, the translation key is shown. Invalid language files are skipped and logged.

### Language-pack schema

```json
{
  "meta": {
    "code": "fr_FR",
    "name": "Français"
  },
  "strings": {
    "tabs.layout": "Disposition",
    "state.running": "●  Actif · {count} fenêtres"
  }
}
```

Rules:

- The filename should match `meta.code`, for example `fr_FR.json`.
- `meta.code` must be stable because it is persisted in settings.
- `meta.name` is the native-language label shown in the language selector.
- `strings` maps stable translation keys to text.
- Preserve named placeholders exactly. For example, `{count}`, `{summary}`, `{mode}`, `{error}`, `{number}`, and `{value}` may be reordered but must not be renamed or removed when the sentence requires them.
- Save files as UTF-8 JSON.
- Keep the key set aligned with `zh_CN.json`. The test suite verifies the two built-in packs automatically.

### Adding a language

1. Copy `assets/i18n/en_US.json` to a new locale filename.
2. Change `meta.code` and `meta.name`.
3. Translate every value in `strings`; do not translate the keys.
4. Run the localization and full test suite.
5. Build the EXE. No Python registration code or build-script change is required.

Use translations in Python through:

```python
from sidescreen.i18n import tr

label.setText(tr("tabs.layout"))
status.setText(tr("state.running", count=3))
```

Add every new user-facing string to both built-in language packs. Avoid constructing sentences from translated fragments; use one complete translation key with named placeholders.

Language changes are persisted immediately and applied throughout the UI on the next application start. This avoids rebuilding stateful widgets during an active capture session.

## Capture and memory model

Each selected source window owns one `CaptureSession`. The preferred backend is Windows Graphics Capture. If WGC cannot start, the session falls back to `PrintWindow`.

Captured frames are BGRA NumPy arrays. The normal memory-saving mode limits persistent raw frames to approximately one megapixel and a maximum dimension of 1600 pixels. Full-resolution mode stores an owned, contiguous copy of every source pixel. The filtered array is passed directly to `QImage` while its NumPy owner remains alive, avoiding intermediate `bytes` and `QImage.copy()` allocations.

The application periodically asks Windows to reclaim unused working-set pages. This lowers idle physical memory without deleting application state, although required pages may be loaded again during active capture.

## Filters

`FilterConfig` is immutable and shared with capture sessions. A filter change reprocesses the most recently cached raw frame immediately. Animated monochrome filters periodically refresh the cached frame with a new hue.

The contour filter computes horizontal, vertical, and diagonal luminance differences, applies a soft threshold ramp, and grows the result using adjustable cross-shaped dilation. Keep the implementation NumPy-only unless the package-size impact of a new dependency is explicitly accepted.

## Testing

Run all unit tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run linting:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
```

The tests cover settings normalization and persistence, language-pack parity, layouts, motion, filters, frame compaction, overlay frame ownership, and layout-edit mode behavior.

## Packaging

```powershell
.\scripts\build.ps1
.\scripts\build-native.ps1
```

The full-edition build creates a one-file, windowed executable with Python bytecode optimization. It includes:

- the runtime PNG and multi-size ICO;
- all files in `assets/i18n`;
- the vendored native WGC extension and its license.

It excludes OpenCV, the public `windows_capture` wrapper, QtNetwork, and unused testing/documentation modules.

After packaging, run both checks with the exact release executable:

```powershell
.\dist\SideScreenUtil.exe --smoke-test
.\dist\SideScreenUtil.exe --capture-smoke-test
```

The second command must acquire a real WGC/`PrintWindow` frame and apply the contour filter before exiting successfully.

The native build creates `dist\SideScreenUtil-native.exe`, verifies that it has no adjacent DLL
dependency, runs its packaged smoke tests, and writes its checksum. See
[NATIVE_PREVIEW.md](NATIVE_PREVIEW.md) for the native toolchain and architecture details.

## Release checklist

1. Update the same version in `pyproject.toml`, `src/sidescreen/__init__.py`, `native/Cargo.toml`, and `native/app.rc`.
2. Verify that built-in language packs contain identical key sets.
3. Run Ruff and the complete test suite.
4. Build with `scripts/build.ps1` and `scripts/build-native.ps1`.
5. Run the packaged smoke tests for both editions.
6. Record both EXE sizes and SHA-256 checksums.
7. Confirm that `dist` contains only the two intended release executables and their checksums.

## Automated releases

`.github/workflows/release.yml` publishes a release whenever a version tag is pushed. The tag
must match the versions in both `pyproject.toml` and `native/Cargo.toml`, including the `v` prefix.

```powershell
git tag -a v0.6.0 -m "SideScreenUtil v0.6.0"
git push origin v0.6.0
```

The Windows runner tests and builds both implementations, runs their packaged smoke tests, writes
separate SHA-256 checksums, uploads one workflow artifact, and creates a GitHub Release containing
both executables and both checksum files. A tag or cross-edition version mismatch stops the
workflow before packaging.
