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
| BUG-23 | Reproduce + fix assistant stopped responding | 3 | — | — | open |
| BUG-19 + E6-I | insight_engine transcript pollution + origin investigation | 3 | — | — | open |
| BUG-21 | Investigate whisper delivery drop to 37.5% | 2 | — | — | open |
| BUG-17 | DevCoach whisper deduplication / decay logic | 3 | — | — | open |
| BUG-20 | Prohibit affirmation framing in behavioral contract | 1 | — | — | open |
| BUG-18 *(stretch)* | Prohibit internal codes in spoken responses | 1 | — | — | open |
| E4-E *(stretch)* | Design: smarter orchestrator routing / fan-out | 2 | — | — | open |

**Sprint total:** committed 12 pts / stretch 3 pts

---

## Velocity Summary

| Sprint | Committed | Delivered | Stretch Delivered | Tokens (total) | Time (total) |
|---|---|---|---|---|---|
| 1 — M2 Kickoff | 12 | 12 | 3 | — | 00:31 |
| 2 — Core Stability | 12 | — | — | — | — |
