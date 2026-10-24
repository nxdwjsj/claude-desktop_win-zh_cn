param(
  [string]$AppResources = 'C:\Program Files\WindowsApps\Claude_2.37337.1.0_x64__pzs8sxrjxfjjc\app\resources',
  [string]$BackupRoot   = "$env:LOCALAPPDATA\Claude-zh-CN-official-backup\json-only"
)

# 第一步：备份将被修改的原始文件（以管理员身份读取即可）。
# 只备份安装目录里会写入的目标文件本身，避免整目录拷贝。
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

$targets = @(
  (Join-Path $AppResources 'en-US.json'),
  (Join-Path $AppResources 'ion-dist\i18n\en-US.json')
)
# i18n 目录下所有语言文件也可能被语言白名单补丁影响，一并备份该目录
$i18nDir = Join-Path $AppResources 'ion-dist\i18n'
if (Test-Path $i18nDir) {
  Get-ChildItem $i18nDir -File -Filter '*.json' | ForEach-Object { $targets += $_.FullName }
  $dynDir = Join-Path $i18nDir 'dynamic'
  if (Test-Path $dynDir) {
    Get-ChildItem $dynDir -File -Filter '*.json' | ForEach-Object { $targets += $_.FullName }
  }
}

$manifest = @()
foreach ($t in ($targets | Select-Object -Unique)) {
  if (-not (Test-Path $t)) { continue }
  # 用相对于 app 目录的路径保存，保持结构
  $rel = $t.Substring($AppResources.Length).TrimStart('\')
  $dst = Join-Path $BackupRoot $rel
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
  if (-not (Test-Path $dst)) {
    Copy-Item -LiteralPath $t -Destination $dst -Force
  }
  $manifest += $rel
}

$manifest | Set-Content -Path (Join-Path $BackupRoot 'MANIFEST.txt') -Encoding UTF8
$info = [ordered]@{
  app_resources = $AppResources
  backed_up_at  = (Get-Date).ToString('o')
  file_count    = $manifest.Count
}
($info | ConvertTo-Json) | Set-Content -Path (Join-Path $BackupRoot 'backup-info.json') -Encoding UTF8
Write-Host ('backed up {0} files -> {1}' -f $manifest.Count, $BackupRoot)
