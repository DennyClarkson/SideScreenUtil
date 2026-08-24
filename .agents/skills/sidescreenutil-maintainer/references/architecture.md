# Architecture and parity map

Read this reference for product code, UI, capture, filter, layout, settings, or localization work.

## Implementation map

| Concern | Full compatibility edition | Compact native edition |
| --- | --- | --- |
| Startup and smoke routing | `src/sidescreen/app.py` | `native/src/main.rs` |
| Main UI and orchestration | `src/sidescreen/main_window.py` | `native/src/ui.rs` |
| Settings model and persistence | `src/sidescreen/models.py`, `settings_store.py` | `native/src/model.rs`, `settings.rs` |
| Multi-window capture | `capture.py`, `multi_capture.py` | `native/src/capture.rs` |
| Overlay, motion, pointer reveal, editing | `overlay.py`, `motion.py`, `layout_editor.py`, `hotkeys.py` | `native/src/overlay.rs`, `ui.rs` |
| Filters and frame compaction | `filters.py`, `frame_utils.py` | `native/src/filter.rs` |
| Layout generation | `layouts.py` | `native/src/layout.rs` |
| Monitor and window enumeration | `win32.py` and capture helpers | `native/src/platform.rs` |
| Localization | `src/sidescreen/i18n.py`, `assets/i18n/*.json` | `native/src/i18n.rs`, embedded `assets/i18n/*.json` |
| Python tests | `tests/` | Unit tests colocated in Rust modules plus native smoke modes |

## Data flow

Both implementations follow the same conceptual pipeline:

1. Enumerate a target monitor and capturable source windows.
2. Normalize settings and source-window layout into `[0, 1]` rectangles.
3. Maintain one capture session per selected source window.
4. Prefer WGC; fall back to GDI/`PrintWindow` when WGC cannot start.
5. Compact frames only when the resolution limit is enabled, then apply the selected filter and brightness.
6. Composite the latest frames on a black target-display overlay.
7. Apply canvas drift, size variation, transitions, pointer reveal, edit mode, and black-rest scheduling.

When adding a setting, update all layers that own it: model/defaults, normalization, persistence, controls, live propagation, translations, overlay/capture behavior, and tests. Do this independently in Python and Rust rather than trying to share serialized files; the editions intentionally use separate settings paths.

## Rendering and capture constraints

- Captured pixels are BGRA. Preserve channel order and alpha expectations when adding filters.
- Filter changes must reprocess or reacquire a frame promptly. Avoid forcing an expensive capture restart for settings that can be applied to a cached frame; debounce restarts when they are required.
- Capture workers publish bounded latest-frame state. Do not create unbounded frame queues.
- The native overlay owns repaint cadence. Capture threads must not invalidate the overlay independently because competing repaints previously caused visible flicker.
- The Python overlay must retain the NumPy owner for every `QImage` that references its memory. Avoid implicit deep copies unless lifetime cannot otherwise be guaranteed.
- Inner-contour output grows edges only into equally bright or brighter source pixels. Preserve dark backgrounds and text interiors; tests should ensure a uniform frame remains black and dark surroundings are not lit.

## Native UI constraints

- `native/src/ui.rs` uses raw Win32 `STATIC` controls for labels to avoid lower-glyph clipping caused by the NWG label subclass at high DPI.
- Heading and page fonts use absolute character heights. Test Chinese and Latin fonts before changing those metrics.
- Responsive layout uses a separate `DeferWindowPos` batch for the root and each page frame because one batch cannot safely mix controls with different parents.
- Layout edits happen in logical coordinates and are scaled using the target window DPI. Keep minimum-window-size handling and maximize/restore behavior working.
- Modern theming is applied recursively. New controls should inherit the existing dark Windows 11-like treatment instead of introducing default classic controls.

## Localization

`assets/i18n/zh_CN.json` is the fallback and schema baseline. Keep the key sets of `zh_CN.json` and `en_US.json` identical and preserve named placeholders. The Python package discovers JSON files at build time, and the native build embeds the same directory through its build process.

For a new visible string:

1. Add a stable key to both built-in packs.
2. Use the translation key in both UIs.
3. Keep complete sentences together instead of concatenating translated fragments.
4. Run localization parity tests and visually check long English text.

## Scope-based validation

| Change | Minimum meaningful validation |
| --- | --- |
| Settings/defaults | Round-trip and invalid/older-settings normalization tests in both editions |
| Layout | Unit tests for bounds/normalization plus manual edit-mode check |
| Filter | Synthetic pixel tests, dark-background invariant, and live visual check |
| Capture | Packaged capture smoke plus moving and occluded window checks |
| Overlay/pointer | Black-only start, pointer enter/leave, pause, rest, and edit hotkey checks |
| UI | Default/minimum/maximized sizes, both languages, DPI/glyph clipping, and resize smoothness |
| Localization | Built-in key parity and packaged lookup in both executables |
