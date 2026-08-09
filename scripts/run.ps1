$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Virtual environment not found. Run .\scripts\setup.ps1 first."
}
& $VenvPython -m sidescreen
if ($LASTEXITCODE -ne 0) {
    throw "SideScreenUtil failed with exit code $LASTEXITCODE."
}
