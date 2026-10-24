param(
  [switch]$SkipBackup,
  [switch]$SkipSync,
  [switch]$SkipChunk,
  [switch]$Force,
  [switch]$Yes
)

# ============================================================
#  Claude Desktop 汉化 · 一键更新脚本
#  用途：Claude Desktop 升级后，重新应用中文补丁
#  用法：右键「以管理员身份运行 PowerShell」，然后：
#        powershell -NoProfile -ExecutionPolicy Bypass -File .\update-zh-cn.ps1
# ============================================================

$ErrorActionPreference = 'Continue'
$Tool   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backup = Join-Path $env:LOCALAPPDATA 'Claude-zh-CN-official-backup\json-only'
$Cfg    = Join-Path $env:LOCALAPPDATA 'Claude-3p\config.json'

function Info($m) { Write-Host $m }
function Ok($m)   { Write-Host $m -ForegroundColor Green }
function Warn($m) { Write-Host $m -ForegroundColor Yellow }
function Err($m)  { Write-Host $m -ForegroundColor Red }

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
  Err '需要管理员权限（WindowsApps 写入要求）。'
  Err '请右键 PowerShell / Windows Terminal -> 以管理员身份运行，然后重新执行本脚本。'
  exit 1
}

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $py) { Err '未找到 Python 3，请先安装。'; exit 1 }

Info ''
Info '=========================================='
Info '  Claude Desktop 汉化 · 更新'
Info '=========================================='
Info ''

# ---------- 0. 关闭 Claude ----------
Get-Process -Name claude -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Ok '[0] 已关闭 Claude'

# ---------- 1. 定位安装目录（自动适配新版本号）----------
$pkg = Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -ErrorAction SilentlyContinue |
       Where-Object { $_.Name -like 'Claude_*_x64__*' } |
       Sort-Object Name -Descending | Select-Object -First 1
if (-not $pkg) {
  # 兼容非商店版安装
  $alt = Join-Path $env:LOCALAPPDATA 'AnthropicClaude'
  if (Test-Path $alt) { $appRoot = $alt } else { Err '未找到 Claude 安装目录。'; exit 1 }
} else {
  $appRoot = Join-Path $pkg.FullName 'app'
}
$res = Join-Path $appRoot 'resources'
if (-not (Test-Path (Join-Path $res 'en-US.json'))) { Err "资源目录不完整：$res"; exit 1 }
Ok ("[1] 安装目录: {0}" -f $appRoot)
Ok ("    资源目录: {0}" -f $res)

# 版本号提示
$verFile = Join-Path $appRoot 'version'
if (Test-Path $verFile) { Info ("    version : {0}" -f (Get-Content $verFile -Raw).Trim()) }

# ---------- 2. 备份官方文件 ----------
if (-not $SkipBackup) {
  New-Item -ItemType Directory -Force -Path $Backup | Out-Null
  $targets = @()
  foreach ($rel in @('en-US.json', 'ion-dist\i18n\en-US.json')) {
    $t = Join-Path $res $rel
    if (Test-Path $t) { $targets += ,@($t, $rel) }
  }
  $i18n = Join-Path $res 'ion-dist\i18n'
  if (Test-Path $i18n) {
    Get-ChildItem $i18n -File -Filter '*.json' | ForEach-Object {
      $targets += ,@($_.FullName, ('ion-dist\i18n\' + $_.Name))
    }
  }
  $n = 0
  foreach ($pair in $targets) {
    $src = $pair[0]; $rel = $pair[1]
    $dst = Join-Path $Backup $rel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    # 只在首次备份时写入，避免用已汉化的文件覆盖干净的原始备份
    if (-not (Test-Path $dst)) { Copy-Item -LiteralPath $src -Destination $dst -Force; $n++ }
  }
  Ok ("[2] 备份完成（新增 {0} 个文件，累计 {1} 个）" -f $n, (Get-ChildItem $Backup -Recurse -File | Measure-Object).Count)
}

# ---------- 3. 同步新版新增 i18n key ----------
if (-not $SkipSync) {
  Info '[3] 正在同步新版 i18n key...'
  Push-Location $Tool
  $syncOut = & $py -B (Join-Path $Tool 'tools\sync_i18n_from_installed.py') --app-dir $appRoot 2>&1
  Pop-Location
  $syncOut | ForEach-Object { Info ('    ' + $_) }
  $untr = 0
  foreach ($line in $syncOut) {
    if ($line -match 'untranslated=(\d+)') { $untr += [int]$matches[1] }
  }
  if ($untr -gt 0) {
    Warn ("[3] 注意：新版有 {0} 条文案暂无中文翻译，将暂时显示英文。" -f $untr)
    Warn '    要补全翻译，把上面的输出发给 AI 助手继续处理。'
  } else {
    Ok '[3] i18n key 已同步（无新增未翻译文案）'
  }
}

# ---------- 4. 接管权限并写入 ----------
Info '[4] 正在接管安装目录权限...'
# 注意：icacls 的授权串含 * 和括号，必须作为单个字符串变量传入，
# 否则 PowerShell 会把 (OI)(CI) 当表达式解析而报语法错误。
& takeown /F $res /R /D Y 2>&1 | Out-Null
$grantArg = '*S-1-5-32-544:(OI)(CI)F'
& icacls $res /grant $grantArg /T /C 2>&1 | Out-Null
Ok '[4] 权限已接管'

Info '[5] 正在写入中文资源...'
Push-Location $Tool
$patchOut = & $py -B (Join-Path $Tool 'patch_windowsapps_json_only.py') --app-dir $appRoot 2>&1
Pop-Location
$patchOut | ForEach-Object { Info ('    ' + $_) }
$patchOk = ($patchOut | Where-Object { $_ -match '^Done' }).Count -gt 0

# ---------- 5b. JS chunk 硬编码文案补丁（必须在 [6] 权限还原之前执行，
#          否则 WindowsApps 会对后续写入报 Permission denied）----------
if (-not $SkipChunk) {
  Info '[5b] 正在修补 JS chunk 硬编码文案...'
  Push-Location $Tool
  $chunkOut = & $py -B (Join-Path $Tool 'patch_chunks_zh_cn.py') --app-dir $appRoot 2>&1
  Pop-Location
  $chunkOut | ForEach-Object { Info ('    ' + $_) }
  if (($chunkOut | Where-Object { $_ -match 'Permission denied|权限不足' }).Count -gt 0) {
    Warn '[5b] chunk 补丁存在写入失败项，相关界面将保持英文。'
  } else {
    Ok '[5b] chunk 补丁完成'
  }
}

# ---------- 6. 还原 ACL ----------
& icacls $res /reset /T /C 2>&1 | Out-Null
Ok '[6] 权限已还原为官方状态'

if (-not $patchOk) { Err '写入失败，请检查上面的输出。'; exit 1 }

# ---------- 7. 设置 locale（关键：必须写真实配置路径）----------
Info '[7] 正在设置 locale...'
if (Test-Path $Cfg) {
  $bak = "$Cfg.zh-cn-backup"
  if (-not (Test-Path $bak)) { Copy-Item -LiteralPath $Cfg -Destination $bak -Force }
  Push-Location $Tool
  & $py -B (Join-Path $Tool 'set_locale.py') 2>&1 | ForEach-Object { Info ('    ' + $_) }
  Pop-Location
}
$loc = (Get-Content $Cfg -Raw | ConvertFrom-Json).locale
if ($loc -eq 'zh-CN') { Ok '[7] locale = zh-CN' } else { Warn ("[7] locale 仍为 {0}，可能需要手工检查" -f $loc) }

# ---------- 8. 验证 ----------
Info ''
Info '=========================================='
Info '  验证'
Info '=========================================='
$checks = @(
  @{ n = '壳层 zh-CN.json';      p = (Join-Path $res 'zh-CN.json') },
  @{ n = '前端 zh-CN.json';      p = (Join-Path $res 'ion-dist\i18n\zh-CN.json') },
  @{ n = 'statsig zh-CN.json';   p = (Join-Path $res 'ion-dist\i18n\statsig\zh-CN.json') }
)
$allOk = $true
foreach ($c in $checks) {
  if (Test-Path $c.p) { Ok ('  [OK]   {0}' -f $c.n) } else { Err ('  [MISS] {0}' -f $c.n); $allOk = $false }
}
if ($loc -eq 'zh-CN') { Ok '  [OK]   locale=zh-CN' } else { $allOk = $false }

Info ''
if ($allOk) {
  Ok '汉化已应用完成。请重新打开 Claude Desktop。'
  Info ''
  Info '提示：如果界面仍有英文，把 update-zh-cn.ps1 的输出发给 AI 助手，'
  Info '     即可继续补全新版新增文案的翻译。'
} else {
  Warn '部分项目未通过，请检查上面输出。'
}

Info ''
# 非交互模式（-Yes）不暂停，便于无人值守/自动化调用；
# 交互模式下才等待按键，避免窗口一闪而过看不到结果。
if (-not $Yes) { Read-Host '按 Enter 退出' }
if (-not $allOk) { exit 1 }
exit 0
