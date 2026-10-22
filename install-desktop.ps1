param(
    [string]$AppDir = (Join-Path $PSScriptRoot 'dist\XiaoXi'),
    [string]$Name = '小汐桌宠'
)
$exe = Join-Path $AppDir 'XiaoXi.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    throw "找不到应用程序：$exe。请先运行 build-desktop.ps1 构建。"
}
$desktop = [Environment]::GetFolderPath('Desktop')
$link = Join-Path $desktop ($Name + '.lnk')
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = (Resolve-Path -LiteralPath $AppDir).Path
$shortcut.IconLocation = "$exe,0"
$shortcut.Description = '小汐桌宠'
$shortcut.Save()
Write-Host "已创建桌面快捷方式：$link"
