import { invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'
import type { ActionResult, InstallTarget, LauncherApi, LiveLog, PatchStatus } from './types'

export function isTauriRuntime(): boolean {
  return '__TAURI_INTERNALS__' in window
}

async function invokeBridge<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (!isTauriRuntime()) {
    throw new Error('当前不在 Tauri 运行时中')
  }
  return invoke<T>(cmd, args)
}

export async function selectClaudeDirectory(title: string): Promise<string | null> {
  if (!isTauriRuntime()) return null
  const selected = await open({ directory: true, multiple: false, title })
  return typeof selected === 'string' ? selected : null
}

export const tauriApi: LauncherApi = {
  async getStatus(target: InstallTarget = 'auto', appDir?: string): Promise<PatchStatus> {
    return invokeBridge<PatchStatus>('get_status', { target, appDir })
  },

  async install(target: InstallTarget, appDir?: string): Promise<ActionResult> {
    return invokeBridge<ActionResult>('install_patch', { target, appDir })
  },

  async restore(target: InstallTarget = 'auto', appDir?: string): Promise<ActionResult> {
    return invokeBridge<ActionResult>('restore_patch', { target, appDir })
  },

  async open(target: InstallTarget = 'auto', appDir?: string): Promise<ActionResult> {
    return invokeBridge<ActionResult>('open_claude', { target, appDir })
  },

  async checkUpdate(target: InstallTarget = 'auto', appDir?: string): Promise<ActionResult> {
    return invokeBridge<ActionResult>('check_update', { target, appDir })
  },

  async getLiveLog(): Promise<LiveLog> {
    return {
      title: '运行日志',
      content: '已连接到本地补丁引擎。',
      updatedAt: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    }
  },
}
