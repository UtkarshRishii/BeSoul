export type SoulState = 'IDLE' | 'LISTENING' | 'THINKING' | 'SEEING' | 'ACTING' | 'VERIFYING' |
  'SPEAKING' | 'WAITING_CONFIRMATION' | 'SUCCESS' | 'ERROR' | 'INTERRUPTED' | 'SHUTTING_DOWN'

export interface RuntimeEvent {
  type: string
  sequence: number
  timestamp: string
  task_id?: string | null
  payload: Record<string, unknown>
}

export interface Preferences {
  soul_name: string
  gemini_text_model: string
  soul_response_mode: 'fast' | 'full'
  soul_tts_enabled: boolean
  gemini_voice_name: string
  soul_voice_engine: 'gemini'
  soul_memory_enabled: boolean
  soul_tools_enabled: boolean
  soul_vision_enabled: boolean
  soul_debug: boolean
  soul_reduced_motion: boolean
  soul_visual_quality: 'auto' | 'low' | 'high'
  soul_onboarding_complete: boolean
  soul_microphone_enabled: boolean
}

export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  streaming: boolean
  task_id?: string | null
}

export interface Confirmation {
  confirmation_id: string
  description: string
  reason: string
  consequence: string
  expires_at: number
}

export interface Receipt {
  id: string
  tool: string
  summary: string
  status: 'running' | 'verified' | 'dispatched' | 'completed' | 'failed'
  elapsed?: number
  event: RuntimeEvent
}

export interface RuntimeSnapshot {
  preview: boolean
  ready: boolean
  state: SoulState
  preferences: Preferences
  sequence: number
  messages: ConversationMessage[]
  events: RuntimeEvent[]
  confirmations: Confirmation[]
  total_input_tokens?: number
  total_output_tokens?: number
  model?: string
  voice_model?: string
  continuous_listening?: boolean
  continuous_phase?: 'listening' | 'paused' | 'off'
  microphone_active?: boolean
  speaking_active?: boolean
}

export interface RuntimeView {
  connected: boolean
  ready: boolean
  preview: boolean
  state: SoulState
  messages: ConversationMessage[]
  receipts: Receipt[]
  confirmations: Confirmation[]
  events: RuntimeEvent[]
  notice: string
  error: string
  currentAction: string
  audioLevel: number
  speakingActive: boolean
  microphoneActive: boolean
  continuousListening: boolean
  continuousPhase: 'listening' | 'paused' | 'off'
  preferences: Preferences
  sequence: number
  totalInputTokens: number
  totalOutputTokens: number
  lastAudioUrl: string
  lastTurnStats?: {
    input_tokens: number
    output_tokens: number
    gemini_seconds: number
    tool_seconds: number
    model: string
    first_token_seconds: number
  }
}

export const defaultPreferences: Preferences = {
  soul_name: 'Soul', gemini_text_model: 'gemini-3.5-flash', soul_response_mode: 'full',
  soul_tts_enabled: true, gemini_voice_name: 'Kore', soul_memory_enabled: true,
  soul_voice_engine: 'gemini',
  soul_tools_enabled: true, soul_vision_enabled: true, soul_debug: false,
  soul_reduced_motion: false, soul_visual_quality: 'auto', soul_onboarding_complete: false,
  soul_microphone_enabled: true,
}
