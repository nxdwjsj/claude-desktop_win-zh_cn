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

Write-Host 'Claude Desktop zh-CN patch (JSON + chunk labels + font customizer)'
Write-Host ''

Write-Host 'Step 1: JSON resources...'
if ($AppDir) {
  & $python.Source "$scriptDir\patch_windowsapps_json_only.py" --app-dir "$AppDir"
} else {
  & $python.Source "$scriptDir\patch_windowsapps_json_only.py"
}

if ($LASTEXITCODE -ne 0) {
  Write-Host ''
  Write-Host 'JSON patch failed. Check errors above.' -ForegroundColor Red
  Read-Host 'Press Enter to exit'
  exit 1
}

Write-Host ''
Write-Host 'Step 2: Chunk UI labels and font customizer...'
if ($AppDir) {
  & $python.Source "$scriptDir\patch_chunks_zh_cn.py" --app-dir "$AppDir"
} else {
  & $python.Source "$scriptDir\patch_chunks_zh_cn.py"
}

Write-Host ''
Write-Host 'Patch complete. Restart Claude Desktop to see Chinese UI.' -ForegroundColor Green
Write-Host 'Font customizer will appear in the existing Settings/Appearance area when available.' -ForegroundColor Green

Read-Host 'Press Enter to exit'
