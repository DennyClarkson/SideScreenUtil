$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Toolchain = Join-Path $env:USERPROFILE ".rustup\toolchains\stable-x86_64-pc-windows-gnullvm"
$LlvmMingw = Join-Path $env:USERPROFILE ".cache\sidescreenutil-toolchains\llvm-mingw-20260616-ucrt-x86_64"
$Cargo = Join-Path $Toolchain "bin\cargo.exe"
$Linker = Join-Path $LlvmMingw "bin\x86_64-w64-mingw32-clang.exe"
if (-not (Test-Path -LiteralPath $Cargo) -or -not (Test-Path -LiteralPath $Linker)) {
    throw "The native Rust/LLVM-MinGW toolchain is missing."
}
$env:CARGO_TARGET_X86_64_PC_WINDOWS_GNULLVM_LINKER = $Linker
$env:CARGO_TARGET_X86_64_PC_WINDOWS_GNULLVM_RUSTFLAGS = "-C target-feature=+crt-static"
$env:RC_x86_64_pc_windows_gnullvm = Join-Path $LlvmMingw "bin\llvm-rc.exe"
$env:PATH = "$(Join-Path $Toolchain 'bin');$(Join-Path $LlvmMingw 'bin');$env:PATH"
Push-Location (Join-Path $ProjectRoot "native")
try {
    & $Cargo fmt -- --check
    if ($LASTEXITCODE -ne 0) { throw "cargo fmt failed." }
    & $Cargo test --target x86_64-pc-windows-gnullvm
    if ($LASTEXITCODE -ne 0) { throw "cargo test failed." }
} finally {
    Pop-Location
}
