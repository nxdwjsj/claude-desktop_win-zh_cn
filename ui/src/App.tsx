import {
  AlertCircle, Check, CheckCircle2, Clipboard, CloudDownload, FileText, FolderOpen,
  Languages, Loader2, Play, RefreshCw, RotateCcw, ShieldCheck, Trash2, Wrench, X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { translations, type UiCopy, type UiLocale } from './i18n'
import { mockApi, PREVIEW_STATUS } from './mockApi'
import { isTauriRuntime, selectClaudeDirectory, tauriApi } from './tauriApi'
import type { ActionCommand, Activity, CheckTone, InstallTarget, LauncherApi, LiveLog, PatchStatus } from './types'
import './App.css'

function toneIcon(tone: CheckTone) {
  if (tone === 'good') return <CheckCircle2 size={17} aria-hidden="true" />
  return <AlertCircle size={17} aria-hidden="true" />
}

function timeLabel(locale: UiLocale) {
  return new Date().toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
}

function statusLabel(status: PatchStatus, copy: UiCopy) {
  if (status.state === 'loading') return copy.checking
  if (status.localized) return copy.localized
  if (!status.installed) return copy.missing
  return copy.pending
}

function statusTone(status: PatchStatus) {
  if (status.state === 'loading') return 'loading'
  if (status.localized) return 'ready'
  if (!status.installed) return 'missing'
  return 'repair'
}

function translatedStatusMessage(status: PatchStatus, locale: UiLocale, copy: UiCopy) {
  if (status.state === 'loading') return copy.loadingText
  if (status.state === 'error') return copy.statusFailedMessage
  if (status.localized) return copy.readyText
  if (!status.installed) return copy.missingText
  if (locale === 'en-US') return copy.installText
  return status.message
}

function translatedActivityText(value: string, copy: UiCopy) {
  const zh = translations['zh-CN']
  const en = translations['en-US']

  if (value === zh.statusComplete || value === en.statusComplete) return copy.statusComplete
  if (value === zh.statusFailed || value === en.statusFailed) return copy.statusFailed
  if (value === zh.statusFailedMessage || value === en.statusFailedMessage) return copy.statusFailedMessage
  if (value === zh.installSuccess || value === en.installSuccess) return copy.installSuccess
  if (value === zh.restoreSuccess || value === en.restoreSuccess) return copy.restoreSuccess
  if (value === zh.openSuccess || value === en.openSuccess) return copy.openSuccess
  if (value === zh.updateSuccess || value === en.updateSuccess) return copy.updateSuccess
  if (value === zh.actionFailedMessage || value === en.actionFailedMessage) return copy.actionFailedMessage
  if (value === PREVIEW_STATUS.message || value === zh.installText || value === en.installText) return copy.installText
  if (value === 'Claude Desktop 中文版可以打开。' || value === zh.readyText || value === en.readyText) return copy.readyText
  if (value === '未找到 Claude Desktop 安装。' || value === zh.missingText || value === en.missingText) return copy.missingText
  return value
}

function translateCheckText(value: string, copy: UiCopy) {
  const known: Record<string, string> = {
    'Claude Desktop': copy.checkClaude,
    '中文资源': copy.checkResources,
    '语言白名单': copy.checkWhitelist,
    '备份文件': copy.checkBackup,
    'Python / PowerShell': copy.checkRuntime,
    '已安装': copy.valueInstalled,
    '已写入': copy.valueWritten,
    '未安装': copy.valueNotInstalled,
    '包含 zh-CN': copy.valueContainsZh,
    '待写入': copy.valuePendingWrite,
    '已准备': copy.valueReady,
    '待生成': copy.valuePendingGenerate,
    '可用': copy.valueAvailable,
    '缺失': copy.valueMissing,
    '未知': copy.valueUnknown,
    '未找到': copy.missing,
  }
  return known[value] ?? value
}

function storedLocale(): UiLocale {
  return window.localStorage.getItem('claude-zh-ui-locale') === 'en-US' ? 'en-US' : 'zh-CN'
}

function App() {
  const [locale, setLocale] = useState<UiLocale>(storedLocale)
  const copy = translations[locale]
  const apiRef = useRef<LauncherApi>(isTauriRuntime() ? tauriApi : mockApi)
  const [status, setStatus] = useState<PatchStatus>(PREVIEW_STATUS)
  const [target, setTarget] = useState<InstallTarget>('auto')
  const [manualAppDir, setManualAppDir] = useState('')
  const [busyAction, setBusyAction] = useState<ActionCommand | null>(null)
  const [activities, setActivities] = useState<Activity[]>([])
  const [liveLog, setLiveLog] = useState<LiveLog>({
    title: copy.operationLog,
    content: PREVIEW_STATUS.message,
    updatedAt: '--:--',
  })
  const [showRestoreConfirm, setShowRestoreConfirm] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)
  const nextActivityId = useRef(1)

  const targetOptions = [
    { value: 'auto' as const, label: copy.targetAuto, note: copy.targetAutoNote },
    { value: 'windows-apps' as const, label: copy.targetWindows, note: copy.targetWindowsNote },
    { value: 'app-data' as const, label: copy.targetAppData, note: copy.targetAppDataNote },
    { value: 'manual' as const, label: copy.targetManual, note: copy.targetManualNote },
  ]
  const actionLabels: Record<ActionCommand, string> = {
    install: copy.install,
    restore: copy.restore,
    open: copy.openClaude,
    'check-update': copy.checkUpdate,
    refresh: copy.refresh,
  }

  const busy = busyAction !== null
  const selectedAppDir = target === 'manual' ? manualAppDir.trim() || undefined : undefined
  const primaryAction: ActionCommand = status.localized ? 'open' : 'install'
  const primaryLabel = actionLabels[primaryAction]
  const displayInstallPath = target === 'manual' ? manualAppDir.trim() || copy.noManualPath : status.installPath
  const currentTarget = targetOptions.find((option) => option.value === target) ?? targetOptions[0]
  const currentStatusText = useMemo(
    () => translatedStatusMessage(status, locale, copy),
    [copy, locale, status],
  )
  const translatedChecks = useMemo(
    () => status.checks.map((check) => ({
      ...check,
      label: translateCheckText(check.label, copy),
      value: translateCheckText(check.value, copy),
    })),
    [copy, status.checks],
  )
  const displayedLogContent = useMemo(
    () => translatedActivityText(liveLog.content, copy),
    [copy, liveLog.content],
  )

  useEffect(() => {
    document.documentElement.lang = locale
    document.title = copy.pageTitle
    window.localStorage.setItem('claude-zh-ui-locale', locale)
    setLiveLog((current) => ({
      ...current,
      title: current.title === translations['zh-CN'].operationLog || current.title === translations['en-US'].operationLog
        ? copy.operationLog
        : current.title,
    }))
  }, [copy.operationLog, copy.pageTitle, locale])

  useEffect(() => {
    void refreshStatus(true, target, selectedAppDir)
  }, [target])

  async function refreshStatus(
    silent = false,
    nextTarget: InstallTarget = target,
    appDir: string | undefined = nextTarget === 'manual' ? manualAppDir.trim() || undefined : undefined,
  ) {
    if (busyAction) return
    if (nextTarget === 'manual' && !appDir) {
      setStatus({
        ...PREVIEW_STATUS,
        state: 'missing',
        installed: false,
        localized: false,
        target: 'manual',
        installPath: copy.noManualPath,
        message: copy.missingText,
      })
      setLiveLog((current) => ({ ...current, updatedAt: timeLabel(locale) }))
      return
    }

    setBusyAction('refresh')
    setStatus((current) => ({ ...current, state: 'loading', message: copy.loadingText }))
    try {
      const nextStatus = await apiRef.current.getStatus(nextTarget, appDir)
      setStatus(nextStatus)
      setLiveLog((current) => ({ ...current, updatedAt: timeLabel(locale) }))
      if (!silent) {
        addActivity({
          tone: nextStatus.localized ? 'good' : nextStatus.installed ? 'warn' : 'danger',
          title: copy.statusComplete,
          summary: translatedStatusMessage(nextStatus, locale, copy),
        })
      }
    } catch (error) {
      addActivity({ tone: 'danger', title: copy.statusFailed, summary: String(error) })
      setStatus((current) => ({ ...current, state: 'error', message: copy.statusFailedMessage }))
    } finally {
      setBusyAction(null)
    }
  }

  async function browseForAppDir() {
    if (busy) return
    if (!isTauriRuntime()) {
      setTarget('manual')
      return
    }
    try {
      const selected = await selectClaudeDirectory(copy.chooseDialogTitle)
      if (!selected) return
      setManualAppDir(selected)
      setTarget('manual')
      await refreshStatus(true, 'manual', selected)
    } catch (error) {
      addActivity({ tone: 'danger', title: copy.statusFailed, summary: String(error) })
    }
  }

  async function runAction(command: Exclude<ActionCommand, 'refresh'>) {
    if (busy) return
    setBusyAction(command)
    const actionName = actionLabels[command]
    const logTitle = locale === 'zh-CN' ? `${actionName}日志` : `${actionName} log`
    setLiveLog({ title: logTitle, content: `[${copy.startPrefix}] ${actionName}...`, updatedAt: timeLabel(locale) })
    try {
      let result
      if (command === 'install') result = await apiRef.current.install(target, selectedAppDir)
      else if (command === 'restore') result = await apiRef.current.restore(target, selectedAppDir)
      else if (command === 'open') result = await apiRef.current.open(target, selectedAppDir)
      else result = await apiRef.current.checkUpdate(target, selectedAppDir)

      const successMessage = locale === 'zh-CN'
        ? result.message
        : command === 'install'
          ? copy.installSuccess
          : command === 'restore'
            ? copy.restoreSuccess
            : command === 'open'
              ? copy.openSuccess
              : copy.updateSuccess
      const resultMessage = result.ok ? successMessage : result.message
      setLiveLog({ title: logTitle, content: result.log, updatedAt: timeLabel(locale) })
      setStatus((current) => ({ ...current, state: result.state, localized: result.state === 'ready', message: resultMessage }))
      addActivity({
        tone: result.ok ? 'good' : 'danger',
        title: locale === 'zh-CN'
          ? `${actionName}${result.ok ? copy.completeSuffix : copy.failedSuffix}`
          : `${actionName} ${result.ok ? copy.completeSuffix : copy.failedSuffix}`,
        summary: resultMessage,
        detail: result.log,
      })
      if (command !== 'open') {
        const nextStatus = await apiRef.current.getStatus(target, selectedAppDir)
        setStatus(nextStatus)
      }
    } catch (error) {
      const detail = String(error)
      setLiveLog({ title: logTitle, content: detail, updatedAt: timeLabel(locale) })
      addActivity({
        tone: 'danger',
        title: locale === 'zh-CN' ? `${actionName}${copy.failedSuffix}` : `${actionName} ${copy.failedSuffix}`,
        summary: copy.actionFailedMessage,
        detail,
      })
    } finally {
      setBusyAction(null)
    }
  }

  function addActivity(activity: Omit<Activity, 'id' | 'time'>) {
    const next: Activity = { ...activity, id: nextActivityId.current, time: timeLabel(locale) }
    nextActivityId.current += 1
    setActivities((current) => [next, ...current].slice(0, 5))
  }

  async function copyValue(value: string, label: string) {
    try {
      await navigator.clipboard?.writeText(value)
      setCopied(label)
      window.setTimeout(() => setCopied(null), 1400)
    } catch {
      addActivity({ tone: 'warn', title: copy.clipboardFailed, summary: copy.clipboardFailedMessage })
    }
  }

  const diagnosticText = [
    `${copy.statusLabel}: ${currentStatusText}`,
    `${copy.claudeLabel}: ${displayInstallPath}`,
    `${copy.versionLabel}: ${status.version}`,
    `${copy.languageLabel}: ${translateCheckText(status.language, copy)}`,
    displayedLogContent,
    ...activities.map((activity) => `${translatedActivityText(activity.title, copy)}\n${translatedActivityText(activity.summary, copy)}\n${activity.detail ?? ''}`),
  ].join('\n')

  return (
    <main className="app-shell">
      <header className="top-bar">
        <div className="brand-lockup">
          <img className="brand-mark" src="/claude-icon.svg" alt="" />
          <div>
            <div className="brand-line">
              <strong>{copy.appName}</strong>
              <span className="version-tag">{isTauriRuntime() ? copy.desktopEdition : copy.previewEdition}</span>
            </div>
            <span className="brand-subtitle">{copy.subtitle}</span>
          </div>
        </div>
        <div className="top-actions">
          <div className="language-control" role="group" aria-label={copy.language}>
            <Languages size={15} aria-hidden="true" />
            <button className={locale === 'zh-CN' ? 'active' : ''} type="button" onClick={() => setLocale('zh-CN')}>中</button>
            <button className={locale === 'en-US' ? 'active' : ''} type="button" onClick={() => setLocale('en-US')}>EN</button>
          </div>
          <span className="connection-state"><span className="state-dot" />{isTauriRuntime() ? copy.localEngine : copy.localPreview}</span>
          <button className="ghost-button" type="button" onClick={() => void refreshStatus()} disabled={busy}>
            {busyAction === 'refresh' ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
            {copy.refresh}
          </button>
        </div>
      </header>

      <div className="workspace" aria-busy={busy}>
        <section className="main-panel">
          <div className="hero-meta">
            <span className={`status-pill ${statusTone(status)}`}>{statusLabel(status, copy)}</span>
            <span className="sync-label">{copy.lastChecked} {liveLog.updatedAt}</span>
          </div>
          <div className="hero-copy">
            <span className="section-kicker">{copy.localManagement}</span>
            <h1>{status.localized ? copy.heroReady : copy.heroInstall}</h1>
            <p>{currentStatusText}</p>
          </div>

          <section className="setup-section" aria-labelledby="setup-title">
            <div className="section-heading">
              <div><span className="section-kicker">{copy.setupKicker}</span><h2 id="setup-title">{copy.setupTitle}</h2></div>
              <ShieldCheck size={20} aria-hidden="true" />
            </div>
            <div className="target-row">
              <label className="field-label" htmlFor="install-target">{copy.installLocation}</label>
              <div className="select-wrap">
                <select id="install-target" value={target} onChange={(event) => setTarget(event.target.value as InstallTarget)} disabled={busy}>
                  {targetOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
                <FolderOpen size={16} aria-hidden="true" />
              </div>
              <span className="field-note">{currentTarget.note}</span>
            </div>

            {target === 'manual' ? (
              <div className="manual-directory-row">
                <input
                  type="text"
                  value={manualAppDir}
                  onChange={(event) => setManualAppDir(event.target.value)}
                  onBlur={() => void refreshStatus(true, 'manual', manualAppDir.trim() || undefined)}
                  onKeyDown={(event) => { if (event.key === 'Enter') void refreshStatus(false, 'manual', manualAppDir.trim() || undefined) }}
                  placeholder={copy.manualPlaceholder}
                  aria-label={copy.manualPlaceholder}
                  disabled={busy}
                />
                <button className="browse-button" type="button" onClick={() => void browseForAppDir()} disabled={busy}>
                  <FolderOpen size={16} />{copy.browse}
                </button>
              </div>
            ) : null}

            <div className="path-preview"><FileText size={15} aria-hidden="true" /><code>{displayInstallPath}</code></div>
          </section>

          <div className="action-row">
            <button className="primary-button" type="button" onClick={() => void runAction(primaryAction)} disabled={busy || !status.installed}>
              {busyAction === primaryAction ? <Loader2 className="spin" size={18} /> : primaryAction === 'open' ? <Play size={18} /> : <Wrench size={18} />}
              {busy ? copy.processing : primaryLabel}
            </button>
            <button className="outline-button" type="button" onClick={() => void runAction('check-update')} disabled={busy || !status.installed}>
              <CloudDownload size={17} />{copy.checkUpdate}
            </button>
            <button className="outline-button" type="button" onClick={() => setShowRestoreConfirm(true)} disabled={busy || !status.installed}>
              <RotateCcw size={17} />{copy.restore}
            </button>
          </div>
          <p className={`action-hint ${status.localized ? 'good' : 'warn'}`}>{status.localized ? copy.installedHint : copy.installHint}</p>

          <section className="log-panel" aria-live="polite">
            <div className="panel-heading">
              <div>
                <div className="heading-with-badge"><h2>{liveLog.title}</h2><span className={`log-badge ${busy ? 'running' : 'done'}`}>{busy ? copy.running : copy.scanComplete}</span></div>
                <span className="panel-subtitle">{busy ? copy.refreshingOutput : copy.latestOutput}</span>
              </div>
              <div className="panel-tools">
                <button className="small-button" type="button" onClick={() => void copyValue(liveLog.content, 'log')} disabled={!liveLog.content} title={copy.copyLogTitle}>
                  {copied === 'log' ? <Check size={14} /> : <Clipboard size={14} />}{copied === 'log' ? copy.copied : copy.copy}
                </button>
                <button className="small-button" type="button" onClick={() => setLiveLog((current) => ({ ...current, content: '' }))} disabled={!liveLog.content} title={copy.clearLogTitle}>
                  <Trash2 size={14} />{copy.clear}
                </button>
              </div>
            </div>
            <pre>{displayedLogContent || copy.emptyLog}</pre>
          </section>
        </section>

        <aside className="side-panel">
          <section className="side-card status-card">
            <div className="panel-heading">
              <div><span className="section-kicker">{copy.environmentScan}</span><h2>{copy.currentStatus}</h2></div>
              <span className="card-version">v{status.version}</span>
            </div>
            <div className="status-list">
              {translatedChecks.map((check) => (
                <div className={`status-row ${check.tone}`} key={check.label}>
                  {status.state === 'loading' ? <Loader2 className="spin" size={17} /> : toneIcon(check.tone)}
                  <span>{check.label}</span><strong>{status.state === 'loading' ? copy.checking : check.value}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="side-card location-card">
            <div className="panel-heading">
              <div><span className="section-kicker">{copy.currentTarget}</span><h2>{currentTarget.label}</h2></div>
              <FolderOpen size={18} aria-hidden="true" />
            </div>
            <code className="location-path">{displayInstallPath}</code>
            <span className="location-note">{copy.locationNote}</span>
          </section>

          <section className="side-card diagnostic-card">
            <div className="panel-heading">
              <div><span className="section-kicker">{copy.traceableRecords}</span><h2>{copy.diagnostics}</h2></div>
              <button className="icon-text-button" type="button" onClick={() => void copyValue(diagnosticText, 'diagnostics')} title={copy.copyDiagnostics}>
                {copied === 'diagnostics' ? <Check size={14} /> : <Clipboard size={14} />}{copied === 'diagnostics' ? copy.copied : copy.copy}
              </button>
            </div>
            {activities.length === 0 ? (
              <div className="empty-state"><ShieldCheck size={22} aria-hidden="true" /><strong>{copy.noActivity}</strong><span>{copy.noActivityNote}</span></div>
            ) : (
              <ol className="activity-list">
                {activities.map((activity) => (
                  <li className={activity.tone} key={activity.id}>
                    {toneIcon(activity.tone)}
                    <div>
                      <div className="activity-title"><strong>{translatedActivityText(activity.title, copy)}</strong><time>{activity.time}</time></div>
                      <span>{translatedActivityText(activity.summary, copy)}</span>
                      {activity.detail ? <details><summary>{copy.technicalDetails}</summary><pre>{activity.detail}</pre></details> : null}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </aside>
      </div>

      {showRestoreConfirm ? (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowRestoreConfirm(false)}>
          <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="restore-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="confirm-icon"><RotateCcw size={19} aria-hidden="true" /></div>
            <button className="modal-close" type="button" onClick={() => setShowRestoreConfirm(false)} aria-label={copy.closeDialog} title={copy.closeDialog}><X size={17} /></button>
            <div className="confirm-content"><span className="section-kicker">{copy.restoreKicker}</span><h2 id="restore-title">{copy.restoreTitle}</h2><p>{copy.restoreDescription}</p></div>
            <div className="confirm-actions">
              <button className="outline-button" type="button" onClick={() => setShowRestoreConfirm(false)}>{copy.cancel}</button>
              <button className="danger-button" type="button" onClick={() => { setShowRestoreConfirm(false); void runAction('restore') }}><RotateCcw size={16} />{copy.confirmRestore}</button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  )
}

export default App
