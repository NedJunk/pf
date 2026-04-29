#!/usr/bin/env bash
# Pull logs from all stack services for debugging.
# Usage:
#   ./scripts/dev-logs.sh                     # last 60 lines, all services
#   ./scripts/dev-logs.sh -n 200              # last 200 lines
#   ./scripts/dev-logs.sh -s router-service   # single service
#   ./scripts/dev-logs.sh -f                  # follow (tail -f mode)
#   ./scripts/dev-logs.sh -i b9a16813         # filter by session ID prefix

set -euo pipefail

TAIL=60
SERVICE=""
FOLLOW=""
SESSION=""
COMPOSE_FILE="$(dirname "$0")/../docker-compose.yml"
SERVICES="router-service orchestrator dev-coach"

while [[ $# -gt 0 ]]; do
  case $1 in
    -n) TAIL="$2"; shift 2 ;;
    -s) SERVICE="$2"; shift 2 ;;
    -f) FOLLOW="--follow"; shift ;;
    -i) SESSION="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

TARGET="${SERVICE:-$SERVICES}"

if [[ -n "$SESSION" ]]; then
  docker compose -f "$COMPOSE_FILE" logs --tail="$TAIL" $FOLLOW $TARGET 2>&1 \
    | grep -E "(^|[[:space:]])($SESSION|INFO|WARNING|ERROR)" \
    | grep -v "GET /health"
else
  docker compose -f "$COMPOSE_FILE" logs --tail="$TAIL" $FOLLOW $TARGET 2>&1 \
    | grep -v "GET /health"
fi
