# Autostart on Windows: a shortcut in the startup folder, the journal at every
# login with no window left on the screen.
#
#   the downloaded file:
#     powershell -ExecutionPolicy Bypass -File plainbook-startup.ps1 -File C:\Users\NAME\Plainbook-VERSION-windows.exe
#   from the source:
#     powershell -ExecutionPolicy Bypass -File plainbook-startup.ps1 -Source C:\Users\NAME\plainbook
#   taken out again:
#     powershell -ExecutionPolicy Bypass -File plainbook-startup.ps1 -Remove
#
# Where the records live is PLAINBOOK_ROOT, a user environment variable
# (System properties, Environment Variables); without it a source install
# keeps them next to the program and the downloaded file in %USERPROFILE%\Plainbook.
# The running journal is stopped in the Task Manager: Plainbook for the file,
# pythonw for the source.
param([string]$File, [string]$Source, [switch]$Remove)

$link = Join-Path ([Environment]::GetFolderPath('Startup')) 'Plainbook.lnk'
if ($Remove) {
    Remove-Item $link -ErrorAction SilentlyContinue
    "taken out: $link"
    exit 0
}

$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($link)
if ($File) {
    $shortcut.TargetPath = (Resolve-Path $File).Path
    $shortcut.Arguments = '--background'
    $shortcut.WorkingDirectory = Split-Path $shortcut.TargetPath
} elseif ($Source) {
    # pythonw is the Python with no console; the py launcher's twin is pyw
    $python = Get-Command pythonw, pyw -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $python) { 'No pythonw or pyw found: is Python installed?'; exit 1 }
    $shortcut.TargetPath = $python.Source
    $shortcut.Arguments = '-m plainbook.server --background'
    $shortcut.WorkingDirectory = (Resolve-Path $Source).Path
} else {
    'Say -File with the path of the downloaded file, -Source with the program folder, or -Remove.'
    exit 1
}
# minimized: the downloaded file is a console program, and the instant before
# it hands the journal to a copy with no window stays off the screen
$shortcut.WindowStyle = 7
$shortcut.Save()
"set: $link -> $($shortcut.TargetPath) $($shortcut.Arguments)"
