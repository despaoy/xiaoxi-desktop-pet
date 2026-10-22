param(
    [string]$Python = ''
)
$ErrorActionPreference = 'Stop'
if (-not $Python) {
    $Python = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $Python) {
    throw '找不到 python。可传入 -Python "C:\path\python.exe"。'
}
$root = $PSScriptRoot
$tools = Join-Path $root '.build-tools'
if (-not (Test-Path -LiteralPath (Join-Path $tools 'PyInstaller'))) {
    throw '缺少 PyInstaller。请先运行：python -m pip install --target .build-tools pyinstaller'
}
$env:PYTHONPATH = $tools
Push-Location $root
try {
    & $Python -m PyInstaller --noconfirm --clean XiaoXi.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败（exit $LASTEXITCODE）" }
    $dist = Join-Path $root 'dist\XiaoXi'
    $data = Join-Path $dist 'data'
    if (-not (Test-Path -LiteralPath $data)) {
        Copy-Item -LiteralPath (Join-Path $root 'data') -Destination $data -Recurse
    }
    Write-Host "构建完成：$dist\XiaoXi.exe"
    Write-Host '运行 .\install-desktop.ps1 创建桌面快捷方式。'
} finally {
    Pop-Location
}
