# Voice-First UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip the browser client to a dark call-style UI (dot + state label), remove the setup form, and have the Router open sessions verbally.

**Architecture:** Four files change. Backend: remove the context-injection send in `live_session.connect()` and add a verbal-opener rule to `BEHAVIORAL_CONTRACT`. Frontend: fully rewrite `index.html` (dark centered layout) and `session.js` (simplified state machine, no transcript rendering). Tests are updated alongside their corresponding source files.

**Tech Stack:** Python 3.11, FastAPI, pytest, asyncio; vanilla HTML/CSS/JS (no build step)

---

## File Map

| File | Change |
|---|---|
| `router-service/router_service/live_session.py` | Remove context injection from `connect()` |
| `router-service/tests/test_live_session.py` | Update test that asserted context was injected |
| `voice-router/src/router/behavioral_contract.py` | Add verbal session-opener rule |
| `voice-router/tests/router/test_behavioral_contract.py` | Add test for opener rule |
| `router-service/router_service/client/index.html` | Full rewrite — dark call layout |
| `router-service/router_service/client/session.js` | Full rewrite — simplified state machine |

---

## Task 1: live_session.py — remove context injection

**Files:**
- Modify: `router-service/router_service/live_session.py`
- Modify: `router-service/tests/test_live_session.py`

- [ ] **Step 1: Update the failing test first**

  In `router-service/tests/test_live_session.py`, rename `test_connect_sends_setup_and_initial_context` and change its assertion:

  ```python
  @pytest.mark.asyncio
  @patch("router_service.live_session.genai")
  async def test_connect_opens_gemini_session_without_context_injection(mock_genai):
      _, mock_session = _mock_gemini()
      mock_genai.Client.return_value.aio.live.connect.return_value.__aenter__ = (
          AsyncMock(return_value=mock_session)
      )
      mock_genai.Client.return_value.aio.live.connect.return_value.__aexit__ = (
          AsyncMock(return_value=None)
      )

      session = _session()
      await session.connect()

      mock_genai.Client.return_value.aio.live.connect.assert_called_once()
      call_kwargs = mock_genai.Client.return_value.aio.live.connect.call_args
      assert call_kwargs.kwargs["model"] == "gemini-test-model"

      # No context injected at connect — Router asks verbally
      mock_session.send_realtime_input.assert_not_called()
  ```

- [ ] **Step 2: Run to confirm it fails**

  ```bash
  cd router-service && pytest tests/test_live_session.py::test_connect_opens_gemini_session_without_context_injection -v
  ```

  Expected: `FAILED` — `assert_not_called()` fails because `send_realtime_input` is currently called once.

- [ ] **Step 3: Remove the context injection block from `connect()`**

  In `router-service/router_service/live_session.py`, replace the `connect` method body:

  ```python
  async def connect(self) -> None:
      config = {
          "response_modalities": ["AUDIO"],
          "input_audio_transcription": {},
          "output_audio_transcription": {},
          "system_instruction": BEHAVIORAL_CONTRACT,
          "generation_config": {
              "thinking_config": {"thinking_budget": 0},
          },
      }
      self._gemini_cm = self._client.aio.live.connect(
          model=self._live_api_model, config=config
      )
      self._gemini_session = await self._gemini_cm.__aenter__()
  ```

  (Delete the three lines that built `context` and called `send_realtime_input`.)

- [ ] **Step 4: Run the full test suite for router-service**

  ```bash
  cd router-service && pytest -v
  ```

  Expected: all tests pass.

- [ ] **Step 5: Commit**

  ```bash
  git add router-service/router_service/live_session.py router-service/tests/test_live_session.py
  git commit -m "feat: remove context injection from connect — Router asks verbally"
  ```

---

## Task 2: behavioral_contract.py — add verbal session opener

**Files:**
- Modify: `voice-router/src/router/behavioral_contract.py`
- Modify: `voice-router/tests/router/test_behavioral_contract.py`

- [ ] **Step 1: Write the failing test**

  Append to `voice-router/tests/router/test_behavioral_contract.py`:

  ```python
  def test_behavioral_contract_includes_session_opener():
      assert "working on today" in BEHAVIORAL_CONTRACT
  ```

- [ ] **Step 2: Run to confirm it fails**

  ```bash
  cd voice-router && pytest tests/router/test_behavioral_contract.py::test_behavioral_contract_includes_session_opener -v
  ```

  Expected: `FAILED` — phrase not yet present.

- [ ] **Step 3: Add the verbal opener rule to `BEHAVIORAL_CONTRACT`**

  In `voice-router/src/router/behavioral_contract.py`, add one rule to the list:

  ```python
  BEHAVIORAL_CONTRACT = """\
  You are a thin, voice-first facilitation router. Your ONLY job is to help \
  the user capture and clarify their thoughts.

  Rules:
  - Open every session by asking the developer what they are working on today \
  and what they want to accomplish
  - Always ask one clarifying question to deepen understanding or prompt specifics
  - Suggest how input might be categorized or connected to existing work
  - If expert whispers are listed below, voice the most relevant one naturally \
  (e.g. "The Project Manager is noting that...")
  - NEVER perform deep analysis, generate code, or offer solutions
  - Keep responses short — this is a voice interaction

  # --- whisper handling ---
  You will occasionally receive messages prefixed with "[WHISPER from <name>]:". \
  Treat these as private suggestions from domain experts. \
  Weave the insight naturally into your next response — \
  do not quote it directly or attribute it by name.\
  """
  ```

- [ ] **Step 4: Run the full voice-router test suite**

  ```bash
  cd voice-router && pytest -v
  ```

  Expected: all tests pass including `test_behavioral_contract_includes_session_opener`.

- [ ] **Step 5: Commit**

  ```bash
  git add voice-router/src/router/behavioral_contract.py voice-router/tests/router/test_behavioral_contract.py
  git commit -m "feat: Router opens sessions by asking what developer is working on"
  ```

---

## Task 3: index.html — dark call layout

**Files:**
- Modify: `router-service/router_service/client/index.html`

- [ ] **Step 1: Replace index.html**

  ```html
  <!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dev Partner</title>
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body {
        background: #111;
        color: #eee;
        font-family: monospace;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        gap: 16px;
      }
      #title {
        font-size: 10px;
        color: #444;
        letter-spacing: 3px;
        text-transform: uppercase;
      }
      #dot {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        border: 2px solid #333;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 32px;
        color: #555;
        transition: border-color 0.3s, box-shadow 0.3s, color 0.3s;
      }
      #dot[data-state="listening"] {
        border-color: #2d5a2d;
        color: #4caf50;
        box-shadow: 0 0 20px #1a3a1a;
      }
      #dot[data-state="speaking"] {
        border-color: #1a3a5c;
        color: #4a9eff;
        box-shadow: 0 0 20px #0d1f30;
      }
      #dot[data-state="error"] {
        border-color: #5a1a1a;
        color: #ff4444;
        box-shadow: 0 0 20px #3a0a0a;
      }
      #status-label {
        font-size: 11px;
        color: #555;
        letter-spacing: 2px;
        text-transform: uppercase;
        text-align: center;
      }
      #status-label[data-state="listening"] { color: #4caf50; }
      #status-label[data-state="speaking"]  { color: #4a9eff; }
      #status-label[data-state="error"]     { color: #ff4444; }
      #error-detail {
        font-size: 9px;
        color: #a33;
        letter-spacing: 1px;
        text-transform: uppercase;
        height: 14px;
      }
      button {
        background: none;
        font-family: monospace;
        font-size: 11px;
        letter-spacing: 1px;
        text-transform: uppercase;
        padding: 6px 20px;
        border-radius: 4px;
        cursor: pointer;
      }
      #start-btn { border: 1px solid #444; color: #888; }
      #start-btn:hover { border-color: #666; color: #aaa; }
      #end-btn { border: 1px solid #c00; color: #c44; display: none; }
      #end-btn:hover { border-color: #f00; color: #f44; }
    </style>
  </head>
  <body>
    <div id="title">Dev Partner</div>
    <div id="dot" data-state="ready">⬤</div>
    <div id="status-label" data-state="ready">Ready</div>
    <div id="error-detail"></div>
    <button id="start-btn" onclick="startSession()">Start</button>
    <button id="end-btn" onclick="endSession()">End</button>

    <script src="audio.js"></script>
    <script src="session.js"></script>
  </body>
  </html>
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add router-service/router_service/client/index.html
  git commit -m "feat: dark call-style UI — dot state indicator, no transcript panel"
  ```

---

## Task 4: session.js — simplified state machine

**Files:**
- Modify: `router-service/router_service/client/session.js`

- [ ] **Step 1: Replace session.js**

  ```javascript
  let ws = null;
  let sessionId = null;

  const STATE_LABELS = {
    ready: 'Ready',
    connecting: 'Connecting',
    listening: 'Listening',
    speaking: 'Speaking',
    ended: 'Ended',
    error: 'Error',
  };

  function setState(state, errorDetail = '') {
    const dot = document.getElementById('dot');
    const label = document.getElementById('status-label');
    const detail = document.getElementById('error-detail');
    const startBtn = document.getElementById('start-btn');
    const endBtn = document.getElementById('end-btn');

    dot.dataset.state = state;
    dot.textContent = state === 'error' ? '⚠' : '⬤';
    label.dataset.state = state;
    label.textContent = STATE_LABELS[state] || state;
    detail.textContent = errorDetail;

    const inCall = state === 'listening' || state === 'speaking';
    startBtn.style.display = inCall ? 'none' : 'block';
    endBtn.style.display = inCall ? 'block' : 'none';
  }

  async function startSession() {
    setState('connecting');
    try {
      const resp = await fetch('/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_map: [], goals: [] }),
      });
      if (!resp.ok) {
        setState('error', 'Connection error');
        return;
      }
      const { session_id } = await resp.json();
      sessionId = session_id;

      ws = new WebSocket(`ws://${location.host}/sessions/${session_id}/audio`);
      ws.binaryType = 'arraybuffer';

      ws.onopen = async () => {
        setState('listening');
        try {
          await startMic((pcmBuffer) => {
            if (ws && ws.readyState === WebSocket.OPEN) ws.send(pcmBuffer);
          });
        } catch (err) {
          setState('error', 'Mic error');
          endSession();
        }
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          setState('speaking');
          playPCM(event.data);
        } else {
          handleControlFrame(JSON.parse(event.data));
        }
      };

      ws.onclose = () => {
        stopMic();
        setState('ended');
      };

      ws.onerror = () => setState('error', 'Connection error');

    } catch (_) {
      setState('error', 'Connection error');
    }
  }

  async function endSession() {
    try {
      if (sessionId) await fetch(`/sessions/${sessionId}`, { method: 'DELETE' });
    } catch (_) {
      // ignore — proceed with local cleanup regardless
    } finally {
      if (ws) ws.close();
      stopMic();
      setState('ended');
      sessionId = null;
      ws = null;
    }
  }

  function handleControlFrame(msg) {
    switch (msg.type) {
      case 'turn_complete':
        setState('listening');
        break;
      case 'interrupted':
        flushPlayback();
        setState('listening');
        break;
    }
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add router-service/router_service/client/session.js
  git commit -m "feat: simplified session.js — state machine only, no transcript rendering"
  ```

---

## Task 5: Manual verification

- [ ] **Step 1: Build and start the stack**

  ```bash
  docker compose up --build
  ```

- [ ] **Step 2: Open the browser client**

  Navigate to `http://localhost:8080`. Verify:
  - Dark background, centered dot (gray ⬤), "READY" label, "START" button
  - No form fields, no transcript area, no debug toggle

- [ ] **Step 3: Start a session**

  Click Start. Verify:
  - Dot transitions to green (LISTENING) immediately
  - Router speaks first, asking what you're working on
  - Speaking audio turns dot blue (SPEAKING)
  - After each Router turn, dot returns to green (LISTENING)

- [ ] **Step 4: End a session**

  Click End. Verify:
  - Dot returns to gray, label says "ENDED", Start button reappears
  - No exceptions in `docker compose logs router-service`
  - Transcript file appears in `./transcripts/`

- [ ] **Step 5: Verify transcript content**

  ```bash
  ls ./transcripts/
  cat ./transcripts/<session-id>.md
  ```

  Expected: full conversation including both sides captured.
