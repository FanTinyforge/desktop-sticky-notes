# 重新打包成单文件 exe（按 spec 构建，确保精简依赖/版本信息生效）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

& "$root\.venv\Scripts\pyinstaller.exe" --noconfirm --clean "$root\桌面便利贴.spec"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 构建失败，退出码 $LASTEXITCODE"
}

$exe = "$root\dist\桌面便利贴.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "没有生成 $exe"
}

$size = [math]::Round((Get-Item -LiteralPath $exe).Length / 1MB, 2)
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
Write-Host "打包完成：$exe"
Write-Host "体积：$size MB"
Write-Host "SHA256：$hash"
