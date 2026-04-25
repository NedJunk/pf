# Full System Architecture Design

## 1. Overview

The Voice-First Development Partner is composed of three independently deployable services — Router, Orchestrator, and Expert Agents — sitting behind a provider-agnostic telephony adapter. The Router Core (already built) is the foundation. This spec defines the system that surrounds it.

**Core constraint carried forward:** The Router must not perform deep analysis or code generation. Orchestration of agents is a facilitation function, not a reasoning function — the Router knows how to receive a whisper, not which agent to ask.

---

## 2. System Map

```
[ Phone Call ]  [ Web / Mobile (future) ]
       ↓                  ↓
  [ Telephony Adapter — provider-agnostic ]
       ↓  (audio WebSocket)
  [ Router Service ]  ←——  POST /whisper  ←——  [ Orchestrator Service ]
       ↓  (Gemini Live API)                            ↓
  [ Gemini 2.0 Flash ]                    [ Expert Agent A ]  (REST)
       ↓  (session end)                   [ Expert Agent B ]  (REST)
  [ Transcript artifacts ]                [ Expert Agent N ]  (REST)
```

At session start, the Orchestrator injects the project map and goals into the Router. During the session, the Orchestrator monitors turn context and pushes whispers to the Router's REST endpoint. Expert agents are stateless REST services conforming to the Whisper API contract — any LLM vendor, any language, any host.

---

## 3. Router Service

Extends the Router Core with a server layer. The existing `Router`, `StateStore`, `Facilitator`, and `TranscriptWriter` classes are unchanged — the server wraps them without reaching into their internals.

### 3.1 Telephony Adapter

A WebSocket endpoint accepts an inbound audio stream from any compliant telephony provider and bridges it to the Gemini Live API. Provider-specific concerns (call routing, codec negotiation) live in an adapter layer that conforms to a simple internal contract: audio in, audio out. No telephony provider is assumed — the first implementation will choose one.

### 3.2 Session Lifecycle Endpoints (REST)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/sessions` | Open a session; accepts injected `project_map` and `goals` |
| `POST` | `/sessions/{id}/whisper` | Receive a whisper from the Orchestrator |
| `DELETE` | `/sessions/{id}` | Close session; triggers transcript write |

### 3.3 Session Registry

An in-memory map of session ID → Router instance. Supports multiple concurrent calls without state collision. The registry is local to the Router Service process — it is not shared with the Orchestrator.

### 3.4 Turn Events

After each `facilitate()` call, the Router Service posts a lightweight turn event to the Orchestrator:

```json
{
  "session_id": "string",
  "history_tail": ["string"],
  "goals": ["string"],
  "project_map": ["string"]
}
```

This is the only outbound call the Router Service makes.

---

## 4. Orchestrator Service

The Orchestrator is the intelligent hub between sessions and agents.

### 4.1 Agent Registry

A configuration-driven list of available agents: endpoint URL, display name, domain description, and optional activation hints (keywords, topic areas). No agent is hardcoded — adding an expert means adding a config entry. The registry is the sole source of truth for which agents exist.

### 4.2 Context-Based Routing

On each turn event received from the Router, the Orchestrator evaluates session context against the registry and invokes agents whose domain is relevant. It can also prime new agents as the conversation shifts direction.

The routing logic is implementation-agnostic: it may be rules-based, LLM-assisted (a cheap model asked "which agents are relevant given this context?"), or both. The interface to agents is the same regardless.

### 4.3 Whisper Forwarding

Collects responses from invoked agents and pushes relevant whispers to the Router via `POST /sessions/{id}/whisper`. Whispers below a configurable confidence threshold are dropped and not forwarded.

### 4.4 Agent Health Monitoring

The Orchestrator polls each registered agent's `GET /health` endpoint. Agents that fail to respond are removed from active rotation until they recover. This is the mechanism for dynamic scaling — agents can be spun up or down and the Orchestrator detects availability automatically.

---

## 5. Whisper API Contract

The shared contract that makes expert agents independently swappable. Any agent — regardless of vendor, language, or host — implements two endpoints.

### `POST /whisper`

**Request:**
```json
{
  "session_id": "string",
  "context": {
    "history": ["string"],
    "goals": ["string"],
    "project_map": ["string"]
  }
}
```

**Response — has whisper (200):**
```json
{
  "source": "string",
  "message": "string",
  "confidence": 0.0
}
```
`source` is the agent's display name as it will be spoken by the Router (e.g. `"ProjectManager"`). `confidence` is 0.0–1.0; the Orchestrator filters whispers below its configured threshold.

**Response — nothing to add (204 No Content):**
The agent processed the context and has nothing relevant to surface. The Orchestrator treats any `204` as a skip — nothing is forwarded to the Router.

### `GET /health`

```json
{ "status": "ok" }
```

Used by the Orchestrator for availability detection and dynamic scaling.

---

## 6. Option C Transition Note

The current architecture uses a synchronous push model: the Orchestrator calls agents, collects responses, and pushes whispers to the Router. The natural evolution toward a fully event-driven system (Option C) would replace this with a message bus — the Router publishes turn events, agents subscribe and push whispers independently.

**The seam that enables this transition is the Orchestrator.** As long as routing logic lives in the Orchestrator (not the Router), and agents call the Orchestrator (not the Router directly), the transition cost stays bounded.

**Evaluate any new feature that touches agent invocation against these two questions:**
1. Does this move routing logic into the Router?
2. Does this create a direct channel between an agent and the Router that bypasses the Orchestrator?

If yes to either, the feature makes Option C harder. Flag it before building.

---

## 7. What Is Out of Scope

- **Persistence of the project map and knowledge graph** — owned by the client or a higher-level orchestrator; injected at session start. The Router and Orchestrator are stateless across sessions.
- **Gemini vendor lock-in** — acknowledged as a current constraint; addressed in a future iteration by abstracting the LLM call behind an interface.
- **Web and mobile clients** — the phone call interface is the primary target. Other client types (PWA, native app) will conform to the same session lifecycle endpoints.
- **Authentication and security** — deferred; addressed once the server layer architecture is defined.
