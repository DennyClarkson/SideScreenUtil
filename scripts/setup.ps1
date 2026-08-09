param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Invoke-Checked {
    param(
        [string]$Executable,
        [string[]]$CommandArgs
    )
    & $Executable @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Executable $CommandArgs"
    }
}

if (-not $PythonExe) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCommand) {
        $PythonExe = $PythonCommand.Source
    }
}

if ($PythonExe) {
    Invoke-Checked $PythonExe @("-m", "venv", (Join-Path $ProjectRoot ".venv"))
} else {
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $PyLauncher) {
        throw "Python was not found. Pass -PythonExe 'C:\path\to\python.exe'."
    }
    Invoke-Checked $PyLauncher.Source @("-3", "-m", "venv", (Join-Path $ProjectRoot ".venv"))
}

Invoke-Checked $VenvPython @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Checked $VenvPython @("-m", "pip", "install", "-e", "$ProjectRoot[dev]")
Write-Host "Setup complete. Run: .\scripts\run.ps1"
