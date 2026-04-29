# C4 Architecture Diagrams

Diagrams follow the [C4 model](https://c4model.com). Update these whenever a new service, container, or major component is added or removed. See backlog item E6-F for the maintenance workflow.

---

## Level 1 — System Context

Who uses the system and what external systems does it depend on.

```mermaid
C4Context
  title System Context — Voice Development Partner

  Person(dev, "Developer", "Uses voice to capture and structure thoughts during a development session.")

  System_Boundary(vp, "Voice Partner") {
    System(vp_core, "Voice Partner", "Facilitates voice-first development sessions; routes expert insights back to the developer in real time.")
  }

  System_Ext(gemini_live, "Gemini Live API", "Google. Bidirectional real-time audio conversation with transcription.")
  System_Ext(gemini_api, "Gemini API", "Google. LLM inference for expert agent whisper and wiki ingest.")

  Rel(dev, vp_core, "Speaks to", "WebSocket / PCM audio")
  Rel(vp_core, dev, "Responds with voice + whispers", "WebSocket / PCM audio")
  Rel(vp_core, gemini_live, "Streams audio session", "HTTPS / WebSocket")
  Rel(vp_core, gemini_api, "Calls for agent inference", "HTTPS")
```

---

## Level 2 — Containers

The deployable units inside the system.

```mermaid
C4Container
  title Container Diagram — Voice Development Partner

  Person(dev, "Developer", "Browser-based voice client.")

  System_Boundary(vp, "Voice Partner") {

    Container(browser, "Browser Client", "HTML / JavaScript", "Captures microphone audio, plays back responses, displays transcripts and whispers.")

    Container(router_svc, "Router Service", "Python / FastAPI", "Manages Gemini Live API sessions. Accepts audio over WebSocket, injects whispers, writes transcripts on session close. Port 8080.")

    Container(orchestrator, "Orchestrator", "Python / FastAPI", "Receives turn events, fans out to healthy expert agents, posts whisper results back to the router. Port 8081.")

    Container(dev_coach, "Dev Coach Agent", "Python / FastAPI", "Expert agent: generates coaching whispers and ingests session transcripts into its wiki. Port 8082.")

    ContainerDb(transcripts, "Transcripts", "Filesystem (volume)", "Markdown transcript files written at session close. Filename: timestamp + session-id + topic slug.")

    ContainerDb(wiki, "Dev Coach Wiki", "Filesystem (volume)", "Markdown knowledge pages built up from ingested session transcripts.")
  }

  System_Ext(gemini_live, "Gemini Live API", "Google.")
  System_Ext(gemini_api, "Gemini API", "Google.")

  Rel(dev, browser, "Uses", "HTTPS")
  Rel(browser, router_svc, "Streams audio / receives audio + events", "WebSocket")
  Rel(router_svc, gemini_live, "Bidirectional audio session", "HTTPS / WebSocket")
  Rel(router_svc, orchestrator, "POST /turns (per turn), POST /sessions/{id}/close", "HTTP")
  Rel(orchestrator, dev_coach, "POST /whisper, POST /ingest", "HTTP")
  Rel(orchestrator, router_svc, "POST /sessions/{id}/whisper", "HTTP")
  Rel(router_svc, transcripts, "Writes transcript on close", "Filesystem")
  Rel(dev_coach, wiki, "Reads / writes wiki pages", "Filesystem")
  Rel(dev_coach, gemini_api, "Inference for whisper + ingest", "HTTPS")
```

---

## Level 3 — Router Service Components

Internal structure of the most complex container.

```mermaid
C4Component
  title Component Diagram — Router Service

  Container_Boundary(router_svc, "Router Service") {

    Component(main, "FastAPI App", "Python / FastAPI", "HTTP endpoints: POST /sessions, DELETE /sessions/{id}, POST /sessions/{id}/whisper. Starts and tears down LiveSession instances.")

    Component(session_registry, "SessionRegistry", "Python", "In-memory map of session_id → LiveSession. Guards against duplicate session creation.")

    Component(live_session, "LiveSession", "Python / asyncio", "Owns a single Gemini Live API connection. Runs three concurrent tasks: browser↔Gemini audio relay, whisper drain, turn-complete detection. Flushes transcript on close.")

    Component(behavioral_contract, "BehavioralContract", "Python / string constant", "The Router's system prompt. Defines facilitation rules, whisper handling, and tone. Injected into Gemini session config at connect time.")

    Component(transcript_writer, "TranscriptWriter", "Python", "Writes session history to a timestamped Markdown file on close.")
  }

  Container_Ext(browser, "Browser Client", "Sends audio bytes; receives audio bytes + JSON events.")
  Container_Ext(orchestrator, "Orchestrator", "Receives turn events; sends whisper payloads.")
  System_Ext(gemini_live, "Gemini Live API", "Google.")

  Rel(browser, main, "WebSocket /sessions/{id}/audio", "WebSocket")
  Rel(main, session_registry, "Looks up / registers sessions")
  Rel(main, live_session, "Creates, streams, closes")
  Rel(main, live_session, "Calls inject_whisper()")
  Rel(live_session, behavioral_contract, "Reads system prompt at connect")
  Rel(live_session, gemini_live, "Bidirectional audio + text", "HTTPS / WebSocket")
  Rel(live_session, orchestrator, "POST /turns after each turn_complete", "HTTP")
  Rel(live_session, transcript_writer, "Writes history on close")
```

---

## Level 3 — Expert Agent Base Components

Internal structure shared by all expert agents (via `ExpertAgentBase`).

```mermaid
C4Component
  title Component Diagram — Expert Agent Base (shared by all agents)

  Container_Boundary(agent, "Expert Agent (e.g. Dev Coach)") {

    Component(fastapi_app, "FastAPI App", "Python / FastAPI", "Endpoints: POST /whisper, POST /ingest, GET /health. Concrete agent subclasses ExpertAgentBase.")

    Component(agent_base, "ExpertAgentBase", "Python ABC", "Abstract base class. Implements /whisper, /ingest, /health. Calls abstract _generate() for whisper inference. Manages wiki read/write lifecycle.")

    Component(wiki_manager, "WikiManager", "Python", "Reads and writes Markdown wiki pages from the filesystem volume. Supplies index and relevant pages to the LLM prompt.")

    Component(generate, "_generate() impl", "Python / Gemini SDK", "Concrete implementation in each agent subclass. Calls Gemini API with conversation context + wiki pages. Returns whisper text + confidence score.")
  }

  Container_Ext(orchestrator, "Orchestrator", "Calls /whisper and /ingest.")
  ContainerDb_Ext(wiki, "Wiki Volume", "Filesystem.")
  System_Ext(gemini_api, "Gemini API", "Google.")

  Rel(orchestrator, fastapi_app, "POST /whisper, POST /ingest, GET /health", "HTTP")
  Rel(fastapi_app, agent_base, "Delegates to")
  Rel(agent_base, wiki_manager, "Reads index + relevant pages")
  Rel(agent_base, generate, "Calls for whisper inference")
  Rel(wiki_manager, wiki, "Read / write Markdown files", "Filesystem")
  Rel(generate, gemini_api, "LLM inference", "HTTPS")
```

---

*Last updated: 2026-04-29. Generated manually from codebase inspection — no tooling required.*
