$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Toolchain = Join-Path $env:USERPROFILE ".rustup\toolchains\stable-x86_64-pc-windows-gnullvm"
$LlvmMingw = Join-Path $env:USERPROFILE ".cache\sidescreenutil-toolchains\llvm-mingw-20260616-ucrt-x86_64"
$Cargo = Join-Path $Toolchain "bin\cargo.exe"
$Rustc = Join-Path $Toolchain "bin\rustc.exe"
if (-not (Test-Path -LiteralPath $Cargo) -or -not (Test-Path -LiteralPath $Rustc)) {
    throw "The Rust gnullvm toolchain is missing. Run rustup toolchain install stable-x86_64-pc-windows-gnullvm --profile minimal."
}
$Linker = Join-Path $LlvmMingw "bin\x86_64-w64-mingw32-clang.exe"
if (-not (Test-Path -LiteralPath $Linker)) {
    throw "LLVM-MinGW is missing from the SideScreenUtil toolchain cache."
}
$env:CARGO_TARGET_X86_64_PC_WINDOWS_GNULLVM_LINKER = $Linker
$env:CARGO_TARGET_X86_64_PC_WINDOWS_GNULLVM_RUSTFLAGS = "-C target-feature=+crt-static"
$env:RC_x86_64_pc_windows_gnullvm = Join-Path $LlvmMingw "bin\llvm-rc.exe"
$env:PATH = "$(Join-Path $Toolchain 'bin');$(Join-Path $LlvmMingw 'bin');$env:PATH"
Push-Location (Join-Path $ProjectRoot "native")
try {
    & $Cargo build --release --target x86_64-pc-windows-gnullvm
    if ($LASTEXITCODE -ne 0) {
        throw "Native build failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}

$BuiltExe = Join-Path $ProjectRoot "native\target\x86_64-pc-windows-gnullvm\release\sidescreenutil-native.exe"
$ReadObj = Join-Path $LlvmMingw "bin\llvm-readobj.exe"
$Imports = & $ReadObj --coff-imports $BuiltExe
if ($Imports -match "(?i)libunwind\.dll") {
    throw "The native executable unexpectedly depends on libunwind.dll."
}

foreach ($Argument in "--smoke-test", "--capture-smoke-test", "--ui-smoke-test") {
    $Process = Start-Process -FilePath $BuiltExe -ArgumentList $Argument -Wait -PassThru
    if ($Process.ExitCode -ne 0) {
        throw "Native smoke test '$Argument' failed with exit code $($Process.ExitCode)."
    }
}

$Dist = Join-Path $ProjectRoot "dist"
New-Item -ItemType Directory -Path $Dist -Force | Out-Null
$OutputExe = Join-Path $Dist "SideScreenUtil-native.exe"
Copy-Item -LiteralPath $BuiltExe -Destination $OutputExe -Force
$Hash = (Get-FileHash -LiteralPath $OutputExe -Algorithm SHA256).Hash.ToLowerInvariant()
$ChecksumPath = "$OutputExe.sha256"
Set-Content -LiteralPath $ChecksumPath -Value "$Hash  SideScreenUtil-native.exe" -Encoding ascii
$Size = (Get-Item -LiteralPath $OutputExe).Length
Write-Host "Native build ready: $OutputExe"
Write-Host ("Size: {0:N0} bytes ({1:N3} MiB)" -f $Size, ($Size / 1MB))
Write-Host "SHA-256: $Hash"
