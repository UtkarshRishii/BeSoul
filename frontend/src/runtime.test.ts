import { describe, expect, it } from 'vitest'
import { initialView, normalizeState, reduceEvent, snapshotView } from './runtime'
import { defaultPreferences, type RuntimeEvent } from './types'

const event = (sequence: number, type: string, payload: Record<string, unknown> = {}): RuntimeEvent => ({ sequence, type, payload, timestamp: '2026-10-04T00:00:00Z', task_id: 'task-1' })

describe('real runtime events', () => {
  it('normalizes existing core aliases without manufacturing activity', () => {
    expect(normalizeState('ready')).toBe('IDLE')
    expect(normalizeState('generating_voice')).toBe('THINKING')
    expect(normalizeState('seeing')).toBe('SEEING')
    expect(initialView.receipts).toEqual([])
  })

  it('streams a single response and ignores duplicate replay events', () => {
    let view = reduceEvent(initialView, event(1, 'UserMessageReceived', { text: 'A request' }))
    view = reduceEvent(view, event(2, 'AssistantResponseStarted'))
    const chunk = event(3, 'AssistantTokenReceived', { token: 'Hello' })
    view = reduceEvent(view, chunk)
    view = reduceEvent(view, chunk)
    view = reduceEvent(view, event(4, 'AssistantTokenReceived', { token: ' world' }))
    view = reduceEvent(view, event(5, 'AssistantResponseEnded'))
    expect(view.messages).toHaveLength(2)
    expect(view.messages[1].text).toBe('Hello world')
    expect(view.messages[1].streaming).toBe(false)
  })

  it('shows dispatched and verified outcomes separately using execution IDs', () => {
    let view = reduceEvent(initialView, event(1, 'ToolStarted', { tool_name: 'click_target', execution_id: 'click-1' }))
    view = reduceEvent(view, event(2, 'ToolCompleted', { tool_name: 'click_target', execution_id: 'click-1', success: true, action_dispatched: true, desired_result_verified: false, summary: 'Click dispatched' }))
    expect(view.receipts).toHaveLength(1)
    expect(view.receipts[0].status).toBe('dispatched')
    view = reduceEvent(view, event(3, 'ToolCompleted', { tool_name: 'verify_result', execution_id: 'verify-1', success: true, desired_result_verified: true, summary: 'Playback observed' }))
    expect(view.receipts[1].status).toBe('verified')
    expect(view.receipts[0].status).toBe('dispatched')
  })

  it('reports tool failures and never treats successful dispatch as verification', () => {
    const failed = reduceEvent(initialView, event(1, 'ToolFailed', { tool_name: 'open_application', execution_id: 'failed', success: false, summary: 'Windows denied focus' }))
    expect(failed.receipts[0].status).toBe('failed')
    const completed = reduceEvent(initialView, event(1, 'ToolCompleted', { tool_name: 'get_time', execution_id: 'read', success: true }))
    expect(completed.receipts[0].status).toBe('completed')
  })

  it('ignores executor confirmation metadata until the bridge provides a real decision ID', () => {
    let view = reduceEvent(initialView, event(1, 'ConfirmationRequested', { tool_name: 'close_application' }))
    expect(view.confirmations).toEqual([])
    view = reduceEvent(view, event(2, 'ConfirmationRequested', { confirmation_id: 'confirm-1', description: 'Close app?', reason: 'Unsaved work', consequence: 'The application will close', expires_at: 1 }))
    expect(view.confirmations).toHaveLength(1)
    view = reduceEvent(view, event(3, 'ConfirmationResolved', { confirmation_id: 'confirm-1' }))
    expect(view.confirmations).toEqual([])
  })

  it('uses actual audio levels and clears them on state changes and interruption', () => {
    let view = reduceEvent(initialView, event(1, 'StateChanged', { state: 'speaking' }))
    view = reduceEvent(view, event(2, 'SpeechAmplitude', { amplitude: .6 }))
    expect(view.audioLevel).toBe(.6)
    view = reduceEvent(view, event(3, 'StateChanged', { state: 'idle' }))
    expect(view.audioLevel).toBe(0)
    view = reduceEvent(view, event(4, 'MicrophoneAmplitude', { amplitude: 1.5 }))
    expect(view.audioLevel).toBe(1)
    view = reduceEvent(view, event(5, 'TaskInterrupted'))
    expect(view.audioLevel).toBe(0)
  })

  it('restores text from the bootstrap snapshot without duplicating streamed events', () => {
    const view = snapshotView({ ready: true, preview: false, state: 'IDLE', preferences: defaultPreferences, sequence: 10,
      messages: [{ id: 'response', role: 'assistant', text: 'Preserved text', streaming: false }],
      events: [event(1, 'AssistantResponseStarted'), event(10, 'AssistantResponseEnded')], confirmations: [] })
    expect(view.messages).toHaveLength(1)
    expect(view.messages[0].text).toBe('Preserved text')
    expect(view.sequence).toBe(10)
  })

  it('bounds event, conversation and receipt history', () => {
    let view = initialView
    for (let i = 1; i <= 350; i++) view = reduceEvent(view, event(i, 'ToolCompleted', { tool_name: 'get_time', execution_id: String(i), success: true }))
    expect(view.events).toHaveLength(200)
    expect(view.receipts).toHaveLength(80)
  })

  it('tracks backend hands-free and microphone phases through recording and replies', () => {
    let view = reduceEvent(initialView, event(1, 'ContinuousListeningChanged', { enabled: true, phase: 'listening' }))
    view = reduceEvent(view, event(2, 'MicrophoneStarted', { continuous: true }))
    expect(view.continuousListening).toBe(true)
    expect(view.microphoneActive).toBe(true)
    view = reduceEvent(view, event(3, 'MicrophoneStopped'))
    view = reduceEvent(view, event(4, 'ContinuousListeningChanged', { enabled: true, phase: 'paused' }))
    expect(view.microphoneActive).toBe(false)
    expect(view.continuousPhase).toBe('paused')
    view = reduceEvent(view, event(5, 'ContinuousListeningChanged', { enabled: false, phase: 'off' }))
    expect(view.continuousListening).toBe(false)
  })

  it('keeps native playback visible during concurrent text streaming without replaying audio', () => {
    let view = reduceEvent(initialView, event(1, 'SpeechStarted', { playback: 'native', audio_url: '/api/audio/segment.wav' }))
    view = reduceEvent(view, event(2, 'StateChanged', { state: 'responding' }))
    expect(view.speakingActive).toBe(true)
    expect(view.lastAudioUrl).toBe('')
    view = reduceEvent(view, event(3, 'SpeechEnded'))
    expect(view.speakingActive).toBe(false)
    expect(view.state).toBe('THINKING')
  })

  it('restores voice state from a reconnect snapshot', () => {
    const view = snapshotView({ continuous_listening: true, continuous_phase: 'listening', microphone_active: true, speaking_active: false })
    expect(view.continuousListening).toBe(true)
    expect(view.microphoneActive).toBe(true)
    expect(view.continuousPhase).toBe('listening')
    expect(view.speakingActive).toBe(false)
  })
})
