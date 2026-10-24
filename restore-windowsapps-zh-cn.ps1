param(
  [string]$AppDir
)

$ErrorActionPreference = 'Stop'

# Admin check
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Host ''
  Write-Host '检测到当前终端没有管理员权限，正在请求管理员权限...' -ForegroundColor Yellow
  try {
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    if ($PSBoundParameters.ContainsKey('AppDir') -and $AppDir) {
      $argList += @('-AppDir', "`"$AppDir`"")
    }
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $argList -WorkingDirectory $scriptDir | Out-Null
    exit 0
  } catch {
    Write-Host ''
    Write-Host '未获得管理员权限，补丁未执行。' -ForegroundColor Red
    Write-Host '请右键 PowerShell 或 Windows Terminal，选择“以管理员身份运行”，然后重新执行。' -ForegroundColor Gray
    Write-Host ''
    Read-Host '按 Enter 退出'
    exit 1
  }
}
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) {
  Write-Host 'Python 3 not found. Please install Python 3 first.' -ForegroundColor Red
  exit 1
}

Get-Process -Name claude -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host 'Restore Claude Desktop zh-CN patch backup'
Write-Host ''

if ($AppDir) {
  & $python.Source "$scriptDir\restore_claude_zh_cn_windowsapps.py" --app-dir "$AppDir"
} else {
  & $python.Source "$scriptDir\restore_claude_zh_cn_windowsapps.py"
}

if ($LASTEXITCODE -ne 0) {
  Write-Host ''
  Write-Host 'Restore failed. Check errors above.' -ForegroundColor Red
} else {
  Write-Host ''
  Write-Host 'Restore complete. Restart Claude Desktop to see English UI.' -ForegroundColor Green
}

Read-Host 'Press Enter to exit'
