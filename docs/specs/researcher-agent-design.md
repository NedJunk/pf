# Researcher Agent Design

**Date:** 2026-05-03
**Epic:** E4 — Expert Ecosystem
**Status:** design draft

---

## 1. Purpose

The Researcher is the second expert agent. It uses Gemini Deep Research to conduct
background research during development sessions and surfaces findings as whispers.
Unlike the dev-coach (which draws on accumulated session wiki), the Researcher
operates on live external knowledge.

---

## 2. Trigger Modes

Two trigger modes are instrumented from the start. Comparing their relevance and acceptance rates is the primary evaluation signal (E4-K).

### 2.1 Autonomous Mode

The agent analyses recent conversation history at /ingest time and infers research topics without the user explicitly asking. The inference prompt looks for:

- Technology names the developer mentioned that the agent has no prior wiki entries for
- Design decisions where the developer expressed uncertainty
- Bug symptoms that match known research-worthy patterns

Topic extraction is LLM-assisted: Gemini Flash reads the last N turns and returns a ranked list of candidate topics. The agent queues research tasks for any topic above a relevance threshold (configurable, default 0.6).

**Instrumentation:** every task spawned autonomously is tagged trigger_mode: autonomous.

### 2.2 Explicit Mode

The user directly requests research mid-session ("look up...", "can you find out...", "research..."). The /ingest endpoint detects explicit requests via a lightweight regex + LLM classifier. Explicit requests bypass the relevance threshold and queue immediately.

**Instrumentation:** every task spawned explicitly is tagged trigger_mode: explicit.

### 2.3 Mode Evaluation (E4-K)

Both modes use the same task lifecycle and storage. At evaluation time, trigger_mode on each task lets us compute separate precision/recall metrics for autonomous vs. explicit sourcing.

---

## 3. Async Task Lifecycle

Research takes 30-120 seconds. The agent must not block /ingest or /whisper.

### 3.1 State Machine

queued -> in-progress -> complete (with findings) | failed (with error)

- **queued**: task created, not yet submitted to the research model
- **in-progress**: Gemini Deep Research call in flight
- **complete**: findings written to wiki, task record updated
- **failed**: error captured; not retried automatically

### 3.2 Task Storage

Tasks stored in an in-memory dict keyed by a stable topic hash: sha256(topic.strip().lower())[:12]. This gives:

- Deduplication: same topic from two close sessions is one task
- O(1) lookup at /whisper time for in-progress check
- Acceptable restart cost: tasks not in wiki = not complete; re-queue on restart is fine

Task schema (in-memory dataclass):
- topic: str
- task_id: str (topic hash)
- trigger_mode: str (autonomous | explicit)
- session_id: str
- status: str (queued|in-progress|complete|failed)
- error: str | None
- created_at / completed_at: datetime

### 3.3 Background Execution

asyncio.create_task() runs research in the background. FastAPI + asyncio keeps endpoints non-blocking. For a single-user system, concurrent tasks will rarely exceed 3.

### 3.4 Whisper Response for In-Progress Tasks

When /whisper is called and a relevant task is in-progress, the agent returns a status whisper: "I am actively researching [topic] — findings incoming." Capped to one status whisper per topic per session via a _whispered_in_progress set.

---

## 4. Findings Persistence — Wiki Schema

Findings are stored as agent wiki pages with two page types.

### 4.1 Findings Page

Filename: research-{task_id}.md

Fields:
- # Research: {topic}
- Status: complete | partial
- Summary: 1-3 paragraph synthesis from Deep Research
- Key Sources: URLs/citations
- Open Questions: what the research could not resolve (gaps are first-class)
- Relevance Tags: comma-separated topic tags for whisper scoring

### 4.2 Gaps as First-Class Results

Partial or incomplete research is Status: partial, not a failure. The Open Questions section records what was found and what could not be resolved. The agent does NOT retry partial results automatically — the user or a follow-up session triggers a new task on the same topic.

### 4.3 Synthesis (E4-L Integration)

The researcher _synthesize() override:
1. Reads all findings pages
2. Identifies topic clusters (pages with overlapping relevance tags)
3. Merges clusters into denser summary pages
4. Promotes recurring gaps to open-questions.md (gaps in 3+ tasks are surfaced proactively)
5. Updates the index

Runs at agent startup and on demand via POST /synthesize.

---

## 5. Whisper Scoring

The researcher overrides the default whisper scoring:

1. **Semantic relevance**: score current turn against each wiki page relevance tags + first paragraph (keyword overlap for v1; embeddings after E1-B harness exists)
2. **Recency bonus**: findings from the current session score higher
3. **Status gate**: in-progress tasks return a status note, not a findings excerpt
4. **Gap surfacing**: if the turn mentions a topic with only partial research, the whisper notes the gap explicitly

---

## 6. Endpoints

Inherited: /ingest, /whisper, /health, /synthesize (from ExpertAgentBase)

Agent-specific:

### GET /research/tasks

Returns the current task list with status. Used for debugging and session-review skill.
Fields per task: task_id, topic, status, trigger_mode, session_id, created_at, completed_at.

No write endpoints — task lifecycle is driven by /ingest and background tasks.

---

## 7. Model Selection

- **Research model**: Gemini Deep Research — verify exact model string via E6-A script before E4-I coding starts. Do not hardcode.
- **Topic extraction**: gemini-2.0-flash or equivalent cheap fast model used in the /ingest autonomous classifier
- **Synthesis**: same as topic extraction; Deep Research is not needed for compression

Async handling: the research call runs in a background asyncio.create_task(); it must not block the HTTP endpoint. FastAPI + asyncio handles this natively.

---

## 8. Divergences from dev-coach Pattern

| Dimension | dev-coach | researcher |
|---|---|---|
| Wiki content | accumulated session observations | external research findings |
| LLM call pattern | one call per whisper | one long call per task (background) |
| Whisper source | retrospective (past turns) | prospective (researched ahead of turn) |
| State between turns | stateless (wiki is the memory) | stateful (in-flight task dict) |
| Failure mode | no whisper | partial findings, explicit gap |

The biggest divergence is the in-memory task dict. Risk: dict is lost on container restart. Acceptable for a single-user system; add wiki-backed persistence if multi-session reliability becomes important.

---

## 9. Open Questions (Must Resolve Before E4-I)

1. **Model string**: what is the current production model string for Gemini Deep Research? Run E6-A script before E4-I. Do not hardcode.

2. **Relevance threshold for autonomous mode**: 0.6 is a guess. The evalset (E1-A/B) will give the real signal. E4-I should expose this as a config value.

3. **Session boundary for deduplication**: the task hash deduplicates across sessions. Add a TTL if staleness becomes a problem.

4. **Explicit trigger detection**: the classifier for detecting user research requests needs testing. Collect false positives from E4-K before hardening.

5. **Whisper latency**: research takes 30-120 seconds; the whisper window on a typical turn is 2-4 seconds. The agent will almost never deliver fresh findings on the trigger turn. The value is in subsequent turns. A status whisper sets expectations better than silence.

6. **GET /research/tasks auth**: exposes session metadata; fine for single-user local system, flag for E7.

7. **Deep Research quota**: may have per-call rate limits. Add a circuit breaker if repeated failures observed in E4-K evaluation sessions.
