export type LauncherState = 'loading' | 'ready' | 'missing' | 'update' | 'repair' | 'error'

export type CheckTone = 'good' | 'warn' | 'danger'

export type ActionCommand = 'install' | 'restore' | 'open' | 'check-update' | 'refresh'

export type InstallTarget = 'auto' | 'windows-apps' | 'app-data' | 'manual'

export type StatusCheck = {
  label: string
  value: string
  tone: CheckTone
}

export type PatchStatus = {
  state: LauncherState
  installed: boolean
  localized: boolean
  version: string
  language: string
  target: InstallTarget
  installPath: string
  message: string
  checks: StatusCheck[]
}

export type ActionResult = {
  ok: boolean
  state: LauncherState
  message: string
  log: string
}

export type LiveLog = {
  title: string
  content: string
  updatedAt: string
}

export type Activity = {
  id: number
  tone: CheckTone
  title: string
  summary: string
  detail?: string
  time: string
}

export interface LauncherApi {
  getStatus(target?: InstallTarget, appDir?: string): Promise<PatchStatus>
  install(target: InstallTarget, appDir?: string): Promise<ActionResult>
  restore(target?: InstallTarget, appDir?: string): Promise<ActionResult>
  open(target?: InstallTarget, appDir?: string): Promise<ActionResult>
  checkUpdate(target?: InstallTarget, appDir?: string): Promise<ActionResult>
  getLiveLog(): Promise<LiveLog>
}
