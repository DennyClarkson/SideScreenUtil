# Build, CI, and dual-edition releases

Read this reference for packaging, CI, versioning, tagging, or GitHub Release work.

## Release invariant

One product version and one Git tag publish both maintained Windows editions:

- `SideScreenUtil.exe` — full Python/Qt compatibility edition;
- `SideScreenUtil-native.exe` — compact Rust/Win32 edition;
- one `.sha256` file for each executable.

Do not create separate version lines or separate Releases unless the user explicitly changes this policy.

## Version locations

Keep the version identical in:

- `pyproject.toml`;
- `src/sidescreen/__init__.py`;
- `native/Cargo.toml` and its resolved package entry in `native/Cargo.lock`;
- `native/app.rc` file and product metadata.

The tag must be `v<version>`. `.github/workflows/release.yml` rejects a tag that differs from either project manifest.

## Local release validation

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest -q
.\scripts\test-native.ps1
.\scripts\build.ps1
.\dist\SideScreenUtil.exe --smoke-test
.\dist\SideScreenUtil.exe --capture-smoke-test
.\scripts\build-native.ps1
```

`build-native.ps1` builds the statically linked `x86_64-pc-windows-gnullvm` executable, verifies that `libunwind.dll` is not imported, runs four smoke modes, copies the executable to `dist`, and writes its checksum. Prefer the script over reconstructing its compiler environment manually.

The compact build depends on the Rust gnullvm toolchain and LLVM-MinGW. The current scripts and release workflow agree on the LLVM-MinGW release and cache path. If upgrading the toolchain bundle, update `scripts/build-native.ps1`, `scripts/test-native.ps1`, and `.github/workflows/release.yml` together, then verify executable size and imports again.

## CI behavior

`.github/workflows/ci.yml` runs two Windows jobs on `main` and pull requests:

- Python lint, tests, optimized packaging, packaged smoke tests, and artifact upload;
- Rust formatting, tests, MSVC debug/release builds, headless-safe native smoke, and artifact upload.

The CI native artifact is a diagnostic MSVC build. The GitHub Release uses the smaller statically linked gnullvm build produced by `build-native.ps1`.

`.github/workflows/release.yml` runs on `v*` tag pushes. It verifies cross-edition versions, tests both implementations, builds both executables, writes both checksums, uploads one workflow artifact, and creates the GitHub Release.

## Publishing procedure

Publishing changes GitHub state. Only proceed when the user explicitly requests a release.

1. Ensure the intended commit is on `main`, local status has no task-related changes, and the main-branch CI is green.
2. Confirm the tag does not already exist locally or remotely.
3. Create and push an annotated `v<version>` tag.
4. Wait for the Release workflow to finish. Do not declare success while it is merely queued or running.
5. Inspect the resulting Release and confirm all four assets are present and it is neither draft nor prerelease unless requested.
6. Download both executables and checksum files from GitHub and independently verify both SHA-256 values.
7. Report the Release URL, asset names and sizes, CI result, and checksum verification result.

Do not upload locally built binaries as a silent fallback after an automated release failure. Diagnose and fix the workflow or clearly ask the user before changing the release method.
