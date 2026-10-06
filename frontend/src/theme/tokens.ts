/* ───────────────────────────────────────────────────────────────────
   SOUL Design Tokens
   Centralized design system for the spatial AI interface
   ─────────────────────────────────────────────────────────────────── */

export const colors = {
  background: {
    deep: '#050809',
    base: '#070B0D',
    surface: '#091011',
    elevated: '#0D1418',
  },
  soul: {
    core: '#EAFBF8',
    coreInner: '#FFFFFF',
    accent: '#B8F5EA',
    secondary: '#8FE3D3',
    tertiary: '#71CFC1',
    dim: '#4A9B8E',
  },
  text: {
    primary: '#E8EDEB',
    secondary: '#9AADA3',
    tertiary: '#6B8278',
    ghost: '#3D5249',
  },
  spectral: {
    violet: '#B8A4D6',
    indigo: '#8B9BCD',
    blue: '#A2D5EE',
  },
  warning: '#D7AA83',
  error: '#C48B72',
  success: '#B8F5EA',
  glass: {
    border: 'rgba(180, 240, 230, 0.08)',
    borderActive: 'rgba(180, 240, 230, 0.15)',
    fill: 'rgba(12, 20, 24, 0.65)',
    fillActive: 'rgba(12, 20, 24, 0.8)',
  },
} as const

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '24px',
  xxl: '32px',
  xxxl: '48px',
} as const

export const radius = {
  small: '8px',
  medium: '12px',
  large: '16px',
  xl: '20px',
} as const

export const typography = {
  fontFamily: "'Inter', 'Segoe UI Variable', -apple-system, BlinkMacSystemFont, sans-serif",
  mono: "'JetBrains Mono', Consolas, monospace",
  sizes: {
    response: '30px',
    overlayTitle: '26px',
    heading: '20px',
    body: '14px',
    label: '12px',
    stateLabel: '10px',
    meta: '10px',
  },
  weights: {
    light: 300,
    regular: 400,
    medium: 500,
  },
} as const

export const motion = {
  fast: '150ms',
  medium: '300ms',
  slow: '500ms',
  glacial: '800ms',
  curves: {
    appear: 'cubic-bezier(0.22, 1, 0.36, 1)',
    disappear: 'cubic-bezier(0.4, 0, 1, 1)',
    spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
    smooth: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
  },
} as const

export const depth = {
  background: 0,
  ambientField: 1,
  soulOuter: 2,
  soulCore: 3,
  contextUI: 4,
  modal: 5,
  critical: 6,
} as const
