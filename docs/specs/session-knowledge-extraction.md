# Session Knowledge Extraction — Design Spec

**Date:** 2026-05-05
**Epic:** E2-A
**Status:** spike — 2-day time-box
**Scope:** How session transcripts become queryable cross-session knowledge

---

## 1. What Already Exists

The extraction pipeline is **fully implemented and live**:

- On session close, `live_session.py` POSTs `{ session_id, transcript }` to `POST /sessions/{id}/close` on the orchestrator.
- The orchestrator fans out `POST /ingest` to every healthy agent (`orchestrator/session_handler.py`), idempotency-guarded via `_ingested_sessions`.
- `ExpertAgentBase._ingest_session()` sends the transcript to an LLM with the agent's `wiki_schema.md` and writes structured pages to `wiki/pages/`, updates `wiki/index.md`, and appends `wiki/log.md`.
- At whisper time, `_handle_whisper()` calls `_query_wiki(history)` to retrieve relevant pages and injects them into `WhisperContext.wiki_context`.

The question E2-A answers is: **does the current pipeline produce specific, cross-session-useful knowledge, and does retrieval surface it when needed?**

---

## 2. What the Spike Must Answer

Two questions cannot be settled by design alone — they require running real ingests and inspecting output:

1. Does `_ingest_session` produce structured, retrievable pages from a real transcript — or generic summaries?
2. Does `_query_wiki` surface cross-session knowledge at whisper time, or is retrieval too narrow to connect past decisions to current context?

The spike is **empirical first, design second.** Changes are only made after the failure modes are confirmed.

---

## 3. Schema Changes (Proposed)

The current `wiki_schema.md` tracks four categories: technical decisions, recurring problems, patterns observed, tech choices. Two gaps:

### 3.1 Missing: Open Questions / Follow-Up Items

Sessions often surface things the developer explicitly deferred: "I need to figure out X later," "TODO: check Y." These are not decisions or patterns — they're work items with cross-session relevance.

Add a fifth category to `wiki_schema.md`:

> **Open questions and follow-up items** — things explicitly flagged for future research or decision. Naming convention: `followup-<topic>.md`.

Ingest prompt already passes `session_id` — use it to populate a `Last updated` line in pages.

### 3.2 Missing: Temporal Metadata in Pages

Without a date on each page, the index cannot convey recency. Add a convention:

```
Last updated: YYYY-MM-DD | session: {session_id[:8]}
```

No change to `WikiManager` or `ExpertAgentBase` — `wiki_schema.md` is the sole customization point.

---

## 4. Retrieval: Session-Start Priming

`_query_wiki` is currently called per-turn using `context.history` as the query. For the first turn of a new session, history is empty — cross-session priming doesn't fire.

The `goals` and `project_map` fields are already in `WhisperContext` from the session-open payload. These are the natural query context before any turns exist.

**Option A (passive):** No code change. Observe whether the first real turn naturally triggers relevant wiki context via `_query_wiki(history)`. Validate this before building anything.

**Option B (active):** If passive priming proves insufficient, add a `/prime` endpoint to `ExpertAgentBase._build_app()`:

```
POST /prime
{ "goals": [...], "project_map": [...] }
→ { "wiki_context": "..." }
```

Orchestrator calls this on session open (parallel to the existing session-close ingest fan-out). Only build if Day 2 validation confirms Option A is weak.

---

## 5. Two-Day Plan

### Day 1 — Validate Extraction Quality

**Step 1:** Run `_ingest_session()` against the three most recent transcripts in `./transcripts/`. Use a one-shot script calling DevCoach's `_ingest_session` directly — not a live session.

**Evaluate:**
- Are pages specific to this developer's work or generic?
- Are follow-up items captured (or only completed decisions)?
- Is the index scannable as a retrieval target?

**Step 2:** Update `wiki_schema.md` based on findings — add `followup-<topic>.md` and the date convention.

**Step 3:** Re-run ingest on the same transcripts. Compare before/after.

### Day 2 — Validate Retrieval

**Step 4:** Run `_query_wiki()` with representative session-start contexts (goals + project_map strings from past sessions). Inspect which pages are returned.

**Evaluate:**
- Does retrieval surface cross-session context, or only the most recent ingest?
- Do follow-up items surface when the topic is mentioned?

**Step 5:** If retrieval is weak, evaluate the index.md format as the bottleneck:
- Option: richer index entries (add keyword tags per page)
- Option: full-text fallback scan when LLM returns NONE

**Step 6:** Implement `/prime` only if passive session-start priming is confirmed insufficient.

---

## 6. Storage

No change. Filesystem wiki (`wiki/pages/`, `wiki/index.md`) remains the knowledge store. BM25 or embedding retrieval is E2-B — validate LLM-assisted index lookup first.

The wiki persists across container restarts via the existing volume mount:
```yaml
./expert-agents/dev-coach/wiki:/app/wiki
```

---

## 7. Out of Scope

- New storage backends (SQLite, vector DB) — E2-B
- Embedding-based retrieval — E2-B
- Multi-agent knowledge aggregation — DevCoach only for this spike
- New services

---

## 8. Tests

Follow existing patterns in `expert-agents/base/tests/`:

- **Ingest quality:** `tmp_path` wiki dir + stubbed `_generate` returning a canned response with known pages. Assert `wiki/pages/` and `wiki/index.md` match expected structure.
- **Retrieval:** pre-populated mock wiki + stubbed `_generate` returning known filenames. Assert `_query_wiki()` returns the right page content.
- **Schema coverage:** transcript fixture with explicit follow-up language ("I need to look into X later") → stubbed LLM returns `followup-*.md` page → assert it appears in the wiki.

If `/prime` is built: standard endpoint test, stubbed `_query_wiki`.

---

## 9. Open Questions the Spike Will Answer

| Question | How |
|---|---|
| Does `_ingest_session` produce specific, cross-session-useful pages? | Manual inspection after ingesting real transcripts |
| Does `_query_wiki` surface cross-session knowledge at session start? | Manually run retrieval with past session goals as query |
| Is a `/prime` endpoint needed, or does turn-0 priming suffice? | Validate passive path first |
| How many ingests before the wiki needs synthesis? | Observe log.md growth; trigger `/synthesize` once and inspect |

---

## 10. Key Risk

`_query_wiki` asks an LLM to select pages by scanning `index.md`. If the index is sparse or the LLM doesn't infer a connection between current goals and past decisions, retrieval silently returns nothing. The spike must directly test this failure mode — not assume it works because the mechanism exists.
