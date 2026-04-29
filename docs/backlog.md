# Product Backlog

Items are ordered by priority within each epic. Epics are listed in priority order — reference codes are stable and do not imply epic ordering. Security and scalability are explicitly deferred until the system is working well for a single user. Local deployment is a long-term goal; provider independence is the path toward it.

---

## Now

Two items are immediately actionable and independent — they can be worked in parallel.

- [ ] **BUG-01 — orchestrator ↔ dev-coach connectivity errors** — partially fixed (2026-04-29). Pipeline is now unblocked: BackgroundTasks fix confirmed working, whispers reaching dev-coach for first time (3× `POST /whisper 204` in live session). However, 2 of 5 turns still produced `Agent DevCoach error [ReadTimeout]` — Gemini API calls inside dev-coach occasionally exceed the 15s ceiling. Root fix is correct; timeout needs further tuning. Whisper-back timeout (orchestrator → router) also raised 2s → 5s (2026-04-29).

  **Remaining work:** raise `agent_timeout_seconds` to 30s (or higher) in `agents.yaml` and `docker-compose.yml`, or add a fast-path in dev-coach that returns low-confidence immediately if generation is slow (prevents blocking the whisper slot). Re-test with a full session.

  **Done when:** a complete session produces no `Agent DevCoach error` log lines, and at least one whisper is delivered to the router.

- [x] **BUG-02 — router refuses to relay context to whisper agents** — fixed (2026-04-29): updated `behavioral_contract.py` to explicitly carve out in-session agent relay as facilitation (not an external action), and added a standing tone directive prohibiting affirmations and ego-bolstering phrases. 30 tests passing.

---

## Known Bugs

- [x] **BUG-00 — voice interruption broken** — confirmed fixed in session f1f1fdda (2026-04-29).
- [ ] **BUG-01** — partially fixed; see Now section above.
- [x] **BUG-02** — see Now section above.
- [ ] **BUG-03 — httpx client created per call (no connection pooling)** — identified in architecture review (2026-04-29). Five sites open a new `httpx.AsyncClient` on every invocation: `turn_handler._call_agent`, the whisper-back loop in `turn_handler.handle_turn`, `session_handler._call_ingest`, `live_session._post_turn_event`, and `live_session._post_session_close`. Under a 30-turn session this is 30+ connection setups with no reuse. Fix: share a single client (e.g. injected at app startup via FastAPI lifespan, or module-level singleton). Not currently causing visible failures; lower priority than BUG-01.

---

## Epic 4 — Expert Ecosystem

*More agents means more value. The PM agent is the highest-priority second agent based on three sessions of observed user friction. Each agent should be independently deployable and testable.*

- [ ] **E4-A — Design: PM agent** — define whisper contract, backlog integration spec, and evaluation criteria. Scope: backlog-aware, surfaces relevant open items during sessions, drafts and files new items on request, resolves spoken bug codes (e.g. "BUG-01") to full entries. Absorbs E6-B (easy bug referencing) — that feature is delivered by this agent, not a standalone tool.

  **Urgency confirmed** (session c4822cff, 2026-04-29): user ended session early because the router lacked backlog context. This is a productivity blocker, not a UX improvement.

  **Open design question (session c4822cff):** real-time injection (agent whispers on every relevant turn) vs. summary-based approach (backlog digest injected at session start). Tradeoffs: real-time has higher latency cost per turn; summary-based risks stale context mid-session.

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

- [ ] **E6-A — Skill + scripts: Gemini model availability lookup** — Note: `docker-compose.yml` still defaults `DEV_COACH_MODEL=gemini-2.0-flash`; user is overriding via env. Default should be updated to the current working model string once confirmed. — Claude's training knowledge of available Gemini model strings goes stale between releases. A lightweight skill + companion script should let Claude verify current model names before using them, without loading full API documentation. Script should call the Gemini models list endpoint and cache the result to a local file to minimise token cost on repeated use. Skill instructs Claude to run the script and check the cache before specifying any model string.

- [ ] **E6-D — Feature: Router agent skill awareness** — the Router has no awareness of what tools and skills are available to Claude Code in the current session. User noted in session b9a16813 (2026-04-29) that the Router should be able to surface or reference newly added skills (e.g. `pm-skills`, `product-skills`) during a session. Design question: is this a behavioral contract addition, a session-start context injection, or a whisper from a meta-agent?

- [x] **E6-E — Build: log retrieval workflow** — delivered `scripts/dev-logs.sh` (2026-04-29). Pulls all three services, filters health checks, supports `-n` (lines), `-s` (single service), `-f` (follow), `-i` (session ID filter).

- [ ] **E6-C1 — SPIKE: debug mode design** — time-boxed (1 day). Resolve the open design questions: activation scope (logging only vs. agent swap vs. both), debug agent identity and context sources, session isolation strategy, passphrase management, reset behavior. Deliverable: written design decision.

- [ ] **E6-C2 — Build: debug mode activation + logging** — implement passphrase detection and verbose logging mode. No agent swap yet — this delivers the logging half independently.

- [ ] **E6-C3 — Build: debug agent** — implement the debug-aware agent loaded on passphrase activation, informed by the E6-C1 design. Depends on E6-C2.

- [ ] **E6-F — Workflow: C4 diagram maintenance** — C4 diagrams (L1 context, L2 containers, L3 router service, L3 expert agent base) live in `docs/architecture/c4-diagrams.md`. Update them whenever a new service, container, or major component is added or removed. Trigger: any commit that touches `docker-compose.yml`, adds a new service directory, or significantly restructures an existing container's internals. No tooling required — diagrams are hand-authored Mermaid; the `engineering-skills:senior-architect` skill's diagram generator can assist but its auto-detection is coarse and the C4 output should be reviewed manually.

---

## Epic 7 — Security & Scalability

*Explicitly deferred. Revisit when the system is working well for a single user and sharing it with others becomes relevant.*

- [ ] **E7-A — Authentication and session authorization**
- [ ] **E7-B — Rate limiting and abuse protection**
- [ ] **E7-C — Multi-user session isolation**
- [ ] **E7-D — Horizontal scaling of Router and Orchestrator services**
