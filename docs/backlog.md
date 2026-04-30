# Product Backlog

Items are ordered by priority within each epic. Epics are listed in priority order — reference codes are stable and do not imply epic ordering. Security and scalability are explicitly deferred until the system is working well for a single user. Local deployment is a long-term goal; provider independence is the path toward it.

---

## Now

- [x] **E6-G — Build: `/session-review` shorthand skill** — delivered (2026-04-30): `.claude/commands/session-review.md` chains `session-review.sh` with session-type detection (auto or explicit) and a modular analysis pipeline. New session types and analysis modules can be added by editing the registry table and module library sections in the command file.

- [ ] **E4-A — Design: PM agent** — define whisper contract, backlog integration spec, and evaluation criteria. Scope: backlog-aware, surfaces relevant open items during sessions, drafts and files new items on request, resolves spoken bug codes (e.g. "BUG-01") to full entries. Absorbs E6-B (easy bug referencing) — that feature is delivered by this agent, not a standalone tool.

  **Urgency confirmed** (session c4822cff, 2026-04-29): user ended session early because the router lacked backlog context. This is a productivity blocker, not a UX improvement.

  **Open design question (session c4822cff):** real-time injection (agent whispers on every relevant turn) vs. summary-based approach (backlog digest injected at session start). Tradeoffs: real-time has higher latency cost per turn; summary-based risks stale context mid-session. Note: a summary-based approach bypasses the whisper timeout problem (BUG-01 tail) for this agent entirely.

  **Design question partially resolved (session 8d775b26, 2026-04-29):** backlog-at-session-start is now proven — the router correctly cited E6-C1 and E6-C2 by code in response to a natural reference. This validates the summary-based approach for the PM agent. Real-time whispers from the PM agent remain valuable for surfacing items mid-session, but session-start injection is the confirmed baseline.

---

## Known Bugs

- [x] **BUG-00 — voice interruption broken** — confirmed fixed in session f1f1fdda (2026-04-29).
- [x] **BUG-01** — **fixed** (2026-04-29, session c20adebf): async callback pattern eliminated all timeouts. 11 turns, zero `ReadTimeout` errors, 7 of 10 whispers delivered. Two late callbacks arrived post-close (404) — expected behavior of async pattern. See commit f3a1dbf.
- [x] **BUG-02 — router refuses to relay context to whisper agents** — fixed (2026-04-29): updated `behavioral_contract.py` to carve out in-session agent relay as facilitation and added tone directive prohibiting affirmations. 30 tests passing.
- [ ] **BUG-03 — httpx client created per call (no connection pooling)** — identified in architecture review (2026-04-29). Five sites: `turn_handler._call_agent`, whisper-back loop in `turn_handler.handle_turn`, `session_handler._call_ingest`, `live_session._post_turn_event`, `live_session._post_session_close`. Fix is mechanical — share a single client via FastAPI lifespan. Not causing visible failures. **Explicitly deferred** — schedule as a warmup task when other Now items are clear; do not let it accumulate further.

- [x] **BUG-04 — router stock opener ignores user-supplied context** — confirmed fixed in session 8d775b26 (2026-04-29). Originally confirmed in session 0185cc4f (2026-04-29): user opened with a complete context statement ("I'm doing some exploratory user testing right now. You're participating."); router fired the mandatory opener anyway. User called it out: "That seems like a stock starting phrase." Also observed in session 7e9bc99b (frame lock after opener). Fix: conditional opener — if the user's first turn already establishes context, acknowledge it and ask a clarifying question rather than defaulting to the standard opener. Behavioral contract change required.

- [x] **BUG-05 — router produces unsolicited closings and summaries** — fixed (2026-04-30, commit 93a1d80): added explicit closing-question prohibition to behavioral contract ("NEVER ask closing questions such as 'Is there anything else?'…"). Confirmed pattern was still present in most-recent transcript before fix ("Is there anything else you need to clarify during this debugging session?"). BUG-07 fragmentation was amplifying the closing pattern; both are now resolved.

- [x] **BUG-06 — router denies whisper awareness when asked directly** — **confirmed fixed** in session 8d775b26 (2026-04-29): router responded "I will work with whatever context arrives in the session." — natural deflection, no denial. Commit 743db2b.

- [x] **BUG-02 verification** — confirmed active in session 0185cc4f (2026-04-29, 13:23): no affirmations present. Affirmations in session 7e9bc99b (12:40) were pre-rebuild. Closed.

- [x] **BUG-07 — duplicate/fragmented assistant turns in transcript** — fixed (2026-04-29, commit efd7aac). Root cause: Gemini Live API emits multiple consecutive `turn_complete` events per logical response. Fix: `_flush_output_buf()` coalesces into any trailing `"Assistant:"` entry. **Separator fix applied** (commit 3be9329): run-on joins like `?Are` now get a space inserted — confirmed effective in session 6275d9ca (no run-ons of that form). **Primary fragmentation root cause identified and fixed (2026-04-29, session d954dfad RCA):** `[Whisper from ...]` history entries appended by `_whisper_drain` between two consecutive assistant `turn_complete` events caused `_flush_output_buf()` to fail its coalesce check (`history[-1].startswith("Assistant:")` returned False), creating a new `"Assistant:"` entry instead of coalescing. Fix: scan backward past whisper entries before checking for a trailing assistant entry. 14 tests passing. **Remaining known fragmentation:** after a Gemini-interrupted continuation, the resumed response starts mid-sentence — this is Gemini API behavior, not fixable in the client.

- [x] **BUG-10 — router vocalizes whisper content** — confirmed in session d5920363 (2026-04-29): router spoke `[WHISPER from insight_engine]: The current debug mode is still in design...` verbatim, including the injection prefix. **Confirmed again with multiple instances in session 6275d9ca (2026-04-29):** router answered DevCoach whispers directly and partially read a raw injection prefix aloud. Root cause: `send_realtime_input(text=...)` is the VAD user-turn channel — Gemini treats any text sent there as a user utterance and immediately generates an audio response. **Fix applied (2026-04-29, commit 7f650e7):** switched injection to `send_client_content(turns=..., turn_complete=False)`. Behavioral contract updated with explicit prohibition on speaking, repeating, or acknowledging whisper content. **Validation session 0722db0e (2026-04-29):** user did not hear any whisper vocalization — audio side appears fixed. However, transcript shows a suspicious `Assistant: [WHISPER from dev_coach]: ...` entry (note: source capitalisation `dev_coach` differs from injected `DevCoach`, suggesting transcription of injected input rather than synthesized speech). Working hypothesis: `send_client_content(turn_complete=False)` suppresses audio but causes Gemini to emit spurious `output_transcription` events for the injected content, which our code records as `"Assistant:"` transcript entries — polluting the transcript without audio. **Next step (first task of next session):** run with `LOG_LEVEL=DEBUG` and check whether `response.data` (audio bytes) accompanied the suspicious turn in session 0722db0e or a fresh equivalent. If no audio bytes, BUG-10 audio is confirmed fixed and the transcript pollution is a separate issue to address. If audio bytes were present, the fix is ineffective and Option B (buffer at orchestrator boundary) must be evaluated.

- [x] **BUG-11 — multiple ingest calls per session** — fixed (2026-04-30, commit 4e0d2a7): root cause was `session-review.sh` counting ingest calls across the entire log tail rather than filtering to the specific session. Added `_ingested_sessions` idempotency set to `session_handler.py` (belt-and-suspenders guard) and fixed the script metric to filter by `session=$short_id`.

- [x] **BUG-09 — router overstates PM agent capability** — fixed (2026-04-30, commit 93a1d80): removed PM relay phrasing from behavioral contract. Router now uses first-person transcript framing only: "I'll note that in the transcript." No reference to passing items to any downstream agent or system.

- [x] **BUG-08 — router persona has no human name** — fixed (2026-04-30, commit 93a1d80): voice agent is named Kai. Behavioral contract updated with identity block: "Your name is Kai. If someone asks your name, say 'Kai' and continue. Never refer to yourself as 'the router' in conversation." Service name (Router Service) unchanged.

---

## Epic 4 — Expert Ecosystem

*More agents means more value. The PM agent is the highest-priority second agent based on three sessions of observed user friction. Each agent should be independently deployable and testable.*

- [ ] **E4-A** — in Now section above.

- [ ] **E4-B — Build: PM agent core** — implement whisper responses and session context awareness. Agent reads the backlog at startup, listens for bug/feature references during turns, and surfaces relevant items above confidence threshold.

  **Design constraint (session 6275d9ca, 2026-04-29):** at high whisper volume (24 acks in 28 turns), delivery rate dropped to 37.5% — whispers queued faster than they could be injected. The PM agent must throttle or batch whispers rather than firing on every relevant turn. Consider a minimum inter-whisper gap or a turn-budget cap per session.

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

  **Open design question:** current diagrams use Mermaid's C4-specific syntax (`C4Context`, `C4Container`, `C4Component`) which requires Mermaid v9.4+ with C4 plugin support — not rendered by GitHub or standard VS Code Markdown preview. Three options: (a) rewrite as standard `flowchart` diagrams using subgraphs/node shapes to approximate C4 style — renders everywhere, loses strict C4 formalism; (b) keep C4 syntax and adopt a C4-aware renderer (e.g. Structurizr DSL or a VS Code C4/Mermaid plugin); (c) intermediate conversion layer — render Mermaid C4 diagrams to PNG at build/doc-generation time and embed static images in README/wiki — avoids renderer dependency but images go stale if diagrams aren't regenerated. Resolve before next diagram update.

- [ ] **E6-D — Feature: Router agent skill awareness** — the Router has no awareness of what tools and skills are available to Claude Code in the current session. User noted in session b9a16813 (2026-04-29) that the Router should be able to surface or reference newly added skills (e.g. `pm-skills`, `product-skills`) during a session. Design question: is this a behavioral contract addition, a session-start context injection, or a whisper from a meta-agent?

- [x] **E6-E — Build: log retrieval workflow** — delivered `scripts/dev-logs.sh` (2026-04-29). Pulls all three services, filters health checks, supports `-n` (lines), `-s` (single service), `-f` (follow), `-i` (session ID filter).

- [x] **E6-G — Skill: `/session-review` shorthand** — delivered (2026-04-30): see Now section entry for details.

- [ ] **E6-H — Design: epic naming conventions for developer recall** — user finds current codes + nature-descriptions adequate for orientation but struggles to recall codes from memory mid-session, defaulting to describing epic content instead. Scope: evaluate naming conventions (mnemonic codes, short aliases, or descriptive slugs) that improve unaided recall. The PM agent design (E4-A) should factor in this cognitive style — surfacing items by description match as well as by code. May be fully absorbed into E4-A scope; evaluate at design time.

- [ ] **E6-C1 — SPIKE: debug mode design** — time-boxed (1 day). Resolve the open design questions: activation scope (logging only vs. agent swap vs. both), debug agent identity and context sources, session isolation strategy, passphrase management, reset behavior. Deliverable: written design decision.

  **Design note (session 0185cc4f, 2026-04-29):** user proposed a challenge/response passphrase pattern — e.g. router asks "how's the sky today" and the PM agent responds "orange is as orange does" — as a verification mechanism for agent context delivery. Could serve as both a debug activation trigger and a live integration test for the whisper pipeline.

- [ ] **E6-I — Investigate: `insight_engine` agent origin** — an `insight_engine` whisper appeared in session d5920363 (2026-04-29) but `dev-coach` is the only registered agent in `agents.yaml`. Source unknown — could be a stale container, a misconfigured registry entry, or a Gemini artifact. Check `orchestrator/orchestrator/agents.yaml` and confirm only intended agents are active before next session.

- [ ] **E6-J — Docs: enable `LOG_LEVEL=DEBUG` for BUG-07 investigation** — commit 3be9329 added debug-level event-sequence logging to `live_session.py` to diagnose late-arriving `output_transcription` chunks. To activate: set `LOG_LEVEL=DEBUG` on the `router-service` container (env var in `docker-compose.yml` or shell export before `docker compose up`). Document this in a comment in `docker-compose.yml` so it's findable without a transcript review.

- [ ] **E6-C2 — Build: debug mode activation + logging** — implement passphrase detection and verbose logging mode. No agent swap yet — this delivers the logging half independently.

- [ ] **E6-C3 — Build: debug agent** — implement the debug-aware agent loaded on passphrase activation, informed by the E6-C1 design. Depends on E6-C2.

---

## Epic 7 — Security & Scalability

*Explicitly deferred. Revisit when the system is working well for a single user and sharing it with others becomes relevant.*

**Risk note (session 15383d0b, 2026-04-29):** user explicitly flagged that security should be built in from the beginning, not retrofitted. Before deferral becomes a blocker, conduct an adequacy assessment: how hard will it be to add authentication, session isolation, and rate limiting to the current architecture? The answer should inform whether Epic 7 stays deferred or gets pulled earlier. Do not let this note age without a deliberate decision.

- [ ] **E7-A — Authentication and session authorization**
- [ ] **E7-B — Rate limiting and abuse protection**
- [ ] **E7-C — Multi-user session isolation**
- [ ] **E7-D — Horizontal scaling of Router and Orchestrator services**
