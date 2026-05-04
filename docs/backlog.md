# Product Backlog

Items are ordered by priority within each epic. Epics are listed in priority order — reference codes are stable and do not imply epic ordering. Security and scalability are explicitly deferred until the system is working well for a single user. Local deployment is a long-term goal; provider independence is the path toward it.

---

## Now

*Core Stability Milestone: Prioritize resolving transcript pollution, routing inefficiency, and prompt contradictions before adding heavy async agents.*

- [x] **BUG-23 — Assistant stopped responding (suspected BUG-22 regression)** — fixed (2026-05-04) via static analysis: after an interrupted event, _output_buf is flushed immediately. A subsequent assistant turn_complete with empty _output_buf was unconditionally clearing _model_generating, blocking _whisper_drain for the next real user turn. Fix: check had_output before the flush; only clear _model_generating when the assistant turn actually produced output. Could not reproduce live (would have required LOG_LEVEL=DEBUG session), but root cause is architecturally sound and covered by regression test.

- [x] **BUG-22 — Fix transcript turn ordering inversion** — fixed (2026-05-04): race condition in `live_session.py` — when Gemini begins emitting `output_transcription` (assistant response) before the user's `turn_complete` fires, `_flush_output_buf()` was called before the user turn was appended to `_history`, producing inverted order. Fix: record user turn first in both the `turn_complete` handler and `close()`. Also added immediate flush in the `interrupted` handler so stale partial output never survives into a later user turn. Two regression tests added. Root cause confirmed by static analysis session 1f89e5e2 (2026-05-04).

- [x] **BUG-12 — Fix transcript pollution from whisper injections** — fixed (2026-05-03): `_gemini_to_browser` now filters `output_transcription` events whose text starts with `[WHISPER from` — these are Gemini echoing the `send_client_content` injection back as transcription. Filtered events are dropped before reaching `_output_buf` or the browser transcript feed.

- [x] **BUG-13 — Fix router opening with fallback phrase** — fixed (2026-05-03): `send_realtime_input(text=...)` was already removed from `connect()` (test `test_connect_opens_gemini_session_without_context_injection` confirms). Added explicit "do not generate audio proactively at session start" instruction to `behavioral_contract.py` to prevent Gemini interpreting the session-opener rule as a proactive greeting.

- [x] **BUG-15 — Fix prompt contradiction on whisper handling** — fixed (2026-05-03): updated `behavioral_contract.py` whisper section to say "use the insight to ask a more targeted or informed question — let the whisper guide where you probe next, not what you say." Updated `transcripts.py` ground-truth fixture to show silent incorporation (not relay) and corrected `REQUIRED_BEHAVIORS` description.

- [ ] **E4-E — Design: agent routing improvements (Fix Fan-Out Problem)** — Smarter orchestrator routing beyond broadcast-all. The orchestrator currently POSTs to every agent on every turn, which will not scale. Wire up the `select_expert` stub before adding more agents.

- [x] **BUG-03 — Fix httpx client created per call (Connection pooling)** — fixed (2026-05-03): `httpx.AsyncClient()` moved to `LiveSession.__init__` as `self._http_client`; closed via `aclose()` at the end of `close()`. Both `_post_turn_event` and `_post_session_close` now reuse the session-scoped client — no per-call socket churn.

- [x] **E6-G — Build: `/session-review` shorthand skill** — delivered (2026-04-30): `.claude/commands/session-review.md` chains `session-review.sh` with session-type detection (auto or explicit) and a modular analysis pipeline. New session types and analysis modules can be added by editing the registry table and module library sections in the command file.

---

## Known Bugs

- [x] **BUG-00 — voice interruption broken** — confirmed fixed in session f1f1fdda (2026-04-29).
- [x] **BUG-01** — **fixed** (2026-04-29, session c20adebf): async callback pattern eliminated all timeouts. 11 turns, zero `ReadTimeout` errors, 7 of 10 whispers delivered. Two late callbacks arrived post-close (404) — expected behavior of async pattern. See commit f3a1dbf.
- [x] **BUG-02 — router refuses to relay context to whisper agents** — fixed (2026-04-29): updated `behavioral_contract.py` to carve out in-session agent relay as facilitation and added tone directive prohibiting affirmations. 30 tests passing.
- [x] **BUG-03** — Fixed. See Now section.

- [x] **BUG-04 — router stock opener ignores user-supplied context** — confirmed fixed in session 8d775b26 (2026-04-29). Originally confirmed in session 0185cc4f (2026-04-29): user opened with a complete context statement ("I'm doing some exploratory user testing right now. You're participating."); router fired the mandatory opener anyway. User called it out: "That seems like a stock starting phrase." Also observed in session 7e9bc99b (frame lock after opener). Fix: conditional opener — if the user's first turn already establishes context, acknowledge it and ask a clarifying question rather than defaulting to the standard opener. Behavioral contract change required.

- [x] **BUG-05 — router produces unsolicited closings and summaries** — fixed (2026-04-30, commit 93a1d80): added explicit closing-question prohibition to behavioral contract ("NEVER ask closing questions such as 'Is there anything else?'…"). Confirmed pattern was still present in most-recent transcript before fix ("Is there anything else you need to clarify during this debugging session?"). BUG-07 fragmentation was amplifying the closing pattern; both are now resolved.

- [x] **BUG-06 — router denies whisper awareness when asked directly** — **confirmed fixed** in session 8d775b26 (2026-04-29): router responded "I will work with whatever context arrives in the session." — natural deflection, no denial. Commit 743db2b.

- [x] **BUG-02 verification** — confirmed active in session 0185cc4f (2026-04-29, 13:23): no affirmations present. Affirmations in session 7e9bc99b (12:40) were pre-rebuild. Closed.

- [x] **BUG-07 — duplicate/fragmented assistant turns in transcript** — fixed (2026-04-29, commit efd7aac). Root cause: Gemini Live API emits multiple consecutive `turn_complete` events per logical response. Fix: `_flush_output_buf()` coalesces into any trailing `"Assistant:"` entry. **Separator fix applied** (commit 3be9329): run-on joins like `?Are` now get a space inserted — confirmed effective in session 6275d9ca (no run-ons of that form). **Primary fragmentation root cause identified and fixed (2026-04-29, session d954dfad RCA):** `[Whisper from ...]` history entries appended by `_whisper_drain` between two consecutive assistant `turn_complete` events caused `_flush_output_buf()` to fail its coalesce check (`history[-1].startswith("Assistant:")` returned False), creating a new `"Assistant:"` entry instead of coalescing. Fix: scan backward past whisper entries before checking for a trailing assistant entry. 14 tests passing. **Remaining known fragmentation:** after a Gemini-interrupted continuation, the resumed response starts mid-sentence — this is Gemini API behavior, not fixable in the client.

- [x] **BUG-10 — router vocalizes whisper content** — confirmed in session d5920363 (2026-04-29): router spoke `[WHISPER from insight_engine]: The current debug mode is still in design...` verbatim, including the injection prefix. **Confirmed again with multiple instances in session 6275d9ca (2026-04-29):** router answered DevCoach whispers directly and partially read a raw injection prefix aloud. Root cause: `send_realtime_input(text=...)` is the VAD user-turn channel — Gemini treats any text sent there as a user utterance and immediately generates an audio response. **Fix applied (2026-04-29, commit 7f650e7):** switched injection to `send_client_content(turns=..., turn_complete=False)`. Behavioral contract updated with explicit prohibition on speaking, repeating, or acknowledging whisper content. **Validation session 0722db0e (2026-04-29):** user did not hear any whisper vocalization — audio side appears fixed. However, transcript shows a suspicious `Assistant: [WHISPER from dev_coach]: ...` entry (note: source capitalisation `dev_coach` differs from injected `DevCoach`, suggesting transcription of injected input rather than synthesized speech). Working hypothesis: `send_client_content(turn_complete=False)` suppresses audio but causes Gemini to emit spurious `output_transcription` events for the injected content, which our code records as `"Assistant:"` transcript entries — polluting the transcript without audio. **Next step (first task of next session):** run with `LOG_LEVEL=DEBUG` and check whether `response.data` (audio bytes) accompanied the suspicious turn in session 0722db0e or a fresh equivalent. If no audio bytes, BUG-10 audio is confirmed fixed and the transcript pollution is a separate issue to address. If audio bytes were present, the fix is ineffective and Option B (buffer at orchestrator boundary) must be evaluated.

- [ ] **BUG-12** — Moved to Now section.

- [ ] **BUG-13** — Moved to Now section.

- [x] **BUG-14 — whisper delivery metric reported 0% (false negative)** — fixed (2026-04-30): two root causes, neither was a real delivery failure. (1) `session-review.sh` used `--tail=200` on the combined container log stream; with debug-level logging active, the router-service debug lines dominated the tail and pushed turn/whisper lines beyond the window — `session_logs` was effectively empty. Fix: pull the full log stream (no tail) and derive `session_logs` via session-id grep. (2) The orchestrator had no `logging.basicConfig()` — `logger.info()` calls in `session_handler.py` were silently dropped by Python's default WARNING-level root handler. The ingest success log never reached stdout. Fix: added `logging.basicConfig` + `LOG_LEVEL` env var support to `orchestrator/main.py`. Actual delivery for session a23a2089: 5 successful callbacks (200 OK), 2 post-close 404s (expected), 1 NO_WHISPER. Orchestrator logging fix takes effect on next container restart.

- [x] **BUG-11 — multiple ingest calls per session** — fixed (2026-04-30, commit 4e0d2a7): root cause was `session-review.sh` counting ingest calls across the entire log tail rather than filtering to the specific session. Added `_ingested_sessions` idempotency set to `session_handler.py` (belt-and-suspenders guard) and fixed the script metric to filter by `session=$short_id`.

- [x] **BUG-09 — router overstates PM agent capability** — fixed (2026-04-30, commit 93a1d80): removed PM relay phrasing from behavioral contract. Router now uses first-person transcript framing only: "I'll note that in the transcript." No reference to passing items to any downstream agent or system.

- [x] **BUG-08 — router persona has no human name** — fixed (2026-04-30, commit 93a1d80): voice agent is named Kai. Behavioral contract updated with identity block: "Your name is Kai. If someone asks your name, say 'Kai' and continue. Never refer to yourself as 'the router' in conversation." Service name (Router Service) unchanged.

- [x] **BUG-16 — router says "I'll note that in the transcript"** — fixed (2026-05-04): behavioral contract updated to either silently acknowledge or ask a clarifying follow-up question — no longer announces what it is recording.

- [x] **BUG-17 — DevCoach whisper loop** — fixed (2026-05-04): two-layer deduplication — (1) prompt-side: last 5 session whispers injected as "do not repeat these" context; (2) Jaccard word-overlap filter (threshold 0.7) suppresses near-duplicates as a client-side backstop. Session history tracked per session_id, capped at 10 entries.

- [x] **BUG-18 — router surfaces internal backlog codes in user-facing speech** — fixed (2026-05-04): behavioral contract now explicitly prohibits all internal backlog/epic codes in spoken responses; Kai must describe work items by meaning, not identifier.

- [x] **BUG-19 — insight_engine transcript pollution active** — fixed (2026-05-04): root cause traced (E6-I resolved): insight_engine is not a registered agent; the pollution came from Gemini splitting the whisper echo across multiple output_transcription chunks. BUG-12's filter only caught the first chunk (starting with "[WHISPER from"). Fixed via _in_whisper_echo state flag that suppresses all continuation chunks until turn_complete.

- [x] **BUG-20 — router affirmation pattern persists** — fixed (2026-05-04): behavioral contract now has an explicit NEVER directive covering structural patterns like "adding X makes sense", "makes sense", "absolutely", "that's a good idea" — not just the specific phrases listed before.

- [ ] **BUG-21 — whisper delivery rate dropped to 37.5%** — session 1f89e5e2 (2026-05-04) recorded 24 acks but only 9 deliveries (37.5%), down from 91.7% the prior session; 15 acknowledged dispatches had no delivery callback. **Update (session 7a263bea, 2026-05-04):** delivery was 16/16 (100%) in a 16-turn session — may be load-related or incidentally fixed by BUG-03 connection pooling. Needs a longer session (24+ turns) to confirm resolution before closing.

---

## Epic 4 — Expert Ecosystem

*Multiple agents with distinct behaviors give the routing layer something real to optimize. Each agent is independently deployable and testable.*

- [~] **E4-A — Design: PM agent** — won't-do (2026-04-30): dev-coach is covering the backlog-context use case adequately. A dedicated PM agent is not justified at current scale for a single-user system.

- [~] **E4-B — Build: PM agent core** — won't-do (2026-04-30): blocked on E4-A; closed with it.

- [~] **E4-C — Build: PM agent backlog write + bug code resolution** — won't-do (2026-04-30): closed with PM agent chain.

- [~] **E4-D — Eval: PM agent quality** — won't-do (2026-04-30): closed with PM agent chain.

- [x] **E4-H — Design: researcher agent** — delivered (2026-05-04): design doc at `docs/specs/researcher-agent-design.md`. Covers async background research (autonomous + explicit trigger modes), findings persistence in agent wiki, whisper delivery of relevant excerpts. Both trigger modes instrumented for evaluation. See E4-I/J/K for build items.

- [ ] **E4-I — Build: researcher agent core** — implement `/ingest` endpoint: extract research topics from transcript (autonomous inference + explicit instruction detection), tag trigger mode, spawn async Gemini Deep Research tasks, track task status (queued / in-progress / complete), write findings and gaps to agent wiki on completion. Depends on E4-H design.

- [ ] **E4-J — Build: researcher agent whisper** — implement `/whisper` endpoint: score wiki against current turn context, return most relevant research excerpt. If a relevant task is in-progress, whisper a brief status note. Depends on E4-I.

- [ ] **E4-K — Eval: autonomous vs. instructed research mode** — compare trigger modes across sessions: relevance of autonomously-inferred topics vs. explicitly requested ones, whisper acceptance rate, user follow-up rate. Feeds into E1 evalset.

- [x] **E4-L — Build: `/synthesize` endpoint on ExpertAgentBase** — delivered (2026-05-04): `POST /synthesize` added to base ABC with default Karpathy-style implementation (wiki compression, ingest log awareness). DevCoach overrides with roadmap-aware synthesis via `ROADMAP_PATH` env var. Agents without an override get the default. Absorbed E4-G.

- [ ] **BUG-24 — DevCoach whispers reference hallucinated personas and invented patterns** — session 7a263bea (2026-05-04): DevCoach suggested "addressing the Project Manager persona", using "Live Timestamp Isolation", "Logging Extraction", "Validation Passphrase", and "Bug Validation Patterns wiki" — none of which exist in the project. Root cause likely: `ROADMAP_PATH` was not wired in `docker-compose.yml`, so E4-M ran with no backlog context and the model filled the void with hallucinated patterns. Fix: mount backlog and set `ROADMAP_PATH` in dev-coach service config; verify whisper quality in next session.

- [ ] **BUG-25 — Router spoke before user's first turn (session opener regression)** — transcript 7a263bea (2026-05-04) shows `A: Which project or domain` preceding the user's first `Hi, I'm verifying...` line. Either the BUG-13 fix was not deployed (containers running old code) or the fix is incomplete for this opener path. Verify after container rebuild; if it persists, re-examine behavioral contract session opener rule.

- [ ] **E4-E** — Moved to Now section (Fan-Out Problem fix).

- [ ] **E4-F — Build: improved routing** — implement the routing design from E4-E.

- [~] **E4-G — Feature: startup synthesis for expert agents** — absorbed into E4-L (`/synthesize` endpoint on ExpertAgentBase). Closed.

- [x] **E4-M — Feature: dev-coach roadmap awareness** — delivered (2026-05-04): DevCoach loads `ROADMAP_PATH` at startup and injects the backlog snapshot into both the whisper prompt and the synthesis override. Roadmap-aware synthesis deduces stale vs. active entries against current epic/milestone state.

---

## Epic 2 — Knowledge Layer

*The core value proposition: the system accumulates what it learns about your work and surfaces it at the right moment.*

- [ ] **E2-A — SPIKE: session knowledge extraction design** — time-boxed (2 days max). Deliverable: a written design doc covering extraction strategy, storage schema, and how knowledge differs from the existing wiki. Decision: extend the wiki model or build a separate store?

- [ ] **E2-B — SPIKE: knowledge retrieval strategy** — time-boxed (1 day max). Deliverable: written decision on retrieval approach (BM25, embedding, hybrid), injection point (session start only vs. per-turn), and latency budget. Informed by E2-A.

- [ ] **E2-C — Build: knowledge store** — persistent store for extracted session knowledge, keyed by project. Implement the schema from E2-A spike.

- [ ] **E2-D — Build: knowledge injection into session context** — surface relevant knowledge at session start and on turn events, using the retrieval strategy from E2-B spike.

- [ ] **E2-E — Eval: knowledge retrieval quality** — did the right knowledge surface? precision/recall for retrieval. Feeds into E1 evalset.

- [ ] **E2-F — Design: multi-domain backlog support** — user wants to manage multiple independent project domains each with its own backlog; current system is hardcoded to the gcsb project; scope: domain registration, per-domain knowledge stores, and routing context scoped to the active domain. First stated in session 1f89e5e2 (2026-05-04).

---

## Epic 1 — Evaluation Framework

*How we know the system is working and getting better.*

Note: the transcript labeling workflow (E1-C below) was previously blocked by UUID-only filenames. The transcript naming improvement (2026-04-29) unblocks it — files now include timestamp and topic slug.

- [x] **E1-A — Design: expert selection evalset** — delivered (2026-05-04): spec and schema at `docs/specs/evalset-schema-design.md`.
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

- [ ] **E6-H — Design: epic naming conventions for developer recall** — user finds current codes + nature-descriptions adequate for orientation but struggles to recall codes from memory mid-session, defaulting to describing epic content instead. Scope: evaluate naming conventions (mnemonic codes, short aliases, or descriptive slugs) that improve unaided recall. The PM agent design (E4-A) should factor in this cognitive style — surfacing items by description match as well as by code. May be fully absorbed into E4-A scope; evaluate at design time. **Session 1f89e5e2 (2026-05-04) adds a specific behavioral requirement:** when asked for a status report, the router should ask which project/domain the user means before reporting — add this discovery-first pattern explicitly to the behavioral contract rather than leaving it implicit in naming-convention scope.

- [ ] **E6-C1 — SPIKE: debug mode design** — time-boxed (1 day). Resolve the open design questions: activation scope (logging only vs. agent swap vs. both), debug agent identity and context sources, session isolation strategy, passphrase management, reset behavior. Deliverable: written design decision.

  **Design note (session 0185cc4f, 2026-04-29):** user proposed a challenge/response passphrase pattern — e.g. router asks "how's the sky today" and the PM agent responds "orange is as orange does" — as a verification mechanism for agent context delivery. Could serve as both a debug activation trigger and a live integration test for the whisper pipeline.

- [x] **E6-I — Investigate: `insight_engine` agent origin** — resolved (2026-05-04): `agents.yaml` has only DevCoach; no stale container or registry entry. insight_engine is not a real agent — the whispers attributed to it were Gemini echoing injected whisper text as output_transcription chunks, with the source name (`insight_engine`) from an older session's whisper injection prefix leaking through the BUG-12 filter as a multi-chunk continuation. Fixed in BUG-19.

- [ ] **E6-J — Docs: enable `LOG_LEVEL=DEBUG` for BUG-07 investigation** — commit 3be9329 added debug-level event-sequence logging to `live_session.py` to diagnose late-arriving `output_transcription` chunks. To activate: set `LOG_LEVEL=DEBUG` on the `router-service` container (env var in `docker-compose.yml` or shell export before `docker compose up`). Document this in a comment in `docker-compose.yml` so it's findable without a transcript review.

- [ ] **E6-C2 — Build: debug mode activation + logging** — implement passphrase detection and verbose logging mode. No agent swap yet — this delivers the logging half independently.

- [ ] **E6-C3 — Build: debug agent** — implement the debug-aware agent loaded on passphrase activation, informed by the E6-C1 design. Depends on E6-C2.

- [ ] **E6-K2 — Feature: separate audio-data log gate (`LOG_AUDIO` env var)** — debug logging at `LOG_LEVEL=DEBUG` includes raw audio byte data, making logs excessively verbose and hard to parse for event-sequence diagnostics. Add a `LOG_AUDIO=true` env var (default false) to gate audio-buffer log lines independently from event-sequence debug logging. Raised in session 7a263bea (2026-05-04).

- [ ] **E6-K — Investigate: ingest call count 0 despite 8 turns processed** — session a23a2089 (2026-04-30) shows turns processed: 8, whisper acks: 8, but ingest calls: 0. Determine whether this is a metric instrumentation gap in `session-review.sh` (log parser not correctly counting from container log output vs. file) or a real failure in the ingest path. May be related to the absence of a log file — debug logging was active via containers only, and the parser may assume file-based logs.

---

## Epic 7 — Security & Scalability

*Explicitly deferred. Revisit when the system is working well for a single user and sharing it with others becomes relevant.*

**Risk note (session 15383d0b, 2026-04-29):** user explicitly flagged that security should be built in from the beginning, not retrofitted. Before deferral becomes a blocker, conduct an adequacy assessment: how hard will it be to add authentication, session isolation, and rate limiting to the current architecture? The answer should inform whether Epic 7 stays deferred or gets pulled earlier. Do not let this note age without a deliberate decision.

- [ ] **E7-A — Authentication and session authorization**
- [ ] **E7-B — Rate limiting and abuse protection**
- [ ] **E7-C — Multi-user session isolation**
- [ ] **E7-D — Horizontal scaling of Router and Orchestrator services**
