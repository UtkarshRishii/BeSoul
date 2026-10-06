import { useCallback, useEffect, useRef, useState } from 'react'
import {
  defaultPreferences, type Confirmation, type Preferences, type Receipt, type RuntimeEvent,
  type RuntimeSnapshot, type RuntimeView, type SoulState,
} from './types'

export const initialView: RuntimeView = {
  connected: false, ready: false, preview: false, state: 'IDLE', messages: [], receipts: [],
  confirmations: [], events: [], notice: '', error: '', currentAction: '', audioLevel: 0,
  preferences: defaultPreferences, sequence: 0,
  totalInputTokens: 0, totalOutputTokens: 0, lastAudioUrl: '',
  speakingActive: false, microphoneActive: false, continuousListening: false, continuousPhase: 'off',
}

const aliases: Record<string, SoulState> = {
  READY: 'IDLE', PROCESSING: 'THINKING', RETRIEVING_MEMORY: 'THINKING', RESPONDING: 'THINKING',
  EXECUTING_TOOL: 'ACTING', CALLING_TOOL: 'THINKING', GENERATING_SPEECH: 'THINKING', GENERATING_VOICE: 'THINKING', STARTING: 'IDLE',
}
export function normalizeState(value: unknown): SoulState {
  const state = String(value || 'IDLE').toUpperCase().replace(/[\s-]+/g, '_')
  return aliases[state] || state as SoulState
}

const text = (value: unknown) => typeof value === 'string' ? value : ''
const friendlyTool = (name: string) => ({
  observe_screen: 'Looking at your screen', locate_target: 'Finding the right control',
  click_target: 'Using the selected control', open_application: 'Opening an application',
  click_mouse: 'Using the selected control', double_click: 'Opening the selected item',
  right_click: 'Opening the context menu', keyboard_shortcut: 'Using a keyboard shortcut',
  finalize_task: 'Preparing your response',
  focus_application: 'Focusing an application', verify_result: 'Checking the result',
  type_text: 'Entering text', press_key: 'Using the keyboard', scroll: 'Navigating the page',
  open_url: 'Opening a page', search_youtube: 'Searching YouTube',
} as Record<string, string>)[name] || name.replace(/_/g, ' ')

function receiptFrom(event: RuntimeEvent, previous?: Receipt): Receipt {
  const p = event.payload
  const nested = p.result && typeof p.result === 'object' ? p.result as Record<string, unknown> : {}
  const tool = text(p.tool_name) || text(p.name) || text(p.tool) || previous?.tool || 'Action'
  const success = p.success ?? nested.success
  const verified = p.desired_result_verified ?? nested.desired_result_verified
  const dispatched = p.action_dispatched ?? nested.action_dispatched
  const status: Receipt['status'] = event.type === 'ToolStarted' ? 'running'
    : event.type === 'ToolFailed' || success === false ? 'failed'
    : verified === true ? 'verified' : dispatched === true ? 'dispatched' : 'completed'
  return {
    id: text(p.execution_id) || previous?.id || `${event.task_id || ''}:${tool}:${event.sequence}`,
    tool, summary: text(p.summary) || text(p.message) || text(nested.summary) || text(nested.message) || friendlyTool(tool),
    status, elapsed: typeof p.duration_ms === 'number' ? p.duration_ms : previous?.elapsed, event,
  }
}

/** Reducer consumes real runtime events only. Duplicate/replayed events are ignored. */
export function reduceEvent(view: RuntimeView, event: RuntimeEvent): RuntimeView {
  if (event.sequence <= view.sequence) return view
  const next: RuntimeView = { ...view, sequence: event.sequence, events: [...view.events, event].slice(-200) }
  const p = event.payload || {}
  switch (event.type) {
    case 'StateChanged':
      next.state = normalizeState(p.state || p.current)
      if (next.state !== 'SPEAKING' && next.state !== 'LISTENING') next.audioLevel = 0
      break
    case 'RuntimeReady': next.ready = true; next.error = ''; break
    case 'StartupFailed': case 'RuntimeError': next.ready = false; next.error = text(p.message) || 'Soul could not start. Check your desktop configuration.'; break
    case 'UserMessageReceived':
      next.messages = [...view.messages, {
        id: String(event.sequence), role: 'user' as const, text: text(p.text) || text(p.message),
        streaming: false, task_id: event.task_id,
      }].slice(-100)
      next.error = ''; next.notice = ''
      break
    case 'AssistantResponseStarted':
      next.messages = [...view.messages, {
        id: String(event.sequence), role: 'assistant' as const, text: '', streaming: true, task_id: event.task_id,
      }].slice(-100)
      break
    case 'AssistantTokenReceived': {
      const messages = [...view.messages]
      let last = messages.at(-1)
      if (!last || last.role !== 'assistant') {
        last = { id: String(event.sequence), role: 'assistant', text: '', streaming: true, task_id: event.task_id }
        messages.push(last)
      }
      messages[messages.length - 1] = { ...last, text: (last.text + text(p.token)).slice(-120_000), streaming: true }
      next.messages = messages
      break
    }
    case 'AssistantResponseEnded':
      next.messages = view.messages.map((message, i) => i === view.messages.length - 1 ? { ...message, streaming: false } : message)
      break
    case 'ToolStarted': case 'ToolCompleted': case 'ToolFailed': {
      const tool = text(p.tool_name) || text(p.name) || text(p.tool)
      const execution = text(p.execution_id)
      const previous = [...view.receipts].reverse().find(r => execution ? r.id === execution : r.tool === tool && r.status === 'running')
      const receipt = receiptFrom(event, previous)
      next.receipts = previous ? view.receipts.map(r => r.id === previous.id ? receipt : r) : [...view.receipts, receipt].slice(-80)
      next.currentAction = tool === 'finalize_task' ? 'Preparing your response' : receipt.summary
      break
    }
    case 'ConfirmationRequested':
      if (typeof p.confirmation_id !== 'string') break
      next.confirmations = [...view.confirmations.filter(c => c.confirmation_id !== p.confirmation_id), p as unknown as Confirmation]
      break
    case 'ConfirmationResolved':
      next.confirmations = view.confirmations.filter(c => c.confirmation_id !== p.confirmation_id)
      break
    case 'Notice': case 'ModelChanged': next.notice = text(p.message); break
    case 'Error': next.error = text(p.message); break
    case 'SpeechStarted':
      next.speakingActive = true
      next.state = 'SPEAKING'
      if (p.audio_url && p.playback !== 'native') next.lastAudioUrl = text(p.audio_url)
      break
    case 'SpeechEnded':
      next.speakingActive = false
      if (next.state === 'SPEAKING') next.state = 'IDLE'
      next.audioLevel = 0
      break
    case 'MicrophoneStarted': next.microphoneActive = true; next.state = 'LISTENING'; break
    case 'MicrophoneStopped': case 'MicrophoneCancelled':
      next.microphoneActive = false
      next.audioLevel = 0
      break
    case 'ContinuousListeningChanged':
      next.continuousListening = p.enabled === true
      next.continuousPhase = p.phase === 'listening' ? 'listening' : p.phase === 'paused' ? 'paused' : 'off'
      break
    case 'TurnCompleted':
      next.totalInputTokens = (view.totalInputTokens || 0) + Number(p.input_tokens || 0)
      next.totalOutputTokens = (view.totalOutputTokens || 0) + Number(p.output_tokens || 0)
      next.lastTurnStats = {
        input_tokens: Number(p.input_tokens || 0),
        output_tokens: Number(p.output_tokens || 0),
        gemini_seconds: Number(p.gemini_seconds || 0),
        tool_seconds: Number(p.tool_seconds || 0),
        model: text(p.model) || view.preferences.gemini_text_model || 'gemini-3.5-flash',
        first_token_seconds: Number(p.first_token_seconds || 0),
      }
      break
    case 'AudioAmplitude': case 'SpeechAmplitude': case 'MicrophoneAmplitude':
      next.audioLevel = Math.max(0, Math.min(1, Number(p.amplitude ?? p.level ?? 0)))
      break
    case 'PreferencesChanged': next.preferences = { ...view.preferences, ...p.preferences as Partial<Preferences> }; break
    case 'TaskCompleted': next.currentAction = ''; break
    case 'TaskInterrupted':
      next.currentAction = text(p.message) || 'Request stopped'
      next.messages = view.messages.map(m => ({ ...m, streaming: false }))
      next.audioLevel = 0
      next.speakingActive = false
      next.microphoneActive = false
      break
    case 'ConversationCleared': next.messages = []; break
  }
  return next
}

export function snapshotView(snapshot: Partial<RuntimeSnapshot>): RuntimeView {
  const events = Array.isArray(snapshot?.events) ? snapshot.events : []
  const previous = events.reduce(reduceEvent, initialView)
  return {
    ...previous,
    connected: true,
    ready: snapshot?.ready ?? true,
    preview: snapshot?.preview ?? false,
    state: normalizeState(snapshot?.state || 'IDLE'),
    preferences: { ...defaultPreferences, ...(snapshot?.preferences || {}) },
    sequence: snapshot?.sequence || 0,
    messages: Array.isArray(snapshot?.messages) ? snapshot.messages : [],
    confirmations: Array.isArray(snapshot?.confirmations) ? snapshot.confirmations : [],
    totalInputTokens: snapshot?.total_input_tokens ?? previous.totalInputTokens ?? 0,
    totalOutputTokens: snapshot?.total_output_tokens ?? previous.totalOutputTokens ?? 0,
    lastAudioUrl: previous.lastAudioUrl || '',
    continuousListening: snapshot?.continuous_listening ?? previous.continuousListening,
    continuousPhase: snapshot?.continuous_phase ?? previous.continuousPhase,
    microphoneActive: snapshot?.microphone_active ?? previous.microphoneActive,
    speakingActive: snapshot?.speaking_active ?? previous.speakingActive,
  }
}

function getToken(): string {
  const token = new URLSearchParams(window.location.hash.slice(1)).get('token')
  if (token) {
    sessionStorage.setItem('soul-session', token)
    history.replaceState(null, '', window.location.pathname)
    return token
  }
  return sessionStorage.getItem('soul-session') || ''
}

export function useRuntime() {
  const [token] = useState(getToken)
  const [view, setView] = useState<RuntimeView>(() => ({ ...initialView, preview: !token }))
  const reconnectTimer = useRef<number | null>(null)
  const sequence = useRef(0)

  const api = useCallback(async <T = Record<string, unknown>>(path: string, method = 'GET', body?: unknown): Promise<T> => {
    if (!token) {
      if (path === 'preferences' && method === 'PATCH') {
        setView(v => ({ ...v, preferences: { ...v.preferences, ...body as Partial<Preferences> } }))
        return { restart_required: false } as T
      }
      throw new Error('Open the Soul desktop app to use voice and AI.')
    }
    const response = await fetch(`/api/${path}`, {
      method, credentials: 'omit',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    const result = await response.json().catch(() => ({ error: 'The desktop connection is unavailable.' }))
    if (!response.ok) throw new Error(result.error || 'Soul could not complete this request.')
    return result as T
  }, [token])

  useEffect(() => {
    let active = true
    let socket: WebSocket | undefined
    let retry = 700
    let connecting = false

    async function connect() {
      if (connecting || !active) return
      connecting = true
      try {
        const snapshot = await api<RuntimeSnapshot>('bootstrap')
        if (!active) return
        sequence.current = snapshot.sequence || 0
        setView(snapshotView(snapshot))
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        socket = new WebSocket(`${protocol}//${window.location.host}/api/events?since=${sequence.current}`, [`soul.${token}`])
        socket.onopen = () => { retry = 700; setView(v => ({ ...v, connected: true })) }
        socket.onmessage = message => {
          try {
            const event = JSON.parse(message.data) as RuntimeEvent
            sequence.current = Math.max(sequence.current, event.sequence)
            setView(v => reduceEvent(v, event))
          } catch { setView(v => ({ ...v, error: 'A runtime event could not be read.' })) }
        }
        socket.onclose = scheduleReconnect
        socket.onerror = () => socket?.close()
      } catch (error) {
        if (!active) return
        setView(v => ({ ...v, connected: false, ready: false, microphoneActive: false,
          speakingActive: false, audioLevel: 0,
          error: token ? (error instanceof Error ? error.message : 'Reconnecting to Soul…') : '',
        }))
        if (token) scheduleReconnect()
      } finally { connecting = false }
    }

    function scheduleReconnect() {
      if (!active) return
      setView(v => ({ ...v, connected: false, ready: false, microphoneActive: false, speakingActive: false, audioLevel: 0 }))
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      reconnectTimer.current = window.setTimeout(connect, retry)
      retry = Math.min(retry * 2, 10_000)
    }

    if (token) void connect()
    return () => {
      active = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      socket?.close()
    }
  }, [api, token])

  const setError = useCallback((message: string) => setView(v => ({ ...v, error: message })), [])
  return { view, api, setError }
}
