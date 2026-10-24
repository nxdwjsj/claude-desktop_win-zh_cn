param(
  [string]$AppResources = 'C:\Program Files\WindowsApps\Claude_2.37337.1.0_x64__pzs8sxrjxfjjc\app\resources',
  [string]$Tool         = 'D:\claude-desktop_win-zh_cn-0.1.0',
  [string]$Log          = 'D:\Project\DeepSeek\out\zh-work\_install2_log.txt'
)

# 第二步：以管理员身份接管 app\resources 的所有权 -> 写入中文资源 -> 恢复 ACL。
$ErrorActionPreference = 'Continue'
function Log($m) { $m | Add-Content -Path $Log -Encoding UTF8 }

'=== step2: take ownership + write zh-CN resources ===' | Set-Content -Path $Log -Encoding UTF8

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Log ("admin: {0}" -f $admin)
if (-not $admin) { Log 'ERROR: not elevated'; exit 1 }

# 记录原始 ACL 以便恢复
$aclBackup = Join-Path (Split-Path $Log -Parent) 'acl_backup.txt'
$origAcl = (& icacls $AppResources) 2>&1 | Out-String
$origAcl | Set-Content -Path $aclBackup -Encoding UTF8
Log 'original ACL saved to acl_backup.txt'

# 1) 接管所有权（当前目录 + 子项）
Log '--- takeown ---'
(& takeown /F $AppResources /R /D Y) 2>&1 | ForEach-Object { Log $_ }
Log ("takeown exit: {0}" -f $LASTEXITCODE)

# 2) 授予 Administrators 完全控制，以及当前用户写权限
Log '--- icacls grant ---'
(& icacls $AppResources /grant "*S-1-5-32-544:(OI)(CI)F" /T /C) 2>&1 | ForEach-Object { Log $_ }
Log ("icacls grant exit: {0}" -f $LASTEXITCODE)

# 3) 写入中文资源
Log '--- patch (JSON resources) ---'
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
Log ("python: {0}" -f $py)
Set-Location $Tool
& $py -B (Join-Path $Tool 'patch_windowsapps_json_only.py') --app-dir (Split-Path $AppResources -Parent) *>&1 |
  ForEach-Object { Log $_.ToString() }
Log ("patch exit: {0}" -f $LASTEXITCODE)

# 4) 恢复原始 ACL（去掉我们授予的宽权限）
Log '--- restore ACL ---'
$aclFile = $aclBackup
(& icacls $AppResources /reset /T /C) 2>&1 | ForEach-Object { Log $_ }
Log ("icacls reset exit: {0}" -f $LASTEXITCODE)

Log '=== step2 done ==='
