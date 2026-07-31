# Capture the Promptbox window to a PNG.
#   powershell -ExecutionPolicy Bypass -File assets\capture.ps1 -Out assets\screenshot.png
#
# Uses PrintWindow(PW_RENDERFULLCONTENT) so the window renders itself into the
# bitmap. CopyFromScreen would capture whatever happens to sit on top of it.
param([string]$Out = "assets\screenshot.png", [string]$Title = "Promptbox")

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(
      IntPtr hwnd, int attr, out RECT r, int size);
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

$proc = Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -eq $Title } | Select-Object -First 1
if (-not $proc) { Write-Error "No window titled '$Title'. Launch the app first."; exit 1 }
$h = $proc.MainWindowHandle

[Win]::ShowWindow($h, 9) | Out-Null
[Win]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 1400

$r = New-Object Win+RECT
[Win]::DwmGetWindowAttribute($h, 9, [ref]$r, 16) | Out-Null   # EXTENDED_FRAME_BOUNDS
$w  = $r.Right - $r.Left
$ht = $r.Bottom - $r.Top
if ($w -le 0 -or $ht -le 0) { Write-Error "Bad window bounds ($w x $ht)"; exit 1 }

$bmp = New-Object System.Drawing.Bitmap $w, $ht
$g   = [System.Drawing.Graphics]::FromImage($bmp)
$dc  = $g.GetHdc()
$ok  = [Win]::PrintWindow($h, $dc, 2)      # 2 = PW_RENDERFULLCONTENT
$g.ReleaseHdc($dc)
$g.Dispose()
if (-not $ok) { Write-Warning "PrintWindow returned false; image may be blank." }

$root = Split-Path -Parent $PSScriptRoot
$full = if ([System.IO.Path]::IsPathRooted($Out)) { $Out } else { Join-Path $root $Out }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $full) | Out-Null
$bmp.Save($full, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "saved $full ($w x $ht)"
