# Build Promptbox.exe with the app icon embedded.
#   powershell -ExecutionPolicy Bypass -File build_exe.ps1
#
# Output: dist\Promptbox.exe  (windowed, no console, no Python needed to run it)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py   = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "No .venv. Run: python -m venv .venv"; exit 1 }

$icon  = Join-Path $root "assets\promptbox.ico"
$ui    = (Join-Path $root "promptbox\ui\index.html") + ";promptbox/ui"
$entry = Join-Path $root "run.py"

& $py -m pip install --quiet pyinstaller
& $py -m PyInstaller `
    --noconfirm --clean --onefile --windowed `
    --name Promptbox `
    --icon $icon `
    --add-data $ui `
    --collect-all webview `
    --paths $root `
    $entry

$exe = Join-Path $root "dist\Promptbox.exe"
if (Test-Path $exe) {
  Write-Host "built: $exe" -ForegroundColor Green
} else {
  Write-Error "build failed"
}
