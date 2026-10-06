import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Icon } from '../Icons'
import type { SoulState } from '../types'

interface CommandDockProps {
  available: boolean
  listening: boolean
  active: boolean
  confirmations: number
  preview: boolean
  micEnabled: boolean
  onSubmit: (text: string) => void
  onStop: () => void
  onMicStart: () => void
  onMicRelease: (cancel?: boolean) => void
}

export default function CommandDock({
  available, listening, active, confirmations, preview, micEnabled,
  onSubmit, onStop, onMicStart, onMicRelease,
}: CommandDockProps) {
  const [text, setText] = useState('')
  const [expanded, setExpanded] = useState(false)
  const [sending, setSending] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const activate = useCallback(() => {
    setExpanded(true)
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [])

  const deactivate = useCallback(() => {
    if (!text.trim()) {
      setExpanded(false)
    }
  }, [text])

  async function handleSubmit() {
    const trimmed = text.trim()
    if (!trimmed || !available || sending || confirmations > 0) return
    setSending(true)
    onSubmit(trimmed)
    setText('')
    setExpanded(false)
    setSending(false)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
    if (e.key === 'Escape') {
      setText('')
      setExpanded(false)
      inputRef.current?.blur()
    }
  }

  // Global keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // '/' or Cmd+K to activate
      if ((e.key === '/' || (e.metaKey && e.key === 'k') || (e.ctrlKey && e.key === 'k')) && !expanded) {
        e.preventDefault()
        activate()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [expanded, activate])

  return (
    <div className="command-dock-wrapper">
      <AnimatePresence mode="wait">
        {active && (
          <motion.button
            className="dock-stop-button"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            onClick={onStop}
            aria-label="Stop current request"
          >
            <Icon name="stop" size={13} />
            <span>Stop</span>
            <kbd>Esc</kbd>
          </motion.button>
        )}
      </AnimatePresence>

      <motion.div
        className={`command-dock ${expanded ? 'expanded' : ''} ${listening ? 'listening' : ''}`}
        animate={{
          width: expanded ? 580 : 280,
        }}
        transition={{
          type: 'spring',
          stiffness: 400,
          damping: 30,
          mass: 0.8,
        }}
        onClick={!expanded ? activate : undefined}
      >
        {expanded ? (
          <div className="dock-inner-expanded">
            <input
              ref={inputRef}
              type="text"
              className="dock-input"
              placeholder={listening ? 'Listening…' : preview ? 'Interface preview mode' : 'Ask SOUL…'}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={deactivate}
              maxLength={12000}
              aria-label="Command input"
            />
            <div className="dock-actions">
              {micEnabled && (
                <button
                  className={`dock-mic ${listening ? 'active' : ''}`}
                  aria-label="Hold to speak"
                  title="Hold to speak · Ctrl+Space"
                  disabled={!available || confirmations > 0}
                  onPointerDown={(e) => { e.preventDefault(); e.currentTarget.setPointerCapture(e.pointerId); onMicStart() }}
                  onPointerUp={() => onMicRelease()}
                  onPointerCancel={() => onMicRelease(true)}
                >
                  <Icon name="mic" size={16} />
                </button>
              )}
              <button
                className="dock-send"
                disabled={!available || !text.trim() || sending || confirmations > 0}
                onClick={handleSubmit}
                aria-label="Send"
              >
                <Icon name="arrow" size={16} />
              </button>
            </div>
          </div>
        ) : (
          <div className="dock-inner-dormant">
            <span className="dock-hint">Ask SOUL…</span>
            <kbd className="dock-shortcut">/</kbd>
          </div>
        )}
      </motion.div>
    </div>
  )
}
