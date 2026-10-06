import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Icon } from './Icons'
import type { Preferences, RuntimeView } from './types'

type Api = <T = Record<string, unknown>>(path: string, method?: string, body?: unknown) => Promise<T>
const tabs = ['AI', 'Voice', 'Vision', 'Automation', 'Memory', 'Privacy', 'Appearance', 'Advanced', 'Developer'] as const
type Tab = typeof tabs[number]
const icons: Record<Tab, string> = { AI: 'spark', Voice: 'voice', Vision: 'eye', Automation: 'action', Memory: 'memory', Privacy: 'shield', Appearance: 'spark', Advanced: 'settings', Developer: 'code' }

export function Modal({ children, title, onClose, className = '' }: { children: ReactNode; title: string; onClose: () => void; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const container = ref.current
    container?.querySelector<HTMLElement>('button, input, select')?.focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.stopImmediatePropagation(); onClose() }
      if (event.key === 'Tab' && container) {
        const items = [...container.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')]
        const first = items[0], last = items.at(-1)
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
      }
    }
    document.addEventListener('keydown', keydown, true)
    return () => { document.removeEventListener('keydown', keydown, true); previous?.focus() }
  }, [onClose])
  return <div className="modal-backdrop" onPointerDown={event => { if (event.target === event.currentTarget) onClose() }}>
    <div className={`modal ${className}`} role="dialog" aria-modal="true" aria-label={title} ref={ref}>
      {children}
    </div>
  </div>
}

export function Toggle({ label, description, checked, onChange }: { label: string; description?: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <label className="setting-row">
    <span><strong>{label}</strong>{description && <small>{description}</small>}</span>
    <input className="switch-input" type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} />
    <span className="switch" aria-hidden="true" />
  </label>
}

export function Settings({ view, api, onClose }: { view: RuntimeView; api: Api; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>('AI')
  const [draft, setDraft] = useState(view.preferences)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [failed, setFailed] = useState(false)
  const [memories, setMemories] = useState<{ id: number; content: string; category: string }[]>([])
  const [memoryStatus, setMemoryStatus] = useState('')
  const patch = <K extends keyof Preferences>(key: K, value: Preferences[K]) => setDraft(p => ({ ...p, [key]: value }))
  useEffect(() => { setDraft(view.preferences) }, [view.preferences])

  async function save() {
    const changed = Object.fromEntries(Object.entries(draft).filter(([key, value]) => value !== view.preferences[key as keyof Preferences]))
    if (!Object.keys(changed).length) { setMessage('Your preferences are up to date.'); setFailed(false); return }
    setSaving(true); setMessage('')
    try {
      const result = await api<{ restart_required: boolean }>('preferences', 'PATCH', changed)
      setFailed(false)
      setMessage(view.preview ? 'Preview preferences updated for this session.' : result.restart_required ? 'Saved. Restart SOUL to initialize newly enabled services.' : 'Preferences saved.')
    } catch (error) { setFailed(true); setMessage(error instanceof Error ? error.message : 'Preferences could not be saved.') }
    finally { setSaving(false) }
  }
  async function refreshMemories() {
    setMemoryStatus('Reading your local memories…')
    try {
      const result = await api<{ memories: typeof memories; available: boolean }>('memories')
      setMemories(result.memories)
      setMemoryStatus(result.available ? result.memories.length ? '' : 'No stored memories yet.' : 'Memory is not available in this session.')
    } catch (error) { setMemoryStatus(error instanceof Error ? error.message : 'Memories could not be read.') }
  }
  async function forget(id?: number) {
    try { await api('message', 'POST', { text: id === undefined ? '/memory clear' : `/forget ${id}` }); onClose() }
    catch (error) { setMemoryStatus(error instanceof Error ? error.message : 'This request could not be submitted.') }
  }

  const content: Record<Tab, ReactNode> = {
    AI: <>
      <p className="settings-description">One intelligence, connected to your computer. SOUL uses your configured Gemini models for reasoning and perception.</p>
      <label className="field-label">Assistant name<input maxLength={40} value={draft.soul_name} onChange={e => patch('soul_name', e.target.value)} /></label>
      <label className="field-label">Reasoning model<input maxLength={120} value={draft.gemini_text_model} onChange={e => patch('gemini_text_model', e.target.value)} /><small>Configured identifier. Availability is verified when the model is used.</small></label>
      <label className="field-label">Response mode<select value={draft.soul_response_mode} onChange={e => patch('soul_response_mode', e.target.value as Preferences['soul_response_mode'])}><option value="full">Full · primary model</option><option value="fast">Fast · configured low latency mode</option></select></label>
      <div className="info-note"><Icon name="shield" />Your API key stays in the Python configuration. It is never sent to this interface.</div>
    </>,
    Voice: <>
      <p className="settings-description">Speak naturally, and interrupt whenever you need. Hold to talk, or enable Hands-free in the voice widget to keep the conversation going.</p>
      <Toggle label="Spoken replies" description="Read responses aloud using your selected voice engine." checked={draft.soul_tts_enabled} onChange={v => patch('soul_tts_enabled', v)} />
      <label className="field-label">Voice engine<select value={draft.soul_voice_engine} onChange={e => patch('soul_voice_engine', e.target.value as Preferences['soul_voice_engine'])}><option value="gemini">Gemini Live 3.5 TTS · natural, cloud generation</option></select><small>Gemini Live 3.5 TTS uses your configured voice and streams neural audio directly from Gemini.</small></label>
      <Toggle label="Push-to-talk" description="Hold the microphone button or hold Ctrl + Space. Release to send." checked={draft.soul_microphone_enabled} onChange={v => patch('soul_microphone_enabled', v)} />
      <label className="field-label">Gemini voice name<input value={draft.gemini_voice_name} maxLength={60} onChange={e => patch('gemini_voice_name', e.target.value)} /><small>Use a voice supported by your configured Gemini speech model.</small></label>
      <div className="info-note"><Icon name="mic" />Microphone: {view.microphoneActive ? 'active now' : view.continuousListening ? 'hands-free paused' : 'inactive'}. Hands-free is optional and pauses while Soul replies.</div>
    </>,
    Vision: <>
      <p className="settings-description">Vision Eye observes the desktop when a task needs it, grounds controls and checks what changed.</p>
      <Toggle label="Vision Eye" description="Allow task-based screen observation and visual grounding." checked={draft.soul_vision_enabled} onChange={v => patch('soul_vision_enabled', v)} />
      <div className="info-note"><Icon name="eye" />{view.state === 'SEEING' || view.state === 'VERIFYING' ? 'SOUL is observing the screen now.' : 'Screen observation is currently inactive.'}</div>
      <p className="setting-explanation">Screenshots are processed in memory and sent to Gemini for the current task. They are not saved as a local recording. Enabling a service requires a restart.</p>
    </>,
    Automation: <>
      <p className="settings-description">Let SOUL use validated capabilities to help with applications, browser tasks and Windows controls.</p>
      <Toggle label="Desktop automation" description="Allow registered tools and bounded desktop actions." checked={draft.soul_tools_enabled} onChange={v => patch('soul_tools_enabled', v)} />
      <div className="safety-controls"><Icon name="shield" size={23} /><strong>You keep control.</strong><p>Press Escape or Stop to interrupt. Move your mouse to a screen corner to trigger the desktop failsafe. Consequential actions ask for your permission.</p></div>
      <p className="setting-explanation">Disabling automation stops the active workflow. Existing action limits and confirmation gates remain enforced.</p>
    </>,
    Memory: <>
      <p className="settings-description">Keep useful preferences and recurring context. Durable facts stay in a local SQLite database.</p>
      <Toggle label="Remember useful context" description="Save selected, filtered facts between sessions." checked={draft.soul_memory_enabled} onChange={v => patch('soul_memory_enabled', v)} />
      <div className="memory-actions"><button className="secondary-button" disabled={!view.ready} onClick={refreshMemories}>Inspect memories</button><button className="text-button danger-text" disabled={!view.ready} onClick={() => forget()}>Clear all…</button></div>
      {memoryStatus && <p className="setting-explanation" role="status">{memoryStatus}</p>}
      <div className="memory-list">{memories.map(memory => <div key={memory.id}><span><small>{memory.category}</small><p>{memory.content}</p></span><button className="icon-button" aria-label={`Forget memory ${memory.id}`} onClick={() => forget(memory.id)}><Icon name="trash" /></button></div>)}</div>
      <p className="setting-explanation">Deletion asks for confirmation. Disabling memory also stops new extraction; enabling it requires a restart.</p>
    </>,
    Privacy: <>
      <p className="settings-description">Sensitive states stay visible. You decide when SOUL can listen, see, act and remember.</p>
      <div className="privacy-list">{[
        ['Microphone', view.microphoneActive ? 'Active · recording' : view.continuousListening ? 'Hands-free · paused' : 'Inactive', 'mic'],
        ['Screen perception', ['SEEING', 'VERIFYING'].includes(view.state) ? 'Observing this task' : 'Inactive', 'eye'],
        ['Persistent memory', view.preferences.soul_memory_enabled ? 'Enabled · local SQLite' : 'Disabled', 'memory'],
        ['Spoken replies', view.preferences.soul_tts_enabled ? 'Enabled' : 'Disabled', 'voice'],
        ['Automation', view.preferences.soul_tools_enabled ? 'Enabled · confirmation gates active' : 'Disabled', 'action'],
      ].map(([label, value, icon]) => <div key={label}><Icon name={icon} /><span>{label}</span><small>{value}</small></div>)}</div>
      <div className="info-note"><Icon name="shield" />Requests, selected context, screen observations and voice recordings are sent to the configured Gemini service when needed. Screen content cannot authorize actions.</div>
    </>,
    Appearance: <>
      <p className="settings-description">Quiet by default. Motion follows real assistant activity, with an accessible fallback for every computer.</p>
      <Toggle label="Reduce motion" description="Keep the central entity still. System accessibility preferences also apply." checked={draft.soul_reduced_motion} onChange={v => patch('soul_reduced_motion', v)} />
      <label className="field-label">Visual quality<select value={draft.soul_visual_quality} onChange={e => patch('soul_visual_quality', e.target.value as Preferences['soul_visual_quality'])}><option value="auto">Automatic · balanced</option><option value="low">Low · fewer particles, lower resolution</option><option value="high">High · detailed geometry</option></select></label>
      <div className="palette-preview"><span /><span /><span /><span /><p>Mint / slate</p></div>
      <p className="setting-explanation">The static visual fallback appears automatically when WebGL is unavailable.</p>
    </>,
    Advanced: <>
      <p className="settings-description">The existing Python runtime remains the source of truth. The presentation layer carries only authenticated local events.</p>
      <div className="privacy-list"><div><span>Desktop bridge</span><small>Loopback · authenticated</small></div><div><span>Physical input</span><small>Sequential · bounded</small></div><div><span>Completion reporting</span><small>Receipt and verification based</small></div></div>
      <p className="setting-explanation">Timeouts, action budgets, monitor selection and trusted configuration paths remain in Python configuration. Secrets and raw environment values are excluded from this interface.</p>
      <button className="secondary-button" onClick={() => { setMessage('CLI mode is available with: python main.py --cli'); setFailed(false) }}>CLI and recovery mode</button>
    </>,
    Developer: <>
      <p className="settings-description">Inspect the same events and tool receipts that drive this interface.</p>
      <Toggle label="Developer diagnostics" description="Enable runtime diagnostic logging and the event inspector." checked={draft.soul_debug} onChange={v => patch('soul_debug', v)} />
      <div className="privacy-list"><div><span>Connection</span><small>{view.connected ? 'Local bridge connected' : 'Disconnected'}</small></div><div><span>Last event sequence</span><small>{view.sequence}</small></div><div><span>Assistant state</span><small>{view.state}</small></div></div>
      <details className="developer-events"><summary>Recent runtime events</summary><pre>{JSON.stringify(view.events.slice(-8), null, 2)}</pre></details>
    </>,
  }
  return <Modal title="SOUL settings" onClose={onClose} className="settings-modal">
    <header className="modal-header"><div><span className="eyebrow">Make it yours</span><h2>Settings</h2></div><button className="icon-button" aria-label="Close settings" onClick={onClose}><Icon name="close" /></button></header>
    <div className="settings-body"><nav className="settings-nav" aria-label="Settings categories">{tabs.map(name => <button key={name} className={tab === name ? 'selected' : ''} aria-current={tab === name ? 'page' : undefined} onClick={() => setTab(name)}><Icon name={icons[name]} />{name}</button>)}</nav>
      <section className="settings-content"><h3>{tab}</h3>{content[tab]}</section></div>
    <footer className="modal-footer"><p role="status" className={failed ? 'danger-text' : ''}>{message || (view.preview ? 'Preview · preferences stay in this session.' : 'Stored on this computer.')}</p><button className="primary-button" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save preferences'}</button></footer>
  </Modal>
}

export function Onboarding({ view, api, onClose }: { view: RuntimeView; api: Api; onClose: () => void }) {
  const [draft, setDraft] = useState(view.preferences)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  async function complete() {
    setSaving(true)
    try { await api('preferences', 'PATCH', { ...draft, soul_onboarding_complete: true }); onClose() }
    catch (error) { setError(error instanceof Error ? error.message : 'Preferences could not be saved.') }
    finally { setSaving(false) }
  }
  return <Modal title="Welcome to SOUL" onClose={onClose} className="onboarding-modal">
    <header className="modal-header"><span className="eyebrow">Welcome to Soul</span><button className="icon-button" aria-label="Skip welcome for this session" onClick={onClose}><Icon name="close" /></button></header>
    <div className="onboarding-intro"><div className="onboarding-mark"><Icon name="spark" size={33} /></div><h2>A little more possibility.<br />A lot more presence.</h2><p>Talk naturally. Let SOUL see your screen, help with tasks and remember what matters. You stay in control.</p></div>
    <div className="onboarding-capabilities">{[['voice', 'Talk'], ['eye', 'See'], ['action', 'Act'], ['memory', 'Remember']].map(([icon, label]) => <span key={label}><Icon name={icon} />{label}</span>)}</div>
    <div className="onboarding-options">
      <label className="field-label">Call your assistant<input value={draft.soul_name} maxLength={40} onChange={e => setDraft(p => ({ ...p, soul_name: e.target.value }))} /></label>
      <Toggle label="Voice replies" checked={draft.soul_tts_enabled} onChange={v => setDraft(p => ({ ...p, soul_tts_enabled: v }))} />
      <Toggle label="Push-to-talk microphone" checked={draft.soul_microphone_enabled} onChange={v => setDraft(p => ({ ...p, soul_microphone_enabled: v }))} />
      <Toggle label="Task-based screen vision" checked={draft.soul_vision_enabled} onChange={v => setDraft(p => ({ ...p, soul_vision_enabled: v }))} />
      <Toggle label="Desktop automation" checked={draft.soul_tools_enabled} onChange={v => setDraft(p => ({ ...p, soul_tools_enabled: v }))} />
      <Toggle label="Useful local memories" checked={draft.soul_memory_enabled} onChange={v => setDraft(p => ({ ...p, soul_memory_enabled: v }))} />
    </div>
    <p className="onboarding-safety"><Icon name="shield" />Press Escape or Stop at any time. Hold the microphone to speak; release to send. Screen observations and requests go to Gemini when needed.</p>
    {error && <p className="danger-text" role="alert">{error}</p>}
    <button className="primary-button onboarding-continue" disabled={saving} onClick={complete}>{saving ? 'Saving…' : 'Meet your Soul'}<Icon name="chevron" size={16} /></button>
  </Modal>
}
