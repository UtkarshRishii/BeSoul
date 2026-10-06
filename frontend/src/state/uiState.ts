import { create } from 'zustand'
import type { SoulState } from '../types'

export type SoulVisualState =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'seeing'
  | 'acting'
  | 'verifying'
  | 'speaking'
  | 'waiting'
  | 'success'
  | 'error'
  | 'interrupted'

export type ViewOverlay = 'none' | 'settings' | 'memory' | 'activity'

export interface SoulVisualConfig {
  coreBrightness: number
  coreScale: number
  particleDensity: number
  particleSpeed: number
  shellDistortion: number
  neuralDensity: number
  rotationSpeed: number
  lightIntensity: number
  statusText: string
  statusSecondary: string
  accentColor: string
}

const visualConfigs: Record<SoulVisualState, SoulVisualConfig> = {
  idle: {
    coreBrightness: 0.6, coreScale: 1.0, particleDensity: 1.0, particleSpeed: 0.3,
    shellDistortion: 0.0, neuralDensity: 0.15, rotationSpeed: 0.02,
    lightIntensity: 1.0, statusText: 'SOUL', statusSecondary: '',
    accentColor: '#EAFBF8',
  },
  listening: {
    coreBrightness: 0.8, coreScale: 1.06, particleDensity: 1.2, particleSpeed: 0.5,
    shellDistortion: 0.15, neuralDensity: 0.25, rotationSpeed: 0.03,
    lightIntensity: 1.3, statusText: 'LISTENING', statusSecondary: '',
    accentColor: '#B8F5EA',
  },
  thinking: {
    coreBrightness: 0.95, coreScale: 0.88, particleDensity: 1.8, particleSpeed: 0.7,
    shellDistortion: 0.3, neuralDensity: 0.7, rotationSpeed: 0.06,
    lightIntensity: 1.5, statusText: 'THINKING', statusSecondary: '',
    accentColor: '#8FE3D3',
  },
  seeing: {
    coreBrightness: 0.75, coreScale: 1.04, particleDensity: 1.3, particleSpeed: 0.4,
    shellDistortion: 0.2, neuralDensity: 0.35, rotationSpeed: 0.025,
    lightIntensity: 1.2, statusText: 'SEEING', statusSecondary: '',
    accentColor: '#A2D5EE',
  },
  acting: {
    coreBrightness: 0.85, coreScale: 1.02, particleDensity: 1.4, particleSpeed: 0.8,
    shellDistortion: 0.25, neuralDensity: 0.4, rotationSpeed: 0.045,
    lightIntensity: 1.4, statusText: 'ACTING', statusSecondary: '',
    accentColor: '#71CFC1',
  },
  verifying: {
    coreBrightness: 0.7, coreScale: 0.92, particleDensity: 0.8, particleSpeed: 0.2,
    shellDistortion: 0.05, neuralDensity: 0.1, rotationSpeed: 0.015,
    lightIntensity: 1.1, statusText: 'VERIFYING', statusSecondary: '',
    accentColor: '#8FE3D3',
  },
  speaking: {
    coreBrightness: 0.75, coreScale: 1.0, particleDensity: 1.1, particleSpeed: 0.4,
    shellDistortion: 0.1, neuralDensity: 0.2, rotationSpeed: 0.025,
    lightIntensity: 1.2, statusText: 'SPEAKING', statusSecondary: '',
    accentColor: '#B8F5EA',
  },
  waiting: {
    coreBrightness: 0.5, coreScale: 0.98, particleDensity: 0.7, particleSpeed: 0.1,
    shellDistortion: 0.0, neuralDensity: 0.05, rotationSpeed: 0.01,
    lightIntensity: 0.8, statusText: 'WAITING', statusSecondary: '',
    accentColor: '#E2CDA6',
  },
  success: {
    coreBrightness: 1.0, coreScale: 1.08, particleDensity: 1.5, particleSpeed: 0.6,
    shellDistortion: 0.1, neuralDensity: 0.3, rotationSpeed: 0.03,
    lightIntensity: 1.6, statusText: '', statusSecondary: 'Done',
    accentColor: '#B8F5EA',
  },
  error: {
    coreBrightness: 0.4, coreScale: 0.95, particleDensity: 0.6, particleSpeed: 0.15,
    shellDistortion: 0.35, neuralDensity: 0.05, rotationSpeed: 0.01,
    lightIntensity: 0.7, statusText: '', statusSecondary: '',
    accentColor: '#D7AA83',
  },
  interrupted: {
    coreBrightness: 0.45, coreScale: 0.96, particleDensity: 0.5, particleSpeed: 0.08,
    shellDistortion: 0.0, neuralDensity: 0.02, rotationSpeed: 0.005,
    lightIntensity: 0.75, statusText: 'Interrupted', statusSecondary: '',
    accentColor: '#A8B4BE',
  },
}

export function mapSoulState(state: SoulState): SoulVisualState {
  const map: Record<string, SoulVisualState> = {
    IDLE: 'idle', LISTENING: 'listening', THINKING: 'thinking', SEEING: 'seeing',
    ACTING: 'acting', VERIFYING: 'verifying', SPEAKING: 'speaking',
    WAITING_CONFIRMATION: 'waiting', SUCCESS: 'success', ERROR: 'error',
    INTERRUPTED: 'interrupted', SHUTTING_DOWN: 'idle',
  }
  return map[state] || 'idle'
}

export function getVisualConfig(state: SoulVisualState): SoulVisualConfig {
  return visualConfigs[state]
}

interface UIStore {
  visualState: SoulVisualState
  overlay: ViewOverlay
  commandDockActive: boolean
  commandDockExpanded: boolean
  mouseX: number
  mouseY: number
  startupComplete: boolean
  responseVisible: boolean
  responseText: string
  userQuery: string
  contextAction: string
  setVisualState: (state: SoulVisualState) => void
  setOverlay: (overlay: ViewOverlay) => void
  setCommandDockActive: (active: boolean) => void
  setCommandDockExpanded: (expanded: boolean) => void
  setMouse: (x: number, y: number) => void
  setStartupComplete: (complete: boolean) => void
  setResponseVisible: (visible: boolean) => void
  setResponseText: (text: string) => void
  setUserQuery: (query: string) => void
  setContextAction: (action: string) => void
}

export const useUIStore = create<UIStore>((set) => ({
  visualState: 'idle',
  overlay: 'none',
  commandDockActive: false,
  commandDockExpanded: false,
  mouseX: 0.5,
  mouseY: 0.5,
  startupComplete: false,
  responseVisible: false,
  responseText: '',
  userQuery: '',
  contextAction: '',
  setVisualState: (state) => set({ visualState: state }),
  setOverlay: (overlay) => set({ overlay }),
  setCommandDockActive: (active) => set({ commandDockActive: active }),
  setCommandDockExpanded: (expanded) => set({ commandDockExpanded: expanded }),
  setMouse: (x, y) => set({ mouseX: x, mouseY: y }),
  setStartupComplete: (complete) => set({ startupComplete: complete }),
  setResponseVisible: (visible) => set({ responseVisible: visible }),
  setResponseText: (text) => set({ responseText: text }),
  setUserQuery: (query) => set({ userQuery: query }),
  setContextAction: (action) => set({ contextAction: action }),
}))
