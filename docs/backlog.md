# Product Backlog

Items are ordered by priority within each epic. Epics are listed in priority order — reference codes are stable and do not imply epic ordering. Security and scalability are explicitly deferred until the system is working well for a single user. Local deployment is a long-term goal; provider independence is the path toward it.

---

## Now

Two items are immediately actionable and independent.

- [ ] **BUG-04/05/06 — behavioral contract gaps** — three related issues confirmed across sessions 7e9bc99b, 0185cc4f, c20adebf. All require changes to `voice-router/src/router/behavioral_contract.py`: (1) conditional opener — skip the stock opener if the user's first turn establishes context; (2) no summaries or directives — closing move must be a question or brief acknowledgement; (3) whisper deflection — when asked about external context, deflect naturally rather than denying the capability. All three can be fixed in one pass with corresponding tests.

- [ ] **E4-A — Design: PM agent** — define whisper contract, backlog integration spec, and evaluation criteria. Scope: backlog-aware, surfaces relevant open items during sessions, drafts and files new items on request, resolves spoken bug codes (e.g. "BUG-01") to full entries. Absorbs E6-B (easy bug referencing) — that feature is delivered by this agent, not a standalone tool.

  **Urgency confirmed** (session c4822cff, 2026-04-29): user ended session early because the router lacked backlog context. This is a productivity blocker, not a UX improvement.

  **Open design question (session c4822cff):** real-time injection (agent whispers on every relevant turn) vs. summary-based approach (backlog digest injected at session start). Tradeoffs: real-time has higher latency cost per turn; summary-based risks stale context mid-session. Note: a summary-based approach bypasses the whisper timeout problem (BUG-01 tail) for this agent entirely.

---

## Known Bugs

- [x] **BUG-00 — voice interruption broken** — confirmed fixed in session f1f1fdda (2026-04-29).
- [x] **BUG-01** — **fixed** (2026-04-29, session c20adebf): async callback pattern eliminated all timeouts. 11 turns, zero `ReadTimeout` errors, 7 of 10 whispers delivered. Two late callbacks arrived post-close (404) — expected behavior of async pattern. See commit f3a1dbf.
- [x] **BUG-02 — router refuses to relay context to whisper agents** — fixed (2026-04-29): updated `behavioral_contract.py` to carve out in-session agent relay as facilitation and added tone directive prohibiting affirmations. 30 tests passing.
- [ ] **BUG-03 — httpx client created per call (no connection pooling)** — identified in architecture review (2026-04-29). Five sites open a new `httpx.AsyncClient` on every invocation: `turn_handler._call_agent`, the whisper-back loop in `turn_handler.handle_turn`, `session_handler._call_ingest`, `live_session._post_turn_event`, and `live_session._post_session_close`. Under a 30-turn session this is 30+ connection setups with no reuse. Fix: share a single client (e.g. injected at app startup via FastAPI lifespan, or module-level singleton). Not currently causing visible failures; lower priority than BUG-01.

- [ ] **BUG-04 — router stock opener ignores user-supplied context** — confirmed in session 0185cc4f (2026-04-29): user opened with a complete context statement ("I'm doing some exploratory user testing right now. You're participating."); router fired the mandatory opener anyway. User called it out: "That seems like a stock starting phrase." Also observed in session 7e9bc99b (frame lock after opener). Fix: conditional opener — if the user's first turn already establishes context, acknowledge it and ask a clarifying question rather than defaulting to the standard opener. Behavioral contract change required.

- [ ] **BUG-05 — router produces unsolicited closings and summaries** — confirmed in session 0185cc4f (2026-04-29): router ended with "You can now terminate the session" (directive). Also observed in session 7e9bc99b: unprompted structured summary. Systematic behavioral gap. Fix: add a rule prohibiting summaries and directives; router's only closing move should be a question or a brief neutral acknowledgement.

- [ ] **BUG-06 — router denies whisper awareness when asked directly** — observed in session 0185cc4f (2026-04-29): user asked "you should be receiving whispers from a project manager agent, I think. Is that the case?"; router responded "Confirmation of external communication is beyond my scope." This is factually wrong and breaks trust. Behavioral contract instructs natural weaving of whispers but gives no guidance for direct questions about the mechanism. Fix: add a rule — when asked about external input or context, deflect naturally without denying the capability (e.g. "I'll work with whatever context arrives in the session").

- [x] **BUG-02 verification** — confirmed active in session 0185cc4f (2026-04-29, 13:23): no affirmations present. Affirmations in session 7e9bc99b (12:40) were pre-rebuild. Closed.

- [ ] **BUG-07 — duplicate assistant turns in transcript** — observed in session c20adebf (2026-04-29): two consecutive identical `A:` lines appear mid-transcript. Either a transcription bug (buffer flushed twice on `turn_complete`) or Gemini fired two `turn_complete` events for one turn. Investigate `_gemini_to_browser` in `live_session.py` — specifically whether `turn_complete` can fire twice for a single assistant turn.

- [ ] **BUG-08 — router persona has no human name** — flagged in session c20adebf (2026-04-29): user noted "router" is confusing for the conversational agent they're speaking with. *"I think of this router as the individual agent with whom I'm speaking right now... it should be named after some function of a person rather than some piece of hardware."* Requires a terminology audit across the codebase and a rename proposal for the router's voice persona. Separate from the service name (Router Service stays); this is about what the voice agent calls itself and how it is referred to in docs and the behavioral contract.

---

## Epic 4 — Expert Ecosystem

*More agents means more value. The PM agent is the highest-priority second agent based on three sessions of observed user friction. Each agent should be independently deployable and testable.*

- [ ] **E4-A** — in Now section above.

- [ ] **E4-B — Build: PM agent core** — implement whisper responses and session context awareness. Agent reads the backlog at startup, listens for bug/feature references during turns, and surfaces relevant items above confidence threshold.

  **Design notes from architecture review (2026-04-29):** (1) `goals` and `project_map` fields exist in every turn event payload but the browser client never populates them — they are always empty. The PM agent will need goals context; either the browser client must be extended to collect goals at session start, or the PM agent reads the backlog directly. (2) Whisper delivery is fire-and-forget with no retry — if the router session closes before a whisper arrives, it 404s silently. Acceptable for MVP but worth noting in the design.

- [ ] **E4-C — Build: PM agent backlog write + bug code resolution** — agent can draft new backlog items from session context and resolve spoken short codes to full entries. Depends on E4-B.

- [ ] **E4-D — Eval: PM agent quality** — labeled test cases for: correct item surfacing, correct item drafting, correct refusal (not surfacing irrelevant items). Feeds into E1 evalset.

- [ ] **E4-E — Design: agent routing improvements** — smarter orchestrator routing beyond broadcast-all; LLM-assisted relevance scoring so agents only receive turns relevant to their domain. Pre-work: `orchestrator/orchestrator/routing.py` contains a `select_expert` stub that raises `NotImplementedError` and is never called — the orchestrator currently broadcasts directly in `turn_handler.py`. Wire up or clearly tombstone the stub before building on it.

- [ ] **E4-F — Build: improved routing** — implement the routing design from E4-E.

---

## Epic 2 — Knowledge Layer

*The core value proposition: the system accumulates what it learns about your work and surfaces it at the right moment.*

- [ ] **E2-A — SPIKE: session knowledge extraction design** — time-boxed (2 days max). Deliverable: a written design doc covering extraction strategy, storage schema, and how knowledge differs from the existing wiki. Decision: extend the wiki model or build a separate store?

- [ ] **E2-B — SPIKE: knowledge retrieval strategy** — time-boxed (1 day max). Deliverable: written decision on retrieval approach (BM25, embedding, hybrid), injection point (session start only vs. per-turn), and latency budget. Informed by E2-A.

- [ ] **E2-C — Build: knowledge store** — persistent store for extracted session knowledge, keyed by project. Implement the schema from E2-A spike.

- [ ] **E2-D — Build: knowledge injection into session context** — surface relevant knowledge at session start and on turn events, using the retrieval strategy from E2-B spike.

- [ ] **E2-E — Eval: knowledge retrieval quality** — did the right knowledge surface? precision/recall for retrieval. Feeds into E1 evalset.

---

## Epic 1 — Evaluation Framework

*How we know the system is working and getting better.*

Note: the transcript labeling workflow (E1-C below) was previously blocked by UUID-only filenames. The transcript naming improvement (2026-04-29) unblocks it — files now include timestamp and topic slug.

- [ ] **E1-A — Design: expert selection evalset** — spec and schema for labeled conversation test cases (in progress)
- [ ] **E1-B — Build: evalset runner** — pytest-based evaluator that scores orchestrator routing decisions against labeled ground truth
- [ ] **E1-C — Tooling: human labeling workflow** — lightweight process for reviewing transcripts and adding labeled turns to the evalset
- [ ] **E1-D — CI: eval regression gate** — add evalset runner to GitHub Actions so routing regressions are caught automatically

---

## Epic 3 — Provider Independence

*Protect the ability to run fully locally and avoid deepening platform lock-in.*

- [ ] **E3-A — SPIKE: evaluate local voice alternatives** — time-boxed research into replacing Gemini Live API with a local model. Primary candidate: [Moshi](https://github.com/kyutai-labs/moshi) (Kyutai real-time speech-to-speech). Also evaluate modular approach (Whisper ASR + local LLM + local TTS). Deliverable: a short written assessment covering capability gap, hardware requirements, integration cost, and recommended abstraction boundary.
- [ ] **E3-B — Design: LLM/voice provider abstraction** — informed by the spike; define the interface boundary that lets the voice model be swapped without touching Router or Orchestrator logic. Note: expert agent wiki design currently names Gemini directly in whisper/ingest prompts — this abstraction should cover the expert agent LLM as well as the realtime voice conversation agent, so neither is hardcoded.
- [ ] **E3-C — Build: provider abstraction layer** — implement the boundary so Gemini Live and a local alternative can coexist behind the same interface.

---

## Epic 5 — Telephony

*The primary client per the system spec. Deferred until the knowledge layer is useful enough to justify a phone interface.*

- [ ] **E5-A — Design: telephony adapter** — provider-agnostic inbound audio WebSocket; first implementation candidate: Twilio
- [ ] **E5-B — Build: telephony adapter**
- [ ] **E5-C — Test: end-to-end voice call session**

---

## Epic 6 — Meta-tooling & Developer Experience

*Tooling for the developers building and debugging the system itself. Not user-facing features.*

- [ ] **E6-A — Skill + scripts: Gemini model availability lookup** — `docker-compose.yml` still defaults `DEV_COACH_MODEL=gemini-2.0-flash`; user is overriding via env. Default should be updated to the current working model string once confirmed. Claude's training knowledge of available Gemini model strings goes stale between releases. A lightweight skill + companion script should let Claude verify current model names before using them, without loading full API documentation. Script should call the Gemini models list endpoint and cache the result to a local file to minimise token cost on repeated use. Skill instructs Claude to run the script and check the cache before specifying any model string.

- [ ] **E6-F — Workflow: C4 diagram maintenance** — C4 diagrams (L1 context, L2 containers, L3 router service, L3 expert agent base) live in `docs/architecture/c4-diagrams.md`. Update them whenever a new service, container, or major component is added or removed. Trigger: any commit that touches `docker-compose.yml`, adds a new service directory, or significantly restructures an existing container's internals.

  **Open design question:** current diagrams use Mermaid's C4-specific syntax (`C4Context`, `C4Container`, `C4Component`) which requires Mermaid v9.4+ with C4 plugin support — not rendered by GitHub or standard VS Code Markdown preview. Two options: (a) rewrite as standard `flowchart` diagrams using subgraphs/node shapes to approximate C4 style — renders everywhere, loses strict C4 formalism; (b) keep C4 syntax and adopt a C4-aware renderer (e.g. Structurizr DSL or a VS Code C4/Mermaid plugin). Resolve before next diagram update.

- [ ] **E6-D — Feature: Router agent skill awareness** — the Router has no awareness of what tools and skills are available to Claude Code in the current session. User noted in session b9a16813 (2026-04-29) that the Router should be able to surface or reference newly added skills (e.g. `pm-skills`, `product-skills`) during a session. Design question: is this a behavioral contract addition, a session-start context injection, or a whisper from a meta-agent?

- [x] **E6-E — Build: log retrieval workflow** — delivered `scripts/dev-logs.sh` (2026-04-29). Pulls all three services, filters health checks, supports `-n` (lines), `-s` (single service), `-f` (follow), `-i` (session ID filter).

- [ ] **E6-C1 — SPIKE: debug mode design** — time-boxed (1 day). Resolve the open design questions: activation scope (logging only vs. agent swap vs. both), debug agent identity and context sources, session isolation strategy, passphrase management, reset behavior. Deliverable: written design decision.

  **Design note (session 0185cc4f, 2026-04-29):** user proposed a challenge/response passphrase pattern — e.g. router asks "how's the sky today" and the PM agent responds "orange is as orange does" — as a verification mechanism for agent context delivery. Could serve as both a debug activation trigger and a live integration test for the whisper pipeline.

- [ ] **E6-C2 — Build: debug mode activation + logging** — implement passphrase detection and verbose logging mode. No agent swap yet — this delivers the logging half independently.

- [ ] **E6-C3 — Build: debug agent** — implement the debug-aware agent loaded on passphrase activation, informed by the E6-C1 design. Depends on E6-C2.

---

## Epic 7 — Security & Scalability

*Explicitly deferred. Revisit when the system is working well for a single user and sharing it with others becomes relevant.*

- [ ] **E7-A — Authentication and session authorization**
- [ ] **E7-B — Rate limiting and abuse protection**
- [ ] **E7-C — Multi-user session isolation**
- [ ] **E7-D — Horizontal scaling of Router and Orchestrator services**
