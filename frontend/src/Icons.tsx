import type { CSSProperties } from 'react'

const paths: Record<string, React.ReactNode> = {
  arrow: <><path d="M12 19V5m-6 6 6-6 6 6" /></>,
  mic: <><rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2m-7 9v3m-4 0h8" /></>,
  stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
  settings: <><path d="m9 3-1 3-3 1-1 4 2 2-1 4 3 2 3-1 3 2 4-2v-3l2-3-2-3V7l-4-2-3 1Z" /><circle cx="12" cy="12" r="3" /></>,
  timeline: <><path d="M5 4v16m5-14h10M10 12h7m-7 6h10" /><circle cx="5" cy="6" r="1" /><circle cx="5" cy="12" r="1" /><circle cx="5" cy="18" r="1" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  chevron: <path d="m9 5 7 7-7 7" />,
  check: <path d="m5 12 4 4L19 6" />,
  shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9S4 17 4 12V6Z" /><path d="m8 12 3 3 5-6" /></>,
  eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>,
  memory: <><path d="M8 3a4 4 0 0 0-4 4v1a4 4 0 0 0 0 8v1a4 4 0 0 0 8 0V7a4 4 0 0 0-4-4Zm8 0a4 4 0 0 1 4 4v1a4 4 0 0 1 0 8v1a4 4 0 0 1-8 0V7a4 4 0 0 1 4-4Z" /><path d="M7 9h3m4 6h3" /></>,
  action: <><path d="m14 3-9 11h6l-1 7 9-11h-6Z" /></>,
  voice: <><path d="M4 10h4l5-5v14l-5-5H4Z" /><path d="M17 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14" /></>,
  alert: <><path d="m12 3 10 18H2Z" /><path d="M12 9v5m0 3h.01" /></>,
  spark: <><path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5Z" /></>,
  code: <><path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18" /></>,
  trash: <><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7" /></>,
}

export function Icon({ name, size = 18, style }: { name: string; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}>{paths[name] || paths.spark}</svg>
}
