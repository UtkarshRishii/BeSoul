import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Icon } from '../Icons'
import type { SoulState } from '../types'

interface HUDVoiceDockProps {
  available: boolean
  listening: boolean
  active: boolean
  speaking: boolean
  thinking: boolean
  state: SoulState
  amplitude: number
  micEnabled: boolean
  confirmations: number
  preview: boolean
  onSubmit: (text: string) => void
  onStop: () => void
  onMicStart: () => void
  onMicRelease: (cancel?: boolean) => void
}

export default function HUDVoiceDock({
  available,
  listening,
  active,
  speaking,
  thinking,
  state,
  amplitude,
  micEnabled,
  confirmations,
  preview,
  onSubmit,
  onStop,
  onMicStart,
  onMicRelease,
}: HUDVoiceDockProps) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // Status badge config
  const statusLabel = speaking
    ? 'SPEAKING'
    : listening
    ? 'LISTENING'
    : thinking
    ? 'THINKING'
    : active
    ? 'ACTIVE'
    : 'ONLINE'

  const statusClass = speaking
    ? 'badge-speaking'
    : listening
    ? 'badge-listening'
    : thinking
    ? 'badge-thinking'
    : 'badge-online'

  async function handleSubmit() {
    const trimmed = text.trim()
    if (!trimmed || !available || sending || confirmations > 0) return
    setSending(true)
    onSubmit(trimmed)
    setText('')
    setSending(false)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
    if (e.key === 'Escape') {
      if (active) onStop()
      else {
        setText('')
        inputRef.current?.blur()
      }
    }
  }

  // 48-bar spectrum equalizer
  const BAR_COUNT = 48
  const [bars, setBars] = useState<number[]>(() => Array.from({ length: BAR_COUNT }, () => 4))

  useEffect(() => {
    let animId: number
    const animate = () => {
      const time = Date.now() * 0.006
      const baseAmp = Math.max(amplitude, speaking ? 0.45 : listening ? 0.35 : thinking ? 0.2 : 0.06)

      const nextBars = Array.from({ length: BAR_COUNT }, (_, i) => {
        const center = BAR_COUNT / 2
        const distFromCenter = Math.abs(i - center) / center
        const bellCurve = Math.max(0.15, 1 - Math.pow(distFromCenter, 1.6))

        const wave1 = Math.sin(time * 2.2 + i * 0.45)
        const wave2 = Math.cos(time * 1.5 - i * 0.3)
        const noise = (Math.random() - 0.5) * 0.15

        let h = (bellCurve * 0.7 + wave1 * 0.2 + wave2 * 0.1 + noise) * baseAmp * 38
        if (speaking || listening) {
          h = Math.max(3, Math.min(42, h))
        } else if (thinking) {
          h = Math.max(3, Math.min(22, 4 + Math.sin(time * 3 + i * 0.6) * 12))
        } else {
          // Idle ambient pulse
          h = Math.max(2, Math.min(10, 3 + Math.sin(time * 0.8 + i * 0.25) * 3))
        }
        return h
      })

      setBars(nextBars)
      animId = requestAnimationFrame(animate)
    }

    animId = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(animId)
  }, [amplitude, speaking, listening, thinking])

  return (
    <div className="hud-voice-dock-wrapper">
      {/* ─── Stop button when active ─── */}
      <AnimatePresence>
        {active && (
          <motion.button
            className="hud-stop-button"
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            onClick={onStop}
            aria-label="Stop current activity"
          >
            <span className="stop-led" />
            <span>INTERRUPT</span>
            <kbd>ESC</kbd>
          </motion.button>
        )}
      </AnimatePresence>

      {/* ─── Sci-Fi HUD Voice Capsule ─── */}
      <div className={`hud-voice-capsule ${speaking ? 'active-speaking' : ''} ${listening ? 'active-listening' : ''}`}>
        <div className="capsule-corner tl" />
        <div className="capsule-corner tr" />
        <div className="capsule-corner bl" />
        <div className="capsule-corner br" />

        {/* Top Header */}
        <div className="capsule-header">
          <div className="channel-indicator">
            <span className={`channel-led ${speaking || listening ? 'led-pulsing' : ''}`} />
            <span className="channel-text">A.I VOICE CHANNEL</span>
          </div>

          <div className="capsule-title">
            <span>VOICE SYSTEM</span>
          </div>

          <div className={`capsule-badge ${statusClass}`}>
            <span className="badge-dot" />
            <span className="badge-text">{statusLabel}</span>
          </div>
        </div>

        {/* Dynamic Waveform Spectrum Bars */}
        <div className="capsule-visualizer" aria-hidden="true">
          <div className="freq-mark freq-left">12.4 kHz</div>
          <div className="spectrum-bars">
            {bars.map((height, i) => (
              <span
                key={i}
                className="spectrum-bar"
                style={{
                  height: `${height}px`,
                  opacity: Math.max(0.3, Math.min(1, height / 28)),
                }}
              />
            ))}
          </div>
          <div className="freq-mark freq-right">
            {speaking ? 'GAIN: +2.1dB' : listening ? 'MIC: ACTIVE' : '48.0 kHz'}
          </div>
        </div>

        {/* Telemetry line */}
        <div className="capsule-telemetry">
          <span className="telemetry-item">
            <span className="tag">SYS</span> NOMINAL
          </span>
          <span className="telemetry-sep">|</span>
          <span className="telemetry-item">
            <span className="tag">MODEL</span> GEMINI-2.5-FLASH
          </span>
          <span className="telemetry-sep">|</span>
          <span className="telemetry-item">
            <span className="tag">LATENCY</span> 18ms
          </span>
          <span className="telemetry-sep">|</span>
          <span className="telemetry-item">
            <span className="tag">ARCH</span> ZERO-CLOUD / LOCAL
          </span>
        </div>

        {/* Integrated Command Input */}
        <div className="capsule-input-dock">
          <div className="prompt-prefix">
            <span className="prompt-bracket">&gt;</span>
          </div>
          <input
            ref={inputRef}
            type="text"
            className="capsule-input"
            placeholder={
              listening
                ? 'Listening to your voice…'
                : speaking
                ? 'SOUL is speaking… ask anything to interrupt'
                : preview
                ? 'Type anything to test SOUL… (e.g. "Who is Jarvis?", "What are the latest AI models?")'
                : 'Ask SOUL anything or press Ctrl+Space to speak…'
            }
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            maxLength={12000}
            aria-label="Command input"
          />

          <div className="capsule-actions">
            {micEnabled && (
              <button
                className={`capsule-btn mic-btn ${listening ? 'listening' : ''}`}
                aria-label="Hold to speak"
                title="Hold to speak · Ctrl+Space"
                disabled={!available || confirmations > 0}
                onPointerDown={(e) => {
                  e.preventDefault()
                  e.currentTarget.setPointerCapture(e.pointerId)
                  onMicStart()
                }}
                onPointerUp={() => onMicRelease()}
                onPointerCancel={() => onMicRelease(true)}
              >
                <Icon name="mic" size={15} />
              </button>
            )}

            <button
              className="capsule-btn send-btn"
              disabled={!available || !text.trim() || sending || confirmations > 0}
              onClick={handleSubmit}
              aria-label="Submit command"
              title="Submit (Enter)"
            >
              <Icon name="arrow" size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
