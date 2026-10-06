import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Icon } from '../Icons'
import type { ConversationMessage, Receipt, SoulState } from '../types'

interface HUDRightActivityProps {
  messages: ConversationMessage[]
  receipts: Receipt[]
  state: SoulState
  onClear?: () => void
}

export default function HUDRightActivity({
  messages,
  receipts,
  state,
  onClear,
}: HUDRightActivityProps) {
  const [collapsed, setCollapsed] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new message or token arrives
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, receipts, state])

  // Filter tool receipts to exclude internal finalize_task
  const visibleReceipts = receipts.filter(r => r.tool !== 'finalize_task')

  if (collapsed) {
    return (
      <button
        className="hud-panel-minimized hud-right-min"
        onClick={() => setCollapsed(false)}
        title="Expand Intelligence Stream"
        aria-label="Expand Stream"
      >
        <span className="min-icon">💬</span>
        <span className="min-label">STREAM ({messages.length})</span>
      </button>
    )
  }

  return (
    <motion.div
      className="hud-panel hud-right-panel"
      initial={{ opacity: 0, x: 30 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="panel-corner tl" />
      <div className="panel-corner tr" />
      <div className="panel-corner bl" />
      <div className="panel-corner br" />

      {/* Panel Header */}
      <div className="hud-panel-header">
        <div className="header-title">
          <span className="header-icon-box">◈</span>
          <div>
            <span className="header-eyebrow">LIVE TELEMETRY</span>
            <h3 className="header-main">INTELLIGENCE STREAM</h3>
          </div>
        </div>
        <div className="header-actions">
          {onClear && messages.length > 0 && (
            <button className="panel-action-btn" onClick={onClear} title="Clear stream">
              <Icon name="trash" size={13} />
            </button>
          )}
          <button
            className="panel-collapse-btn"
            onClick={() => setCollapsed(true)}
            title="Minimize panel"
            aria-label="Minimize panel"
          >
            ─
          </button>
        </div>
      </div>

      {/* Stream Messages Container */}
      <div className="stream-scroll-container" ref={scrollRef}>
        {messages.length === 0 && visibleReceipts.length === 0 ? (
          <div className="stream-empty-state">
            <div className="empty-reticle" />
            <p className="empty-title">STREAM DORMANT</p>
            <span className="empty-subtitle">
              Speak with Ctrl+Space or type below. Responses, tool executions, and system actions stream here in real time.
            </span>
            <div className="empty-hints">
              <span className="hint-pill">"Who is Jarvis?"</span>
              <span className="hint-pill">"What are the latest AI launches?"</span>
              <span className="hint-pill">"Inspect screen"</span>
            </div>
          </div>
        ) : (
          <div className="stream-feed">
            {messages.map((msg, idx) => (
              <div
                key={msg.id || idx}
                className={`stream-bubble ${msg.role === 'user' ? 'bubble-user' : 'bubble-assistant'}`}
              >
                <div className="bubble-header">
                  <span className="bubble-sender">
                    {msg.role === 'user' ? 'USER // OPERATOR' : 'SOUL // INTELLIGENCE'}
                  </span>
                  <span className="bubble-time">
                    {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
                <div className="bubble-content">
                  <p>{msg.text}</p>
                  {msg.streaming && <span className="stream-cursor" />}
                </div>
              </div>
            ))}

            {/* If thinking but no message stream yet */}
            {state === 'THINKING' && messages[messages.length - 1]?.role !== 'assistant' && (
              <div className="stream-bubble bubble-assistant bubble-thinking">
                <div className="bubble-header">
                  <span className="bubble-sender">SOUL // REASONING</span>
                  <span className="bubble-time">ACTIVE</span>
                </div>
                <div className="thinking-indicator">
                  <span className="thinking-scanline" />
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                  <span className="thinking-text">Formulating response &amp; evaluating capabilities…</span>
                </div>
              </div>
            )}

            {/* Active or recent tool receipts */}
            {visibleReceipts.length > 0 && (
              <div className="stream-receipts-block">
                <span className="receipts-header">DISPATCHED CAPABILITIES</span>
                {visibleReceipts.slice(-4).map(r => (
                  <div key={r.id} className={`receipt-badge receipt-${r.status}`}>
                    <span className="receipt-icon">
                      {r.status === 'running' ? '⏳' : r.status === 'failed' ? '⚠' : '✓'}
                    </span>
                    <span className="receipt-tool">{r.tool}</span>
                    <span className="receipt-summary">{r.summary}</span>
                    <span className="receipt-status-tag">{r.status.toUpperCase()}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Stream Footer */}
      <div className="hud-panel-footer stream-footer">
        <span className="footer-status-indicator">
          <span className={`status-led ${state !== 'IDLE' ? 'led-active' : ''}`} />
          <span>{state}</span>
        </span>
        <span className="footer-meta-info">BUFFER: 100 MSG</span>
      </div>
    </motion.div>
  )
}
