param(
  [string]$Tool = 'D:\claude-desktop_win-zh_cn-0.1.0',
  [string]$Log  = 'D:\Project\DeepSeek\out\zh-work\_restore_log.txt'
)

# 卸载：从备份恢复 Claude 官方资源，移除中文资源与 locale=zh-CN。
# 需要管理员权限（WindowsApps 写入）。
$ErrorActionPreference = 'Continue'
function Log($m) { $m | Add-Content -Path $Log -Encoding UTF8 }

'=== restore Claude Desktop to official (en-US) ===' | Set-Content -Path $Log -Encoding UTF8

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Log ("admin: {0}" -f $admin)
if (-not $admin) { Log 'ERROR: 需要管理员权限'; exit 1 }

# 停掉 Claude
Get-Process -Name claude -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Log 'claude stopped'

# 定位安装目录
$app = (Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'Claude_*' } |
        Sort-Object Name -Descending | Select-Object -First 1).FullName
if (-not $app) { Log 'ERROR: Claude 安装目录未找到'; exit 1 }
$appRoot = Join-Path $app 'app'
$res = Join-Path $appRoot 'resources'
Log ("app: {0}" -f $appRoot)

# 接管权限
(& takeown /F $res /R /D Y) 2>&1 | Out-Null
(& icacls $res /grant "*S-1-5-32-544:(OI)(CI)F" /T /C) 2>&1 | Out-Null
Log 'ownership taken'

# 1) 从备份恢复官方文件
$backup = Join-Path $env:LOCALAPPDATA 'Claude-zh-CN-official-backup\json-only'
$restored = 0
if (Test-Path $backup) {
  Get-ChildItem $backup -Recurse -File -Filter '*.json' | ForEach-Object {
    if ($_.Name -eq 'backup-info.json') { return }
    $rel = $_.FullName.Substring($backup.Length).TrimStart('\')
    $dst = Join-Path $res $rel
    if (Test-Path $dst) {
      Copy-Item -LiteralPath $_.FullName -Destination $dst -Force
      $restored++
    }
  }
}
Log ("restored from backup: {0}" -f $restored)

# 2) 删除中文资源
foreach ($f in @(
  (Join-Path $res 'zh-CN.json'),
  (Join-Path $res 'ion-dist\i18n\zh-CN.json'),
  (Join-Path $res 'ion-dist\i18n\statsig\zh-CN.json')
)) {
  if (Test-Path $f) { Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue; Log ("removed {0}" -f $f) }
}

# 3) 恢复 locale
$cfg = Join-Path $env:LOCALAPPDATA 'Claude-3p\config.json'
if (Test-Path $cfg) {
  $bak = "$cfg.zh-cn-backup"
  if (Test-Path $bak) {
    Copy-Item -LiteralPath $bak -Destination $cfg -Force
    Log 'locale restored from .zh-cn-backup'
  } else {
    Log 'WARN: 无 locale 备份，请手动把 config.json 的 locale 改回 en-US'
  }
}

# 4) 恢复 ACL
(& icacls $res /reset /T /C) 2>&1 | Out-Null
Log 'ACL reset'

Log '=== restore done ==='
