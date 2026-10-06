import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Icon } from '../Icons'

interface SoulMenuProps {
  onNavigate: (view: string) => void
  activeView: string
  visionActive: boolean
  micActive: boolean
  connected: boolean
}

export function SoulMark() {
  return (
    <svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">
      <g fill="none" stroke="currentColor" strokeWidth="1.25">
        <path d="M16 3C5 9 7 24 16 29C27 23 25 8 16 3Z" />
        <path d="M16 3C25 10 26 21 16 29C6 22 5 11 16 3Z" transform="rotate(60 16 16)" />
        <path d="M16 3C25 10 26 21 16 29C6 22 5 11 16 3Z" transform="rotate(-60 16 16)" />
      </g>
    </svg>
  )
}

const menuItems = [
  { id: 'home', label: 'Home', icon: 'spark' },
  { id: 'activity', label: 'Activity', icon: 'timeline' },
  { id: 'memory', label: 'Memory', icon: 'memory' },
  { id: 'settings', label: 'Settings', icon: 'settings' },
]

export default function SoulMenu({ onNavigate, activeView, visionActive, micActive, connected }: SoulMenuProps) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <>
      {/* Top-left SOUL mark */}
      <div className="soul-mark-wrapper">
        <button
          className="soul-mark-button"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="SOUL menu"
          aria-expanded={menuOpen}
        >
          <SoulMark />
        </button>
        <span className="soul-mark-label">SOUL</span>
      </div>

      {/* Top-right indicators */}
      <div className="top-indicators">
        {visionActive && (
          <motion.span
            className="indicator indicator-active"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            title="Vision active"
          >
            <Icon name="eye" size={12} />
          </motion.span>
        )}
        {micActive && (
          <motion.span
            className="indicator indicator-active"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            title="Listening"
          >
            <Icon name="mic" size={12} />
          </motion.span>
        )}
        <span className={`indicator ${connected ? 'indicator-online' : ''}`} title={connected ? 'Connected' : 'Disconnected'}>
          <span className="indicator-dot" />
        </span>
      </div>

      {/* Floating menu */}
      <AnimatePresence>
        {menuOpen && (
          <>
            <motion.div
              className="menu-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMenuOpen(false)}
            />
            <motion.nav
              className="floating-menu"
              initial={{ opacity: 0, y: -10, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.96 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
              aria-label="Navigation"
            >
              {menuItems.map((item) => (
                <button
                  key={item.id}
                  className={`menu-item ${activeView === item.id ? 'active' : ''}`}
                  onClick={() => { onNavigate(item.id); setMenuOpen(false) }}
                >
                  <Icon name={item.icon} size={16} />
                  <span>{item.label}</span>
                </button>
              ))}
            </motion.nav>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
