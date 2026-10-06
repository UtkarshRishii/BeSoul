import { useEffect, useState } from 'react'
import { Icon } from '../Icons'
import { SoulMark } from './SoulMenu'

interface HUDTopBarProps {
  connected: boolean
  visionActive: boolean
  micActive: boolean
  onToggleVision: () => void
  onOpenSettings: () => void
  onOpenActivity?: () => void
}

export default function HUDTopBar({
  connected,
  visionActive,
  micActive,
  onToggleVision,
  onOpenSettings,
}: HUDTopBarProps) {
  const [fps, setFps] = useState(60)

  // Measure approximate FPS
  useEffect(() => {
    let frameCount = 0
    let lastTime = performance.now()
    let animId: number

    const loop = (now: number) => {
      frameCount++
      if (now - lastTime >= 1000) {
        setFps(Math.min(60, Math.round((frameCount * 1000) / (now - lastTime))))
        frameCount = 0
        lastTime = now
      }
      animId = requestAnimationFrame(loop)
    }

    animId = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(animId)
  }, [])

  return (
    <header className="hud-top-bar" role="banner">
      {/* Top Left: System Identifier */}
      <div className="top-brand">
        <div className="brand-logo-frame">
          <SoulMark />
        </div>
        <div className="brand-titles">
          <div className="brand-main">
            <span className="brand-name">SOUL</span>
            <span className="brand-version">// SPATIAL AI</span>
          </div>
          <span className="brand-sub">LOCAL NODE: 127.0.0.1</span>
        </div>
      </div>

      {/* Top Center: System Status Banner */}
      <div className="top-center-banner" aria-hidden="true">
        <span className="banner-bracket">[</span>
        <span className="banner-dot" />
        <span className="banner-text">HARDWARE RUNNING ON-DEVICE · ZERO CLOUD LEAK</span>
        <span className="banner-bracket">]</span>
      </div>

      {/* Top Right: Badges & Controls */}
      <div className="top-controls">
        <div className="hud-pill hud-pill-fps" title="Render Framerate">
          <span className="pill-dot dot-green" />
          <span>{fps} FPS</span>
        </div>

        <div className="hud-pill hud-pill-audio" title="Audio Sample Rate">
          <span>48.0 kHz</span>
        </div>

        <button
          className={`hud-pill-btn ${visionActive ? 'btn-active' : ''}`}
          onClick={onToggleVision}
          title="Toggle Screen Vision Eye"
          aria-label="Toggle Screen Vision"
        >
          <Icon name="eye" size={13} />
          <span>VISION</span>
        </button>

        <button
          className="hud-pill-btn btn-settings"
          onClick={onOpenSettings}
          title="Open System Settings"
          aria-label="Open Settings"
        >
          <Icon name="settings" size={13} />
          <span>SETTINGS</span>
        </button>
      </div>
    </header>
  )
}
