import { motion } from 'framer-motion'
import { Icon } from '../Icons'
import type { Receipt, RuntimeView } from '../types'

const overlayVariants = {
  initial: { opacity: 0, x: 60 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 60 },
}

const transition = {
  duration: 0.5,
  ease: [0.22, 1, 0.36, 1] as const,
}

interface ActivityOverlayProps {
  view: RuntimeView
  onClose: () => void
}

export default function ActivityOverlay({ view, onClose }: ActivityOverlayProps) {
  const receipts = view.preferences.soul_debug
    ? view.receipts
    : view.receipts.filter(r => r.tool !== 'finalize_task')

  return (
    <motion.aside
      className="overlay-panel activity-overlay"
      variants={overlayVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={transition}
      aria-label="Activity timeline"
    >
      <header className="overlay-header">
        <div>
          <span className="overlay-label">ACTIVITY</span>
          <h2 className="overlay-title">Task Timeline</h2>
        </div>
        <button className="overlay-close" onClick={onClose} aria-label="Close activity">
          <Icon name="close" size={16} />
        </button>
      </header>

      <div className="overlay-scroll">
        {receipts.length === 0 ? (
          <div className="overlay-empty">
            <Icon name="timeline" size={24} />
            <p>No activity yet.</p>
            <span>Tool receipts appear here when SOUL takes action.</span>
          </div>
        ) : (
          <ol className="activity-timeline">
            {receipts.map((receipt) => (
              <li key={receipt.id} className={`timeline-item item-${receipt.status}`}>
                <div className="timeline-dot">
                  <Icon
                    name={
                      receipt.status === 'failed' ? 'alert' :
                      receipt.status === 'verified' ? 'check' :
                      receipt.status === 'running' ? 'action' : 'chevron'
                    }
                    size={11}
                  />
                </div>
                <div className="timeline-content">
                  <div className="timeline-meta">
                    <span className="timeline-tool">{receipt.tool.replace(/_/g, ' ')}</span>
                    {receipt.elapsed !== undefined && (
                      <span className="timeline-elapsed">{(receipt.elapsed / 1000).toFixed(1)}s</span>
                    )}
                  </div>
                  <p className="timeline-summary">{receipt.summary}</p>
                  <span className={`timeline-status status-${receipt.status}`}>
                    {receipt.status === 'dispatched' ? 'Dispatched' :
                     receipt.status === 'completed' ? 'Completed' :
                     receipt.status === 'verified' ? 'Verified' :
                     receipt.status === 'failed' ? 'Failed' : 'In progress'}
                  </span>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </motion.aside>
  )
}
