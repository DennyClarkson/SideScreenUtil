$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ReleaseExe = Join-Path $ProjectRoot "dist\SideScreenUtil.exe"
$PreviousExe = Join-Path $ProjectRoot "dist\SideScreenUtil.previous.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Virtual environment not found. Run .\scripts\setup.ps1 first."
}
$RunningRelease = Get-Process -Name "SideScreenUtil" -ErrorAction SilentlyContinue | Where-Object {
    try {
        $_.Path -eq $ReleaseExe
    } catch {
        $false
    }
}
if ($RunningRelease) {
    throw "SideScreenUtil is running from dist. Close it before rebuilding."
}
$BuildSucceeded = $false
Push-Location $ProjectRoot
try {
    if (Test-Path -LiteralPath $PreviousExe) {
        Remove-Item -LiteralPath $PreviousExe
    }
    if (Test-Path -LiteralPath $ReleaseExe) {
        Move-Item -LiteralPath $ReleaseExe -Destination $PreviousExe
    }
    & $VenvPython -m PyInstaller --noconfirm --clean SideScreenUtil.spec
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed with exit code $LASTEXITCODE."
    }
    $BuildSucceeded = $true
} catch {
    if (-not (Test-Path -LiteralPath $ReleaseExe) -and (Test-Path -LiteralPath $PreviousExe)) {
        Move-Item -LiteralPath $PreviousExe -Destination $ReleaseExe
    }
    throw
} finally {
    if ($BuildSucceeded -and (Test-Path -LiteralPath $PreviousExe)) {
        Remove-Item -LiteralPath $PreviousExe
    }
    Pop-Location
}
