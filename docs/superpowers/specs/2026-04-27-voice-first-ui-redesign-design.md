# Voice-First UI Redesign

**Date:** 2026-04-27
**Status:** Approved

## Goal

Strip the browser client down to a call-style interface. No transcript visible in the browser, no setup form, no debug controls. The page exists only to show current voice state and surface errors. Everything spoken — both sides, plus whispers — is captured to the transcript file.

## Changes

### index.html + session.js

- Remove the setup form (project/goals textareas, Cancel/Connect buttons) entirely
- Remove the transcript panel (`#transcript` div)
- Remove the debug toggle checkbox
- The Start button directly calls `startSession()` — no intermediate form step
- Layout: dark background, single state indicator centered, End button only visible during active call
- State dot colors:
  - Ready: dim gray `#555`
  - Listening: green `#4caf50` with subtle glow
  - Speaking: blue `#4a9eff` with subtle glow
  - Error: red `#ff4444`, ⚠ icon, short label below dot — "Mic error" for mic failures, "Connection error" for WebSocket/fetch failures
- `handleControlFrame` keeps processing `turn_complete` and `interrupted` for state transitions; drops `transcript` and `whisper` rendering (no display target)

### behavioral_contract.py

- Router opens every session with a verbal question gathering context — e.g. *"What are you working on today, and what do you want to accomplish?"*
- This replaces the pre-filled project/goals form data

### live_session.py

- Remove the context injection block at session start (the `send_realtime_input(text=context)` call) — with empty `project_map` and `goals` it was sending noise
- `POST /sessions` always receives empty `project_map: []` and `goals: []`; orchestrator expert agents continue to receive context via `history_tail`

### Transcript (no change)

`TranscriptWriter` already writes the full history (user turns, assistant turns) to `./transcripts/{session_id}.md` on session close. Whispers are injected into the Gemini session as `[WHISPER from {source}]` text turns and are transcribed as part of the conversation history.

## What Is Not Changing

- WebSocket audio pipeline
- Orchestrator fan-out and whisper injection
- Session lifecycle (create → stream → close)
- Transcript file format and location

## Success Criteria

- Browser page shows only: title, state dot, status label, Start/End button
- No text appears on screen during or after a session
- Session starts immediately on Start with no form interaction
- Router opens verbally by asking for context
- Errors surface as dot color change + short label
- Transcript file continues to capture full session content
