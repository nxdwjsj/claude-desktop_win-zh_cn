import type { ActionResult, InstallTarget, LauncherApi, LiveLog, PatchStatus } from './types'

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

let localized = false
let lastLog = [
  '[启动] 当前是桌面助手预览模式。',
  '[提示] 接入现有补丁脚本后，这里会显示真实检测结果。',
].join('\n')

const targetLabel: Record<InstallTarget, string> = {
  auto: '自动检测',
  'windows-apps': 'WindowsApps 商店版',
  'app-data': 'AppData 网页版',
  manual: '手动指定目录',
}

function buildStatus(target: InstallTarget = 'auto', appDir?: string): PatchStatus {
  const manualMissing = target === 'manual' && !appDir
  return {
    state: manualMissing ? 'missing' : localized ? 'ready' : 'repair',
    installed: !manualMissing,
    localized: manualMissing ? false : localized,
    version: '1.14271.0.0',
    language: !manualMissing && localized ? 'zh-CN' : '未安装',
    target,
    installPath: target === 'manual'
      ? (appDir || '尚未选择 Claude app 目录')
      : target === 'app-data'
      ? 'C:\\Users\\you\\AppData\\Local\\AnthropicClaude'
      : 'C:\\Program Files\\WindowsApps\\Claude_1.14271.0.0_x64__pzs8sxrjxfjc',
    message: manualMissing
      ? '请选择 Claude app 目录。'
      : localized
        ? 'Claude Desktop 中文版可以打开。'
        : 'Claude Desktop 已找到，可以安装中文补丁。',
    checks: [
      { label: 'Claude Desktop', value: manualMissing ? '未找到' : '已安装', tone: manualMissing ? 'danger' : 'good' },
      { label: '中文资源', value: manualMissing ? '未知' : localized ? '已写入' : '未安装', tone: localized ? 'good' : 'warn' },
      { label: '语言白名单', value: manualMissing ? '未知' : localized ? '包含 zh-CN' : '待写入', tone: localized ? 'good' : 'warn' },
      { label: '备份文件', value: manualMissing ? '未知' : localized ? '已准备' : '待生成', tone: localized ? 'good' : 'warn' },
      { label: 'Python / PowerShell', value: '可用', tone: 'good' },
    ],
  }
}

function writeLog(lines: string[]) {
  lastLog = lines.join('\n')
}

export const PREVIEW_STATUS = buildStatus()

export const mockApi: LauncherApi = {
  async getStatus(target: InstallTarget = 'auto', appDir?: string) {
    await wait(420)
    return buildStatus(target, appDir)
  },

  async install(target, appDir) {
    writeLog([
      '[准备] 正在关闭 Claude Desktop...',
      `[检测] 安装目标：${targetLabel[target]}${appDir ? ` (${appDir})` : ''}`,
      '[备份] 正在确认官方资源备份...',
      '[资源] 正在写入 zh-CN JSON 资源...',
      '[运行时] 正在注入字体和会话增强...',
    ])
    await wait(900)
    localized = true
    writeLog([
      ...lastLog.split('\n'),
      '[校验] JSON 资源和语言白名单校验通过。',
      '[完成] 中文补丁已安装。',
    ])
    return {
      ok: true,
      state: 'ready',
      message: '中文补丁已安装，Claude Desktop 可以打开。',
      log: lastLog,
    }
  },

  async restore(_target: InstallTarget = 'auto', _appDir?: string) {
    writeLog([
      '[准备] 正在关闭 Claude Desktop...',
      '[恢复] 正在从官方备份恢复资源...',
      '[清理] 正在移除 zh-CN、locale 和运行时标记...',
    ])
    await wait(850)
    localized = false
    writeLog([...lastLog.split('\n'), '[完成] 已恢复原样，Claude 数据保持不变。'])
    return {
      ok: true,
      state: 'repair',
      message: '已恢复原样，Claude 数据保持不变。',
      log: lastLog,
    }
  },

  async open(_target: InstallTarget = 'auto', _appDir?: string) {
    writeLog(['[启动] 正在打开 Claude Desktop...', '[完成] Claude Desktop 已启动。'])
    await wait(500)
    return {
      ok: true,
      state: 'ready',
      message: 'Claude Desktop 已启动。',
      log: lastLog,
    }
  },

  async checkUpdate(_target: InstallTarget = 'auto', _appDir?: string) {
    writeLog(['[更新] 正在读取当前 Claude Desktop 版本...', '[更新] 当前已是可用版本。'])
    await wait(650)
    return {
      ok: true,
      state: localized ? 'ready' : 'repair',
      message: '当前版本已是可用版本。',
      log: lastLog,
    }
  },

  async getLiveLog(): Promise<LiveLog> {
    return {
      title: '运行日志',
      content: lastLog,
      updatedAt: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    }
  },
}
