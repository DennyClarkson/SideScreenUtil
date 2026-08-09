$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Virtual environment not found. Run .\scripts\setup.ps1 first."
}
Push-Location $ProjectRoot
try {
    & $VenvPython -m PyInstaller --noconfirm --clean --windowed --onefile --optimize 2 --name SideScreenUtil --icon assets\sidescreen.ico --add-data "assets\sidescreen-logo-app.png;assets" --add-data "assets\sidescreen.ico;assets" --add-data "assets\i18n;assets\i18n" --add-binary "src\sidescreen\native\windows_capture.pyd;sidescreen\native" --add-data "src\sidescreen\native\WINDOWS_CAPTURE_LICENSE.txt;licenses" --exclude-module cv2 --exclude-module windows_capture --exclude-module PySide6.QtNetwork --exclude-module numpy.testing --exclude-module tkinter --exclude-module unittest --exclude-module pydoc --exclude-module doctest src\sidescreen\app.py
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
