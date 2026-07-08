#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/logs"
BACKEND_PORT="${BACKEND_PORT:-8010}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"

mkdir -p "$LOG_DIR"
"$ROOT_DIR/stop-dashboard.sh" >/dev/null 2>&1 || true

port_busy() {
  local port="${1:?port required}"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | awk '{print $4 " " $NF}' | grep -Eq "[:.]${port}[[:space:]]"
    return
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN
    return
  fi
  return 1
}

assert_port_free() {
  local label="${1:?label required}"
  local port="${2:?port required}"
  if port_busy "$port"; then
    echo "${label} port ${port} is already in use. Refusing to start because this could open the wrong dashboard workspace." >&2
    echo "Stop the owning process or choose another port, for example:" >&2
    echo "  BACKEND_PORT=8014 FRONTEND_PORT=5180 ./start-dashboard.sh" >&2
    exit 1
  fi
}

assert_port_free "Backend" "$BACKEND_PORT"
assert_port_free "Frontend" "$FRONTEND_PORT"

cd "$BACKEND_DIR"
if [ ! -x ".venv/bin/python" ]; then
  echo "backend virtualenv not found: $BACKEND_DIR/.venv"
  exit 1
fi
nohup .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" \
  >"$LOG_DIR/backend-${BACKEND_PORT}.out.log" 2>"$LOG_DIR/backend-${BACKEND_PORT}.err.log" &
echo $! > "$LOG_DIR/backend.pid"

cd "$FRONTEND_DIR"
nohup env VITE_API_BASE_URL="http://127.0.0.1:${BACKEND_PORT}" npm run dev --host 127.0.0.1 --port "$FRONTEND_PORT" \
  >"$LOG_DIR/frontend-${FRONTEND_PORT}.out.log" 2>"$LOG_DIR/frontend-${FRONTEND_PORT}.err.log" &
echo $! > "$LOG_DIR/frontend.pid"

echo "Backend:  http://127.0.0.1:${BACKEND_PORT}"
echo "Frontend: http://127.0.0.1:${FRONTEND_PORT}"
echo "Logs:     $LOG_DIR"
