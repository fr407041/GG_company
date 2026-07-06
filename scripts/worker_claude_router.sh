#!/usr/bin/env bash
set -u

JOB_PATH="${1:-}"
if [ -z "$JOB_PATH" ]; then
  echo "WORKER_RUNTIME_MISSING: missing job path"
  exit 1
fi

python_bin="${PYTHON_BIN:-python3}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
  python_bin="python"
fi

"$python_bin" - "$JOB_PATH" <<'PY'
import json
import sys
from pathlib import Path

job_path = Path(sys.argv[1]).resolve()
job = json.loads(job_path.read_text(encoding="utf-8"))
run_dir = job_path.parent.parent
results_dir = run_dir / "results"
results_dir.mkdir(parents=True, exist_ok=True)
prefix = results_dir / job["id"]
raw_path = prefix.with_suffix(".raw.txt")
log_path = prefix.with_suffix(".exec.log")
status_path = prefix.with_suffix(".status.json")

runtime_available = False
for name in ("claude", "ccr"):
    from shutil import which
    if which(name):
        runtime_available = True
        break

if not runtime_available:
    raw_path.write_text("WORKER_RUNTIME_MISSING\nLocal worker adapter could not find claude or ccr.\n", encoding="utf-8")
    log_path.write_text("WORKER_RUNTIME_MISSING\n", encoding="utf-8")
    sys.exit(1)

payload = {
    "id": job["id"],
    "status": "NEEDS_REPLAN",
    "scope_path": job.get("scope_path", ""),
    "require_change": job.get("require_change", False),
    "files": job.get("files", []),
    "owner_role": job.get("owner_role", ""),
    "actual_changed_files": [],
    "actual_changed_count": 0,
    "verification_note": "Local worker adapter is present, but project-specific live prompting is not configured in this repository bundle.",
    "subagent_summary": "Adapter reached runtime but requires project-specific live prompt wiring.",
    "key_claims": [{"claim": "Adapter runtime exists but live execution wiring still needs project-specific setup.", "evidence_refs": [str(raw_path.name)]}],
    "confidence": "low",
    "limitations": ["No repository-local live prompt harness is configured yet."],
    "handoff_next": "Configure project-specific live prompting or use mock mode for regression testing.",
    "raw_file": str(raw_path),
    "exec_log_file": str(log_path),
    "success_check": job.get("success_check", ""),
    "test_command": job.get("test_command", ""),
    "test_executed_command": "",
    "test_output_file": str(prefix.with_suffix(".test.txt")),
    "test_exit_code": 0,
    "exit_code": 0,
    "duration_sec": 1,
    "raw_output_parse_status": "adapter_placeholder",
    "format_cleaning_applied": False,
    "contract_valid": True,
    "failure_family": "",
}
raw_path.write_text(json.dumps({"status": payload["status"], "note": payload["verification_note"]}, ensure_ascii=False), encoding="utf-8")
log_path.write_text("adapter_placeholder\n", encoding="utf-8")
status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY
