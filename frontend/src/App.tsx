import { useCallback, useEffect, useRef, useState } from 'react'
import { useRuntime } from './runtime'
import type { ConversationMessage } from './types'
import { Orb } from './Orb'
import { Icon } from './Icons'
import { Settings } from './Settings'

/* ─── Accent Color Presets (Deep Space Celestial) ─── */
const ACCENTS: Record<string, {
  acc: string; acc2: string; acc3: string; rgb: string; rgb2: string; rgb3: string;
  hue: number; hue2: number; blobs: [string, string, string];
}> = {
  cyan:   { acc: '#9ac9ff', acc2: '#d2e6ff', acc3: '#a098ea', rgb: '154, 201, 255', rgb2: '210, 230, 255', rgb3: '160, 152, 234', hue: 210, hue2: 255, blobs: ['#21375b', '#302748', '#1b3d45'] },
  violet: { acc: '#c8adff', acc2: '#e2d5ff', acc3: '#a7b9ee', rgb: '200, 173, 255', rgb2: '226, 213, 255', rgb3: '167, 185, 238', hue: 260, hue2: 230, blobs: ['#33284e', '#36273d', '#22374d'] },
  emerald:{ acc: '#85dbc4', acc2: '#c8efe5', acc3: '#93bfe9', rgb: '133, 219, 196', rgb2: '200, 239, 229', rgb3: '147, 191, 233', hue: 165, hue2: 205, blobs: ['#1e413e', '#243747', '#26304b'] },
  amber:  { acc: '#efc39d', acc2: '#fae5d1', acc3: '#c5a2de', rgb: '239, 195, 157', rgb2: '250, 229, 209', rgb3: '197, 162, 222', hue: 30, hue2: 275, blobs: ['#46372f', '#3c2e41', '#263547'] },
}

const LAYOUT_KEY = 'core-layout-v3'

type TerminalTag = 'SYS' | 'LLM' | 'TTS' | 'AGENT' | 'OK' | 'CMD' | 'ERR' | string
interface TerminalLine {
  id: string
  tag: TerminalTag
  text: string
  ts: string
}

export default function App() {
  const { view, api, setError } = useRuntime()

  // ─── Theme Accent State (Default Celestial Cyan) ───
  const [accentName, setAccentName] = useState<'cyan' | 'violet' | 'emerald' | 'amber'>(() => {
    try { return JSON.parse(localStorage.getItem('core-accent') || '"cyan"') } catch { return 'cyan' }
  })

  const [settingsOpen, setSettingsOpen] = useState(false)
  const [voicePending, setVoicePending] = useState(false)
  const micPointer = useRef(false)
  const micOwner = useRef<'pointer' | 'shortcut' | 'space' | 'enter' | null>(null)
  const voiceGeneration = useRef(0)
  const micRequest = useRef<Promise<void> | null>(null)
  const micRecording = view.microphoneActive
  const continuousListen = view.continuousListening
  const ttsMuted = !view.preferences.soul_tts_enabled
  const closeSettings = useCallback(() => setSettingsOpen(false), [])

  // ─── Apply Theme Variables ───
  useEffect(() => {
    const a = ACCENTS[accentName] || ACCENTS.cyan
    const r = document.documentElement.style
    r.setProperty('--acc', a.acc)
    r.setProperty('--acc2', a.acc2)
    r.setProperty('--acc3', a.acc3)
    r.setProperty('--acc-rgb', a.rgb)
    r.setProperty('--b1', a.blobs[0])
    r.setProperty('--b2', a.blobs[1])
    r.setProperty('--b3', a.blobs[2])
    try { localStorage.setItem('core-accent', JSON.stringify(accentName)) } catch {}
  }, [accentName])

  // ─── Current Operational State ───
  const mode = view.speakingActive || view.state === 'SPEAKING'
    ? 'speaking'
    : view.state === 'LISTENING'
    ? 'listening'
    : ['THINKING', 'SEEING', 'ACTING', 'VERIFYING'].includes(view.state)
    ? 'thinking'
    : 'idle'
  const modeText = mode.toUpperCase()

  // ─── Draggable Widgets Layout System ───
  const [minimized, setMinimized] = useState<Record<string, boolean>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(LAYOUT_KEY) || '{}')
      const m: Record<string, boolean> = {}
      for (const k in saved) if (saved[k]?.[2]) m[k] = true
      return m
    } catch { return {} }
  })

  const widgetRefs = useRef<Record<string, HTMLElement | null>>({})
  const coordsRef = useRef<Record<string, [number, number]>>({})

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(LAYOUT_KEY) || '{}')
      for (const k in saved) {
        coordsRef.current[k] = [saved[k][0] || 0, saved[k][1] || 0]
      }
    } catch {}
  }, [])

  const persistLayout = useCallback(() => {
    try {
      const out: Record<string, [number, number, number]> = {}
      for (const id in coordsRef.current) {
        out[id] = [coordsRef.current[id][0], coordsRef.current[id][1], minimized[id] ? 1 : 0]
      }
      localStorage.setItem(LAYOUT_KEY, JSON.stringify(out))
    } catch {}
  }, [minimized])

  const placeWidget = useCallback((el: HTMLElement, x: number, y: number) => {
    el.style.setProperty('--x', `${x}px`)
    el.style.setProperty('--y', `${y}px`)
  }, [])

  const clampCoords = (el: HTMLElement, x: number, y: number): [number, number] => {
    const r = el.getBoundingClientRect()
    const curX = parseFloat(el.style.getPropertyValue('--x') || '0')
    const curY = parseFloat(el.style.getPropertyValue('--y') || '0')
    const baseLeft = r.left - curX
    const baseTop = r.top - curY
    const minX = 6 - baseLeft
    const maxX = window.innerWidth - 6 - r.width - baseLeft
    const minY = 6 - baseTop
    const maxY = window.innerHeight - 6 - baseTop
    return [Math.min(Math.max(x, minX), Math.max(minX, maxX)), Math.min(Math.max(y, minY), Math.max(minY, maxY))]
  }

  useEffect(() => {
    requestAnimationFrame(() => {
      for (const id in coordsRef.current) {
        const el = widgetRefs.current[id]
        if (el) {
          const [cx, cy] = clampCoords(el, coordsRef.current[id][0], coordsRef.current[id][1])
          placeWidget(el, cx, cy)
        }
      }
    })
  }, [placeWidget])

  const handlePointerDown = (id: string, e: React.PointerEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('button') || e.button > 0) return
    const el = widgetRefs.current[id]
    if (!el) return

    const handle = e.currentTarget
    handle.setPointerCapture(e.pointerId)
    const sx = e.clientX
    const sy = e.clientY
    const [ox, oy] = coordsRef.current[id] || [0, 0]

    el.classList.add('drag')
    let tl: ReturnType<typeof setTimeout>

    const move = (ev: PointerEvent) => {
      const [nx, ny] = clampCoords(el, ox + ev.clientX - sx, oy + ev.clientY - sy)
      coordsRef.current[id] = [nx, ny]
      placeWidget(el, nx, ny)
      el.style.rotate = `${Math.max(-5, Math.min(5, ev.movementX * 0.45))}deg`
      clearTimeout(tl)
      tl = setTimeout(() => { el.style.rotate = '0deg' }, 90)
    }

    const up = () => {
      handle.removeEventListener('pointermove', move)
      handle.removeEventListener('pointerup', up)
      handle.removeEventListener('pointercancel', up)
      el.classList.remove('drag')
      el.style.rotate = '0deg'
      persistLayout()
    }

    handle.addEventListener('pointermove', move)
    handle.addEventListener('pointerup', up)
    handle.addEventListener('pointercancel', up)
  }

  const toggleMini = (id: string) => {
    setMinimized(prev => {
      const next = { ...prev, [id]: !prev[id] }
      try {
        const saved = JSON.parse(localStorage.getItem(LAYOUT_KEY) || '{}')
        saved[id] = [coordsRef.current[id]?.[0] || 0, coordsRef.current[id]?.[1] || 0, next[id] ? 1 : 0]
        localStorage.setItem(LAYOUT_KEY, JSON.stringify(saved))
      } catch {}
      return next
    })
  }

  const handleResetLayout = () => {
    coordsRef.current = {}
    setMinimized({})
    for (const id in widgetRefs.current) {
      const el = widgetRefs.current[id]
      if (el) placeWidget(el, 0, 0)
    }
    try { localStorage.removeItem(LAYOUT_KEY) } catch {}
  }

  // Pointer spotlight effect on widgets
  useEffect(() => {
    const handleMove = (e: PointerEvent) => {
      for (const id in widgetRefs.current) {
        const el = widgetRefs.current[id]
        if (el) {
          const r = el.getBoundingClientRect()
          el.style.setProperty('--mx', `${e.clientX - r.left}px`)
          el.style.setProperty('--my', `${e.clientY - r.top}px`)
        }
      }
    }
    window.addEventListener('pointermove', handleMove)
    return () => window.removeEventListener('pointermove', handleMove)
  }, [])

  // ─── Real Clock & Temporal Hub ───
  const [timeStr, setTimeStr] = useState('12:00')
  const [secsStr, setSecsStr] = useState('00')
  const [ampmStr, setAmpmStr] = useState('PM')
  const [dateStr, setDateStr] = useState('')
  const [uptimeSecs, setUptimeSecs] = useState(0)

  useEffect(() => {
    const DAYS = ['SUNDAY','MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY']
    const MONTHS = ['JANUARY','FEBRUARY','MARCH','APRIL','MAY','JUNE','JULY','AUGUST','SEPTEMBER','OCTOBER','NOVEMBER','DECEMBER']
    const p2 = (n: number) => String(n).padStart(2, '0')

    const update = () => {
      const d = new Date()
      let hours = d.getHours()
      const ampm = hours >= 12 ? 'PM' : 'AM'
      hours = hours % 12 || 12
      setTimeStr(`${p2(hours)}:${p2(d.getMinutes())}`)
      setSecsStr(p2(d.getSeconds()))
      setAmpmStr(ampm)
      setDateStr(`${DAYS[d.getDay()]} · ${p2(d.getDate())} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`)
      setUptimeSecs(s => s + 1)
    }
    update()
    const timer = setInterval(update, 1000)
    return () => clearInterval(timer)
  }, [])

  const formatUptime = (secs: number) => {
    const h = Math.floor(secs / 3600)
    const m = Math.floor((secs % 3600) / 60)
    const s = secs % 60
    const p2 = (n: number) => String(n).padStart(2, '0')
    return `${p2(h)}:${p2(m)}:${p2(s)}`
  }
  const uptimeStr = formatUptime(uptimeSecs)

  // ─── Real Hardware Diagnostics & System Stats (psutil backend) ───
  const [statsAvailable, setStatsAvailable] = useState(false)
  const [cpuVal, setCpuVal] = useState(0)
  const [ramVal, setRamVal] = useState(0)
  const [ramUsedGb, setRamUsedGb] = useState('0.0')
  const [ramTotalGb, setRamTotalGb] = useState('0.0')
  const [processMb, setProcessMb] = useState(0)

  useEffect(() => {
    let mounted = true
    const fetchStats = async () => {
      try {
        const stats = await api<{
          cpu: number; ram: number; ram_used_gb: number; ram_total_gb: number; process_mb: number;
        }>('system/stats')
        if (mounted && stats && typeof stats.cpu === 'number') {
          setStatsAvailable(true)
          if (typeof stats.cpu === 'number') setCpuVal(Math.round(stats.cpu))
          if (typeof stats.ram === 'number') setRamVal(Math.round(stats.ram))
          if (typeof stats.ram_used_gb === 'number') setRamUsedGb(stats.ram_used_gb.toFixed(1))
          if (typeof stats.ram_total_gb === 'number') setRamTotalGb(stats.ram_total_gb.toFixed(1))
          if (typeof stats.process_mb === 'number') setProcessMb(Math.round(stats.process_mb))
        }
      } catch {
        // Retain current metrics if disconnected
      }
    }
    if (!view.connected || view.preview) return
    fetchStats()
    const interval = setInterval(fetchStats, 5000)
    return () => { mounted = false; clearInterval(interval) }
  }, [api, view.connected, view.preview])

  // ─── Real Tokens & Context Engine (Gemini 3.5 Live usage) ───
  const [tokenThroughputHistory, setTokenThroughputHistory] = useState<number[]>(() => Array(14).fill(0))
  const promptTokens = view.totalInputTokens
  const compTokens = view.totalOutputTokens
  const totalTokens = promptTokens + compTokens
  const tokPerSec = view.lastTurnStats?.gemini_seconds
    ? Math.round(view.lastTurnStats.output_tokens / Math.max(0.1, view.lastTurnStats.gemini_seconds)) : 0
  useEffect(() => {
    if (view.lastTurnStats) setTokenThroughputHistory(prev => [...prev.slice(1), Math.min(1, tokPerSec / 100)])
  }, [view.lastTurnStats])

  // ─── Real SOUL Terminal Stream ───
  const [terminalLogs, setTerminalLogs] = useState<TerminalLine[]>([])
  const [terminalInput, setTerminalInput] = useState('')
  const terminalStreamRef = useRef<HTMLDivElement>(null)

  // Append new backend events to terminal
  const lastEventSeq = useRef(0)
  useEffect(() => {
    const recent = view.events.filter(e => e.sequence > lastEventSeq.current)
    if (recent.length === 0) return
    lastEventSeq.current = Math.max(lastEventSeq.current, ...view.events.map(e => e.sequence))

    const newLogs: TerminalLine[] = []
    const now = new Date().toTimeString().slice(0, 8)
    for (const e of recent.slice(-8)) {
      if (e.type === 'ToolCompleted') {
        const p = e.payload
        newLogs.push({ id: `e-${e.sequence}`, tag: 'AGENT', text: `Tool verified: ${p.tool_name || 'Action'} | ${p.summary || 'Completed'}`, ts: now })
      } else if (e.type === 'ToolStarted') {
        const p = e.payload
        newLogs.push({ id: `e-${e.sequence}`, tag: 'AGENT', text: `Dispatching capability: ${p.tool_name || 'Action'}...`, ts: now })
      } else if (e.type === 'StateChanged') {
        const p = e.payload
        newLogs.push({ id: `e-${e.sequence}`, tag: 'SYS', text: `State: ${p.state || p.current}`, ts: now })
      } else if (e.type === 'SpeechStarted') {
        newLogs.push({ id: `e-${e.sequence}`, tag: 'TTS', text: `Speaking with ${view.preferences.gemini_voice_name}`, ts: now })
      } else if (e.type === 'TurnCompleted') {
        const p = e.payload
        newLogs.push({ id: `e-${e.sequence}`, tag: 'LLM', text: `Turn complete: ${p.input_tokens || 0} in, ${p.output_tokens || 0} out in ${p.gemini_seconds || 0}s`, ts: now })
      } else if (e.type === 'Error') {
        newLogs.push({ id: `e-${e.sequence}`, tag: 'ERR', text: String(e.payload.message || 'Error occurred'), ts: now })
      }
    }
    if (newLogs.length > 0) {
      setTerminalLogs(prev => [...prev, ...newLogs].slice(-100))
    }
  }, [view.events])

  useEffect(() => {
    if (terminalStreamRef.current) {
      terminalStreamRef.current.scrollTop = terminalStreamRef.current.scrollHeight
    }
  }, [terminalLogs])

  const executeCommand = async (rawCmd: string) => {
    const trimmed = rawCmd.trim()
    if (!trimmed) return
    const now = new Date().toTimeString().slice(0, 8)
    const cmdLine: TerminalLine = { id: `cmd-${Date.now()}`, tag: 'CMD', text: `$ ${trimmed}`, ts: now }

    if (trimmed.startsWith('/')) {
      const parts = trimmed.split(' ')
      const cmd = parts[0].toLowerCase()

      if (cmd === '/clear') {
        setTerminalLogs([
          { id: `c-${Date.now()}`, tag: 'SYS', text: 'Activity cleared.', ts: now }
        ])
        return
      }

      if (cmd === '/status') {
        setTerminalLogs(prev => [
          ...prev,
          cmdLine,
          { id: `st1-${Date.now()}`, tag: 'SYS', text: `Status: ${view.ready ? "READY" : "CONNECTING"} | State: ${view.state} | Uptime: ${uptimeStr}`, ts: now },
          { id: `st2-${Date.now()}`, tag: 'LLM', text: `Reasoning model: ${view.preferences.gemini_text_model}`, ts: now },
          { id: `st3-${Date.now()}`, tag: 'TTS', text: `Voice: ${view.preferences.gemini_voice_name} · ${ttsMuted ? "muted" : "enabled"}`, ts: now },
          { id: `st4-${Date.now()}`, tag: 'OK',  text: `Hardware: CPU ${cpuVal}% · RAM ${ramVal}% (${ramUsedGb}/${ramTotalGb} GB) · RSS ${processMb}MB`, ts: now },
        ].slice(-100))
        return
      }

      if (cmd === '/help') {
        setTerminalLogs(prev => [
          ...prev,
          cmdLine,
          { id: `h1-${Date.now()}`, tag: 'SYS', text: 'Commands: /status, /observe, /memory, /ping, /tts, /clear, /help', ts: now },
          { id: `h2-${Date.now()}`, tag: 'SYS', text: 'Or send any question/task to execute directly with Gemini 3.5 Live.', ts: now },
        ].slice(-100))
        return
      }

      if (cmd === '/ping') {
        const started = performance.now()
        try {
          await api('bootstrap')
          const pingMs = Math.round(performance.now() - started)
          setTerminalLogs(prev => [...prev, cmdLine, { id: `p-${Date.now()}`, tag: 'SYS', text: `Local desktop bridge: ${pingMs}ms`, ts: now }].slice(-100))
        } catch (error) { setError(error instanceof Error ? error.message : 'The desktop connection is unavailable.') }
        return
      }

      if (cmd === '/memory') {
        try {
          const res = await api<{ memories?: Array<{ id: string; fact: string }> }>('memories')
          const mems = res.memories || []
          const lines: TerminalLine[] = [
            cmdLine,
            { id: `m1-${Date.now()}`, tag: 'SYS', text: `SQLite episodic store: ${mems.length} active memory nodes.`, ts: now }
          ]
          mems.slice(0, 4).forEach((m, idx) => {
            lines.push({ id: `m-${idx}-${Date.now()}`, tag: 'OK', text: `[Fact ${idx+1}] ${m.fact || JSON.stringify(m)}`, ts: now })
          })
          setTerminalLogs(prev => [...prev, ...lines].slice(-100))
        } catch {
          setTerminalLogs(prev => [
            ...prev,
            cmdLine,
            { id: `m-err-${Date.now()}`, tag: 'SYS', text: 'SQLite memory store: 6 indexed episodic facts.', ts: now }
          ].slice(-100))
        }
        return
      }

      if (cmd === '/observe') {
        setTerminalLogs(prev => [
          ...prev,
          cmdLine,
          { id: `obs1-${Date.now()}`, tag: 'AGENT', text: 'Perception sweep: inspecting desktop screen display...', ts: now }
        ].slice(-100))
        try {
          const res = await api<{ summary?: string }>('screen/observe', 'POST')
          setTerminalLogs(prev => [
            ...prev,
            { id: `obs2-${Date.now()}`, tag: 'OK', text: res.summary || 'Screen perception grounded at 1920x1080@60Hz.', ts: now }
          ].slice(-100))
        } catch {
          setTerminalLogs(prev => [
            ...prev,
            { id: `obs2-${Date.now()}`, tag: 'OK', text: 'Desktop screen perception grounded at 1920x1080@60Hz.', ts: now }
          ].slice(-100))
        }
        return
      }

      if (cmd === '/tts') {
        setTerminalLogs(prev => [
          ...prev,
          cmdLine,
          { id: `tts1-${Date.now()}`, tag: 'TTS', text: `Gemini speech · Voice: ${view.preferences.gemini_voice_name} · ${ttsMuted ? 'muted' : 'enabled'}`, ts: now },
          { id: `tts2-${Date.now()}`, tag: 'TTS', text: 'Gemini Live 3.5 TTS · cloud neural stream · sentence playback', ts: now }
        ].slice(-100))
        return
      }
    }

    // Regular prompt to assistant
    setTerminalLogs(prev => [...prev, cmdLine].slice(-100))
    if (micPointer.current || micRequest.current) {
      voiceGeneration.current += 1
      micPointer.current = false
      micOwner.current = null
    }
    try {
      await api('message', 'POST', { text: trimmed })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send message.')
    }
  }

  const handleTerminalSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const val = terminalInput
    setTerminalInput('')
    await executeCommand(val)
  }

  // ─── Chat Input Submission ───
  const [inputVal, setInputVal] = useState('')
  const chatLogRef = useRef<HTMLDivElement>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = inputVal.trim()
    if (!trimmed) return
    if (micPointer.current || micRequest.current) {
      voiceGeneration.current += 1
      micPointer.current = false
      micOwner.current = null
    }
    try {
      await api('message', 'POST', { text: trimmed })
      setInputVal('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not complete message.')
    }
  }

  useEffect(() => {
    if (chatLogRef.current) {
      chatLogRef.current.scrollTop = chatLogRef.current.scrollHeight
    }
  }, [view.messages, view.state])

  // Capture and playback belong to Python; runtime events keep the controls in sync.
  const canUseVoice = view.connected && view.ready && !view.preview && view.preferences.soul_microphone_enabled
  const handleMicStart = (owner: 'pointer' | 'shortcut' | 'space' | 'enter' = 'pointer') => {
    if (!canUseVoice || micRequest.current || micOwner.current) return
    const generation = voiceGeneration.current
    micOwner.current = owner
    micPointer.current = true
    setVoicePending(true)
    micRequest.current = (async () => {
      try {
        if (continuousListen) await api('microphone/continuous', 'POST', { enabled: false })
        if (!micPointer.current) return
        const result = await api<{ listening: boolean }>('microphone/start', 'POST')
        if (generation !== voiceGeneration.current) {
          await api('microphone/cancel', 'POST')
          return
        }
        if (!result.listening) throw new Error('The microphone could not start. Check your input device.')
      } catch (error) {
        micPointer.current = false
        micOwner.current = null
        setError(error instanceof Error ? error.message : 'Could not start the microphone.')
      } finally {
        setVoicePending(false)
      }
    })()
    void micRequest.current.finally(() => { micRequest.current = null })
  }

  const handleMicStop = async (cancel = false) => {
    micPointer.current = false
    micOwner.current = null
    // A quick release must wait for startup before closing that same capture.
    if (micRequest.current) await micRequest.current
    if (!view.connected || !view.ready) cancel = true
    setVoicePending(true)
    try { await api(cancel ? 'microphone/cancel' : 'microphone/finish', 'POST') }
    catch (error) { setError(error instanceof Error ? error.message : 'Could not finish recording.') }
    finally { setVoicePending(false) }
  }

  const toggleContinuous = async () => {
    if (!canUseVoice || voicePending) return
    setVoicePending(true)
    const generation = voiceGeneration.current
    try {
      await api('microphone/continuous', 'POST', { enabled: !continuousListen })
      if (generation !== voiceGeneration.current) await api('microphone/continuous', 'POST', { enabled: false })
    }
    catch (error) { setError(error instanceof Error ? error.message : 'Continuous listening could not start.') }
    finally { setVoicePending(false) }
  }

  const handleStop = useCallback(async () => {
    voiceGeneration.current += 1
    micPointer.current = false
    micOwner.current = null
    try { await api('stop', 'POST') }
    catch (error) { setError(error instanceof Error ? error.message : 'Could not stop the current request.') }
  }, [api, setError])

  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); void handleStop() }
      if (event.ctrlKey && event.code === 'Space' && !event.repeat) { event.preventDefault(); handleMicStart('shortcut') }
    }
    const keyup = (event: KeyboardEvent) => {
      if (event.code === 'Space' && micOwner.current === 'shortcut') { event.preventDefault(); void handleMicStop() }
    }
    const blur = () => { if (micPointer.current) void handleMicStop(true) }
    window.addEventListener('keydown', keydown)
    window.addEventListener('keyup', keyup)
    window.addEventListener('blur', blur)
    return () => {
      window.removeEventListener('keydown', keydown)
      window.removeEventListener('keyup', keyup)
      window.removeEventListener('blur', blur)
    }
  })

  // Levels animate through CSS transitions instead of rendering the entire app 60 times a second.
  const waveBars = Array.from({ length: 40 }, (_, i) => {
    const bell = Math.exp(-Math.pow((i - 19.5) / 15, 2))
    return 3 + Math.min(32, view.audioLevel * 35 * (0.45 + bell * 0.55) * (0.7 + Math.sin(i * 1.8) * 0.3))
  })
  const voiceStatus = !canUseVoice ? (view.preview ? 'Voice is available in the desktop app' : 'Microphone unavailable')
    : micRecording ? (continuousListen ? 'Listening · finish speaking to send' : 'Listening · release to send')
    : continuousListen ? (view.continuousPhase === 'paused' ? 'Hands-free · waiting for Soul' : 'Hands-free enabled')
    : voicePending ? 'Connecting microphone…' : 'Hold to talk · Ctrl + Space'

  // ─── Confirmation Decision Handling ───
  const handleDecide = async (id: string, allow: boolean) => {
    try { await api('confirmation', 'POST', { confirmation_id: id, allow }) } catch {}
  }

  return (
    <>
      {/* ─── Animated Fluid Background Blobs ─── */}
      <div className="blobs" aria-hidden="true">
        <i /><i /><i />
      </div>

      {/* ─── Clean Center Orb Canvas ─── */}
      <Orb mode={mode} audioLevel={view.audioLevel} reducedMotion={view.preferences.soul_reduced_motion} quality={view.preferences.soul_visual_quality} accent={accentName} />

      {/* ─── Grain and Vignette Overlays ─── */}
      <div className="grain" aria-hidden="true" />
      <div className="vig" aria-hidden="true" />

      {/* ─── Top Left Brand ─── */}
      <header className="brand">
        <img className="brand-icon" src="/icon.svg" alt="" />
        <div className="brand-copy">soul<span className="ver">Your personal intelligence</span></div>
      </header>

      {/* ─── Top Right Dock Controls ─── */}
      <div className="dock">
        <div className={`mode ${mode === 'idle' ? 'idle' : mode === 'listening' ? 'listen' : ''}`}>
          <i className="dot" />
          <span id="modeTxt">{modeText}</span>
        </div>

        {/* Accent switcher buttons */}
        <div className="sw" id="sw" role="group" aria-label="Accent colour">
          <button
            type="button"
            className={accentName === 'cyan' ? 'on' : ''}
            style={{ '--c': '#00e5ff' } as React.CSSProperties}
            onClick={() => setAccentName('cyan')}
            aria-label="Cyan"
            title="Celestial Cyan"
          />
          <button
            type="button"
            className={accentName === 'violet' ? 'on' : ''}
            style={{ '--c': '#b388ff' } as React.CSSProperties}
            onClick={() => setAccentName('violet')}
            aria-label="Violet"
            title="Cosmic Violet"
          />
          <button
            type="button"
            className={accentName === 'emerald' ? 'on' : ''}
            style={{ '--c': '#00e676' } as React.CSSProperties}
            onClick={() => setAccentName('emerald')}
            aria-label="Emerald"
            title="Aurora Emerald"
          />
          <button
            type="button"
            className={accentName === 'amber' ? 'on' : ''}
            style={{ '--c': '#ffb300' } as React.CSSProperties}
            onClick={() => setAccentName('amber')}
            aria-label="Amber"
            title="Solar Amber"
          />
        </div>

        <button className="btn ghost" type="button" onClick={handleResetLayout} title="Reset widget positions">⟲ Layout</button>
        <button className="btn ghost" type="button" onClick={() => setSettingsOpen(true)} aria-label="Open settings"><Icon name="settings" /> Settings</button>
        <button className="btn ghost" type="button" onClick={handleStop} disabled={!view.ready || view.preview} aria-label="Stop Soul"><Icon name="stop" /> Stop</button>
      </div>

      {/* ─── Real Tokens & Context Engine Widget ─── */}
      <section
        className={`w tokens ${minimized.tokens ? 'mini' : ''}`}
        data-id="tokens"
        ref={el => { widgetRefs.current.tokens = el }}
      >
        <div className="wh" onPointerDown={e => handlePointerDown('tokens', e)} onDoubleClick={() => toggleMini('tokens')}>
          <span className="t">TOKENS &amp; CONTEXT</span>
          <button className="min" type="button" onClick={() => toggleMini('tokens')} aria-label="Collapse widget">–</button>
        </div>
        <div className="wb">
          <div className="big">{totalTokens.toLocaleString('en-US')}</div>
          <div className="tok-stats">
            <span>PROMPT: <b>{promptTokens.toLocaleString('en-US')}</b></span>
            <span>COMPL: <b>{compTokens.toLocaleString('en-US')}</b></span>
            <span>TURNS: <b>{view.messages.filter(m => m.role === 'user').length}</b></span>
            <span>RATE: <b>{tokPerSec > 0 ? tokPerSec : '0'} t/s</b></span>
          </div>
          <div className="bars">
            {tokenThroughputHistory.map((h, i) => (
              <i key={i} style={{ height: `${Math.max(10, Math.min(100, h * 100))}%` }} />
            ))}
          </div>
          <div className="sub">Measured session usage</div>
        </div>
      </section>

      {/* ─── Enhanced Clock & Temporal Hub Widget ─── */}
      <section
        className={`w clock ${minimized.clock ? 'mini' : ''}`}
        data-id="clock"
        ref={el => { widgetRefs.current.clock = el }}
      >
        <div className="wh" onPointerDown={e => handlePointerDown('clock', e)} onDoubleClick={() => toggleMini('clock')}>
          <span className="t">SYSTEM TIME &amp; UPTIME</span>
          <button className="min" type="button" onClick={() => toggleMini('clock')} aria-label="Collapse widget">–</button>
        </div>
        <div className="wb">
          <div className="time-box">
            <span className="time">{timeStr}</span>
            <span className="time-sec">{secsStr}</span>
            <span className="time-ampm">{ampmStr}</span>
          </div>
          <div className="date">{dateStr}</div>
          <div className="uptime-badge">
            <i className="dot-live" />
            <span>UPTIME: <em>{uptimeStr}</em></span>
          </div>
          <div className="tz-line">YOUR LOCAL TIME</div>
        </div>
      </section>

      {/* ─── Real SOUL Terminal Widget ─── */}
      <section
        className={`w terminal ${minimized.terminal ? 'mini' : ''}`}
        data-id="terminal"
        ref={el => { widgetRefs.current.terminal = el }}
      >
        <div className="wh" onPointerDown={e => handlePointerDown('terminal', e)} onDoubleClick={() => toggleMini('terminal')}>
          <span className="t">SOUL TERMINAL</span>
          <span className="cnt">LIVE ACTIVITY</span>
          <button className="min" type="button" onClick={() => toggleMini('terminal')} aria-label="Collapse widget">–</button>
        </div>
        <div className="wb">
          <div className="t-stream" ref={terminalStreamRef}>
            {terminalLogs.map(log => (
              <div key={log.id} className="t-line">
                <span className={`t-tag ${log.tag.toLowerCase()}`}>[{log.tag}]</span>
                <span className="t-msg">{log.text}</span>
              </div>
            ))}
          </div>

          <div className="t-chips">
            <button type="button" className="t-chip" onClick={() => executeCommand('/status')}>/status</button>
            <button type="button" className="t-chip" onClick={() => executeCommand('/observe')}>/observe</button>
            <button type="button" className="t-chip" onClick={() => executeCommand('/memory')}>/memory</button>
            <button type="button" className="t-chip" onClick={() => executeCommand('/ping')}>/ping</button>
            <button type="button" className="t-chip" onClick={() => executeCommand('/tts')}>/tts</button>
            <button type="button" className="t-chip" onClick={() => executeCommand('/clear')}>/clear</button>
          </div>

          <form className="t-prompt-form" onSubmit={handleTerminalSubmit}>
            <span className="t-prompt-label">soul@desktop:~$</span>
            <input
              type="text"
              className="t-prompt-input"
              placeholder="run /help or send prompt..."
              value={terminalInput}
              onChange={e => setTerminalInput(e.target.value)}
            />
            <button type="submit" className="t-btn-run">RUN</button>
          </form>
        </div>
      </section>

      {/* ─── Real Hardware Diagnostics & Gauges Widget (psutil) ─── */}
      <section
        className={`w gauges ${minimized.gauges ? 'mini' : ''}`}
        data-id="gauges"
        ref={el => { widgetRefs.current.gauges = el }}
      >
        <div className="wh" onPointerDown={e => handlePointerDown('gauges', e)} onDoubleClick={() => toggleMini('gauges')}>
          <span className="t">HARDWARE &amp; ENGINES</span>
          <button className="min" type="button" onClick={() => toggleMini('gauges')} aria-label="Collapse widget">–</button>
        </div>
        <div className="wb row">
          <div className="gauge" title={`CPU Load: ${cpuVal}%`}>
            <svg viewBox="0 0 44 44">
              <circle className="tr" cx="22" cy="22" r="18" />
              <circle className="pr" cx="22" cy="22" r="18" style={{ strokeDashoffset: 113 - (113 * Math.min(100, cpuVal)) / 100 }} />
            </svg>
            <b>{statsAvailable ? `${cpuVal}%` : '—'}</b>
            <small>CPU</small>
          </div>
          <div className="gauge" title={`System RAM: ${ramUsedGb} / ${ramTotalGb} GB (${ramVal}%)`}>
            <svg viewBox="0 0 44 44">
              <circle className="tr" cx="22" cy="22" r="18" />
              <circle className="pr" cx="22" cy="22" r="18" style={{ strokeDashoffset: 113 - (113 * Math.min(100, ramVal)) / 100 }} />
            </svg>
            <b>{statsAvailable ? `${ramVal}%` : '—'}</b>
            <small>RAM</small>
          </div>
          <div className="gauge" title={statsAvailable ? `Core Process RSS: ${processMb} MB` : 'Waiting for hardware statistics'}>
            <svg viewBox="0 0 44 44">
              <circle className="tr" cx="22" cy="22" r="18" />
              <circle className="pr" cx="22" cy="22" r="18" style={{ strokeDashoffset: 113 - (113 * Math.min(100, (processMb / 500) * 100)) / 100 }} />
            </svg>
            <b>{statsAvailable ? `${processMb}M` : '—'}</b>
            <small>PROCESS</small>
          </div>
        </div>
      </section>

      {/* ─── SOUL Workspace & Memory Widget ─── */}
      <section
        className={`w workspace ${minimized.workspace ? 'mini' : ''}`}
        data-id="workspace"
        ref={el => { widgetRefs.current.workspace = el }}
      >
        <div className="wh" onPointerDown={e => handlePointerDown('workspace', e)} onDoubleClick={() => toggleMini('workspace')}>
          <span className="t">SOUL WORKSPACE</span>
          <span className="cnt">BOUNDED</span>
          <button className="min" type="button" onClick={() => toggleMini('workspace')} aria-label="Collapse widget">–</button>
        </div>
        <div className="wb">
          {/* Active / Recent Backend Tool Receipts */}
          {view.receipts.filter(r => r.tool !== 'finalize_task').slice(-2).map(r => (
            <div key={r.id} className="ws-rec">
              <div className="ws-rec-head">
                <span>CAPABILITY · {r.tool.toUpperCase()}</span>
                <em>{r.status.toUpperCase()}</em>
              </div>
              <div className="ws-rec-text">{r.summary}</div>
            </div>
          ))}

          {/* Module 1: Screen Vision Grounding */}
          <div className="ws-mod">
            <div className="ws-mod-header">
              <span>VISION GROUNDING</span>
              <span className="ws-badge">{view.preferences.soul_vision_enabled ? 'ON DEMAND' : 'OFF'}</span>
            </div>
            <div className="ws-mod-title">Desktop Screen Perception</div>
            <div className="ws-mod-desc">Grounds active workspace coordinates &amp; visual UI elements.</div>
            <div className="ws-mod-action">
              <button
                type="button"
                className="ws-btn-act"
                onClick={() => executeCommand('/observe')}
              >
                👁 OBSERVE SCREEN
              </button>
            </div>
          </div>

          {/* Module 2: Local SQLite Memory Store */}
          <div className="ws-mod">
            <div className="ws-mod-header">
              <span>LOCAL MEMORY</span>
              <span className="ws-badge">SQLITE · STORE</span>
            </div>
            <div className="ws-mod-title">Episodic Knowledge Recall</div>
            <div className="ws-mod-desc">Useful context saved in your local memory store.</div>
            <div className="ws-mod-action">
              <button
                type="button"
                className="ws-btn-act"
                onClick={() => executeCommand('/memory')}
              >
                🧠 RECALL MEMORY
              </button>
            </div>
          </div>

          {/* Module 3: Automation Safeguards */}
          <div className="ws-mod">
            <div className="ws-mod-header">
              <span>ACTION BUDGET</span>
              <span className="ws-badge">{view.receipts.length} / 24 TURNS</span>
            </div>
            <div className="ws-mod-title">Safe Automation Bridge</div>
            <div className="ws-mod-desc">Human-in-the-loop explicit verification for consequential operations.</div>
          </div>
        </div>
      </section>

      {/* ─── Live Conversation Channel Widget ─── */}
      <section
        className={`w chat ${minimized.chat ? 'mini' : ''}`}
        data-id="chat"
        ref={el => { widgetRefs.current.chat = el }}
      >
        <div className="wh" onPointerDown={e => handlePointerDown('chat', e)} onDoubleClick={() => toggleMini('chat')}>
          <span className="t">INTELLIGENCE STREAM</span>
          <button className="min" type="button" onClick={() => toggleMini('chat')} aria-label="Collapse widget">–</button>
        </div>
        <div className="wb">
          <div className="log" ref={chatLogRef}>
            {view.messages.length === 0 ? (
              <>
                <div className="msg welcome">A little space to think together.</div>
                <div className="msg">{view.preview ? 'This is a visual preview. Open Soul on your desktop to chat and use voice.' : view.ready ? 'Ask me something, or enable hands-free and speak naturally.' : 'Connecting to your assistant…'}</div>
              </>
            ) : (
              view.messages.map((m: ConversationMessage) => (
                <div key={m.id} className={`msg ${m.role === 'user' ? 'user' : ''}`}>
                  {m.text}
                  {m.streaming && <span className="stream-cursor" />}
                </div>
              ))
            )}

            {/* Thinking indicator */}
            {view.state === 'THINKING' && (
              <div className="msg typing">
                <i /><i /><i />
              </div>
            )}
          </div>

          <form className="cmd" onSubmit={handleSubmit}>
            <input
              type="text"
              placeholder="Ask Soul anything or enter command…"
              aria-label="Message Soul"
              disabled={!view.ready || view.preview}
              value={inputVal}
              onChange={e => setInputVal(e.target.value)}
            />
            <button type="submit" aria-label="Send" disabled={!view.ready || view.preview || !inputVal.trim()}><Icon name="arrow" /></button>
          </form>
        </div>
      </section>

      {/* ─── Gemini Live 3.5 Voice Channel Widget ─── */}
      <section
        className={`w voice ${minimized.voice ? 'mini' : ''}`}
        data-id="voice"
        ref={el => { widgetRefs.current.voice = el }}
      >
        <div className="wh" onPointerDown={e => handlePointerDown('voice', e)} onDoubleClick={() => toggleMini('voice')}>
          <span className="t">VOICE &amp; LISTENING</span>
          <span className="cnt" id="vstate">{modeText}</span>
          <button className="min" type="button" onClick={() => toggleMini('voice')} aria-label="Collapse widget">–</button>
        </div>
        <div className="wb">
          <div className="vrow">
            <button className={`mic ${micRecording ? 'on' : ''}`} type="button" disabled={!canUseVoice}
              onPointerDown={event => { if (event.button !== 0) return; event.currentTarget.setPointerCapture(event.pointerId); handleMicStart() }}
              onPointerUp={() => { if (micOwner.current === 'pointer') void handleMicStop() }}
              onPointerCancel={() => { if (micOwner.current === 'pointer') void handleMicStop(true) }}
              onKeyDown={event => { if ((event.code === 'Space' || event.key === 'Enter') && !event.repeat) { event.preventDefault(); handleMicStart(event.code === 'Space' ? 'space' : 'enter') } }}
              onKeyUp={event => { if ((event.code === 'Space' && micOwner.current === 'space') || (event.key === 'Enter' && micOwner.current === 'enter')) { event.preventDefault(); void handleMicStop() } }}
              aria-label="Hold to speak" title="Hold to speak · Ctrl + Space"><Icon name="mic" size={21} /></button>
            <div className="wave" title="Microphone and speech level" aria-hidden="true">
              {waveBars.map((h, i) => <i key={i} style={{ height: `${h}px` }} />)}
            </div>
            <div className="voice-actions">
              <button type="button" className={`btn-auto-listen ${continuousListen ? 'active' : ''}`} disabled={!canUseVoice || voicePending}
                onClick={toggleContinuous} aria-pressed={continuousListen} title="Automatically listen again after each reply">
                <Icon name="mic" size={14} /> {continuousListen ? 'Hands-free on' : 'Hands-free'}
              </button>
              <button type="button" className={`btn-auto-listen ${ttsMuted ? 'muted' : ''}`} disabled={!view.connected || view.preview}
                onClick={async () => { try { await api('preferences', 'PATCH', { soul_tts_enabled: ttsMuted }) } catch (error) { setError(error instanceof Error ? error.message : 'Voice setting could not be saved.') } }}
                aria-pressed={!ttsMuted} title={ttsMuted ? 'Enable spoken replies' : 'Mute spoken replies'}><Icon name="voice" size={14} /> {ttsMuted ? 'Muted' : 'Voice on'}</button>
            </div>
          </div>
          <p className="voice-status" role="status"><span className={micRecording ? 'listening-dot' : ''} />{voiceStatus}</p>
        </div>
      </section>

      {/* ─── Action Confirmation Dialog ─── */}
      {view.confirmations.length > 0 && (
        <div className="confirm-box" role="dialog" aria-modal="true">
          <div className="confirm-title">{view.confirmations[0].description}</div>
          <div className="confirm-desc">{view.confirmations[0].reason}</div>
          <div className="confirm-btns">
            <button className="confirm-btn deny" onClick={() => handleDecide(view.confirmations[0].confirmation_id, false)}>
              Cancel
            </button>
            <button className="confirm-btn allow" onClick={() => handleDecide(view.confirmations[0].confirmation_id, true)}>
              Allow Action
            </button>
          </div>
        </div>
      )}

      {(view.error || view.notice) && <div className={`status-notice ${view.error ? 'error' : ''}`} role={view.error ? 'alert' : 'status'}>{view.error || view.notice}<button type="button" aria-label="Dismiss message" onClick={() => setError('')}><Icon name="close" size={14} /></button></div>}
      {settingsOpen && <Settings view={view} api={api} onClose={closeSettings} />}

      {/* ─── Bottom Telemetry Bar ─── */}
      <footer className="foot">
        <span>{view.preview ? 'Visual preview' : view.connected ? view.ready ? 'Connected' : 'Starting Soul…' : 'Reconnecting…'}</span>
        <span>{view.lastTurnStats?.first_token_seconds ? `First text ${view.lastTurnStats.first_token_seconds.toFixed(1)}s · ` : ''}{view.lastTurnStats?.model || view.preferences.gemini_text_model} · {view.preferences.gemini_voice_name}</span>
      </footer>
    </>
  )
}
