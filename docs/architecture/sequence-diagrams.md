# System Interaction Flows

Sequence diagrams for all major interaction paths in the voice-first development partner. Services:

| Service | Role | Port |
|---|---|---|
| Browser | Web client — microphone in, audio + transcript out | — |
| RouterService | FastAPI + WebSocket, owns Gemini Live session | 8080 |
| LiveSession | Manages 3 concurrent async tasks per session | (in-process) |
| Gemini Live API | Real-time bidirectional audio + transcription | external |
| Orchestrator | Turn handler, agent registry, health monitor | 8081 |
| DevCoach | First expert agent (Gemini 2.0 Flash) | 8082 |
| WikiManager | Per-agent persistent knowledge store | (disk) |

---

## 1 — Session Startup

Browser creates a session, the router opens a Gemini Live API connection with the behavioral contract loaded as system instruction, then upgrades to a WebSocket and spawns three concurrent tasks.

```mermaid
sequenceDiagram
    participant B as Browser
    participant RS as RouterService :8080
    participant SR as SessionRegistry
    participant LS as LiveSession
    participant G as Gemini Live API

    B->>RS: POST /sessions {project_map, goals}
    RS->>SR: create(project_map, goals)
    SR->>LS: __init__(session_id, config)
    SR-->>RS: session_id
    RS->>LS: connect()
    Note right of LS: Loads BEHAVIORAL_CONTRACT<br/>+ backlog.md (if BACKLOG_PATH set)<br/>as system_instruction
    LS->>G: aio.live.connect(model, config)<br/>thinking_budget:0 · AUDIO modality
    G-->>LS: session handle
    RS-->>B: {session_id}

    B->>RS: WS /sessions/{session_id}/audio (upgrade)
    RS->>LS: stream(websocket)
    Note right of LS: Spawns 3 concurrent asyncio tasks<br/>① _browser_to_gemini<br/>② _gemini_to_browser<br/>③ _whisper_drain
```

---

## 2 — Per-Turn Flow

Each time the user speaks, audio is streamed to Gemini, transcribed in both directions, committed to `_history` in the correct order, and then the turn event is dispatched to the orchestrator for expert agent processing.

```mermaid
sequenceDiagram
    participant B as Browser
    participant LS as LiveSession
    participant G as Gemini Live API
    participant O as Orchestrator :8081

    Note over B,O: Tasks ① and ② run concurrently

    loop Continuous audio
        B->>LS: PCM bytes (16 kHz Int16) via WebSocket
        LS->>G: send_realtime_input(audio blob)
    end

    Note over G: VAD detects end-of-turn

    loop receive() — one generator call per turn
        G-->>LS: input_transcription chunk(s)
        LS->>LS: _input_buf.append(chunk)
        LS-->>B: {type:transcript, role:user, text}
        G-->>LS: output_transcription chunk(s)
        LS->>LS: _output_buf.append(chunk)
        LS-->>B: {type:transcript, role:assistant, text}
        G-->>LS: audio bytes (PCM 24 kHz) via response.data
        LS-->>B: audio bytes
        G-->>LS: turn_complete
    end

    Note right of LS: _input_buf non-empty → user branch<br/>1. history.append("User: …")<br/>2. _flush_output_buf() → history.append("Assistant: …")<br/>3. _model_generating.set()

    LS-->>B: {type:turn_complete}
    LS->>O: POST /turns {session_id, history_tail[-10], goals, project_map}
    O-->>LS: 202 Accepted
    Note right of O: handle_turn dispatched<br/>as BackgroundTask
```

---

## 3 — Whisper Pipeline

After each turn, the orchestrator fans out to all healthy agents. Each agent queries its wiki for relevant context, calls Gemini Flash to generate a suggestion, and POSTs the result back as a whisper callback. The `_whisper_drain` task injects it into the live Gemini session as silent context.

```mermaid
sequenceDiagram
    participant O as Orchestrator :8081
    participant HM as HealthMonitor
    participant A as DevCoach :8082
    participant GF as Gemini Flash
    participant W as WikiManager (disk)
    participant RS as RouterService :8080
    participant LS as LiveSession
    participant GL as Gemini Live API

    Note over O,GL: BackgroundTask: handle_turn

    O->>HM: is_healthy("DevCoach")?
    HM-->>O: true
    O->>A: POST /whisper {session_id, context, callback_url, confidence_threshold}
    A-->>O: 202 Accepted
    Note right of A: _handle_whisper dispatched<br/>as BackgroundTask

    A->>W: read_index()
    W-->>A: index.md
    A->>GF: generate(QUERY_WIKI_PROMPT + history)
    GF-->>A: relevant page filenames (up to 5)
    A->>W: read_page(name) × N
    W-->>A: wiki page content → wiki_context

    A->>GF: generate(WHISPER_PROMPT + wiki_context + history_tail)
    GF-->>A: suggestion text OR "NO_WHISPER"

    alt confidence >= threshold
        A->>RS: POST /sessions/{id}/whisper {source, message}
        RS-->>A: 200 {}
        RS->>LS: inject_whisper(source, message)
        LS->>LS: _whisper_queue.put_nowait(whisper)
    else NO_WHISPER or below threshold
        Note right of A: Silent — no callback sent
    end

    Note over LS,GL: Task ③ _whisper_drain (concurrent)

    LS->>LS: await _whisper_queue.get()
    LS->>LS: await _model_generating.wait()
    Note right of LS: Blocks while assistant responds.<br/>Releases when next user turn_complete fires.
    LS-->>RS: send_text {type:whisper, source, message} → browser overlay
    LS->>GL: send_client_content([WHISPER from …], turn_complete=False)
    Note right of GL: Gemini may echo as output_transcription<br/>— dropped by BUG-12 filter
    LS->>LS: _history.append("[Whisper from …]")
```

---

## 4 — Interrupted Turn

When the user speaks over the assistant mid-response, Gemini emits an `interrupted` event. Partial output is flushed to history immediately, preventing stale content from contaminating the next user turn.

```mermaid
sequenceDiagram
    participant B as Browser
    participant LS as LiveSession
    participant G as Gemini Live API

    G-->>LS: output_transcription ("Considering the")
    LS->>LS: _output_buf.append("Considering the")
    G-->>LS: audio bytes (partial)
    LS-->>B: audio bytes

    Note over B: User speaks over the assistant

    G-->>LS: interrupted event
    LS->>LS: _flush_output_buf() immediately<br/>→ history.append("Assistant: Considering the")
    Note right of LS: Flush-on-interrupt prevents stale<br/>partial output contaminating the<br/>next user turn_complete path
    LS-->>B: {type:interrupted}

    B->>LS: new PCM audio (user continues)
    LS->>G: send_realtime_input(audio)
    G-->>LS: input_transcription + turn_complete (new user turn)
    LS->>LS: history.append("User: …")
    LS->>LS: _flush_output_buf() → noop (buffer already clear)
```

---

## 5 — Session Teardown and Wiki Ingest

When the browser disconnects, the session closes the Gemini connection, writes the transcript to disk, and notifies the orchestrator synchronously. The orchestrator fans out `/ingest` to all healthy agents, which run knowledge extraction as background tasks.

```mermaid
sequenceDiagram
    participant B as Browser
    participant RS as RouterService :8080
    participant LS as LiveSession
    participant GL as Gemini Live API
    participant O as Orchestrator :8081
    participant A as DevCoach :8082
    participant GF as Gemini Flash
    participant W as WikiManager (disk)

    B->>RS: WebSocket disconnect
    RS->>LS: close()
    LS->>LS: cancel tasks ①②③
    LS->>GL: __aexit__ (session close)

    Note right of LS: Flush remaining buffers<br/>if _input_buf → history.append("User: …")<br/>_flush_output_buf() → history.append("Assistant: …")

    LS->>LS: TranscriptWriter.write_transcript(session_id, history)
    Note right of LS: ./transcripts/{date}_{id}_{slug}.md

    LS->>O: POST /sessions/{session_id}/close {transcript}
    O-->>LS: 200 OK
    LS->>LS: _http_client.aclose()
    RS->>RS: registry.remove(session_id)

    Note over O,W: handle_session_close (awaited synchronously)

    O->>O: check _ingested_sessions (idempotency guard)
    O->>A: POST /ingest {session_id, transcript}
    A-->>O: 202 Accepted
    Note right of A: _safe_ingest as BackgroundTask

    A->>GF: generate(INGEST_PROMPT + schema + index + transcript)
    GF-->>A: --- PAGE: filename.md --- … --- INDEX ---
    A->>W: write_page(filename, content) × N
    A->>W: write_index(new_index.md)
    A->>W: append_log("[date] ingest | session_id")
```

---

## 6 — Health Monitor Background Loop

The orchestrator starts a background polling loop on startup. Only agents that respond with HTTP 200 to `/health` within 5 seconds are eligible to receive turn events and ingest calls.

```mermaid
sequenceDiagram
    participant O as Orchestrator :8081
    participant HM as HealthMonitor
    participant A as Expert Agent :8082

    Note over O,A: FastAPI lifespan startup

    O->>HM: start()
    Note right of HM: asyncio.create_task(_poll_loop)<br/>All registered agents start healthy

    loop Every 30 seconds
        HM->>A: GET /health
        alt HTTP 200
            A-->>HM: {status: "ok"}
            HM->>HM: _healthy.add(agent.name)
        else timeout / error / non-200
            HM->>HM: _healthy.discard(agent.name)
            Note right of HM: Agent excluded from next<br/>turn dispatch and ingest
        end
    end

    Note over O,A: FastAPI lifespan shutdown
    O->>HM: stop() → cancel poll task
```

---

## Concurrency Model

The three tasks spawned by `LiveSession.stream()` share mutable state without locks. This is safe because asyncio uses cooperative scheduling — only one coroutine runs at a time, and no task yields between a read and its dependent write on `_history`, `_input_buf`, or `_output_buf`.

| Task | Owns | Reads |
|---|---|---|
| `_browser_to_gemini` | — | browser WebSocket |
| `_gemini_to_browser` | `_input_buf`, `_output_buf`, `_history`, `_model_generating` | Gemini event stream |
| `_whisper_drain` | `_whisper_queue` appends to `_history` | `_model_generating` |
