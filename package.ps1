# 构建 + 组装可分发压缩包（给别人直接解压使用）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

& "$root\build.ps1"
if ($LASTEXITCODE -ne 0) { throw "构建失败" }

$name = "桌面便利贴-1.1.3-win64"
$stage = "$root\release\$name"
$zip = "$root\release\$name.zip"

Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $stage -Force | Out-Null
Copy-Item -LiteralPath "$root\dist\桌面便利贴.exe" -Destination $stage
Copy-Item -LiteralPath "$root\使用说明.txt" -Destination $stage
Copy-Item -LiteralPath "$root\卸载.bat" -Destination $stage

Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "$stage\*" -DestinationPath $zip -CompressionLevel Optimal

$exeHash = (Get-FileHash -LiteralPath "$root\dist\桌面便利贴.exe" -Algorithm SHA256).Hash
$zipHash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
@(
    "桌面便利贴 1.1.3 (win64)",
    "exe SHA256: $exeHash",
    "zip SHA256: $zipHash"
) | Set-Content -LiteralPath "$root\release\SHA256SUMS.txt" -Encoding UTF8

Write-Host ""
Write-Host "分发包：$zip"
Write-Host "体积：$([math]::Round((Get-Item -LiteralPath $zip).Length / 1MB, 2)) MB"
Write-Host "zip SHA256：$zipHash"

