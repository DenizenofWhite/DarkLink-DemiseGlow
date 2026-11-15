# Dark Link and Demise Glow - installer window (Windows). Started by Install.bat (hidden console).
# Builds the mod from the player's own game files by running install.py, and can switch options or uninstall.
# -Test runs the same steps without the window (for automated checks):
#   Installer.ps1 -Test -Action state|install|uninstall -Mode game|emulator -Game <dir> | -Romfs <dir> -Load <dir>
#                 [-Look gear|full|none] [-Glow red|stock|off] [-AstcZip <astcenc zip>]
param(
    [switch]$Test,
    [ValidateSet('state', 'install', 'uninstall')][string]$Action = 'state',
    [ValidateSet('game', 'emulator')][string]$Mode = 'game',
    [string]$Game, [string]$Romfs, [string]$Load,
    [ValidateSet('gear', 'full', 'none')][string]$Look = 'gear',
    [ValidateSet('red', 'stock', 'off')][string]$Glow = 'red',
    [string]$AstcZip
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Title = 'Dark Link and Demise Glow'
$Version = '1.1.0'
$ModName = 'DarkLink-DemiseGlow'
$TitleId = '0400486024DEC000'
$AstcPage = 'https://github.com/ARM-software/astc-encoder/releases/tag/5.7.1'
$AstcUrl = 'https://github.com/ARM-software/astc-encoder/releases/download/5.7.1/astcenc-5.7.1-windows-x64.zip'
$AstcHashes = @{                                  # ARM's published SHA-256 for astcenc 5.7.1
    '117ed7cc2b0cc4f3d5774eaa1bde3a2ba75695c2f490e84e4a08d1726c963db8' = 'astcenc-5.7.1-windows-x64.zip'
    '2d8f4084fd2d5d88e5caca1c6c1fe6916f053510b26ec0be0bf12bef9ffe99dd' = 'astcenc-5.7.1-windows-arm64.zip'
}
$PythonWinget = 'Python.Python.3.14'
$IssueUrl = 'https://github.com/DenizenofWhite/DarkLink-DemiseGlow/issues/new'
$SettingsFile = Join-Path $Here 'installer-settings.json'

# ---- logic (shared by the window and -Test) -------------------------------------------------------------------------
function Test-Python([string]$exe) {
    if (-not $exe -or -not (Test-Path -LiteralPath $exe) -or $exe -like '*\WindowsApps\*') { return $null }
    try {
        $v = & $exe -I -c "import sys, compression.zstd; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v) { return ("$v").Trim() }
    } catch { }
    return $null
}

function Find-Python([string]$saved) {
    $cands = New-Object System.Collections.Generic.List[string]
    if ($saved) { $cands.Add($saved) }
    Get-ChildItem "$env:LOCALAPPDATA\*Builder\versions\*\*\tools\python\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | ForEach-Object { $cands.Add($_.FullName) }
    Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | ForEach-Object { $cands.Add($_.FullName) }
    foreach ($n in 'python', 'python3') {
        $c = Get-Command $n -ErrorAction SilentlyContinue
        if ($c) { $cands.Add($c.Source) }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try { $p = & py -3.14 -c "import sys; print(sys.executable)" 2>$null; if ($LASTEXITCODE -eq 0) { $cands.Add(("$p").Trim()) } } catch { }
    }
    foreach ($e in $cands) { if (Test-Python $e) { return $e } }
    return $null
}

function Find-Astcenc {
    $d = Join-Path $Here 'astcenc'
    if (-not (Test-Path $d)) { return $null }
    foreach ($n in 'astcenc-avx2.exe', 'astcenc-sse4.1.exe', 'astcenc-sse2.exe', 'astcenc-neon.exe', 'astcenc.exe') {
        $f = Get-ChildItem $d -Recurse -Filter $n -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($f) { return $f.FullName }
    }
    return $null
}

function Install-AstcencZip([string]$zip) {
    $h = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLower()
    if (-not $AstcHashes.ContainsKey($h)) {
        throw "That file is not ARM's astcenc 5.7.1 for Windows (its fingerprint doesn't match). Download astcenc-5.7.1-windows-x64.zip from the ARM page."
    }
    Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $Here 'astcenc') -Force
    return $AstcHashes[$h]
}

function Get-AstcencOnline {
    $tmp = Join-Path $env:TEMP 'astcenc-5.7.1-windows-x64.zip'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $AstcUrl -OutFile $tmp -UseBasicParsing
    try { return Install-AstcencZip $tmp } finally { Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue }
}

function Get-ModDir([string]$mode, [string]$game, [string]$load) {
    if ($mode -eq 'game') { if ($game) { return Join-Path (Join-Path $game 'mods') $ModName } }
    elseif ($load) { return Join-Path (Join-Path $load $TitleId) $ModName }
    return $null
}

function Get-AddonText([string]$modDir) {
    # add-ons (other DenizenofWhite mods) merged into this one keep a note in <mod>\addons
    if (-not $modDir) { return '' }
    $t = ''
    foreach ($n in Get-ChildItem -LiteralPath (Join-Path $modDir 'addons') -Filter *.json -ErrorAction SilentlyContinue) {
        try { $t += ' + ' + (Get-Content -LiteralPath $n.FullName -Raw | ConvertFrom-Json).title } catch { }
    }
    return $t
}

function Get-InstalledState([string]$modDir) {
    if (-not $modDir -or -not (Test-Path -LiteralPath $modDir)) { return $null }
    $j = Join-Path $modDir 'install.json'
    if (Test-Path -LiteralPath $j) { return (Get-Content -LiteralPath $j -Raw | ConvertFrom-Json) }
    return [pscustomobject]@{ version = '?'; look = '?'; glow = '?' }
}

function Get-GameProcess([string]$game) {
    if (-not $game) { return $null }
    $g = (Resolve-Path -LiteralPath $game -ErrorAction SilentlyContinue)
    if (-not $g) { return $null }
    $g = $g.Path.TrimEnd('\') + '\'
    Get-Process -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -and $_.Path.StartsWith($g, [StringComparison]::OrdinalIgnoreCase) } catch { $false }
    } | Select-Object -First 1
}

function Get-InstallArgs([string]$action, [string]$mode, [string]$game, [string]$romfs, [string]$load,
                         [string]$look, [string]$glow, [string]$astcenc) {
    $a = @('-u', '-I', (Join-Path $Here 'install.py'))
    if ($mode -eq 'game') { $a += @('--hookshot', $game.TrimEnd('\')) }
    else { $a += @('--romfs', $romfs.TrimEnd('\'), '--emulator-load', $load.TrimEnd('\')) }
    if ($action -eq 'uninstall') { $a += '--uninstall' }
    else {
        $a += @('--look', $look, '--glow', $glow)
        if ($astcenc) { $a += @('--astcenc', $astcenc) }
    }
    return $a
}

function Join-Args([string[]]$a) {
    ($a | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
}

function Start-Proc([string]$exe, [string[]]$argv) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.Arguments = Join-Args $argv
    $psi.WorkingDirectory = $Here
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    return [System.Diagnostics.Process]::Start($psi)
}

function Test-Inputs([string]$action, [string]$mode, [string]$game, [string]$romfs, [string]$load) {
    if ($mode -eq 'game') {
        if (-not $game -or -not (Test-Path -LiteralPath (Join-Path $game 'romfs'))) {
            return "Choose your Longshot or Hookshot folder (the one that contains 'romfs' and 'mods')."
        }
        if (Get-GameProcess $game) { return 'The game is running. Close it first, then try again.' }
    } else {
        if ($action -ne 'uninstall' -and (-not $romfs -or -not (Test-Path -LiteralPath $romfs))) {
            return "Choose the 'romfs' folder of your own game dump."
        }
        if (-not $load -or -not (Test-Path -LiteralPath $load)) { return "Choose your emulator's 'load' folder." }
    }
    return $null
}

# ---- -Test: the same steps without the window ------------------------------------------------------------------------
if ($Test) {
    if ($AstcZip) {
        try { "astcenc zip: installed $(Install-AstcencZip $AstcZip) (fingerprint OK)" } catch { "astcenc zip REFUSED: $_" }
    }
    $py = Find-Python $null
    $ast = Find-Astcenc
    $mod = Get-ModDir $Mode $Game $Load
    "python: $py ($(Test-Python $py))"
    "astcenc: $ast"
    "mod folder: $mod"
    "installed before: $((Get-InstalledState $mod) | ConvertTo-Json -Compress)"
    if ($Action -ne 'state') {
        $err = Test-Inputs $Action $Mode $Game $Romfs $Load
        if ($err) { "REFUSED: $err"; exit 2 }
        if (-not $py) { 'REFUSED: no Python 3.14'; exit 2 }
        $p = Start-Proc $py (Get-InstallArgs $Action $Mode $Game $Romfs $Load $Look $Glow $ast)
        $out = $p.StandardOutput.ReadToEndAsync(); $er = $p.StandardError.ReadToEndAsync()
        $p.WaitForExit()
        $out.Result; $er.Result
        "exit: $($p.ExitCode)"
        "installed after: $((Get-InstalledState $mod) | ConvertTo-Json -Compress)"
        exit $p.ExitCode
    }
    exit 0
}

# ---- the window -------------------------------------------------------------------------------------------------------
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
try {
# Tell Windows this window handles high-DPI screens itself (sharp text at 125-200 % scaling instead of a stretched,
# blurry bitmap). Layout below is in 96-DPI units; AutoScaleMode Dpi scales it to the screen.
Add-Type -Namespace DLD -Name Dpi -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
[void][DLD.Dpi]::SetProcessDPIAware()
[System.Windows.Forms.Application]::EnableVisualStyles()
$Clr = @{
    bg = [System.Drawing.Color]::FromArgb(18, 13, 13); panel = [System.Drawing.Color]::FromArgb(30, 22, 22)
    text = [System.Drawing.Color]::FromArgb(248, 244, 240); muted = [System.Drawing.Color]::FromArgb(205, 186, 178)
    red = [System.Drawing.Color]::FromArgb(150, 18, 22); red2 = [System.Drawing.Color]::FromArgb(196, 34, 30)
    ember = [System.Drawing.Color]::FromArgb(255, 132, 60); ok = [System.Drawing.Color]::FromArgb(140, 228, 150)
    bad = [System.Drawing.Color]::FromArgb(240, 96, 84); log = [System.Drawing.Color]::FromArgb(255, 176, 128)
}

$HdrFrames = 60; $HdrTick = 50        # header animation: 60 frames x 50 ms = one seamless 3-second loop
function New-HeaderImage([int]$w, [int]$h, [single]$scale = 1, [double]$phase = 0) {
    # Original art, drawn here: a glowing corrupted blade giving off energy (no game assets). $phase (0..1) is the
    # position in the animation loop: the glow pulses, a sheen runs along the blade, embers rise, sway and fade.
    $bmp = New-Object System.Drawing.Bitmap ([int]($w * $scale)), ([int]($h * $scale))
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.ScaleTransform($scale, $scale)
    $g.SmoothingMode = 'AntiAlias'; $g.TextRenderingHint = 'AntiAlias'
    $rect = New-Object System.Drawing.Rectangle 0, 0, $w, $h
    $bgb = New-Object System.Drawing.Drawing2D.LinearGradientBrush($rect, [System.Drawing.Color]::FromArgb(14, 9, 9), [System.Drawing.Color]::FromArgb(46, 8, 10), 0.0)
    $g.FillRectangle($bgb, $rect)
    $rnd = New-Object System.Random 7
    for ($i = 0; $i -lt 14; $i++) {                 # soft red smoke
        $cx = 300 + $rnd.Next(0, 300); $cy = $rnd.Next(10, $h - 10); $r = $rnd.Next(30, 80)
        $sb = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(10, 200, 30, 25))
        $g.FillEllipse($sb, $cx - $r, $cy - $r, 2 * $r, 2 * $r)
    }
    $st = $g.Save()
    $g.TranslateTransform(396, 66); $g.RotateTransform(-9)
    $blade = New-Object System.Drawing.Drawing2D.GraphicsPath   # bold teeth on both edges, staggered
    $top = @(@(0, -8), @(34, -8), @(48, -17), @(52, -8), @(84, -7.5), @(100, -16), @(104, -7), @(136, -6.5), @(150, -14), @(154, -6), @(176, -5))
    $bot = @(@(176, 5), @(160, 6), @(156, 13), @(142, 6), @(118, 6.5), @(114, 15), @(98, 7), @(70, 7.5), @(66, 16), @(50, 8), @(0, 8))
    $pts = New-Object System.Collections.Generic.List[System.Drawing.PointF]
    foreach ($p in $top) { $pts.Add((New-Object System.Drawing.PointF $p[0], $p[1])) }
    $pts.Add((New-Object System.Drawing.PointF 204, 0))
    foreach ($p in $bot) { $pts.Add((New-Object System.Drawing.PointF $p[0], $p[1])) }
    $blade.AddPolygon($pts.ToArray())
    $pulse = 0.5 - 0.5 * [Math]::Cos(4 * [Math]::PI * $phase)      # glow breathes twice per loop
    for ($k = 7; $k -ge 1; $k--) {                  # glow
        $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb([int](11 + 13 * $pulse), 230, 40, 25)), ((3 * $k + 2) * (1 + 0.2 * $pulse))
        $pen.LineJoin = 'Round'; $g.DrawPath($pen, $blade)
    }
    $bb = New-Object System.Drawing.Drawing2D.LinearGradientBrush((New-Object System.Drawing.PointF 0, 0), (New-Object System.Drawing.PointF 196, 0),
        [System.Drawing.Color]::FromArgb(150, 14, 18), [System.Drawing.Color]::FromArgb(255, 150, 70))
    $g.FillPath($bb, $blade)
    $sx = -50 + 300 * $phase                        # sheen: a hot band running from the guard to past the tip
    $sr = New-Object System.Drawing.RectangleF ([single]($sx - 26)), -20, 52, 40
    $sh = New-Object System.Drawing.Drawing2D.LinearGradientBrush($sr, [System.Drawing.Color]::Transparent, [System.Drawing.Color]::Transparent, 0.0)
    $cb = New-Object System.Drawing.Drawing2D.ColorBlend 3
    $cb.Colors = [System.Drawing.Color[]]@([System.Drawing.Color]::FromArgb(0, 255, 220, 180), [System.Drawing.Color]::FromArgb(185, 255, 236, 205), [System.Drawing.Color]::FromArgb(0, 255, 220, 180))
    $cb.Positions = [single[]]@(0, 0.5, 1); $sh.InterpolationColors = $cb
    $g.SetClip($blade); $g.FillRectangle($sh, $sr); $g.ResetClip()
    $g.DrawLine((New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(140, 70, 0, 0)), 1.5), 6, 0, 160, 0)
    $g.DrawPath((New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(170, 255, 205, 160)), 0.8), $blade)
    $gp = @(                                          # crossguard: arms curve up toward the blade, a spike on each outer curve
        @(-2, -9), @(6, -16), @(16, -30), @(9, -27), @(2, -23), @(-4, -27), @(-6, -20), @(-12, -11),
        @(-12, 11), @(-6, 20), @(-4, 27), @(2, 23), @(9, 27), @(16, 30), @(6, 16), @(-2, 9))
    $guard = [System.Drawing.PointF[]]@($gp | ForEach-Object { New-Object System.Drawing.PointF $_[0], $_[1] })
    $g.FillPolygon((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(34, 26, 28))), $guard)
    $g.DrawPolygon((New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(150, 200, 60, 40)), 1), $guard)
    $g.FillRectangle((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(24, 18, 18))), -56, -4, 42, 8)
    for ($x = -54; $x -lt -16; $x += 5) { $g.DrawLine((New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(70, 120, 30, 30)), 1), $x, -4, ($x + 3), 4) }
    $steel = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(38, 30, 32))        # two-stage pommel + tip
    $rim = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(150, 200, 60, 40)), 1
    $g.FillEllipse($steel, -65, -6.5, 10, 13); $g.DrawEllipse($rim, -65, -6.5, 10, 13)
    $g.FillEllipse($steel, -71, -4, 7, 8); $g.DrawEllipse($rim, -71, -4, 7, 8)
    $tip = [System.Drawing.PointF[]]@((New-Object System.Drawing.PointF -70, -2), (New-Object System.Drawing.PointF -76, 0), (New-Object System.Drawing.PointF -70, 2))
    $g.FillPolygon($steel, $tip); $g.DrawPolygon($rim, $tip)
    $g.Restore($st)
    # Energy leaving the blade. Every particle's state is a function of the loop position, so the loop is seamless.
    # Soft embers: hot core -> red -> dark edge, rising and swaying, shrinking as they fade.
    $er = New-Object System.Random 11
    $cos = [Math]::Cos(-9 * [Math]::PI / 180); $sin = [Math]::Sin(-9 * [Math]::PI / 180)
    $core = @(255, 215, 195); $mid = @(225, 35, 42); $edge = @(70, 0, 6)
    for ($i = 0; $i -lt 30; $i++) {
        $d = 8 + 196 * $er.NextDouble(); $off = $er.NextDouble(); $life = 0.45 + 0.4 * $er.NextDouble()
        $r0 = 4 + 6 * $er.NextDouble(); $seed = 6.28 * $er.NextDouble(); $jit = $er.Next(-5, 6)
        $k = ((($phase - $off) % 1 + 1) % 1) / $life
        if ($k -ge 1) { continue }
        $x = 396 + $d * $cos + 10 * $k + 4 * [Math]::Sin($seed + 7 * $k); $y = 66 + $d * $sin + $jit - 52 * $k
        $r = $r0 * (1 - 0.75 * $k)
        if ($k -lt 0.25) { $q = $k / 0.25; $c0 = $core; $c1 = $mid } else { $q = ($k - 0.25) / 0.75; $c0 = $mid; $c1 = $edge }
        $rgb = 0..2 | ForEach-Object { [int]($c0[$_] + ($c1[$_] - $c0[$_]) * $q) }
        $al = $(if ($k -lt 0.12) { $k / 0.12 } else { 1 - ($k - 0.12) / 0.88 }) * 0.6
        $ep = New-Object System.Drawing.Drawing2D.GraphicsPath
        $ep.AddEllipse([single]($x - $r), [single]($y - $r), [single](2 * $r), [single](2 * $r))
        $pg = New-Object System.Drawing.Drawing2D.PathGradientBrush $ep
        $pg.CenterColor = [System.Drawing.Color]::FromArgb([int](255 * $al), $rgb[0], $rgb[1], $rgb[2])
        $pg.SurroundColors = [System.Drawing.Color[]]@([System.Drawing.Color]::FromArgb(0, $rgb[0], $rgb[1], $rgb[2]))
        $g.FillPath($pg, $ep); $pg.Dispose(); $ep.Dispose()
    }
    for ($i = 0; $i -lt 46; $i++) {                 # bright sparks: faster, once or twice per loop
        $t = $rnd.NextDouble()
        $ex = 372 + 190 * $t * 0.988 + $rnd.Next(-8, 9); $ey = 66 - 30 * $t + $rnd.Next(-6, 10)
        $sz = 1 + $rnd.Next(0, 3); $a = $rnd.Next(110, 240); $gc = $rnd.Next(80, 180)
        $spd = 1 + ($i % 2); $life = 0.5; $off = $er.NextDouble()
        $k = ((($phase * $spd - $off) % 1 + 1) % 1) / $life
        if ($k -ge 1) { continue }
        $fade = [Math]::Sin([Math]::PI * $k)
        $eb = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb([int]($a * $fade), 255, $gc, 40))
        $g.FillEllipse($eb, [single]($ex + 6 * $k), [single]($ey - 40 * $k), $sz, $sz); $eb.Dispose()
    }
    $g.DrawString($Title, (New-Object System.Drawing.Font('Segoe UI Semibold', 19)), (New-Object System.Drawing.SolidBrush $Clr.text), 14, 16)
    $g.DrawString('Builds the mod from your own copy of the game.', (New-Object System.Drawing.Font('Segoe UI', 10)), (New-Object System.Drawing.SolidBrush $Clr.muted), 17, 57)
    $g.DrawString("by DenizenofWhite   v$Version", (New-Object System.Drawing.Font('Segoe UI', 9.5, [System.Drawing.FontStyle]::Italic)), (New-Object System.Drawing.SolidBrush $Clr.ember), 17, 80)
    $g.FillRectangle((New-Object System.Drawing.SolidBrush $Clr.red), 0, ($h - 2), $w, 2)
    $g.Dispose()
    return $bmp
}

$settings = @{}
try { if (Test-Path $SettingsFile) { (Get-Content $SettingsFile -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $settings[$_.Name] = $_.Value } } } catch { }
$script:python = Find-Python $settings['python']
$script:proc = $null; $script:procKind = $null; $script:busy = $false

$f = New-Object System.Windows.Forms.Form
$f.SuspendLayout()
$f.AutoScaleMode = 'None'   # scaled once, by hand, after the layout is built (see below)
$f.Text = "$Title - Installer"
$f.ClientSize = New-Object System.Drawing.Size(600, 800)
$f.FormBorderStyle = 'FixedSingle'; $f.MaximizeBox = $false; $f.StartPosition = 'CenterScreen'
$f.Font = New-Object System.Drawing.Font('Segoe UI', 12)
$f.BackColor = $Clr.bg; $f.ForeColor = $Clr.text

$hdr = New-Object System.Windows.Forms.PictureBox
$hdr.Location = New-Object System.Drawing.Point(0, 0); $hdr.Size = New-Object System.Drawing.Size(600, 110)
$hdr.SizeMode = 'Zoom'
$hdrBig = New-HeaderImage 600 110 2                  # drawn at 2x so it stays crisp when Windows scales the window
$hdr.Image = $hdrBig
$f.Controls.Add($hdr)

function Add-Group($text, $y, $h) {
    $g = New-Object System.Windows.Forms.GroupBox
    $g.Text = $text; $g.ForeColor = $Clr.ember; $g.Location = New-Object System.Drawing.Point(12, $y); $g.Size = New-Object System.Drawing.Size(576, $h)
    $f.Controls.Add($g); return $g
}
function Add-Radio($parent, $text, $x, $y, $w) {
    $r = New-Object System.Windows.Forms.RadioButton
    $r.Text = $text; $r.ForeColor = $Clr.text; $r.UseMnemonic = $false; $r.AutoSize = $true
    $r.Location = New-Object System.Drawing.Point($x, $y)
    $parent.Controls.Add($r); return $r
}
function Style-Button($b, $primary) {
    $b.FlatStyle = 'Flat'; $b.UseMnemonic = $false; $b.ForeColor = $Clr.text; $b.Cursor = 'Hand'
    $b.Font = New-Object System.Drawing.Font('Segoe UI', 10.5)
    if ($primary) { $b.BackColor = $Clr.red; $b.FlatAppearance.BorderColor = $Clr.ember; $b.FlatAppearance.MouseOverBackColor = $Clr.red2 }
    else { $b.BackColor = $Clr.panel; $b.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(110, 40, 40)
           $b.FlatAppearance.MouseOverBackColor = [System.Drawing.Color]::FromArgb(56, 34, 34) }
}
function New-Button($text, $x, $y, $w, $h, $primary) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $text; $b.Location = New-Object System.Drawing.Point($x, $y); $b.Size = New-Object System.Drawing.Size($w, $h)
    Style-Button $b $primary; return $b
}
function Add-PathRow($parent, $label, $y, $value) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $label; $l.ForeColor = $Clr.text; $l.UseMnemonic = $false
    $l.Location = New-Object System.Drawing.Point(12, ($y + 3)); $l.Size = New-Object System.Drawing.Size(150, 20)
    $t = New-Object System.Windows.Forms.TextBox
    $t.Location = New-Object System.Drawing.Point(165, $y); $t.Size = New-Object System.Drawing.Size(310, 23); $t.Text = $value
    $t.BackColor = $Clr.panel; $t.ForeColor = $Clr.text; $t.BorderStyle = 'FixedSingle'
    $b = New-Button 'Browse...' 482 ($y - 1) 80 25 $false
    $b.Add_Click({ $d = New-Object System.Windows.Forms.FolderBrowserDialog; if ($t.Text) { $d.SelectedPath = $t.Text }
                   if ($d.ShowDialog() -eq 'OK') { $t.Text = $d.SelectedPath } }.GetNewClosure())
    $parent.Controls.AddRange(@($l, $t, $b)); return @{ label = $l; box = $t; button = $b }
}
function New-Label($parent, $x, $y, $w, $h) {
    $l = New-Object System.Windows.Forms.Label
    $l.Location = New-Object System.Drawing.Point($x, $y); $l.Size = New-Object System.Drawing.Size($w, $h); $l.UseMnemonic = $false
    $parent.Controls.Add($l); return $l
}

$g1 = Add-Group '2. Your Game' 220 176
$rGame = Add-Radio $g1 'Longshot / Hookshot' 12 22 180
$rEmu = Add-Radio $g1 'Emulator' 200 22 120
$pGame = Add-PathRow $g1 'Game Folder:' 52 $settings['game']
$pRomfs = Add-PathRow $g1 'Game Files (romfs):' 52 $settings['romfs']
$pLoad = Add-PathRow $g1 'Emulator Load Folder:' 84 $settings['load']
$lState = New-Label $g1 12 118 550 48
$lState.Font = New-Object System.Drawing.Font('Segoe UI', 12, [System.Drawing.FontStyle]::Bold)

$g2 = Add-Group '3. Look' 404 104
$rGear = Add-Radio $g2 "Dark Link's Gear (Link's Normal Face)" 12 22 0
$rFull = Add-Radio $g2 "Full Dark Link (Dark Link's Skin and Eyes)" 12 48 0
$rLookNone = Add-Radio $g2 'No Look Change' 12 74 0

$g3 = Add-Group '4. Master Sword Glow' 516 104
$rRed = Add-Radio $g3 'Red Demise Inspired Glow (Corrupted Master Sword)' 12 22 0
$rStock = Add-Radio $g3 'OG Master Sword Glow (Final Battle)' 12 48 0
$rGlowOff = Add-Radio $g3 'No Master Sword Glow (Vanilla)' 12 74 0

$g4 = Add-Group '1. Prerequisites' 120 92
function Add-PrereqRow($y, $name) {
    $n = New-Label $g4 12 ($y + 4) 230 22; $n.Text = $name; $n.ForeColor = $Clr.text
    $s = New-Label $g4 245 ($y + 4) 90 22; $s.Font = New-Object System.Drawing.Font('Segoe UI', 12, [System.Drawing.FontStyle]::Bold)
    $i = New-Button 'Install Prerequisite' 380 $y 184 28 $false
    $g4.Controls.Add($i)
    return @{ status = $s; install = $i; tried = $false }
}
$rowPy = Add-PrereqRow 20 'Python 3.14'
$rowAst = Add-PrereqRow 54 'astcenc 5.7.1 (ARM texture tool)'

$bInstall = New-Button 'Install / Change' 12 630 190 36 $true
$bInstall.Font = New-Object System.Drawing.Font('Segoe UI', 12, [System.Drawing.FontStyle]::Bold)
$bUninstall = New-Button 'Uninstall (Back to Stock)' 210 630 182 36 $false
$bReport = New-Button 'Report a Problem' 400 630 122 36 $false
$bClose = New-Button 'Close' 528 630 60 36 $false
$log = New-Object System.Windows.Forms.TextBox
$log.Multiline = $true; $log.ReadOnly = $true; $log.ScrollBars = 'Vertical'; $log.WordWrap = $true
$log.Location = New-Object System.Drawing.Point(12, 676); $log.Size = New-Object System.Drawing.Size(576, 112)
$log.Font = New-Object System.Drawing.Font('Consolas', 10); $log.BackColor = [System.Drawing.Color]::FromArgb(10, 7, 7)
$log.ForeColor = $Clr.log; $log.BorderStyle = 'FixedSingle'
$f.Controls.AddRange(@($bInstall, $bUninstall, $bReport, $bClose, $log))

function Write-Log($s) { $log.AppendText($s + "`r`n") }
function Get-Mode { if ($rEmu.Checked) { 'emulator' } else { 'game' } }
function Get-Look { if ($rFull.Checked) { 'full' } elseif ($rLookNone.Checked) { 'none' } else { 'gear' } }
function Get-Glow { if ($rStock.Checked) { 'stock' } elseif ($rGlowOff.Checked) { 'off' } else { 'red' } }
function Show-Msg($text, $icon) { [System.Windows.Forms.MessageBox]::Show($text, $Title, 'OK', $icon) | Out-Null }
$Names = @{ gear = "Dark Link's Gear"; full = 'Full Dark Link'; none = 'No Look Change'
            red = 'Red Demise Glow'; stock = 'OG Master Sword Glow'; off = 'No Master Sword Glow' }

function Get-DownloadsDir {
    try { $d = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders').'{374DE290-123F-4565-9164-39C4925E467B}'
          if ($d) { return [Environment]::ExpandEnvironmentVariables($d) } } catch { }
    return Join-Path $env:USERPROFILE 'Downloads'
}
function Test-Prereq([string]$which) {
    # Check Again: look for the prerequisite again; for astcenc also pick up ARM's zip from the Downloads folder.
    if ($which -eq 'python') { $script:python = Find-Python $script:python; Update-View; return [bool]$script:python }
    if (-not (Find-Astcenc)) {
        $zips = foreach ($d in @((Get-DownloadsDir), (Join-Path $env:USERPROFILE 'Downloads')) | Select-Object -Unique) {
            Get-ChildItem -LiteralPath $d -Filter 'astcenc-5.7.1-windows-*.zip' -ErrorAction SilentlyContinue }
        foreach ($z in $zips) {
            try { $n = Install-AstcencZip $z.FullName; Write-Log "astcenc set up from your Downloads folder ($n, ARM fingerprint checked)."; break }
            catch { Write-Log "Skipped $($z.Name): not ARM's genuine file." }
        }
    }
    Update-View
    return [bool](Find-Astcenc)
}

function Show-Manual([string]$which, [string]$why) {
    # When Install Prerequisite fails: what to do by hand, the right download page, and Check Again.
    $m = New-Object System.Windows.Forms.Form
    $m.Text = 'Install by Hand'; $m.ClientSize = New-Object System.Drawing.Size(500, 250); $m.FormBorderStyle = 'FixedDialog'
    $m.MaximizeBox = $false; $m.MinimizeBox = $false; $m.StartPosition = 'CenterParent'; $m.BackColor = $Clr.bg; $m.ForeColor = $Clr.text
    $m.Font = $f.Font
    $t = New-Object System.Windows.Forms.Label
    $t.Location = New-Object System.Drawing.Point(16, 14); $t.Size = New-Object System.Drawing.Size(470, 175); $t.UseMnemonic = $false
    if ($which -eq 'python') {
        $page = 'https://www.python.org/downloads/'
        $t.Text = "Python couldn't be installed automatically$(if ($why) { " ($why)" }).`r`n`r`n" +
                  "1. Click Open Download Page and download the Windows installer for Python 3.14 or newer.`r`n" +
                  "2. Run it. The default options are fine.`r`n" +
                  "3. Click Check Again."
    } else {
        $page = $AstcPage
        $t.Text = "astcenc couldn't be downloaded automatically$(if ($why) { " ($why)" }).`r`n`r`n" +
                  "1. Click Open Download Page and download astcenc-5.7.1-windows-x64.zip to your Downloads folder.`r`n" +
                  "2. Click Check Again. The installer finds it there, checks it's ARM's genuine file and sets it up."
    }
    $b1 = New-Button 'Open Download Page' 16 200 170 34 $true
    $b1.Add_Click({ Start-Process $page }.GetNewClosure())
    $b2 = New-Button 'Check Again' 194 200 120 34 $false
    $b2.Add_Click({ if (Test-Prereq $which) { $m.Close() } else { Show-Msg 'Still not found. Follow the steps above, then click Check Again.' 'Information' } }.GetNewClosure())
    $bx = New-Button 'Close' 404 200 80 34 $false
    $bx.Add_Click({ $m.Close() }.GetNewClosure())
    $m.Controls.AddRange(@($t, $b1, $b2, $bx))
    [void]$m.ShowDialog($f)
}

function Set-Row($row, [bool]$ok) {
    if ($ok) { $row.status.Text = 'Installed'; $row.status.ForeColor = $Clr.ok } else { $row.status.Text = 'Missing'; $row.status.ForeColor = $Clr.bad }
    $row.install.Visible = -not $ok
    $row.install.Text = if ($row.tried) { 'Check Again' } else { 'Install Prerequisite' }
}

function Update-View {
    $emu = $rEmu.Checked
    foreach ($c in $pGame.Values) { $c.Visible = -not $emu }
    foreach ($c in (@($pRomfs.Values) + @($pLoad.Values))) { $c.Visible = $emu }
    $mod = Get-ModDir (Get-Mode) $pGame.box.Text $pLoad.box.Text
    $st = Get-InstalledState $mod
    if ($st) { $lState.Text = "Installed Now: $($Names[$st.look]) + $($Names[$st.glow])$(Get-AddonText $mod) (v$($st.version))"; $lState.ForeColor = $Clr.ok }
    elseif ($mod) { $lState.Text = 'Not installed in this game.'; $lState.ForeColor = $Clr.muted }
    else { $lState.Text = 'Choose your game folder above.'; $lState.ForeColor = $Clr.muted }
    if ($script:S) { $lState.Top = [int]($(if ($emu) { 118 } else { 86 }) * $script:S) }   # no empty gap in Longshot/Hookshot mode
    Set-Row $rowPy ([bool]$script:python)
    Set-Row $rowAst ([bool](Find-Astcenc))
}

function Save-Settings {
    $o = @{ python = $script:python; mode = (Get-Mode); game = $pGame.box.Text; romfs = $pRomfs.box.Text; load = $pLoad.box.Text
            look = (Get-Look); glow = (Get-Glow) }
    try { $o | ConvertTo-Json | Set-Content -LiteralPath $SettingsFile -Encoding UTF8 } catch { }
}

function Set-Busy($busy, $label) {
    if ($busy -and $script:procKind -in 'mod', 'uninstall') {
        if ($script:procKind -eq 'uninstall') { $lState.Text = 'Uninstalling...' }
        else { $lState.Text = "Installing: $($script:pending)..." }
        $lState.ForeColor = $Clr.ember
    }
    # While working, lock the choices WITHOUT greying them out (Windows' grey "disabled" text is unreadable on dark).
    foreach ($r in @($rGame, $rEmu, $rGear, $rFull, $rLookNone, $rRed, $rStock, $rGlowOff)) { $r.AutoCheck = -not $busy }
    foreach ($t in @($pGame.box, $pRomfs.box, $pLoad.box)) { $t.ReadOnly = $busy }
    $script:busy = $busy
    $bInstall.Text = if ($busy) { $label } else { 'Install / Change' }
    if (-not $busy) { $bInstall.BackColor = $Clr.red; Update-View }
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 300
$script:rdOut = $null; $script:rdErr = $null; $script:tick = 0
$timer.Add_Tick({
    if (-not $script:proc) { return }
    $script:tick++
    $bInstall.BackColor = if ($script:tick % 4 -lt 2) { $Clr.red } else { $Clr.red2 }    # pulse while working
    foreach ($k in 'rdOut', 'rdErr') {
        while ($true) {
            $t = Get-Variable -Scope Script -Name $k -ValueOnly
            if (-not $t.IsCompleted -or $null -eq $t.Result) { break }
            Write-Log $t.Result
            $s = if ($k -eq 'rdOut') { $script:proc.StandardOutput } else { $script:proc.StandardError }
            Set-Variable -Scope Script -Name $k -Value $s.ReadLineAsync()
        }
    }
    if ($script:proc.HasExited -and $script:rdOut.IsCompleted -and $null -eq $script:rdOut.Result -and
        $script:rdErr.IsCompleted -and $null -eq $script:rdErr.Result) {
        $code = $script:proc.ExitCode; $kind = $script:procKind
        $script:proc = $null; $timer.Stop()
        if ($kind -eq 'python') { $script:python = Find-Python $null }
        Set-Busy $false
        if ($code -eq 0 -and ($kind -ne 'python' -or $script:python)) {
            if ($kind -eq 'python') { Write-Log '--- Python installed. ---'; Show-Msg 'Python is installed.' 'Information' }
            elseif ($kind -eq 'uninstall') { Write-Log '--- Uninstalled. Your game is back to stock. ---'; Show-Msg 'Uninstalled. Your game is back to stock.' 'Information' }
            else { Write-Log '--- Done. Start the game. ---'; Show-Msg 'Done! Start the game.' 'Information' }
        } else {
            Write-Log "--- Failed (exit $code). See the messages above. ---"
            if ($kind -eq 'python') { $rowPy.tried = $true; Update-View; Show-Manual 'python' "winget exit $code" }
            else { Show-Msg "Something went wrong. Your game was not changed.`r`n`r`nThe messages are in the window. If you want help, click Report a Problem." 'Warning' }
        }
    }
})

function Start-Logged($kind, $label, $exe, $argv) {
    try { $script:proc = Start-Proc $exe $argv } catch { Write-Log "Could not start: $_"; return }
    $script:procKind = $kind
    $script:rdOut = $script:proc.StandardOutput.ReadLineAsync()
    $script:rdErr = $script:proc.StandardError.ReadLineAsync()
    Set-Busy $true $label
    $timer.Start()
}

function Invoke-Action($action) {
    if ($script:busy) { return }
    $mode = Get-Mode
    $err = Test-Inputs $action $mode $pGame.box.Text $pRomfs.box.Text $pLoad.box.Text
    if (-not $err -and -not $script:python -and -not (Test-Prereq 'python')) { $err = 'Python 3.14 is missing: click Install Prerequisite next to it (step 1).' }
    if (-not $err -and $action -eq 'install' -and (Get-Look) -ne 'none' -and -not (Find-Astcenc) -and -not (Test-Prereq 'astcenc')) {
        $err = 'astcenc is missing (the looks need it): click Install Prerequisite next to it (step 1).'
    }
    if (-not $err -and $action -eq 'install' -and (Get-Look) -eq 'none' -and (Get-Glow) -eq 'off') { $err = 'Pick a look or a glow (both are set to no change).' }
    if ($err) { Show-Msg $err 'Information'; return }
    if ($action -eq 'uninstall' -and -not (Get-InstalledState (Get-ModDir $mode $pGame.box.Text $pLoad.box.Text))) {
        Show-Msg 'The mod is not installed in this game, so there is nothing to uninstall.' 'Information'; return
    }
    if ($action -eq 'uninstall') {
        $ok = [System.Windows.Forms.MessageBox]::Show('Remove the mod and put the game back to stock?', 'Uninstall', 'YesNo', 'Question')
        if ($ok -ne 'Yes') { return }
    }
    Save-Settings
    $log.Clear()
    $script:pending = "$($Names[(Get-Look)]) + $($Names[(Get-Glow)])"
    Write-Log $(if ($action -eq 'install') { "Installing: $($Names[(Get-Look)]) + $($Names[(Get-Glow)]). This takes a few minutes..." } else { 'Uninstalling...' })
    $kind = if ($action -eq 'uninstall') { 'uninstall' } else { 'mod' }
    $label = if ($action -eq 'uninstall') { 'Uninstalling Mod...' } else { 'Installing Mod...' }
    Start-Logged $kind $label $script:python (Get-InstallArgs $action $mode $pGame.box.Text $pRomfs.box.Text $pLoad.box.Text (Get-Look) (Get-Glow) (Find-Astcenc))
}

$rGame.Add_CheckedChanged({ Update-View }); $rEmu.Add_CheckedChanged({ Update-View })
$pGame.box.Add_TextChanged({ Update-View }); $pLoad.box.Add_TextChanged({ Update-View })
$bInstall.Add_Click({ Invoke-Action 'install' })
$bUninstall.Add_Click({ Invoke-Action 'uninstall' })
$bClose.Add_Click({ $f.Close() })
function Get-Report {
    # What a bug report carries: versions, tools found, and the window's messages, with the user's name and home folder
    # replaced by placeholders (nothing personal leaves the PC).
    $head = "$Title installer v$Version | Windows $([Environment]::OSVersion.Version) | Python " +
            $(if ($script:python) { Test-Python $script:python } else { 'none' }) + " | astcenc " + $(if (Find-Astcenc) { 'yes' } else { 'no' }) +
            " | mode $(Get-Mode), look $(Get-Look), glow $(Get-Glow)"
    $text = $head + "`r`n" + $log.Text
    foreach ($p in @($env:USERPROFILE, $env:LOCALAPPDATA, $env:APPDATA) | Sort-Object Length -Descending) {
        if ($p) { $text = $text.Replace($p, '%' + $(if ($p -eq $env:USERPROFILE) { 'USERPROFILE' } elseif ($p -eq $env:LOCALAPPDATA) { 'LOCALAPPDATA' } else { 'APPDATA' }) + '%') }
    }
    if ($env:USERNAME) { $text = [regex]::Replace($text, [regex]::Escape($env:USERNAME), '<user>', 'IgnoreCase') }
    return $text
}
$bReport.Add_Click({
    $ok = [System.Windows.Forms.MessageBox]::Show("Open a bug report on the mod's GitHub page in your browser?`r`n`r`nIt is filled in with the installer version, your Windows version, the prerequisites found and the window's last messages. Your user name and folders are hidden. Nothing is sent until you review it and click submit (you need a free GitHub account).`r`n`r`nThe full log is also copied to your clipboard.", 'Report a Problem', 'YesNo', 'Question')
    if ($ok -ne 'Yes') { return }
    $rep = Get-Report
    [System.Windows.Forms.Clipboard]::SetText($rep)
    $lines = $rep -split "`r?`n"
    $body = "**What happened?**`n(describe it here)`n`n**Installer details and last messages:**`n" + '```' + "`n" +
            (($lines | Select-Object -First 1) + "`n" + (($lines | Select-Object -Skip 1 | Select-Object -Last 40) -join "`n")) + "`n" + '```'
    Add-Type -AssemblyName System.Web
    $url = $IssueUrl + '?title=' + [System.Web.HttpUtility]::UrlEncode("Installer problem (v$Version)") + '&body=' + [System.Web.HttpUtility]::UrlEncode($body)
    Start-Process $url
})
$rowAst.install.Add_Click({ if ($script:busy) { return }
    if ($rowAst.tried) {
        if (Test-Prereq 'astcenc') { Write-Log 'astcenc found and set up.' }
        else { Show-Msg 'astcenc still not found. Download astcenc-5.7.1-windows-x64.zip to your Downloads folder, then click Check Again.' 'Information' }
        return
    }
    $ok = [System.Windows.Forms.MessageBox]::Show("Download ARM astcenc 5.7.1 (about 1.7 MB) from ARM's GitHub page?`r`n`r`n$AstcUrl`r`n`r`nIt is checked against ARM's published fingerprint before use. astcenc is open source (Apache 2.0).", 'Install Prerequisite', 'YesNo', 'Question')
    if ($ok -ne 'Yes') { return }
    $f.Cursor = 'WaitCursor'
    $failed = $null
    try { $n = Get-AstcencOnline; Write-Log "astcenc downloaded and set up: $n (ARM fingerprint checked)." }
    catch { $failed = "$_"; Write-Log "astcenc download failed: $failed" }
    $f.Cursor = 'Default'; Update-View
    if ($failed) { $rowAst.tried = $true; Update-View; Show-Manual 'astcenc' 'the download failed' }
})
$rowPy.install.Add_Click({ if ($script:busy) { return }
    if ($rowPy.tried) {
        if (Test-Prereq 'python') { Write-Log "Python $(Test-Python $script:python) found." }
        else { Show-Msg 'Python 3.14 still not found. Install it, then click Check Again.' 'Information' }
        return
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { $rowPy.tried = $true; Update-View; Show-Manual 'python' "winget isn't available on this PC"; return }
    $ok = [System.Windows.Forms.MessageBox]::Show("Install Python 3.14 for your Windows user with winget (Windows' own installer)?`r`n`r`nPackage: $PythonWinget (Python Software Foundation, python.org).`r`nThis accepts Python's license and the winget catalog terms.", 'Install Prerequisite', 'YesNo', 'Question')
    if ($ok -ne 'Yes') { return }
    $log.Clear(); Write-Log 'Installing Python 3.14 with winget...'
    Start-Logged 'python' 'Installing Prerequisite...' 'winget' @('install', '--id', $PythonWinget, '--exact', '--scope', 'user', '--silent',
                                      '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity')
})
$f.Add_FormClosing({ param($s, $e)
    if ($script:proc -and -not $script:proc.HasExited) {
        $ok = [System.Windows.Forms.MessageBox]::Show('Still working. Close anyway? (The mod will not be changed.)', 'Close', 'YesNo', 'Warning')
        if ($ok -ne 'Yes') { $e.Cancel = $true } else { try { $script:proc.Kill() } catch { } }
    }
})

# Install.bat starts PowerShell hidden, and Windows applies that "hidden" to the first window a program shows. Use it
# up on purpose while the form loads, then show the form explicitly.
Add-Type -Namespace DLD -Name Win -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);'
$f.Add_Load({ [void][DLD.Win]::ShowWindow($f.Handle, 0) })
$f.Add_Shown({ [void][DLD.Win]::ShowWindow($f.Handle, 5); $f.Activate() })

# Scale the finished layout ONCE: x1.2 (bigger text and room for it) x the screen's DPI. Fonts are in points, so
# Windows already draws them at the screen's DPI.
$script:S = 1.2 * ($f.DeviceDpi / 96.0)
$f.Scale((New-Object System.Drawing.SizeF($script:S, $script:S)))
$f.ResumeLayout($false); $f.PerformLayout()
# Header animation: each frame is drawn once at the header's real on-screen size (crisp at any DPI), on its first turn
# in the loop, then reused, so after the first 3 seconds the timer only swaps pictures. Paused while minimized.
$script:hf = 0; $script:hframes = New-Object 'object[]' $HdrFrames
$anim = New-Object System.Windows.Forms.Timer; $anim.Interval = $HdrTick
$anim.Add_Tick({
    if ($f.WindowState -eq 'Minimized') { return }
    $script:hf = ($script:hf + 1) % $HdrFrames
    $fr = $script:hframes[$script:hf]
    if (-not $fr) { try { $fr = New-HeaderImage 600 110 $script:S ($script:hf / $HdrFrames); $script:hframes[$script:hf] = $fr } catch { $anim.Stop(); return } }
    $hdr.Image = $fr
})
$f.Add_Shown({ $anim.Start() })
$f.Add_FormClosed({ $anim.Stop() })
if ($settings['mode'] -eq 'emulator') { $rEmu.Checked = $true } else { $rGame.Checked = $true }
switch ($settings['look']) { 'full' { $rFull.Checked = $true } 'none' { $rLookNone.Checked = $true } default { $rGear.Checked = $true } }
switch ($settings['glow']) { 'stock' { $rStock.Checked = $true } 'off' { $rGlowOff.Checked = $true } default { $rRed.Checked = $true } }
Update-View
[void]$f.ShowDialog()
} catch {
    [System.Windows.Forms.MessageBox]::Show("The installer hit an error:`r`n`r`n$_`r`n`r`nYou can still install from the command line (see README).", 'Dark Link and Demise Glow', 'OK', 'Error') | Out-Null
}
