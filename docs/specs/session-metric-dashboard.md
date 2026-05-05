# Session Metric Dashboard — Design Spec

**Date:** 2026-05-05  
**Epic:** E6-M  
**Status:** design  
**Scope:** Live display of core session quality metrics during active voice sessions

---

## Overview

A lightweight terminal-based dashboard displays live session metrics during development sessions. It runs in a split terminal pane alongside the application, polling Docker container logs to extract key health indicators in real time.

This is a **developer tool**, not a user-facing feature. It supports operational awareness during voice sessions and validation of core whisper-delivery quality.

---

## 1. Data Source

### Source Streams
- **router-service logs** — session start, whisper delivery responses  
- **orchestrator logs** — turn receipts, agent whisper acknowledgments  

No new API endpoint is added. The dashboard reads container stdout via `docker logs --since` with a rolling time window to avoid re-reading the full log history.

### Session ID Discovery
Extract from router-service logs at session start:

```
POST /sessions endpoint receives a request → session_id is generated and returned
```

The dashboard listens for the first request after startup (or accepts session ID as a CLI argument) to begin tracking.

### Log Filter Patterns

| Metric | Service | Log Pattern | Example |
|---|---|---|---|
| **Turn count** | orchestrator | `POST /turns` → `200` response logged in handler | `session=abc123` appears on successful POST |
| **Whisper acks** | orchestrator | Agent returns `202` on `/whisper` POST | `Agent <name> returned 202` or timeout/error logged |
| **Whisper delivered** | router-service | `/sessions/{id}/whisper` POST returns `200` | Successful `inject_whisper()` completes without error |
| **Session ID** | router-service | Session created log or WebSocket connect | Extracted from stdout at session start |

---

## 2. Rendering: Terminal Panel

### Output Format

Compact single-line status display with optional multi-line fallback for clarity:

```
Session: abc123 | Turns: 7 | Acks: 7 | Delivered: 6 (85.7%) | [OK]
```

### Status Indicator Logic

| Condition | Status | Meaning |
|---|---|---|
| Delivery rate ≥ 80% | `[OK]` | Whisper delivery healthy |
| Delivery rate < 80% | `[WARN]` | At least one agent whisper failed to reach router |
| No turns yet | `[—]` | Session started, awaiting first turn |

### Justification for Terminal (Not Browser)

1. **Already in terminal workflow** — developer is running containers and logs from shell  
2. **No new web dependency** — keeps runtime footprint minimal  
3. **tmux-friendly** — pairs naturally with split panes or new windows  
4. **Synchronous with session lifecycle** — process dies with session, no orphaned browser tabs  
5. **Easy to integrate into CI/test scripts** — machine-parseable output for automation  

---

## 3. Metrics Definition

### Turn Count
**What:** Number of user turns processed by the orchestrator.  
**Source:** orchestrator logs, `POST /turns` endpoint handler  
**Extraction:** Count log lines matching:
```regex
session=<SESSION_ID>.*POST /turns.*status.*2\d\d
```
(Reuse grep pattern from `session-review.sh`)

**Confidence:** Exact — one log line per turn event received.

### Whisper Acknowledgment Count
**What:** Number of agent whisper POST requests that returned `202 Accepted`.  
**Source:** orchestrator logs, `_call_agent()` handler  
**Extraction:** Count warnings/info messages matching:
```regex
session=<SESSION_ID>.*Agent.*returned 202
```
Also count missing 202s (timeouts, errors, non-202 status) as **ack failures**.

**Confidence:** Best-effort — logs only non-202s and exceptions, so count may underestimate.

### Whisper Delivery Count
**What:** Number of whisper messages successfully delivered to router-service `/sessions/{id}/whisper` endpoint.  
**Source:** router-service logs, `inject_whisper()` handler success (no exception logged)  
**Extraction:** Monitor orchestrator's callback POST logs matching:
```regex
session=<SESSION_ID>.*POST /sessions.*whisper.*200
```

Alternatively: infer from absence of error logs in router-service for that session/whisper pair.

**Confidence:** High — successful HTTP 200 response or absence of logged exception.

### Delivery Rate
**What:** `(Delivered / Acks) * 100%`  
**Handling:** If acks = 0, rate is undefined; show `—%` or `0%` with `[—]` status.

### Session ID
**What:** Unique identifier for the current session.  
**Source:** router-service logs at `POST /sessions` or WebSocket `/sessions/{id}/audio` connect.  
**Extraction:** Grep or parse first line matching the session creation pattern.  
**Argument fallback:** Accept as CLI argument `session_id` if logging it is not feasible.

---

## 4. Update Mechanism

### Polling Strategy
- **Interval:** 3 seconds per refresh cycle  
- **Window:** Use `docker logs --since <timestamp>` with a rolling 10–15 second lookback window to avoid re-reading the entire log  
- **Blocking:** Poll in a loop, not as a streaming connection — allows clean exit on Ctrl+C and avoids complexity of live `docker logs --follow`

### Implementation Pattern

```bash
# Pseudocode
session_id=$(discover_session_id)
last_check=$(date -u +%s)

while true:
  now=$(date -u +%s)
  docker logs --since $((now - 15))s <service> | parse_metrics(session_id)
  last_check=$now
  sleep 3
done
```

### Efficiency Considerations
- Lookback window ≥ 2× the polling interval to avoid race conditions at boundary  
- Grep filters applied **before** output to shell (not after piping to dashboard) to minimize I/O  
- Single `docker logs` call per service per cycle (not separate calls per metric)

---

## 5. Integration Point

### Script Location
`scripts/session-dashboard.sh`

### Invocation
```bash
# With auto-detection
./scripts/session-dashboard.sh

# With explicit session ID
./scripts/session-dashboard.sh abc123

# With custom refresh interval (seconds)
./scripts/session-dashboard.sh --session abc123 --interval 2
```

### Relationship to Existing Tools
- **`dev-logs.sh`:** General log tail for debugging. Dashboard is orthogonal — follows specific metrics, not ad-hoc inspection.  
- **`session-review.sh`:** Post-session analysis (run after close). Dashboard is live (run during session).  
- **Docker compose:** Both use same container references; dashboard assumes `docker compose` is running.

### Output
- Prints single-line status to stdout  
- Refreshes in place using `\r` (carriage return, no newline) for clean terminal UI  
- On Ctrl+C: print final metrics and exit cleanly  
- On session close (detected by session ID disappearing from logs): print final summary and exit

---

## 6. Scope Boundary

### NOT in Scope (E6-M)

- **Browser rendering** — deferred; dashboard is terminal-only  
- **TDD validation status** — deferred to E6-C (integration with test framework)  
- **Historical data or session comparison** — single live session only  
- **External alerts** (Slack, email, desktop notification) — terminal output only  
- **Agent-specific whisper analysis** — aggregated delivery rate only, not per-agent breakdown  
- **Audio quality metrics** — out of scope for voice router  
- **Latency / timing analysis** — would require precise timestamp logging; deferred  

### Future Enhancements
- Per-agent delivery tracking (E6-C or later)  
- Integration with test harness for TDD status injection  
- Multi-session comparison view  
- Export metrics to file (JSON/CSV) for post-session analysis integration

---

## 7. Success Criteria

1. **Script runs without error** during an active session and displays metrics with ≤3s lag  
2. **Session ID is correctly identified** from router-service logs or accepted as argument  
3. **Turn count is accurate** (matches POST /turns count in orchestrator logs)  
4. **Delivery rate reflects reality** — when a whisper fails, rate drops; when delivered, rate updates  
5. **Status indicator [OK]/[WARN] toggles correctly** at the 80% threshold  
6. **Clean exit** on session close or Ctrl+C without leaving zombie processes  

---

## Implementation Notes

- Reuse log patterns from `session-review.sh` where possible for consistency  
- Test with a short session (3–5 turns) to validate metric accuracy  
- Log parsing should be defensive (grep/awk, no assumption of log format stability)  
- Session ID extraction: prioritize CLI argument over log parsing for reliability
