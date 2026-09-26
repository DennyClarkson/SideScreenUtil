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
$OriginalBuildPath = $env:PATH
Push-Location $ProjectRoot
try {
    # Resolve DLLs from this Python installation and Windows, not unrelated
    # tools on PATH (e.g. Poppler's ICU is incompatible with Qt's Windows ICU).
    $PythonBase = & $VenvPython -c "import sys; print(sys.base_prefix)"
    if ($LASTEXITCODE -ne 0) { throw "Unable to locate the Python runtime." }
    $env:PATH = @(
        (Split-Path -Parent $VenvPython),
        $PythonBase,
        (Join-Path $PythonBase 'DLLs'),
        (Join-Path $env:SystemRoot 'System32'),
        $env:SystemRoot
    ) -join [IO.Path]::PathSeparator
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
    $env:PATH = $OriginalBuildPath
    if ($BuildSucceeded -and (Test-Path -LiteralPath $PreviousExe)) {
        Remove-Item -LiteralPath $PreviousExe
    }
    Pop-Location
}
