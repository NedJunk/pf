# Sprint Velocity

Tracks effort per sprint item by estimated story points, Claude tokens consumed, and wall-clock time. Token counts are per-session totals from the Claude Code session log; time is elapsed from first tool call to last on that item.

---

## Columns

| Column | Meaning |
|---|---|
| Est | Story points estimated at sprint start |
| Tokens | Total Claude tokens consumed (input + output) for this item |
| Time | Wall-clock time spent (hh:mm) |
| Status | open / in-progress / done / carried |

---

## Sprint 1 — M2 Kickoff

**Dates:** 2026-05-03 – 2026-05-10
**Goal:** Deliver /synthesize foundation, design researcher agent, establish evalset schema — M2's three parallel tracks unblocked for next sprint.
**Capacity:** 15 pts (committed: 12, stretch: 3)

| Item | Description | Est | Tokens | Time | Status |
|---|---|---|---|---|---|
| BUG-16 | Remove "I'll note that in the transcript" from behavioral contract | 1 | — | 00:01 | done |
| E4-L | Build `/synthesize` endpoint on ExpertAgentBase | 5 | — | 00:08 | done |
| E4-H | Design: researcher agent | 3 | — | 00:12 | done |
| E1-A | Design: expert selection evalset spec + schema | 3 | — | 00:07 | done |
| E4-M *(stretch)* | dev-coach roadmap awareness (depends on E4-L) | 3 | — | 00:03 | done |

**Sprint total:** committed 12 pts / stretch 3 pts

---

## Sprint 2 — Core Stability

**Dates:** 2026-05-04 – TBD
**Goal:** Resolve the assistant-unresponsive regression (BUG-23), eliminate remaining transcript pollution and affirmation patterns, fix whisper delivery rate drop, and curb DevCoach whisper loop.
**Capacity:** TBD pts (committed: 12, stretch: 3)

| Item | Description | Est | Tokens | Time | Status |
|---|---|---|---|---|---|
| BUG-23 | Reproduce + fix assistant stopped responding | 3 | — | — | done |
| BUG-19 + E6-I | insight_engine transcript pollution + origin investigation | 3 | — | — | done |
| BUG-17 | DevCoach whisper deduplication / decay logic | 3 | — | — | done |
| BUG-20 | Prohibit affirmation framing in behavioral contract | 1 | — | — | done |
| BUG-21 | Investigate whisper delivery drop to 37.5% | 2 | — | — | carried |
| BUG-18 *(stretch)* | Prohibit internal codes in spoken responses | 1 | — | — | done |
| E4-E *(stretch)* | Design: smarter orchestrator routing / fan-out | 2 | — | — | open |

**Sprint total:** committed 12 pts / stretch 3 pts

---

## Sprint 3 — Verification + Remaining Stability

**Dates:** 2026-05-05 – 2026-05-05
**Goal:** Close Sprint 2 verification debt, fix the BUG-18 echo regression (BUG-26), and unblock the fan-out routing track.
**Capacity:** 13 pts (committed: 10, stretch: 3)

| Item | Description | Est | Tokens | Time | Status |
|---|---|---|---|---|---|
| BUG-26 | Behavioral contract echo-case for user-provided codes | 2 | — | — | done |
| BUG-21 | Confirm whisper delivery rate over 24+ turn session | 2 | — | — | done |
| BUG-24 | Verify ROADMAP_PATH wiring resolves DevCoach context gap | 1 | — | — | carried |
| BUG-25 | Close after one more clean-session confirmation | 1 | — | — | done |
| E4-E | Design: smarter orchestrator routing / fan-out | 2 | — | — | done |
| E6-L | /session-review: optional user observation argument | 2 | — | — | done |
| E6-K2 *(stretch)* | Separate audio-data log gate (LOG_AUDIO env var) | 2 | — | — | done |
| E6-A *(stretch)* | Automate session bundle ingest (remove manual ! prefix) | 1 | — | — | open |

**Sprint total:** committed 10 pts / stretch 3 pts

---

## Sprint 4 — Code Quality + Routing Build

**Dates:** 2026-05-05 – 2026-05-05
**Goal:** Fix the backlog injection conflict and DevCoach wiki pollution, close BUG-24, build the capability-tag routing design (E4-F), and lock down Kai's facilitation contract boundaries.
**Capacity:** 13 pts (committed: 10, stretch: 3)

| Item | Description | Est | Tokens | Time | Status |
|---|---|---|---|---|---|
| BUG-28 | Fix backlog injection instruction conflict with BUG-18/26 | 1 | — | — | done |
| BUG-29 | Audit and clean DevCoach wiki of hallucinated content | 2 | — | — | done |
| BUG-24 | Close after BUG-29 verified clean in one live session | 1 | — | — | carried |
| E4-F | Build improved routing (capability tags + Jaccard scoring) | 4 | — | — | done |
| E6-N | Design Router facilitation contract boundaries | 2 | — | — | done |
| E6-A *(stretch)* | Gemini model availability skill + script | 1 | — | — | done |
| E6-M *(stretch)* | Real-time session metric dashboard (scope/design) | 2 | — | — | done |

**Sprint total:** committed 10 pts / stretch 3 pts

---

## Sprint 5 — Knowledge Foundation + Dashboard

**Dates:** 2026-05-05 – TBD
**Goal:** Spike the knowledge layer design before committing to a second agent. Build the session dashboard (design done). Close BUG-24 via the first clean live session.
**Capacity:** 9 pts (committed: 5, stretch: 6)

*Pivot rationale: Researcher agent deferred — async research latency (30–120s) makes whisper delivery stale for typical solo-dev sessions; autonomous topic inference requires E1 evalset to tune; no unified wiki schema exists yet. E2-A spike establishes the schema foundation that both DevCoach and a future Researcher should build on.*

| Item | Description | Est | Tokens | Time | Status |
|---|---|---|---|---|---|
| BUG-24 | Close via first clean post-BUG-29 live session | 1 | — | — | open |
| E2-A | SPIKE: session knowledge extraction design (2-day time-box) | 2 | — | 00:20 | done |
| E6-M | Build session dashboard script (`scripts/session-dashboard.sh`) | 2 | — | 00:25 | done |
| E2-B *(stretch)* | SPIKE: knowledge retrieval strategy (1-day time-box, follows E2-A) | 1 | — | 00:20 | done |
| E4-I *(stretch)* | Build researcher agent core — only after E2-A resolves wiki schema | 5 | — | — | carried |

**Sprint total:** committed 5 pts / stretch 6 pts (E4-I stretch is aspirational — carry if E2-A takes time)

---

## Velocity Summary

| Sprint | Committed | Delivered | Stretch Delivered | Tokens (total) | Time (total) |
|---|---|---|---|---|---|
| 1 — M2 Kickoff | 12 | 12 | 3 | — | 00:31 |
| 2 — Core Stability | 12 | 10 (carried: BUG-21) | 1 (BUG-18) | — | — |
| 3 — Verification + Remaining Stability | 10 | 9 (carried: BUG-24) | 2 (E6-K2) | — | — |
| 4 — Code Quality + Routing Build | 10 | 9 (carried: BUG-24) | 2 (E6-A, E6-M) | — | — |
| 5 — Knowledge Foundation + Dashboard | 5 | 4 (carried: BUG-24) | 1 (E2-B) | — | ~01:05 |
