# Session Review

Run a structured post-session analysis. Follow these steps in order.

## Step 1: Ingest the session bundle

Parse the arguments: `$ARGUMENTS`

- Empty → run `! ./scripts/session-review.sh` and set SESSION_TYPE to auto-detect.
- Matches one of `debug`, `design`, `implementation`, `exploration` exactly → run `! ./scripts/session-review.sh`, set SESSION_TYPE to that value, skip Step 2.
- Anything else → treat as a session ID prefix, run `! ./scripts/session-review.sh $ARGUMENTS`, set SESSION_TYPE to auto-detect.

Capture the full script output as the review bundle. It contains a LOG METRICS block and the full transcript.

## Step 2: Detect session type (skip if already set)

Read the transcript and classify by these signals (first match wins):

1. Any of: `BUG-` codes, `LOG_LEVEL=DEBUG`, passphrase trigger (`"orange is as orange does"`), whisper validation language → **debug**
2. Any of: "design", "spec", "approach", "brainstorm", "how should we", "options", "trade-off" → **design**
3. Any of: "implemented", "refactored", "tests passing", "merged", code review language → **implementation**
4. No dominant signal → **exploration**

If ambiguous (signals from multiple types), state your classification and the reasoning, then ask the user to confirm before continuing.

## Step 3: Select modules

Look up the session type in the registry below and note the module list:

| Session type     | Modules (run in this order)                                                                         |
|------------------|-----------------------------------------------------------------------------------------------------|
| `debug`          | session-summary, log-analysis, bug-status, root-cause, communication-patterns, backlog-candidates  |
| `design`         | session-summary, decision-log, open-questions, spec-readiness, backlog-candidates                   |
| `implementation` | session-summary, completion-status, communication-patterns, backlog-candidates                      |
| `exploration`    | session-summary, insights-captured, communication-patterns, backlog-candidates                      |

## Step 4: Run each module

Run every module in the order listed. Output each module's section with a `###` heading.

### Module: session-summary
In 3–5 sentences: what happened, key outcomes, decisions made, or validations completed.

### Module: log-analysis
Parse the LOG METRICS block from the bundle. Report each metric. Flag anomalies:
- Timeouts > 0
- Ingest count ≠ 1
- Whisper delivery rate below 80% (delivered / acks)
- Unexpected 404 counts

### Module: bug-status
For each BUG- code mentioned in the transcript: state whether it was reproduced, fully fixed, partially fixed, or confirmed a regression. Cite the specific transcript line or log metric as evidence.

### Module: root-cause
For any bug confirmed unfixed or partially fixed: state the root cause in one sentence and the narrowest reproduction case. Reference a specific log line if available.

### Module: decision-log
List each decision made in the session. For each: the decision, the rationale given, and any conditions or constraints attached.

### Module: open-questions
List every question raised but not resolved. Flag any that block M1, M2, or downstream work.

### Module: spec-readiness
Is there enough detail from this session to write a spec? List what is present and what is missing. Give a readiness verdict: ready / mostly ready / needs more exploration.

### Module: completion-status
What was built or changed? What was explicitly left incomplete or deferred?

### Module: insights-captured
What did this session reveal that was not previously documented? List each insight as a bullet.

### Module: communication-patterns
Evaluate: router facilitation quality (did it stay in facilitator role?), whisper influence (did the router incorporate or ignore whispers?), any vocalization leaks or transcript pollution (whisper text appearing in assistant lines).

### Module: backlog-candidates
Propose additions to `docs/backlog.md`. For each candidate:
- **Type:** bug | feature | follow-up
- **Proposed wording** (one sentence, matching backlog style)
- **Epic/area** (e.g. "Epic 6 — Meta-tooling", "Known Bugs")

Present as a numbered list. Ask for Y/N on each item before writing anything. After confirmation, append only the approved items to `docs/backlog.md` under the appropriate section.

---

## Extension guide

**Add a new session type:** Insert a row in the Step 3 registry table. Add module references from the existing library or define new modules in Step 4.

**Add a new module:** Append a `### Module: <name>` section under Step 4 with analysis instructions. Reference it in any registry row that should include it.
