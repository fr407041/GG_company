#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAYBOOK_SCRIPTS_DIR="${ROOT_DIR}/deliverables/codex-claude-server-playbook/scripts"
SPEC_PATH="${1:-${ROOT_DIR}/docs/ai_specs/common-research-summary-example.json}"
MODE="${2:-live}"
CCR_HEALTH_URL="${CCR_HEALTH_URL:-http://127.0.0.1:3456/health}"

export AI_COMPANY_WORKER_SCRIPTS_DIR="${PLAYBOOK_SCRIPTS_DIR}"
export CLAUDE_MODEL_ALIAS="${CLAUDE_MODEL_ALIAS:-sonnet}"
export CLAUDE_TOOLS_VALUE="${CLAUDE_TOOLS_VALUE-}"
export CCR_PREFERRED_MODEL="${CCR_PREFERRED_MODEL:-qwen2.5-coder:3b}"
export CCR_MAX_OUTPUT_TOKENS="${CCR_MAX_OUTPUT_TOKENS:-1024}"

if [[ -f "${ROOT_DIR}/.claude/settings.worker.json" && -z "${CLAUDE_CHILD_SETTINGS_PATH:-}" ]]; then
  export CLAUDE_CHILD_SETTINGS_PATH="${ROOT_DIR}/.claude/settings.worker.json"
fi

if [[ "${ALLOW_AUTOSTART:-0}" == "1" ]]; then
  if [[ -n "${START_CCR_BIN:-}" ]]; then
    bash -lc "${START_CCR_BIN}"
  elif [[ -x "${PLAYBOOK_SCRIPTS_DIR}/start_ccr.sh" ]]; then
    bash "${PLAYBOOK_SCRIPTS_DIR}/start_ccr.sh"
  else
    echo "ALLOW_AUTOSTART=1 was set, but START_CCR_BIN is not configured and no generic start_ccr.sh exists." >&2
    exit 1
  fi
fi

if command -v curl >/dev/null 2>&1; then
  if ! curl -fsS "${CCR_HEALTH_URL}" >/dev/null 2>&1; then
    cat >&2 <<EOF
Claude Code Router is not reachable at ${CCR_HEALTH_URL}.
Start your existing router first, or re-run with:
  ALLOW_AUTOSTART=1 START_CCR_BIN='<your existing router start command>'
EOF
    exit 1
  fi
fi

cd "${ROOT_DIR}"
python3 "${ROOT_DIR}/scripts/run_ai_company_task_harness.py" "${SPEC_PATH}" --mode "${MODE}"
