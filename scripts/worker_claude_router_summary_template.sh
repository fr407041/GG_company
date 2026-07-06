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
scope_path = Path(str(job.get("scope_path", run_dir / "worktree")))
scope_path.mkdir(parents=True, exist_ok=True)
summary_path = scope_path / "summary.md"
results_dir = run_dir / "results"
results_dir.mkdir(parents=True, exist_ok=True)
prefix = results_dir / job["id"]
raw_path = prefix.with_suffix(".raw.txt")
log_path = prefix.with_suffix(".exec.log")
status_path = prefix.with_suffix(".status.json")

summary_path.write_text(
    "- Local summary adapter created a bounded placeholder summary.\n"
    "- This path is intended for harness validation, not production-quality live synthesis.\n"
    "- Configure project-specific prompting before relying on this output.\n"
    "Takeaway: the local adapter is installed and can materialize the expected artifact shape.\n",
    encoding="utf-8",
)

payload = {
    "id": job["id"],
    "status": "SUCCESS",
    "scope_path": str(scope_path),
    "require_change": job.get("require_change", False),
    "files": job.get("files", []),
    "owner_role": job.get("owner_role", ""),
    "actual_changed_files": ["summary.md"],
    "actual_changed_count": 1,
    "verification_note": "Local summary template adapter created the expected bounded artifact shape.",
    "subagent_summary": "Local summary template adapter completed.",
    "key_claims": [{"claim": "summary.md was materialized by the local summary adapter.", "evidence_refs": ["summary.md"]}],
    "confidence": "medium",
    "limitations": ["Content is adapter-generated placeholder text, not model-authored research output."],
    "handoff_next": "Use this only for harness validation or replace with project-specific live prompting.",
    "raw_file": str(raw_path),
    "exec_log_file": str(log_path),
    "success_check": job.get("success_check", ""),
    "test_command": job.get("test_command", ""),
    "test_executed_command": "",
    "test_output_file": str(prefix.with_suffix(".test.txt")),
    "test_exit_code": 0,
    "exit_code": 0,
    "duration_sec": 1,
    "raw_output_parse_status": "adapter_summary_template",
    "format_cleaning_applied": False,
    "contract_valid": True,
    "failure_family": "",
}
raw_path.write_text(json.dumps({"status": payload["status"], "summary_file": "summary.md"}, ensure_ascii=False), encoding="utf-8")
log_path.write_text("summary_template_adapter\n", encoding="utf-8")
status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY
