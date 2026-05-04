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

_up() {
    local build_flag="${1:-}"
    _colima_check
    echo ""
    if [ -n "$build_flag" ]; then
        echo "==> Building images and starting stack..."
        docker compose up --build
    else
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
