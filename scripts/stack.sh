#!/usr/bin/env bash
# stack.sh — manage the gcsb voice assistant stack
#
# Usage:
#   ./scripts/stack.sh              # clean stop → rebuild → start (foreground)
#   ./scripts/stack.sh up           # same
#   ./scripts/stack.sh start        # clean stop → start without rebuild (foreground)
#   ./scripts/stack.sh down         # stop all containers including orphans
#   ./scripts/stack.sh status       # show container and port status
#   ./scripts/stack.sh logs [svc]   # tail logs (all services, or one by name)
#
# "Clean" means --remove-orphans on every down/up, which catches containers
# left over from previous sessions that did not shut down properly.

set -euo pipefail

CMD="${1:-up}"
SVC="${2:-}"

_colima_check() {
    if command -v colima &>/dev/null; then
        if ! colima status 2>/dev/null | grep -q "Running"; then
            echo "==> Colima is not running — starting it"
            colima start
        fi
    fi
}

_down() {
    echo "==> Stopping all containers (including orphans)..."
    docker compose down --remove-orphans
}

_stale_build_warn() {
    # BUG-27: warn if backlog or compose config changed since images were last built.
    # DevCoach loads ROADMAP_PATH at startup — a stale image silently misses backlog
    # updates added since the last build.
    local image
    image=$(docker compose images -q dev-coach 2>/dev/null | head -1)
    [ -z "$image" ] && return

    local image_ts
    image_ts=$(docker inspect --format '{{.Created}}' "$image" 2>/dev/null | \
        python3 -c "
import sys, datetime
s = sys.stdin.read().strip()
dt = datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
print(int(dt.timestamp()))
" 2>/dev/null) || return
    [ -z "$image_ts" ] && return

    local warned=0
    for f in docs/backlog.md docker-compose.yml; do
        [ -f "$f" ] || continue
        local file_ts
        file_ts=$(python3 -c "import os; print(int(os.path.getmtime('$f')))" 2>/dev/null) || continue
        if [ "$file_ts" -gt "$image_ts" ]; then
            echo "WARNING: $f changed since dev-coach image was last built"
            warned=1
        fi
    done
    if [ "$warned" -eq 1 ]; then
        echo "         Run './scripts/stack.sh up' to rebuild with the latest config."
        echo ""
    fi
}

_up() {
    local build_flag="${1:-}"
    _colima_check
    echo ""
    if [ -n "$build_flag" ]; then
        echo "==> Building images and starting stack..."
        docker compose up --build
    else
        _stale_build_warn
        echo "==> Starting stack (no rebuild)..."
        docker compose up
    fi
}

_status() {
    echo "==> Container status"
    docker compose ps
    echo ""
    echo "==> Listening ports"
    docker compose ps --format "table {{.Service}}\t{{.Ports}}" 2>/dev/null || true
}

case "$CMD" in
    up)
        _down
        _up --build
        ;;
    start)
        _down
        _up
        ;;
    down)
        _down
        echo "==> Done."
        ;;
    status)
        _status
        ;;
    logs)
        if [ -n "$SVC" ]; then
            docker compose logs -f "$SVC"
        else
            docker compose logs -f
        fi
        ;;
    *)
        echo "Usage: $0 [up|start|down|status|logs [service]]"
        exit 1
        ;;
esac
