# SideScreenUtil compact native edition

The native Windows edition of SideScreenUtil keeps the existing workflow and protection features while replacing Python, Qt, and NumPy with Rust, Win32 controls, Windows Graphics Capture, and a compact CPU filter pipeline. It is released and maintained in parallel with the full Python/Qt edition.

## Test the local build

Run:

```powershell
.\dist\SideScreenUtil-native.exe
```

The native edition stores its settings separately in `%APPDATA%\SideScreenUtil\settings-native.json`, so it does not overwrite settings from the Python/Qt edition.

The single executable includes its icon, Chinese and English translations, and all runtime code. No adjacent DLLs or asset folders are required.

## Included behavior

- Start with no selected windows for a black-only secondary display.
- Monitor and switch multiple windows while the mode is active.
- Use source-relative, grid, horizontal, vertical, or manual layouts.
- Press `Ctrl+Alt+L` to drag and resize the layout on the target display.
- Apply original, grayscale, monochrome, hue-cycling, inner-contour, and cycling inner-contour filters.
- Adjust brightness, contour parameters, canvas size, drift, size variation, black rests, FPS, and the full-resolution switch.
- Reveal the normal desktop immediately when the pointer enters the target display.
- Keep running in the notification area when the control window is closed.
- Optionally start with Windows and launch directly into the notification area.
- Show version, edition, platform, and license information on the Settings page.
- Prefer Windows Graphics Capture and fall back to `PrintWindow` when WGC cannot start.
- Discover and embed every JSON language file in `assets/i18n` during compilation.

## Measured local build

- Executable: approximately 0.6 MiB
- Idle private memory: approximately 3.5 MiB
- Idle working set: approximately 23 MiB

Memory usage increases with the number and resolution of captured windows. The one-megapixel-per-window switch remains enabled by default.

## Developer checks

```powershell
.\scripts\test-native.ps1
.\scripts\build-native.ps1
```

The build script creates `dist\SideScreenUtil-native.exe`, runs four packaged smoke tests, verifies that no `libunwind.dll` is required, and writes a SHA-256 checksum next to the executable. CI can pass `-HeadlessSmoke` to run the environment-safe binary check on a hosted runner.
