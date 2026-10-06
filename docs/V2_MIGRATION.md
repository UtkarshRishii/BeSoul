# SOUL V2 architecture audit and migration

Audited 3 October 2026. This checkout is the existing Python application, not a separate V2 codebase. Its source has been backed up under `data/upgrade-backup-20261003` before implementation; credentials are excluded. No Git metadata or existing tests are present in this checkout.

| Subsystem | Existing files | Decision |
| --- | --- | --- |
| Application coordination | `soul/core/assistant.py`, `lifecycle.py`, `session.py` | Extend with events, interruptible turns and injectable presentation |
| Context and reasoning | `soul/core/brain.py`, `soul/ai/conversation.py`, `prompts.py` | Preserve; add bounded task context and explicit trust boundaries |
| Google SDK boundary | `soul/ai/gemini_client.py` | Extend existing native tool loop; retain exact model parts, IDs and signatures; add transcription |
| Tools and permissions | `soul/tools/models.py`, `registry.py`, `executor.py`, `setup.py` | Extend compatible receipts, recovery and explicitly safe read concurrency |
| Desktop isolation | `soul/desktop/bridge.py`, `worker.py`, `windows.py` | Preserve fixed-operation IPC and worker isolation; add guarded input |
| Application discovery | `soul/desktop/resolver.py`, `context.py` | Preserve discovery/cache/blocklists; track GUI identity and takeover |
| Vision | `soul/desktop/vision.py` | Extend to frame/context models, adaptive capture and accessibility grounding |
| Persistent memory | `soul/memory/long_term.py`, `manager.py`, `models.py` | Preserve WAL/upsert/ordered extraction; improve relevance and credential rejection |
| Voice output | `soul/voice/gemini_voice.py`, `player.py`, `service.py` | Preserve asynchronous Gemini PCM; emit real playback amplitude and cancellation |
| Terminal UI | `soul/cli/renderer.py`, `soul/input/terminal.py`, `main.py` | Retain as explicit CLI recovery/developer mode |
| Runtime events and desktop UI | No existing subsystem | Add event bus, authenticated loopback bridge, native shell and React/Three.js frontend |
| Test coverage | README references missing `tests/` | Add deterministic fake model/worker/audio/bridge tests; live desktop acceptance remains separate |

## Coherent milestones

1. Add authoritative state/events and validated persisted preferences while preserving CLI startup.
2. Extend executor receipts and introduce bounded runtime tasks/recovery; preserve native Gemini history.
3. Extend Vision Eye and keyboard capabilities without weakening single-use targets, confirmation, freshness, shell blocks, Escape or corner failsafes.
4. Connect Python events, confirmations, cancellation and streaming to an authenticated local desktop presentation; ship static assets and graceful rendering fallback.
5. Add opt-in bounded push-to-talk, real speech amplitude, inspectable memory settings and selective retrieval.
6. Run deterministic regressions, build/typecheck frontend, visually inspect UI, and document measured acceptance and remaining environment limitations.

## Non-negotiable boundaries

Python remains the authority. Gemini remains the single reasoning provider and SDK boundary. Tools execute through ToolExecutor. External text, titles, tool content, screenshots and memory are untrusted data. Images/audio stay in RAM. Model-provided shell commands and raw click coordinates remain unavailable. Dispatch never implies verification. GUI operations stay ordered; cancellation invalidates targets and stops future input. The graphical shell must not silently record the microphone or screen.
