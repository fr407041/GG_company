#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

find_project_root() {
  if [[ -n "${AI_COMPANY_PROJECT_ROOT:-}" ]]; then
    cd "${AI_COMPANY_PROJECT_ROOT}" && pwd
    return
  fi
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    git rev-parse --show-toplevel
    return
  fi
  pwd
}

PROJECT_ROOT="$(find_project_root)"
DASHBOARD_DIR="${AI_COMPANY_DASHBOARD_DIR:-${PROJECT_ROOT}/agent_os_mvp}"

test -d "${SKILL_DIR}/assets/agent_os_mvp"
test -f "${DASHBOARD_DIR}/backend/requirements.txt"
test -f "${DASHBOARD_DIR}/frontend/package.json"
test -x "${DASHBOARD_DIR}/backend/.venv/bin/python"
test -d "${DASHBOARD_DIR}/frontend/node_modules"

if command -v curl >/dev/null 2>&1; then
  curl -fsS "http://127.0.0.1:8010/health" >/dev/null
fi

echo "Dashboard smoke check passed."
