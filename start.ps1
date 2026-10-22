param([switch]$Live2D, [switch]$NoSandbox)
$ErrorActionPreference = 'Stop'
$petRoot = $PSScriptRoot
$petBundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe'
if (Test-Path -LiteralPath $petBundled) {
    $petPython = $petBundled
} else {
    $petCommand = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if (-not $petCommand) { throw 'Python 3.10+ with Tkinter is required. See README.md.' }
    $petPython = $petCommand.Source
}
$petArguments = '"' + (Join-Path $petRoot 'run.py') + '"'
if ($Live2D) { $petArguments += ' --live2d' }
if ($NoSandbox) { $petArguments += ' --live2d-no-sandbox' }
Start-Process -FilePath $petPython -ArgumentList $petArguments -WorkingDirectory $petRoot -WindowStyle Hidden
