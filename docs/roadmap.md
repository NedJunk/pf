# Product Roadmap — Voice-First Development Partner

**Last updated:** 2026-04-29
**Project type:** Personal productivity tooling (single user throughout these milestones)
**Target date:** None — sequenced by value, not deadline

---

## Strategic Framing

The system spec names telephony as the primary client and the knowledge layer as the core value proposition. Everything before those is prerequisite infrastructure. Milestones sequence to deliver observable value at each stage while building toward both goals.

Security (Epic 7) is explicitly deferred — it will be re-evaluated if and when the system is shared with others, which is not planned within this roadmap horizon.

---

## Milestone Map

### M0 — Foundation ✓ Complete
Three services running (Router, Orchestrator, DevCoach), docker-compose working, whisper pipeline functional, transcripts writing. MVP vertical slice delivered.

---

### M1 — Reliable Core
**Goal:** The system is stable enough for daily use and produces clean transcripts for downstream epics.

**Rationale:** BUG-07 and BUG-10 corrupt transcripts and erode trust in the router. The knowledge layer (M3) is only as good as the transcripts it ingests — fix the pipeline before building on it.

| Item | Type | Status |
|---|---|---|
| BUG-07 — race-condition turn fragmentation | Bug | Root cause identified; debug logs active |
| BUG-10 — router vocalizes whisper content | Bug | Behavioral contract change required |
| BUG-05 — unsolicited closings and summaries | Bug | May resolve after BUG-07 |
| BUG-08 — router persona has no human name | Bug | Terminology audit + contract change |
| BUG-09 — router overstates PM agent capability | Bug | Contract change |
| BUG-11 — multiple ingest calls per session | Bug | `_closed` guard investigation |
| BUG-03 — httpx connection pooling | Tech debt | Mechanical fix; warmup task |
| E6-G — `/session-review` shorthand skill | Feature | In Now; ~30-minute build |

**Exit criteria:** Five consecutive sessions with no transcript fragmentation, no whisper vocalization, and clean ingest counts (exactly 1 per session).

**Size:** Medium (2–3 sprints)

---

### M2 — PM Agent + Evaluation Framework
**Goal:** Second expert agent live; ability to measure whether agents are working correctly.

**Rationale:** The PM agent is the highest-friction gap in daily use — sessions have ended early because of missing backlog context. The eval framework is the quality gate that prevents silent regressions as agents are added. Both are high-leverage before adding more agents or complexity.

| Item | Type | Notes |
|---|---|---|
| E4-A — PM agent design | Design | Summary-based baseline confirmed; open design questions documented |
| E4-B — PM agent core | Build | Whispers + session context awareness |
| E4-C — PM agent backlog write + bug code resolution | Build | Depends on E4-B |
| E1-A — Expert selection evalset design | Design | Spec exists |
| E1-B — Evalset runner | Build | `select_expert` stub already in place |
| E1-C — Transcript labeling workflow | Tooling | Unblocked by timestamped transcript filenames |
| E4-D — PM agent quality eval | Eval | Labeled test cases for surfacing, drafting, refusal |
| E6-H — Epic naming / recall improvements | Design | Scope may be absorbed into E4-A |

**Exit criteria:** PM agent delivers relevant backlog references in 3+ consecutive live sessions without over-whispering. Evalset runner passes in CI.

**Size:** Large (4–6 sprints)

---

### M3 — Knowledge Layer Alpha
**Goal:** The system accumulates knowledge across sessions and surfaces it at the right moment. This is the core value proposition.

**Rationale:** Until knowledge persists, the system is stateless — valuable in a session, forgotten after. The expert agent wiki design spec is approved and scoped. The knowledge layer must exist before telephony is worth building.

| Item | Type | Notes |
|---|---|---|
| Expert Agent Wiki (WikiManager + `/ingest`) | Build | Approved spec: `docs/superpowers/specs/2026-04-28-expert-agent-wiki-design.md` |
| E2-A — Session knowledge extraction design | SPIKE (2 days) | Extraction strategy, storage schema |
| E2-B — Knowledge retrieval strategy | SPIKE (1 day) | BM25 vs. embedding vs. hybrid |
| E2-C — Knowledge store build | Build | Informed by spikes |
| E2-D — Knowledge injection | Build | Session-start injection confirmed; per-turn TBD |
| E2-E — Knowledge retrieval quality eval | Eval | Precision/recall for retrieval |
| E1-D — CI eval regression gate | CI | Locks in quality floor across all evals |

**Exit criteria:** Agent correctly surfaces a decision or pattern from 3+ sessions ago without being asked. Knowledge retrieval quality eval passes in CI.

**Size:** Large (4–6 sprints)

---

### M4 — Expert Ecosystem Expansion
**Goal:** More domain coverage, smarter routing, reduced broadcast-all overhead.

**Rationale:** Routing improvements need real session data to calibrate against, and the eval framework (M2) must be in place to validate routing changes without silent regression. Sequenced after M3 because additional agents are most valuable once the knowledge layer makes them contextually aware.

| Item | Type | Notes |
|---|---|---|
| E4-E — Agent routing improvements design | Design | Wire or tombstone `select_expert` stub first |
| E4-F — Improved routing build | Build | LLM-assisted or rules-based per design |
| Additional expert agents | Build | Domain TBD based on M1–M3 session patterns |
| E6-D — Router skill awareness | Feature | Design question open (contract vs. injection vs. meta-agent) |
| E6-C1/C2/C3 — Debug mode | Feature | Passphrase activation + verbose logging |

**Size:** Large (4–6 sprints)

---

### M5 — Telephony Alpha
**Goal:** The primary client (phone calls) works end-to-end.

**Rationale:** Per the system spec: *"deferred until the knowledge layer is useful enough to justify a phone interface."* Telephony without knowledge is a voice chat. Telephony with knowledge is the product. Sequenced after M3.

| Item | Type | Notes |
|---|---|---|
| E5-A — Telephony adapter design | Design | Provider-agnostic; first candidate Twilio |
| E5-B — Telephony adapter build | Build | — |
| E5-C — End-to-end voice call test | Test | — |

**Size:** Medium (2–3 sprints)

---

### M6 — Provider Independence
**Goal:** No hard Gemini lock-in; local deployment path open.

**Rationale:** Abstraction over a system that must fully exist first. Worth completing before the architecture calcifies further. Can run in parallel with or after M5.

| Item | Type | Notes |
|---|---|---|
| E3-A — Local voice alternatives evaluation | SPIKE | Moshi + modular ASR/LLM/TTS approach |
| E3-B — Provider abstraction design | Design | Must cover both voice agent and expert agent LLMs |
| E3-C — Provider abstraction build | Build | — |

**Size:** Medium–Large (3–5 sprints)

---

## Sequence

```
M0 ──► M1 ──► M2 ──► M3 ──► M4 ──► M5
Done   Reliable PM+Eval  Know.   Expert  Telephony
       Core     Framework Layer  Ecosys  Alpha
                                           │
                                           ▼
                                          M6
                                    Provider Indep.
                                 (parallel or after M5)
```

---

## Immediate Next Actions (M1)

1. **BUG-07** — pull debug logs from session 6275d9ca; look for `branch=user output_buf>0` signal to confirm race condition, then fix.
2. **BUG-10** — update behavioral contract to prohibit speaking whisper injection text.
3. **E6-G** — build `/session-review` skill (~30 min); delivers immediate session value.

---

## Deferred Indefinitely

**Epic 7 — Security & Scalability** — authentication, rate limiting, multi-user isolation. Trigger: first time the system is shared with another user. No current plan to do so.
