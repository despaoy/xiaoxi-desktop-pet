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
    $dist = Join-Path $root 'dist\XiaoXi'
    # Refuse to replace an output folder that has been used as a personal app.
    & $Python tools/release_safety.py $dist
    if ($LASTEXITCODE -ne 0) { throw '发布检查失败：请先备份旧输出，再使用干净的构建目录。' }
    & $Python -m PyInstaller --noconfirm --clean XiaoXi.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败（exit $LASTEXITCODE）" }
    # Runtime creates its own empty database on first launch; never copy data/.
    & $Python tools/release_safety.py $dist --require-output
    if ($LASTEXITCODE -ne 0) { throw '发布检查失败：产物包含本地数据，不可分发。' }
    Write-Host "构建完成：$dist\XiaoXi.exe"
    Write-Host '运行 .\install-desktop.ps1 创建桌面快捷方式。'
} finally {
    Pop-Location
}
