#!/usr/bin/env bash
# session-review.sh — prepare a compact session review bundle for Claude
#
# Usage:
#   ./scripts/session-review.sh              # latest session
#   ./scripts/session-review.sh c20a         # session matching ID prefix
#
# Output: structured summary of transcript + log metrics, optimised for
# minimal token use when feeding to the meeting-analyzer skill.

set -euo pipefail

TRANSCRIPTS_DIR="$(cd "$(dirname "$0")/.." && pwd)/transcripts"

# ── resolve transcript ────────────────────────────────────────────────────────
if [[ $# -eq 0 ]]; then
  transcript=$(ls -t "$TRANSCRIPTS_DIR"/*.md 2>/dev/null | head -1)
  [[ -z "$transcript" ]] && { echo "No transcripts found in $TRANSCRIPTS_DIR" >&2; exit 1; }
else
  prefix="$1"
  transcript=$(ls -t "$TRANSCRIPTS_DIR"/*.md 2>/dev/null | grep "$prefix" | head -1)
  [[ -z "$transcript" ]] && { echo "No transcript matching '$prefix' in $TRANSCRIPTS_DIR" >&2; exit 1; }
fi

filename=$(basename "$transcript")
session_id=$(grep -m1 "^# Session Transcript:" "$transcript" | awk '{print $NF}')
short_id="${session_id:0:8}"

# ── compute log metrics ───────────────────────────────────────────────────────
# Pull the full container log once — a fixed tail is unreliable when debug-level
# logging is active (the combined stream is dominated by router-service debug
# lines, pushing turn/whisper lines beyond any reasonable tail count).
all_logs=$(docker compose logs 2>/dev/null \
  | grep -v "GET /health\|/healthz" || true)
session_logs=$(echo "$all_logs" | grep "$short_id" || true)

# Counts that don't include session ID in the log line — use full log tail
turns=$(echo "$all_logs"        | grep -c "POST /turns.*202"     || true)
timeouts=$(echo "$all_logs"     | grep -c "ReadTimeout"          || true)
whisper_acks=$(echo "$all_logs" | grep -c "POST /whisper.*202"   || true)
ingest=$(echo "$session_logs"   | grep -c "ingest.*session=$short_id" || true)

# Counts that include session ID — filter to this session only
whisper_delivered=$(echo "$session_logs" | grep -c "POST /sessions.*whisper.*200" || true)
whisper_404=$(echo "$session_logs"       | grep -c "POST /sessions.*whisper.*404" || true)

# ── output ────────────────────────────────────────────────────────────────────
cat <<EOF
SESSION: $short_id | $filename
TRANSCRIPT: $transcript

--- LOG METRICS ---
Turns processed : $turns (all should be 202)
Timeouts        : $timeouts (should be 0)
Whisper acks    : $whisper_acks (dev-coach acknowledged dispatch)
Whispers delivered : $whisper_delivered (router received callback)
Post-close 404s : $whisper_404 (late callbacks after session close — expected)
Ingest calls    : $ingest

--- TRANSCRIPT ---
EOF

cat "$transcript"
