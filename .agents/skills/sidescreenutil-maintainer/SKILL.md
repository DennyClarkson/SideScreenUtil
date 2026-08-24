---
name: sidescreenutil-maintainer
description: Maintain and extend the SideScreenUtil repository across its Python/Qt full edition and Rust/Win32 native edition. Use for feature work, bug fixes, UI, capture, filters, layouts, settings, localization, tests, packaging, CI, and releases in this repository; do not use for unrelated promotional media work.
metadata:
  short-description: Maintain both SideScreenUtil editions
---

# SideScreenUtil Maintainer

Keep SideScreenUtil's two Windows implementations behaviorally aligned while preserving the native edition's small footprint and the full edition's compatibility.

## Start every task

1. Confirm the repository root contains `pyproject.toml`, `native/Cargo.toml`, and `README.md`.
2. Inspect `git status` and preserve unrelated or user-owned changes. Do not add generated `build`, `dist`, or `native/target` content.
3. Read the files that own the requested behavior before editing. Do not assume the Python and Rust implementations have identical internal structure.
4. Decide whether the request affects shared product behavior or only one implementation. Implement shared behavior in both editions unless the user explicitly scopes the task to one edition. For a genuinely implementation-specific fix, state why the other edition does not need a change.

For product code, UI, capture, filter, layout, settings, or localization changes, read [references/architecture.md](references/architecture.md).

For packaging, CI, versioning, tagging, or GitHub Release work, read [references/release.md](references/release.md).

Use `README.md`, `DEVELOPMENT.md`, and `NATIVE_PREVIEW.md` as the current public and developer documentation. Update them when user-visible behavior, requirements, commands, or release contents change.

## Preserve these product invariants

- Starting with no selected source windows must open a black-only protection canvas.
- Source windows may be added, removed, or switched while monitoring remains active.
- Windows Graphics Capture is preferred and `PrintWindow` is the fallback.
- Moving the pointer onto the target display immediately reveals the normal desktop; moving it away restores monitoring. Layout-edit mode temporarily disables this reveal behavior.
- `Ctrl+Alt+L` toggles direct layout editing on the target display, and edited normalized rectangles persist.
- Live filter, brightness, capture-resolution, and protection changes should take effect without stopping monitoring.
- Memory-saving mode limits retained capture resolution; full-resolution mode preserves source pixels and may use substantially more memory.
- OLED protection combines a black background, limited brightness, drift, size variation, and full-black rest periods. Never claim that the application guarantees prevention of burn-in.
- Chinese and English are built in. New user-facing strings must be translated in both language packs and remain available to both editions.
- The full and native editions keep separate settings files so users can run them side by side.

## Engineering priorities

- Preserve the Windows 11 Settings-like visual direction and usable high-DPI behavior.
- Keep the native executable self-contained and approximately sub-megabyte. Avoid adding a native dependency until its binary and memory cost is measured and justified.
- Avoid capture-thread-driven repaint storms. Rendering cadence should remain coordinated by the overlay/UI timer so monitored content does not flicker.
- During native window resizing, batch child layout updates by parent. Do not replace the current per-parent `DeferWindowPos` approach with many independent moves.
- Use native text controls and absolute font sizing where needed to prevent lower-glyph clipping at high DPI.
- Favor bounded frame ownership and reuse over extra image copies. Verify both memory-saving and full-resolution paths when changing capture or filters.
- Keep settings backward compatible: add defaults and normalization for new fields in both models before reading older settings files.

## Implement and verify

1. Trace the requested behavior from UI/settings through capture, filtering, layout, and overlay output.
2. Add or update focused tests in both implementations where the behavior can be tested deterministically.
3. For UI changes, run the actual executable and visually check every affected page at the default size and after resizing. Check Chinese glyph baselines, long English text, focus states, and high-DPI scaling.
4. For capture or rendering changes, test a moving source window and multiple simultaneous windows. Check for flicker, stale frames, unexpected restarts, and memory growth.
5. Run the smallest relevant checks during iteration, then the complete checks for every edition changed.

Full edition checks:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest -q
```

If `.venv` is missing, run `scripts/setup.ps1`. If the machine's global pytest temporary directory has stale permissions, use an ignored directory under `build` as `--basetemp`; do not weaken the tests.

Native edition checks:

```powershell
.\scripts\test-native.ps1
.\scripts\build-native.ps1
```

The native build script runs packaged binary, startup, capture, and UI smoke tests. Use its `-HeadlessSmoke` switch only on a hosted runner without an interactive desktop.

Full packaged checks when packaging or release behavior changes:

```powershell
.\scripts\build.ps1
.\dist\SideScreenUtil.exe --smoke-test
.\dist\SideScreenUtil.exe --capture-smoke-test
```

## Finish the task

- Review `git diff --check` and `git status`.
- Report which editions changed, the checks actually run, and any parity gap that remains.
- Do not push, tag, publish a Release, or mutate GitHub merely because local work is complete. Perform those actions only when the user explicitly requests them.
- When release work is authorized, preserve the single-tag, dual-executable release model described in [references/release.md](references/release.md).
