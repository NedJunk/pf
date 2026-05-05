#!/usr/bin/env bash
# session-dashboard.sh — live session metric dashboard (polls Docker logs)
#
# Usage:
#   ./scripts/session-dashboard.sh                         # auto-discover session
#   ./scripts/session-dashboard.sh abc12345               # explicit session ID
#   ./scripts/session-dashboard.sh --session abc12345 --interval 2

set -euo pipefail

COMPOSE_FILE="$(dirname "$0")/../docker-compose.yml"
INTERVAL=3
SESSION_ID=""
DISCOVER_TIMEOUT=60   # seconds to wait for a session to appear in logs
IDLE_TIMEOUT=30       # seconds of no new turns before declaring session closed

# ── argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --session|-s) SESSION_ID="$2"; shift 2 ;;
    --interval|-i) INTERVAL="$2"; shift 2 ;;
    --help|-h)
      grep '^#' "$0" | grep -v '#!/' | sed 's/^# \?//'
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
    *)
      # positional arg treated as session ID
      SESSION_ID="$1"
      shift
      ;;
  esac
done

# ── rolling-window log helpers ────────────────────────────────────────────────
# RFC3339 timestamp for --since
now_ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Fetch logs since a given timestamp from specified services
fetch_logs() {
  local since="$1"
  local services="${2:-router-service orchestrator dev-coach}"
  docker compose -f "$COMPOSE_FILE" logs --since "$since" $services 2>/dev/null \
    | grep -v "GET /health\|/healthz" || true
}

# ── session ID auto-discovery ─────────────────────────────────────────────────
discover_session() {
  local deadline=$(( $(date +%s) + DISCOVER_TIMEOUT ))
  local since
  since=$(now_ts)
  printf "Waiting for session..." >&2

  while [[ $(date +%s) -lt $deadline ]]; do
    local chunk
    chunk=$(fetch_logs "$since" "router-service orchestrator dev-coach")

    # Pattern: "POST /sessions/abc12345-..." or session ID embedded in log line
    # Session IDs are 8-char hex; UUIDs are longer — grab 8 chars of a UUID segment
    local found
    found=$(printf '%s\n' "$chunk" \
      | grep -oE 'POST /sessions/[0-9a-f]{8}' \
      | grep -oE '[0-9a-f]{8}$' \
      | head -1 || true)

    if [[ -n "$found" ]]; then
      printf '\r%*s\r' 40 '' >&2   # clear the "Waiting..." line
      echo "$found"
      return 0
    fi

    sleep "$INTERVAL"
  done

  echo "" >&2
  echo "No session found within ${DISCOVER_TIMEOUT}s. Is the stack running?" >&2
  exit 1
}

# ── display helpers ───────────────────────────────────────────────────────────
format_line() {
  local session="$1"
  local turns="$2"
  local acks="$3"
  local delivered="$4"

  local status pct
  if [[ "$acks" -eq 0 ]]; then
    status="[—]"
    pct=""
  else
    # integer percentage via awk
    pct=$(awk "BEGIN { printf \"%.1f\", ($delivered / $acks) * 100 }")
    if awk "BEGIN { exit ($delivered / $acks) < 0.80 }"; then
      status="[OK]"
    else
      status="[WARN]"
    fi
    pct=" ($pct%)"
  fi

  printf "Session: %s | Turns: %d | Acks: %d | Delivered: %d%s | %s" \
    "$session" "$turns" "$acks" "$delivered" "$pct" "$status"
}

print_final() {
  printf '\n'
  printf 'Final: %s\n' "$(format_line "$SESSION_ID" "$total_turns" "$total_acks" "$total_delivered")"
}

# ── signal handling ───────────────────────────────────────────────────────────
total_turns=0
total_acks=0
total_delivered=0

trap 'print_final; exit 0' INT TERM

# ── resolve session ID ────────────────────────────────────────────────────────
if [[ -z "$SESSION_ID" ]]; then
  SESSION_ID=$(discover_session)
fi

echo "Dashboard for session: $SESSION_ID  (Ctrl+C to stop)" >&2

# ── main poll loop ────────────────────────────────────────────────────────────
since=$(now_ts)
last_turn_time=$(date +%s)
had_turns=0   # set to 1 once we see the first turn

while true; do
  sleep "$INTERVAL"

  # Fetch the incremental log window
  chunk=$(fetch_logs "$since" "router-service orchestrator")

  # Advance the rolling window
  since=$(now_ts)

  # Count new events in this chunk
  new_turns=$(printf '%s\n' "$chunk" | grep -c "POST /turns.*202" || true)
  new_acks=$(printf '%s\n' "$chunk" | grep -c "POST /whisper.*202" || true)
  new_delivered=$(printf '%s\n' "$chunk" \
    | grep "$SESSION_ID" \
    | grep -c "POST /sessions.*whisper.*200" || true)

  # Accumulate
  total_turns=$(( total_turns + new_turns ))
  total_acks=$(( total_acks + new_acks ))
  total_delivered=$(( total_delivered + new_delivered ))

  # Track idle time for session-close detection
  if [[ "$new_turns" -gt 0 ]]; then
    had_turns=1
    last_turn_time=$(date +%s)
  fi

  # Render in-place
  printf '\r%-80s' "$(format_line "$SESSION_ID" "$total_turns" "$total_acks" "$total_delivered")"

  # Session-close detection: no new turns for IDLE_TIMEOUT after at least 1 turn
  if [[ "$had_turns" -eq 1 ]]; then
    idle=$(( $(date +%s) - last_turn_time ))
    if [[ "$idle" -gt "$IDLE_TIMEOUT" ]]; then
      printf '\nSession idle >%ds — session appears closed.\n' "$IDLE_TIMEOUT"
      print_final
      exit 0
    fi
  fi
done
