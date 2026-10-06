import { motion, AnimatePresence } from 'framer-motion'
import { Icon } from '../Icons'
import type { Confirmation, Receipt } from '../types'

const cardVariants = {
  initial: { opacity: 0, y: 20, scale: 0.95 },
  animate: { opacity: 1, y: 0, scale: 1 },
  exit: { opacity: 0, y: -10, scale: 0.98 },
}

const transition = {
  duration: 0.4,
  ease: [0.22, 1, 0.36, 1] as const,
}

/* ─── Action Card ─── */
export function ActionCard({ action, status }: { action: string; status: 'running' | 'completed' | 'failed' }) {
  return (
    <motion.div
      className={`context-card action-card card-${status}`}
      variants={cardVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={transition}
    >
      <div className="card-indicator">
        {status === 'running' && <span className="card-pulse" />}
        {status === 'completed' && <Icon name="check" size={14} />}
        {status === 'failed' && <Icon name="alert" size={14} />}
      </div>
      <div className="card-content">
        <span className="card-label">
          {status === 'running' ? 'ACTING' : status === 'completed' ? 'DONE' : 'FAILED'}
        </span>
        <p className="card-text">{action}</p>
      </div>
    </motion.div>
  )
}

/* ─── Response Card ─── */
export function ResponseCard({ text, streaming }: { text: string; streaming: boolean }) {
  if (!text) return null

  // Short responses: floating text. Long responses: glass surface
  const isShort = text.length < 120

  return (
    <motion.div
      className={`response-display ${isShort ? 'response-short' : 'response-long'}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={transition}
    >
      <p className="response-text">
        {text}
        {streaming && <span className="response-cursor" />}
      </p>
    </motion.div>
  )
}

/* ─── User Query Display ─── */
export function UserQueryDisplay({ query }: { query: string }) {
  if (!query) return null

  return (
    <motion.div
      className="user-query-display"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 0.6, y: 0 }}
      exit={{ opacity: 0, y: -5 }}
      transition={{ duration: 0.3 }}
    >
      <span className="query-label">You</span>
      <p>{query}</p>
    </motion.div>
  )
}

/* ─── Error Card ─── */
export function ErrorCard({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return (
    <motion.div
      className="context-card error-card"
      variants={cardVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={transition}
    >
      <p className="card-text">{message}</p>
      <button className="card-dismiss" onClick={onDismiss} aria-label="Dismiss">
        <Icon name="close" size={12} />
      </button>
    </motion.div>
  )
}

/* ─── Confirmation Card ─── */
export function ConfirmationCard({
  confirmation,
  onDecide,
}: {
  confirmation: Confirmation
  onDecide: (id: string, allow: boolean) => void
}) {
  return (
    <motion.div
      className="context-card confirmation-surface"
      variants={cardVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={transition}
    >
      <span className="card-label">SOUL needs your permission</span>
      <h3 className="confirmation-title">{confirmation.description}</h3>
      <p className="confirmation-reason">{confirmation.reason}</p>
      {confirmation.consequence && (
        <p className="confirmation-consequence">{confirmation.consequence}</p>
      )}
      <div className="confirmation-buttons">
        <button
          className="btn-secondary"
          onClick={() => onDecide(confirmation.confirmation_id, false)}
        >
          Cancel
        </button>
        <button
          className="btn-primary"
          onClick={() => onDecide(confirmation.confirmation_id, true)}
        >
          Allow
        </button>
      </div>
    </motion.div>
  )
}

/* ─── Task Progress ─── */
export function TaskProgress({ receipts }: { receipts: Receipt[] }) {
  const visible = receipts.filter(r => r.tool !== 'finalize_task')
  if (visible.length === 0) return null

  const running = visible.some(r => r.status === 'running')
  const latest = visible[visible.length - 1]

  return (
    <motion.div
      className="task-progress"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={transition}
    >
      <div className="progress-collapsed">
        <span className={`progress-dot ${running ? 'running' : 'done'}`} />
        <span className="progress-label">{latest?.summary || 'Working…'}</span>
      </div>
    </motion.div>
  )
}

/* ─── Waveform (listening state) ─── */
export function ListeningWaveform({ amplitude }: { amplitude: number }) {
  const bars = 24
  return (
    <motion.div
      className="listening-waveform"
      initial={{ opacity: 0, scaleX: 0 }}
      animate={{ opacity: 1, scaleX: 1 }}
      exit={{ opacity: 0, scaleX: 0 }}
      transition={{ duration: 0.35 }}
    >
      {Array.from({ length: bars }, (_, i) => {
        const center = bars / 2
        const distFromCenter = Math.abs(i - center) / center
        const height = Math.max(2, (1 - distFromCenter * 0.7) * amplitude * 28 + Math.sin(Date.now() * 0.008 + i * 0.4) * 3)
        return (
          <span
            key={i}
            className="waveform-bar"
            style={{ height: `${height}px` }}
          />
        )
      })}
    </motion.div>
  )
}
