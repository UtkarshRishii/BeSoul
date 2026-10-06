# BeSoul

A Windows AI companion built on the existing SOUL Python runtime. Gemini 3.5 Flash interprets requests and chooses native capabilities; the runtime governs permissions, bounded execution, grounded input, verification and cancellation.

## Start

Double-click **start_soul.cmd**, or run:

```powershell
.\.venv\Scripts\python.exe main.py
```

The default opens a native Windows desktop window with a locally bundled React/TypeScript interface. Microsoft Edge WebView2 must be available. The original terminal interface remains available:

```powershell
.\.venv\Scripts\python.exe main.py --cli
```

Preview the interface without starting Gemini, microphone capture or Windows automation:

```powershell
.\.venv\Scripts\python.exe main.py --preview
```

The existing API key, memories and application architecture are preserved. The upgrade sets SOUL_RESPONSE_MODE=full so Gemini 3.5 Flash is primary; Flash-Lite remains a configurable fast mode and transient-error fallback. No model is substituted after actions or partial output have started.

## Installation and frontend development

Python 3.11+ and Windows are required for physical desktop capabilities. From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Only on a new installation:
Copy-Item .env.example .env
# Set GEMINI_API_KEY in .env.
```

Do not overwrite an existing .env. To rebuild the local frontend with Node.js:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run build
npm.cmd test
```

The production frontend assets live in frontend/dist. Runtime operation does not depend on a remote asset CDN. Frontend changes require a rebuild and app restart.

## Interaction

Use the composer to type a request. Hold the microphone button or Ctrl + Space to talk; release to send. Enable **Hands-free** in the voice widget for continuous conversation: local speech detection submits after approximately 0.8 seconds of silence, pauses recording throughout transcription and replies, and resumes when Soul finishes. Hands-free is off at startup and does not persist across sessions. Text remains usable if microphone or speech output fails. A new request stops prior speech. Stop and Escape interrupt active automation; moving the pointer to a display corner or holding a physical key can also prevent further input.

The central glass 3D orb follows idle, listening, thinking and speaking states, real playback amplitude and pointer movement. It supports reduced motion and a WebGL fallback. Midnight blue and violet backgrounds and translucent glass widgets replace the previous neon canvas. Text status, confirmations and activity remain accessible when rendering is reduced or unavailable. The activity inspector contains real execution receipts, including dispatch, verification and error state.

Settings expose AI, voice, vision, automation, memory, privacy, appearance and developer preferences. Public preferences are validated and persisted separately from credentials in data/preferences.json. Service-enabling changes may require restart; privacy disabling stops the affected active work.

## Voice speed and appearance

Open Settings from the top dock. **Voice → Voice engine** offers Windows speech (the Windows default, on-device and quick to generate) or Gemini (the configured natural voice, generated remotely). The stored Gemini voice remains selectable. Both engines use the same cancellable native playback path; the UI never plays a second copy of the audio.

Responses are split at sentence boundaries, with the next audio segment generated during current playback. Full prose is spoken up to `SOUL_TTS_MAX_CHARACTERS` (default 12,000); code fences are skipped. The first segment can start while a final response streams. Tool-selection prose remains staged until it is established as a final answer. Ordinary conversation can answer directly without an extra `finalize_task` round trip; tool tasks retain the final-report path and verification requirements.

Appearance settings include reduced motion and visual quality. Accent buttons choose blue, violet, emerald or warm amber. Widgets remain draggable and collapsible, with layouts adapted to smaller windows. The bundled Soul icon is used in the UI and the native Windows title bar/taskbar.

## Agent execution

The existing Assistant coordinates services; Brain assembles selective context; GeminiClient is the only Google SDK integration boundary. TaskEngine records the goal, current step, application context, receipts, failures and verification in ephemeral runtime state.

Gemini chooses atomic tools dynamically. ToolExecutor validates strict schemas, enforces permissions, confirmations, timeouts and budgets, and serializes physical input. Only explicitly safe read capabilities are eligible for parallel execution. Recovery guidance asks the model to observe again or select another grounded strategy; it never blindly replays uncertain input. Denial, emergency stop, takeover and protection errors stop the restricted workflow.

A dispatched action is not a verified outcome. Browser navigation remains unverified until a linked verify_result observation establishes the requested visible state. Application launch requires an observed window; speaker changes use actual state readback. Unknown side effects survive timeout/cancellation in receipts.

The finalize_task capability requests an honest final report without declaring success. Its subsequent model request disables further tools and streams the answer. Native function IDs, exact model parts and thought signatures survive tool continuations. Legacy AUTO responses containing both prose and tool calls have their prose staged so it cannot appear as completed work.

## Vision Eye and input

Vision is task-driven. ScreenFrame records monitor/crop geometry, application identity, image dimensions, freshness, hash and differences; VisualContext is ephemeral. Captures normally crop the active application and downscale. Unchanged scenes can reuse localization context, while physical input always gets a fresh consistency check.

Optional bounded Windows UI Automation metadata helps identify elements and keyboard focus. Custom interfaces fall back to Gemini multimodal grounding. UI labels, screen text and window titles are untrusted information.

Mouse and keyboard tools require expiring, single-use target IDs. The model cannot supply click coordinates. The runtime checks foreground process/window identity, geometry, pixels, cursor movement and user input. Typing requires an ordinary editable field with established focus. Passwords, authentication codes, command shells, interpreter regions and executable/protocol launchers are blocked. Key and shortcut allowlists are bounded; consequential activation requires confirmation.

Screenshots and microphone recordings remain in RAM. There is no continuous desktop upload. The microphone is active only during push-to-talk or an explicitly enabled Hands-free session; Stop disables Hands-free. Raw screen images and sensitive input arguments are excluded from event telemetry and persistent memory.

## Preserved capabilities

Application discovery/open/focus/graceful close; visible windows; validated HTTP(S) browser navigation; web and YouTube search; YouTube lookup; system information; battery; date/time; volume/mute; user-requested clipboard; allowlisted documents/folders; screen observation and grounding; mouse/scroll; SQLite memory; asynchronous Windows or Gemini speech; and the original CLI commands.

Application discovery still uses Start Menu shortcuts, registry App Paths, safe PATH indexing and shallow installation roots. Cached shell entries remain blocked. Files are opened through a document/media allowlist; generic file tools cannot execute scripts.

Memory retains its sliding conversation window, SQLite WAL/upsert, ordered extraction queue, deletion controls and credential filtering. Retrieval combines lexical relevance, importance, confidence, recency and optional application context. No embedding model is invented or required.

## Safety and privacy

Only actual user input authorizes actions. Screens, websites, files, emails, notifications, clipboard, titles, search results, memory and externally sourced tool content cannot redefine system instructions or grant permissions.

The desktop bridge is authenticated, bound to loopback and checks origins/hosts. It exposes narrow message, preference, microphone and confirmation operations. The native WebView stays on the local application; Python owns all intelligence. The isolated worker has fixed operations and receives no Gemini credentials or model-generated shell commands.

Relevant conversation, memory extraction inputs, requested clipboard data, task-driven screenshots and explicit voice recordings can be sent to Google. Local SQLite memory is unencrypted. Secrets are filtered from extraction, events and structured logs. data, .env and runtime caches remain private local files.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q soul main.py
# Explicit live test: only read-only date/time tools are exposed.
.\.venv\Scripts\python.exe -m tests.live_read_smoke
```

The deterministic suite uses fake models, workers, screenshots and audio so normal tests never control the developer's computer or call the real Gemini API. Coverage includes native tool history, fallback/no replay, recovery, verification, cancellation, safety boundaries, RAM-only visual fixtures, coordinate transforms, single-use targets, user takeover, guarded input, memory, voice and preferences.

Actual acceptance results and remaining machine-specific limitations are recorded in docs/V2_ACCEPTANCE.md. Arbitrary applications, custom renderers, DPI layouts and microphone devices need their own acceptance checks; a smoke test is not a guarantee of every desktop workflow.

## Architecture and migration

The source remains in soul/ai, soul/core, soul/desktop, soul/memory, soul/tools, soul/voice, soul/config and soul/utils. New domains are soul/agent, soul/events and soul/ui_bridge, with the presentation in frontend.

The pre-change source backup is data/upgrade-backup-20261003. It excludes credentials and does not replace the current memory database. The architectural audit and coherent migration decisions are in docs/V2_MIGRATION.md.

References: [Google Gen AI SDK](https://googleapis.github.io/python-genai/), [Gemini 3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash), [native function calling](https://ai.google.dev/gemini-api/docs/function-calling), [thought signatures](https://ai.google.dev/gemini-api/docs/thought-signatures), [speech generation](https://ai.google.dev/gemini-api/docs/speech-generation).
