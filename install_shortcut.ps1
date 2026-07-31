# Creates a Desktop shortcut for Promptbox.
#   powershell -ExecutionPolicy Bypass -File install_shortcut.ps1
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyw  = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pyw)) {
  Write-Host "No .venv found. Run this first:" -ForegroundColor Yellow
  Write-Host "  python -m venv .venv"
  Write-Host "  .venv\Scripts\pip install -r requirements.txt"
  exit 1
}
$ico = Join-Path $root "assets\promptbox.ico"
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "Promptbox.lnk"

$ws = New-Object -ComObject WScript.Shell
$s  = $ws.CreateShortcut($lnk)
$s.TargetPath       = $pyw          # pythonw = no console window
$s.Arguments        = "-m promptbox"
$s.WorkingDirectory = $root
$s.IconLocation     = "$ico,0"
$s.Description      = "Promptbox - local image generation"
$s.Save()
Write-Host "Shortcut created on your Desktop." -ForegroundColor Green
