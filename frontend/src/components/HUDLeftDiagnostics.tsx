import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Icon } from '../Icons'
import type { Preferences, SoulState } from '../types'

interface HUDLeftDiagnosticsProps {
  state: SoulState
  preferences: Preferences
  connected: boolean
  onToggleVision: () => void
  onOpenSettings: () => void
}

export default function HUDLeftDiagnostics({
  state,
  preferences,
  connected,
  onToggleVision,
  onOpenSettings,
}: HUDLeftDiagnosticsProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [cpuUsage, setCpuUsage] = useState(14)
  const [vramUsage, setVramUsage] = useState(5.8)
  const [sparkline, setSparkline] = useState<number[]>([12, 18, 15, 22, 28, 20, 25, 32, 29, 38, 30, 24])

  // Simulate subtle real-time telemetry fluctuations
  useEffect(() => {
    const timer = setInterval(() => {
      const activeLoad = ['THINKING', 'ACTING', 'SEEING'].includes(state)
      const baseCpu = activeLoad ? 32 + Math.floor(Math.random() * 20) : 12 + Math.floor(Math.random() * 8)
      setCpuUsage(baseCpu)

      const baseVram = activeLoad ? 6.4 + (Math.random() * 0.4) : 5.8 + (Math.random() * 0.2)
      setVramUsage(Number(baseVram.toFixed(1)))

      setSparkline(prev => {
        const nextVal = Math.max(10, Math.min(50, prev[prev.length - 1] + (Math.random() - 0.48) * 8))
        return [...prev.slice(1), nextVal]
      })
    }, 1800)
    return () => clearInterval(timer)
  }, [state])

  // Sparkline SVG path
  const svgWidth = 140
  const svgHeight = 28
  const maxVal = 55
  const points = sparkline.map((val, idx) => {
    const x = (idx / (sparkline.length - 1)) * svgWidth
    const y = svgHeight - (val / maxVal) * svgHeight
    return `${x},${y}`
  }).join(' ')

  if (collapsed) {
    return (
      <button
        className="hud-panel-minimized hud-left-min"
        onClick={() => setCollapsed(false)}
        title="Expand System Diagnostics"
        aria-label="Expand Diagnostics"
      >
        <span className="min-icon">⚡</span>
        <span className="min-label">TELEMETRY</span>
      </button>
    )
  }

  return (
    <motion.div
      className="hud-panel hud-left-panel"
      initial={{ opacity: 0, x: -30 }}
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
          <span className="header-icon-box">⚡</span>
          <div>
            <span className="header-eyebrow">SYSTEM DIAGNOSTICS</span>
            <h3 className="header-main">HARDWARE &amp; ENGINES</h3>
          </div>
        </div>
        <button
          className="panel-collapse-btn"
          onClick={() => setCollapsed(true)}
          title="Minimize panel"
          aria-label="Minimize panel"
        >
          ─
        </button>
      </div>

      {/* Metrics Section */}
      <div className="telemetry-section">
        {/* Metric 1: CPU */}
        <div className="hud-metric-row">
          <div className="metric-label-group">
            <span className="metric-name">CPU LOAD</span>
            <span className="metric-val">{cpuUsage}%</span>
          </div>
          <div className="hud-progress-track">
            <div className="hud-progress-fill" style={{ width: `${cpuUsage}%` }} />
          </div>
        </div>

        {/* Metric 2: VRAM */}
        <div className="hud-metric-row">
          <div className="metric-label-group">
            <span className="metric-name">LOCAL VRAM</span>
            <span className="metric-val">{vramUsage} / 16.0 GB</span>
          </div>
          <div className="hud-progress-track">
            <div className="hud-progress-fill" style={{ width: `${(vramUsage / 16) * 100}%` }} />
          </div>
        </div>

        {/* Sparkline chart */}
        <div className="sparkline-wrapper">
          <div className="sparkline-meta">
            <span>NEURAL PIPELINE THROUGHPUT</span>
            <span className="sparkline-rate">{(cpuUsage * 1.8).toFixed(0)} T/s</span>
          </div>
          <svg className="sparkline-svg" width={svgWidth} height={svgHeight}>
            <defs>
              <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00F0FF" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#00F0FF" stopOpacity="0.0" />
              </linearGradient>
            </defs>
            <polyline fill="none" stroke="#00F0FF" strokeWidth="1.5" points={points} />
          </svg>
        </div>
      </div>

      {/* Engine Status Grid */}
      <div className="engine-status-grid">
        <div className="engine-item">
          <div className="engine-dot dot-active" />
          <div className="engine-info">
            <span className="engine-name">REASONING CORE</span>
            <span className="engine-detail">{preferences.gemini_text_model || 'gemini-2.5-flash'}</span>
          </div>
          <span className="engine-pill pill-green">READY</span>
        </div>

        <div className="engine-item">
          <div className={`engine-dot ${preferences.soul_vision_enabled ? 'dot-active' : 'dot-inactive'}`} />
          <div className="engine-info">
            <span className="engine-name">SCREEN VISION</span>
            <span className="engine-detail">{['SEEING', 'VERIFYING'].includes(state) ? 'OBSERVING' : 'READY'}</span>
          </div>
          <button
            className={`engine-toggle-btn ${preferences.soul_vision_enabled ? 'toggle-on' : ''}`}
            onClick={onToggleVision}
            title="Toggle Vision Eye"
          >
            {preferences.soul_vision_enabled ? 'ACTIVE' : 'OFF'}
          </button>
        </div>

        <div className="engine-item">
          <div className="engine-dot dot-active" />
          <div className="engine-info">
            <span className="engine-name">AUTOMATION</span>
            <span className="engine-detail">Windows OS Bridge</span>
          </div>
          <span className="engine-pill pill-blue">BOUNDED</span>
        </div>

        <div className="engine-item">
          <div className="engine-dot dot-active" />
          <div className="engine-info">
            <span className="engine-name">MEMORY ENGINE</span>
            <span className="engine-detail">SQLite On-Device</span>
          </div>
          <span className="engine-pill pill-cyan">SYNCED</span>
        </div>
      </div>

      {/* Bottom Footer info */}
      <div className="hud-panel-footer">
        <span className="footer-tag">ZERO CLOUD DEPENDENCY</span>
        <button className="footer-config-link" onClick={onOpenSettings}>
          CONFIGURE
        </button>
      </div>
    </motion.div>
  )
}
