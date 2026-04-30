# M1 Close: BUG-10, BUG-11, BUG-05/08/09, E6-G Session Review Skill

**Date:** 2026-04-30  
**Milestone:** M1 — Reliable Core  
**Scope:** Fix BUG-10 (first-whisper race), BUG-11 (ingest count), BUG-05/08/09 (behavioral contract), build E6-G (`/session-review` skill)

---

## 1. BUG-10 — First-Whisper Race Condition

### Problem

`_whisper_drain` is a standalone `asyncio.Task` that can call `send_client_content(turn_complete=False)` at any time, including when Gemini is idle between turns. When it does so during an idle window, Gemini accumulates an open user turn and vocalizes the injected content on the next user input. Debug session 2c762c0b confirmed: turn 2 vocalized the full whisper text; turns 3–10 were silent because those whispers arrived while the model was generating.

### Fix

**File:** `router-service/router_service/live_session.py`

Add `self._model_generating = asyncio.Event()` to `__init__`.

In `_gemini_to_browser`, at the `turn_complete` branch:
- `input_buf` non-empty (user turn complete, model about to generate) → `self._model_generating.set()`
- `input_buf` empty (model turn complete, Gemini now idle) → `self._model_generating.clear()`

In `_whisper_drain`, insert `await self._model_generating.wait()` before each `send_client_content` call. The drain blocks while Gemini is idle and releases the moment a user turn completes. No polling. Whispers that arrive during an idle window queue silently and inject at the next generation window.

### Invariant

A whisper is never injected while `_model_generating` is clear (Gemini idle). At most one generation window fires between any two user turns, so a whisper delayed by one idle period arrives no later than the next user turn's response.

---

## 2. BUG-11 — Ingest Call Count Inflation

### Problem

`scripts/session-review.sh` counts ingest calls with `grep -c "POST /ingest.*202"` against the full log tail (`all_logs`), not filtered to the current session. With multiple sessions in the log window, the count is inflated. In session 6275d9ca, 3 close events across 3 sessions were reported as "3 ingest calls" for one session.

The underlying close path is guarded: `LiveSession.close()` sets `_closed = True` immediately and returns early on any subsequent call, so `_post_session_close` (and thus the `/sessions/{id}/close` POST) fires exactly once per session. No true duplicate ingests.

### Fix

Two changes:

**`orchestrator/orchestrator/session_handler.py`:**
1. Add an `_ingested_sessions: set[str]` module-level set. In `handle_session_close`, check before processing and skip with a warning log if already seen. Belt-and-suspenders against any future close-path race.
2. Add a success log line in `_call_ingest` that includes `session_id` when the ingest 202s (currently only warnings are logged).

**`scripts/session-review.sh`:**
Filter the ingest count through `session_logs` (already filtered to `$short_id`) instead of `all_logs`. The `session_logs` variable is `grep "$short_id"` over all `docker compose logs` output, which includes orchestrator container lines — so once the orchestrator logs the session_id on success (change above), the grep will match. Update the `ingest` metric line accordingly.

---

## 3. BUG-05 — Unsolicited Closings (verify-first)

### Problem

Router generates closing-question turns or session-summary language without user signal ("Are there any outstanding questions before you conclude?").

### Fix

Scan the two most recent transcripts for these specific patterns before adding a directive:
- Phrases matching `before you conclude`, `before concluding`, `before we wrap`, `any outstanding`, `anything else before`
- Consecutive assistant turns ending in a question about session closure

**If absent in both transcripts:** close BUG-05 as self-resolved with BUG-07; add a note to the backlog entry.  
**If present:** add a single directive to `behavioral_contract.py`: the router must not generate closing questions, session summaries, or wrap-up language unless the user explicitly signals session end (e.g. "I'm done", "wrap up", "that's all").

---

## 4. BUG-08 — Router Persona Name

### Decision

The voice agent's name is **Kai**. Single syllable, phonetically unambiguous in audio, warm without implying a specific role that may evolve.

### Changes

**`voice-router/src/router/behavioral_contract.py`:**
- Add self-identification: Kai refers to itself as "Kai" when asked its name.
- Prohibit references to "the router" in first-person speech.

No service renaming. `router-service`, `RouterService`, `LiveSession` are internal identifiers and stay unchanged.

---

## 5. BUG-09 — Overstated PM Agent Capability

### Problem

Router uses language implying an active downstream PM agent: "a note will be passed to the project manager," "I'll flag this for the PM." No such agent exists yet.

### Fix

**`voice-router/src/router/behavioral_contract.py`:**
Add directive: all note-taking references use first-person transcript framing only — "I'll note that in the transcript." Prohibit any reference to passing items to another agent, a PM, or any downstream system not currently operational.

---

## 6. E6-G — `/session-review` Skill

### Invocation

**File:** `.claude/commands/session-review.md`

Invoked as `/session-review` (auto-detect session type) or `/session-review <type>` (explicit). Claude Code substitutes `$ARGUMENTS` with whatever follows the command name.

### Entry Point

1. Parse `$ARGUMENTS`:
   - Empty → run `! ./scripts/session-review.sh` (latest session, auto-detect type).
   - Matches a known session type keyword (`debug`, `design`, `implementation`, `exploration`) → run `! ./scripts/session-review.sh` (latest session), record the explicit type, skip detection.
   - Otherwise (treat as session ID prefix) → run `! ./scripts/session-review.sh $ARGUMENTS`, then auto-detect type from the resolved transcript.
   - Session ID prefix + explicit type not supported in a single invocation; if needed, user runs the script manually and pastes the output.
2. Capture script output as the review bundle (transcript + log metrics block).
3. If session type not already recorded, classify from the transcript (see Detection below).

### Module Registry

| Session type     | Modules (in order)                                                                    |
|------------------|---------------------------------------------------------------------------------------|
| `debug`          | session-summary, log-analysis, bug-status, root-cause, communication-patterns, backlog-candidates |
| `design`         | session-summary, decision-log, open-questions, spec-readiness, backlog-candidates     |
| `implementation` | session-summary, completion-status, communication-patterns, backlog-candidates        |
| `exploration`    | session-summary, insights-captured, communication-patterns, backlog-candidates        |

**Extension points:**
- New session type: insert a row in the registry table; add module references to Part 3.
- New module: append a section in Part 3; reference it in any registry row that should include it.

### Session Type Detection

If not explicit, classify by these signals (in priority order):

1. `BUG-` codes, `LOG_LEVEL=DEBUG`, passphrase trigger, whisper validation language → **debug**
2. "design", "spec", "approach", "brainstorm", "how should we", "options" → **design**
3. Code review language, "implemented", "refactored", "tests passing", "merged" → **implementation**
4. "exploring", "trying out", "I wonder if", "what happens if", no dominant structure → **exploration**

On ambiguity: state the classification and reasoning, ask for confirmation before running modules.

### Module Library

**session-summary:** In 3–5 sentences, what happened. Key outcomes, decisions, or validations.

**log-analysis:** Parse the LOG METRICS block from the bundle. Flag anomalies: non-zero timeouts, unexpected 404 counts, ingest count ≠ 1 per session, whisper delivery rate below 80%.

**bug-status:** For each BUG code mentioned: was it reproduced, fully fixed, partially fixed, or a regression? Cite evidence from transcript and log metrics.

**root-cause:** For bugs confirmed unfixed or partially fixed, state the root cause and narrowest reproduction case. Reference specific log lines if available.

**decision-log:** List decisions made, the rationale offered, and any open questions explicitly deferred.

**open-questions:** List questions raised but not resolved. Flag any that block downstream work.

**spec-readiness:** Is there enough detail from the session to write a spec? What is missing?

**completion-status:** What was built or changed? What was left incomplete?

**insights-captured:** What did the session reveal that wasn't known before?

**communication-patterns:** Apply meeting-analyzer logic (abbreviated): router facilitation quality, whisper influence on assistant behavior, any vocalization leaks or transcript pollution.

**backlog-candidates:** Propose additions to `docs/backlog.md`. For each candidate: type (bug/feature/follow-up), proposed wording, which epic/area it belongs to. Present as a Y/N confirmation list. Only write to `docs/backlog.md` after explicit per-item approval.

---

## Implementation Sequence

1. BUG-10 fix (`live_session.py`) + tests
2. BUG-11 fix (`session_handler.py` + `session-review.sh`) + tests
3. BUG-05 check → patch behavioral contract if needed
4. BUG-08 + BUG-09 behavioral contract changes
5. E6-G: create `.claude/commands/` directory, write `session-review.md`
6. Full test suite pass
7. Close M1 in backlog; update roadmap memory
