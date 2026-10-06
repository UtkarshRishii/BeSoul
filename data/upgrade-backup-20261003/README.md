# Soul AI · Episode 1

Windows personal assistant with Gemini conversation, SQLite memory, native function calling, Gemini voice, and screenshot-grounded desktop interaction. Parts 2 and 3 extend the original foundation. No natural-language keyword router, unrestricted shell, or microphone capture.

## Run

Double-click **start_soul.cmd**, or:

```powershell
.\.venv\Scripts\python main.py
```

The launcher uses Soul's Python environment and directory. Absolute paths to Python and main.py also work from another directory: desktop workers explicitly use the project root. Restart an existing Soul process to load changes.

Fresh installation (Python 3.11+):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Set GEMINI_API_KEY, then start Soul.
```

Do not overwrite an existing .env during upgrades. Credentials, local data, logs and caches are ignored.

## Faster interaction

Fast mode uses **gemini-3.5-flash-lite** with minimal thinking and streams text as it arrives. `/mode full` uses your configured **gemini-3.5-flash**; `/mode fast` switches back. The full model remains `GEMINI_TEXT_MODEL`; the fast/availability model is `GEMINI_FALLBACK_MODEL`. A temporary server failure before text/actions start can trigger an announced fallback. Partially executed workflows are never automatically replayed.

Memory extraction runs in an ordered background queue. Voice uses the complete final response, while the keyboard prompt becomes available immediately. A new request interrupts previous speech; `/voice off` cancels it. Memory management commands and shutdown flush pending writes so deleted facts cannot reappear from an older queued write.

A persistent, cancellable desktop worker avoids starting Python for every action. Application discovery is cached for ten minutes. Screenshots and reasoning still involve network/model latency; this is responsive request/response interaction, not continuous Gemini Live audio.

Measured on this machine: a short full CLI reply started at **1.14 seconds** and completed at **1.23 seconds** in fast mode. Memory extraction took **2.36 seconds** and short Gemini voice generation **3.13 seconds**, independently. Warm clock tools took approximately **0–1 ms** after worker startup. These are individual measurements, not guaranteed latency.

## Commands

| Command | Purpose |
| --- | --- |
| `/help` | Reference |
| `/status` | State and measured timings |
| `/models` | Configured and last-used models |
| `/mode fast`, `/mode full` | Choose response mode |
| `/tools` | Capabilities and risk metadata |
| `/memory`, `/memory list` | Real persistent facts and IDs |
| `/forget <id>` | Delete one fact after typing DELETE |
| `/memory clear` | Delete all facts after typing DELETE |
| `/reset` | Clear conversation and transient screen context |
| `/voice on`, `/voice off` | Toggle/cancel speech |
| `/debug` | Diagnostics |
| `/clear` | Clear terminal |
| `/exit` | Flush memory and close services |

Ctrl+C exits. Slash commands are local. Normal requests go to Gemini native function calling.

## Tools

- Applications: discover/open/focus/close apps and list visible windows. Discovery uses Start Menu shortcuts, App Paths registry entries, PATH and shallow install roots. Closing requires confirmation and uses WM_CLOSE, never forced termination; unsaved-work dialogs return CLOSE_PENDING.
- Browser/media: validated HTTP(S) URLs, Google search, YouTube search, and real video lookup with yt-dlp. URL dispatch is distinguished from page loading or audible autoplay.
- System: time/date, OS/CPU/RAM, battery, volume, mute/unmute.
- Clipboard: bounded Unicode text read/write. Bodies are not logged as tool arguments.
- Files: open existing folders and allowlisted documents/media. No deletion, executable/script launching through file opening, or unrestricted shell.
- Screen: observe_screen, locate_target, active-window context, move_mouse, click_mouse, double_click, right_click and bounded scrolling with visual verification.

Try `Open Notepad`, `Open YouTube`, `Search Gemini Python SDK`, `Play Starboy on YouTube`, `What is my battery percentage?`, or `Open my editor` after saving that preference.

## Screen interaction

Select your target application, then return to Soul. Soul remembers the recent non-terminal foreground window and restores it where Windows allows. Failure to focus produces an error instead of a guessed click. SOUL_MONITOR=0 selects the active window's display; positive indexes select a monitor.

locate_target captures a fresh screenshot and asks Gemini for a normalized bounding box, confidence, ambiguity, and consequence classification. A confident target receives a one-use ID. Mouse tools accept that ID, never raw model-supplied coordinates. Before input, Soul rechecks the target age, foreground window, display geometry and target-region pixels. Physical coordinates account for scaling and negative monitor origins.

Navigation can execute directly. Impactful or unknown activation requires typing CONFIRM. Ambiguous references must be clarified. After input, Soul distinguishes **input executed** from **desired result visually verified**; pixel changes alone are not proof.

Hold Esc or move the pointer to a display corner to stop the next mouse action. Iterations, calls, clicks, scrolls, failures, timeouts and turn duration are bounded. Timed-out workers are stopped, but an input may already have occurred, so results warn against blind retries. OS focus restrictions and model mistakes remain possible.

Screenshots remain in RAM, never in SQLite. Recent screen metadata is temporary. Screenshot, clipboard, tool and memory content is treated as untrusted data. This is an Episode 1 foundation, not a guarantee of safe automation for arbitrary high-stakes work.

## Architecture

Input → relevant memories + conversation → Gemini → native tool calls → validated registry/executor → Windows worker or vision service → structured results → Gemini continuation → streaming CLI → background extraction and TTS.

`soul/ai/gemini_client.py` owns Google SDK calls. Model parts, function IDs and thought signatures survive tool iterations. Automatic SDK tool execution is disabled. `soul/tools` owns capabilities and permission checks; `soul/desktop` owns OS integration, discovery, foreground context and visual grounding. The original core, memory, input, CLI and voice modules remain separate.

Worker readiness is checked at startup. Failures stop the action sequence. Actual action receipts survive a later Gemini failure. Memory uses semantic-key updates and bounded lexical retrieval; extraction can make mistakes, so inspect /memory.

## Configuration

See .env.example for all defaults. Important options:

- GEMINI_TEXT_MODEL, GEMINI_FALLBACK_MODEL, GEMINI_VOICE_MODEL and GEMINI_VOICE_NAME.
- GEMINI_VISION_MODEL: optional separate multimodal model; empty follows response mode.
- SOUL_RESPONSE_MODE: fast/full. SOUL_FAST_RESPONSES lowers thinking effort where supported.
- SOUL_BACKGROUND_VOICE keeps keyboard input available during synthesis/playback.
- SOUL_TOOLS_ENABLED and SOUL_VISION_ENABLED toggle capabilities.
- SOUL_REQUEST_TIMEOUT, SOUL_TOOL_TIMEOUT and SOUL_TURN_TIMEOUT bound waits.
- SOUL_MAX_TOOL_ITERATIONS, SOUL_MAX_TOOL_CALLS, SOUL_MAX_CLICKS and SOUL_MAX_SCROLLS bound workflows.
- SOUL_TARGET_CONFIDENCE, SOUL_TARGET_TTL and SOUL_MONITOR configure visual targeting.
- SOUL_SYSTEM_PROMPT_FILE optionally overrides personality; SOUL_DATA_DIR controls memory/log storage.

The application index lives in the project's ignored data directory. SQLite is unencrypted. Relevant conversation, requested clipboard data, memory extraction inputs and on-demand screenshots are sent to Google. There is no continuous screenshot recording or microphone input.

## Testing

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m tests.live_smoke
```

Automated tests cover memory, streaming, native multi-call sequencing/signatures, schema validation, permissions, limits/timeouts, URL checks, target freshness, coordinate mapping, nonblocking voice, ordered memory deletion, fallback, and worker launch from another directory. Most tests simulate external effects.

Live checks passed: normal conversation; native date/time/battery calls; real YouTube and Notepad opening; app resolution; YouTube video lookup; volume reading; memory extraction; Gemini PCM generation; full CLI startup/conversation/shutdown outside the project directory.

For controlled visual acceptance, explicitly launch `python tests/desktop_fixture.py`, keep its window active, then run `python -m tests.live_smoke --desktop` (or add --scroll). It only changes a local test label and expires after ten minutes. Visual guardrails have automated coverage. Complete live contextual click/scroll verification was interrupted by model unavailability and the test window closing; it is not claimed as passed. Different DPI layouts and specific apps still need local acceptance checks.

## References

- [Google Gen AI SDK](https://googleapis.github.io/python-genai/)
- [Native function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Thought signatures](https://ai.google.dev/gemini-api/docs/thought-signatures)
- [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
- [Gemini speech generation](https://ai.google.dev/gemini-api/docs/speech-generation)
