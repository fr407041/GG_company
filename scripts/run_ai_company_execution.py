from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from shutil import which

from ai_company_contracts import (
    append_contract_event,
    clean_json_payload,
    ensure_failure_family,
    load_defaults,
    validate_status_payload,
    write_guard_report,
    write_json,
)
from subagent_claim_ledger import write_claim_ledger


ROOT = Path(__file__).resolve().parent.parent
DELIVERABLES_SCRIPTS_DIR = ROOT / "deliverables" / "codex-claude-server-playbook" / "scripts"
CHECKPOINT_JSON_NAME = "main_agent_memory_checkpoint.json"
CHECKPOINT_MD_NAME = "main_agent_memory_checkpoint.md"
CLAIM_LEDGER_NAME = "subagent_claim_ledger.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_memory_checkpoint(run_dir: Path) -> dict:
    path = run_dir / "ai_company" / CHECKPOINT_JSON_NAME
    if not path.exists():
        return {}
    try:
        return read_json(path)
    except json.JSONDecodeError:
        return {}


def checkpoint_reassignment_note(run_dir: Path) -> str:
    checkpoint = read_memory_checkpoint(run_dir)
    claim_ledger_path = run_dir / "ai_company" / CLAIM_LEDGER_NAME
    claim_ledger_note = (
        f"Claim ledger file: {claim_ledger_path}\n"
        "Use claim ledger plus the current task as the handoff source. Do not replay full raw logs.\n"
        if claim_ledger_path.exists()
        else ""
    )
    if not checkpoint:
        return claim_ledger_note
    md_path = run_dir / "ai_company" / CHECKPOINT_MD_NAME
    return (
        "\nMAIN_AGENT_MEMORY_CHECKPOINT_AVAILABLE.\n"
        f"Checkpoint file: {md_path}\n"
        f"Checkpoint phase: {checkpoint.get('current_phase', '')}\n"
        f"Next recommended action: {checkpoint.get('next_recommended_action', '')}\n"
        f"{claim_ledger_note}"
        "Use this checkpoint as condensed prior state. Do not request or replay full prior logs.\n"
    )


def resolve_worker_script(script_name: str, local_scripts_dir: Path) -> Path:
    env_dir = os.environ.get("AI_COMPANY_WORKER_SCRIPTS_DIR", "").strip()
    candidates: list[Path] = []
    candidates.append(local_scripts_dir / script_name)
    if env_dir:
        candidates.append(Path(env_dir) / script_name)
    candidates.append(DELIVERABLES_SCRIPTS_DIR / script_name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path()


def finalize_status(run_dir: Path, status_path: Path, payload: dict) -> Path:
    errors = validate_status_payload(payload)
    payload["contract_valid"] = not errors
    if errors:
        payload["status"] = "FAILED"
        payload["failure_family"] = ensure_failure_family(payload.get("failure_family", "SCHEMA_INVALID"))
    write_json(status_path, payload)
    append_contract_event(
        run_dir,
        f"results/{status_path.name}",
        not errors,
        errors,
        payload.get("failure_family", "SCHEMA_INVALID") if errors else "",
    )
    return status_path


def ensure_status_file(job: dict, status_path: Path) -> Path:
    if status_path.exists():
        payload = read_json(status_path)
        payload.setdefault("raw_output_parse_status", "exact")
        payload.setdefault("format_cleaning_applied", False)
        payload.setdefault("contract_valid", True)
        payload.setdefault("failure_family", "")
        return finalize_status(Path(job.get("run_dir", status_path.parents[1])), status_path, payload)

    prefix = status_path.with_suffix("")
    raw_path = prefix.with_suffix(".raw.txt")
    log_path = prefix.with_suffix(".exec.log")
    raw = raw_path.read_text(encoding="utf-8", errors="ignore") if raw_path.exists() else ""
    log = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
    combined = "\n".join([raw, log])
    lowered = combined.lower()

    status = "FAILED"
    note = "worker exited before writing a status file"
    if "CHILD_TIMEOUT" in combined:
        status = "CHILD_TIMEOUT"
        note = "worker timed out before writing status metadata"
    elif "CHILD_LIMIT_REACHED" in combined:
        status = "CHILD_LIMIT_REACHED"
        note = "worker hit the child limit before writing status metadata"
    elif (
        "ROUTER_ERROR" in combined
        or "connection refused" in lowered
        or "connection reset" in lowered
        or "upstream unavailable" in lowered
        or "empty response from router" in lowered
        or "econnreset" in lowered
    ):
        status = "ROUTER_ERROR"
        note = "router transport or upstream failure blocked the child request"
    elif (
        "OVERFLOW_DETECTED" in combined
        or "maximum context length" in lowered
        or "output tokens" in lowered
        or "context window" in lowered
        or "token overflow" in lowered
    ):
        status = "OVERFLOW_DETECTED"
        note = "worker overflowed before writing status metadata"
    elif "NEEDS_REPLAN" in combined:
        status = "NEEDS_REPLAN"
        note = "worker requested replan before writing status metadata"

    payload = {
        "id": job.get("id", status_path.stem.replace(".status", "")),
        "status": status,
        "scope_path": job.get("scope_path", ""),
        "require_change": job.get("require_change", False),
        "files": job.get("files", []),
        "owner_role": job.get("owner_role", ""),
        "actual_changed_files": [],
        "actual_changed_count": 0,
        "verification_note": note,
        "subagent_summary": note,
        "key_claims": [{"claim": note}],
        "confidence": "low",
        "limitations": [note],
        "handoff_next": "Replan or repair this task before relying on its output.",
        "raw_file": str(raw_path),
        "exec_log_file": str(log_path),
        "success_check": job.get("success_check", ""),
        "test_command": job.get("test_command", ""),
        "test_executed_command": job.get("test_command", ""),
        "test_output_file": str(prefix.with_suffix(".test.txt")),
        "test_exit_code": 0,
        "exit_code": 1 if status == "FAILED" else 0,
        "duration_sec": 0,
        "raw_output_parse_status": "derived_from_logs",
        "format_cleaning_applied": False,
        "contract_valid": True,
        "failure_family": "" if status not in {"FAILED", "CHILD_TIMEOUT", "CHILD_LIMIT_REACHED", "ROUTER_ERROR", "OVERFLOW_DETECTED", "NEEDS_REPLAN"} else (
            "WORKER_RUNTIME_MISSING" if "runtime" in note else
            "FORMAT_INVALID" if "status metadata" in note else
            ""
        ),
    }
    return finalize_status(Path(job.get("run_dir", status_path.parents[1])), status_path, payload)


def choose_worker_script(scripts_dir: Path, job: dict) -> Path:
    worker_template = str(job.get("worker_template", "")).strip().lower()
    if worker_template == "summary_markdown":
        return resolve_worker_script("worker_claude_router_summary_template.sh", scripts_dir)
    owner_role = str(job.get("owner_role", ""))
    files = list(job.get("files", []))
    require_change = bool(job.get("require_change", False))
    if require_change and len(files) == 1:
        return resolve_worker_script("worker_claude_router_managed_single_file.sh", scripts_dir)
    if owner_role in {"research_agent", "synthesis_agent"}:
        return resolve_worker_script("worker_claude_router.sh", scripts_dir)
    return resolve_worker_script("worker_claude_router.sh", scripts_dir)


def local_to_container_path(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise RuntimeError(f"Path is outside workspace root and cannot be mounted into docker worker: {path}") from exc
    return "/workspace/" + relative.as_posix()


def should_use_docker_workers() -> bool:
    if os.environ.get("AI_COMPANY_USE_DOCKER_WORKERS", "").strip() == "1":
        return True
    if os.name == "nt":
        return True
    return False


def run_worker_via_docker(run_dir: Path, worker_script: Path, job_path: Path) -> int:
    docker_bin = os.environ.get("AI_COMPANY_DOCKER_BIN", "docker")
    image = os.environ.get("AI_COMPANY_DOCKER_IMAGE", "claude-ccr:ubuntu22")
    docker_config = Path(os.environ.get("AI_COMPANY_DOCKER_CONFIG", str(ROOT / "tmp" / "docker-config")))
    docker_config.mkdir(parents=True, exist_ok=True)

    local_job = read_json(job_path)
    container_job = dict(local_job)
    container_job["scope_path"] = local_to_container_path(Path(str(local_job.get("scope_path", run_dir / "worktree"))))
    container_job_path = job_path.with_name(f"{job_path.stem}.docker.json")
    write_json(container_job_path, container_job)

    container_script = local_to_container_path(worker_script)
    container_job_file = local_to_container_path(container_job_path)

    env = os.environ.copy()
    env["DOCKER_CONFIG"] = str(docker_config)

    cmd = [
        docker_bin,
        "run",
        "--rm",
        "--add-host=host.docker.internal:host-gateway",
        "-v",
        f"{ROOT}:/workspace",
        "-e",
        f"CCR_PREFERRED_MODEL={env.get('CCR_PREFERRED_MODEL', 'qwen2.5-coder:3b')}",
        "-e",
        f"CCR_MAX_OUTPUT_TOKENS={env.get('CCR_MAX_OUTPUT_TOKENS', '1024')}",
        "-e",
        f"CLAUDE_MODEL_ALIAS={env.get('CLAUDE_MODEL_ALIAS', 'sonnet')}",
        "-e",
        f"CLAUDE_CHILD_TIMEOUT_SEC={env.get('CLAUDE_CHILD_TIMEOUT_SEC', '600')}",
        "-e",
        f"CLAUDE_TOOLS_VALUE={env.get('CLAUDE_TOOLS_VALUE', '')}",
        "-e",
        "ANTHROPIC_AUTH_TOKEN=local-test-key",
        "-e",
        "ANTHROPIC_BASE_URL=http://127.0.0.1:3456",
        image,
        "bash",
        "-lc",
        f"cd /workspace && bash {container_script} {container_job_file}",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    return proc.returncode


def fallback_owner_role(files: list[str], current_owner: str) -> str:
    lowered = [item.lower() for item in files]
    if any(item.endswith((".md", ".txt", ".rst", ".json")) for item in lowered):
        return "executor_docs" if current_owner != "executor_docs" else "research_agent"
    if any(item.endswith((".py", ".sh", ".js", ".ts")) for item in lowered):
        return "executor_backend" if current_owner != "executor_backend" else "research_agent"
    return "research_agent"


def sync_assignments_to_jobs(run_dir: Path, assignments: list[dict]) -> dict[str, Path]:
    jobs_dir = run_dir / "jobs"
    job_map: dict[str, Path] = {}
    for path in sorted(jobs_dir.glob("job-*.json")):
        job_map[path.stem] = path
        payload = read_json(path)
        job_map[payload.get("id", path.stem)] = path

    for item in assignments:
        if item["owner_role"] == "reviewer_worker":
            continue
        job_path = job_map.get(item["task_id"])
        if not job_path:
            continue
        payload = read_json(job_path)
        payload["owner_role"] = item["owner_role"]
        payload["depends_on"] = item.get("depends_on", [])
        payload["acceptance_criteria"] = item.get("acceptance_criteria", [])
        payload["fallback_plan"] = item.get("fallback_plan", "")
        payload["files"] = item.get("scope", payload.get("files", []))
        write_json(job_path, payload)
    return job_map


def write_mock_status(run_dir: Path, job: dict, status: str, verification_note: str, changed_count: int = 0) -> Path:
    results_dir = run_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    prefix = results_dir / job["id"]
    raw_file = prefix.with_suffix(".raw.txt")
    test_file = prefix.with_suffix(".test.txt")
    status_file = prefix.with_suffix(".status.json")
    raw_file.write_text(f"STATUS: {status}\nFILES: {', '.join(job.get('files', []))}\nSUMMARY: mock execution\n", encoding="utf-8")
    test_file.write_text("mock test output\n", encoding="utf-8")
    actual_changed_files = job.get("files", [])[:changed_count]
    if status == "SUCCESS" and str(job.get("worker_template", "")).strip().lower() == "summary_markdown":
        scope_path = Path(str(job.get("scope_path", run_dir / "worktree")))
        summary_path = scope_path / "summary.md"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            "\n".join(
                [
                    "- The migration pilot reduced cycle time from 95 minutes to 28 minutes, which supports continuing a bounded rollout while tracking uncertainty.",
                    "- Weekly incidents moved from 14 per week to 5 per week, so the pilot signal is useful but should still be verified against operational risk.",
                    "- Rollback readiness remains the key control: keep owners, monitoring, and a reversible release path before expanding migration scope.",
                    "Takeaway: proceed with a cautious pilot expansion, but keep rollback and uncertainty gates active.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        actual_changed_files = ["summary.md"]
    payload = {
        "id": job["id"],
        "status": status,
        "scope_path": job.get("scope_path", ""),
        "require_change": job.get("require_change", False),
        "files": job.get("files", []),
        "owner_role": job.get("owner_role", ""),
        "actual_changed_files": actual_changed_files,
        "actual_changed_count": len(actual_changed_files),
        "verification_note": verification_note,
        "subagent_summary": "Mock worker produced a bounded result for reviewer validation.",
        "key_claims": [
            {
                "claim": verification_note if status != "SUCCESS" else "Mock worker completed the assigned bounded task successfully.",
                "evidence_refs": [str(raw_file.name)],
            }
        ],
        "confidence": "medium" if status == "SUCCESS" else "low",
        "limitations": [] if status == "SUCCESS" else [verification_note],
        "handoff_next": "Use the claim ledger entry and changed artifact for review.",
        "raw_file": str(raw_file),
        "exec_log_file": str(raw_file),
        "success_check": job.get("success_check", ""),
        "test_command": job.get("test_command", ""),
        "test_executed_command": job.get("test_command", ""),
        "test_output_file": str(test_file),
        "test_exit_code": 0,
        "exit_code": 0,
        "duration_sec": 1,
        "raw_output_parse_status": "mock",
        "format_cleaning_applied": False,
        "contract_valid": True,
        "failure_family": "",
    }
    return finalize_status(run_dir, status_file, payload)


def write_runtime_missing_status(run_dir: Path, job: dict, worker_script: Path) -> Path:
    results_dir = run_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    status_path = results_dir / f"{job['id']}.status.json"
    payload = {
        "id": job["id"],
        "status": "FAILED",
        "scope_path": job.get("scope_path", ""),
        "require_change": job.get("require_change", False),
        "files": job.get("files", []),
        "owner_role": job.get("owner_role", ""),
        "actual_changed_files": [],
        "actual_changed_count": 0,
        "verification_note": f"worker runtime missing: {worker_script.name or 'unresolved worker'}",
        "subagent_summary": "worker runtime missing",
        "key_claims": [{"claim": "Worker runtime is unavailable for this execution."}],
        "confidence": "low",
        "limitations": ["Worker runtime unavailable"],
        "handoff_next": "Install or point AI_COMPANY_WORKER_SCRIPTS_DIR to worker scripts before rerun.",
        "raw_file": str(results_dir / f"{job['id']}.raw.txt"),
        "exec_log_file": str(results_dir / f"{job['id']}.exec.log"),
        "success_check": job.get("success_check", ""),
        "test_command": job.get("test_command", ""),
        "test_executed_command": "",
        "test_output_file": str(results_dir / f"{job['id']}.test.txt"),
        "test_exit_code": 1,
        "exit_code": 1,
        "duration_sec": 0,
        "raw_output_parse_status": "worker_runtime_missing",
        "format_cleaning_applied": False,
        "contract_valid": True,
        "failure_family": "WORKER_RUNTIME_MISSING",
    }
    return finalize_status(run_dir, status_path, payload)


def normalize_status_artifact(run_dir: Path, job: dict, status_path: Path) -> Path:
    payload = read_json(status_path)
    raw_file = Path(str(payload.get("raw_file", "")))
    raw_text = raw_file.read_text(encoding="utf-8", errors="ignore") if raw_file.exists() else ""
    cleaned = clean_json_payload(raw_text) if raw_text else {"parse_status": "missing", "format_cleaning_applied": False}
    payload.setdefault("id", job["id"])
    payload.setdefault("scope_path", job.get("scope_path", ""))
    payload.setdefault("files", job.get("files", []))
    payload.setdefault("owner_role", job.get("owner_role", ""))
    payload.setdefault("verification_note", "")
    payload["raw_output_parse_status"] = cleaned.get("parse_status", "missing")
    payload["format_cleaning_applied"] = bool(cleaned.get("format_cleaning_applied", False))
    payload.setdefault("failure_family", "")
    if payload["status"] == "SUCCESS" and cleaned.get("parse_status") in {"invalid_json", "truncated_json"}:
        payload["status"] = "FAILED"
        payload["failure_family"] = "FORMAT_INVALID"
        payload["verification_note"] = (str(payload.get("verification_note", "")).strip() + " | raw output malformed").strip(" |")
    return finalize_status(run_dir, status_path, payload)


def execute_job(run_dir: Path, scripts_dir: Path, job_path: Path) -> Path:
    job = read_json(job_path)
    job["run_dir"] = str(run_dir)
    results_dir = run_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    status_path = results_dir / f"{job['id']}.status.json"

    if os.environ.get("AI_COMPANY_EXECUTION_MOCK", "0") == "1":
        mock_status = job.get("mock_status", "SUCCESS")
        note_map = {
            "SUCCESS": "mock success",
            "NEEDS_REPLAN": "worker requested replan in mock mode",
            "FAILED": "mock failure",
            "OVERFLOW_DETECTED": "mock overflow",
        }
        changed_count = 1 if mock_status == "SUCCESS" and job.get("require_change") else 0
        return write_mock_status(run_dir, job, mock_status, note_map.get(mock_status, "mock status"), changed_count)

    worker_script = choose_worker_script(scripts_dir, job)
    defaults = load_defaults()
    runtime_required = bool(defaults.get("worker_runtime_required", True))
    if runtime_required and (not worker_script or not worker_script.exists()):
        return write_runtime_missing_status(run_dir, job, worker_script)
    if should_use_docker_workers():
        run_worker_via_docker(run_dir, worker_script, job_path)
    else:
        bash_bin = which("bash") or "bash"
        subprocess.run([bash_bin, str(worker_script), str(job_path)], cwd=run_dir, check=False)
    status_path = ensure_status_file(job, status_path)
    return normalize_status_artifact(run_dir, job, status_path)


def run_reviewer(run_dir: Path, scripts_dir: Path) -> dict:
    reviewer_script = scripts_dir / "run_ai_company_reviewer_worker.py"
    reviewer_out = run_dir / "ai_company" / "reviewer_verdicts.json"
    subprocess.run([sys.executable, str(reviewer_script), str(run_dir), str(reviewer_out)], check=True)
    return read_json(reviewer_out)


def create_reassignment_job(run_dir: Path, source_job: dict, verdict: dict, attempt: int) -> Path:
    jobs_dir = run_dir / "jobs"
    new_id = f"{source_job['id']}-reassign-{attempt:02d}"
    narrowed_files = list(source_job.get("files", []))[:1] or list(source_job.get("files", []))
    owner_role = fallback_owner_role(narrowed_files, source_job.get("owner_role", "research_agent"))
    payload = dict(source_job)
    payload["id"] = new_id
    payload["title"] = f"{source_job.get('title', source_job['id'])} reassigned {attempt}"
    payload["instruction"] = (
        "REASSIGNMENT after reviewer verdict.\n"
        f"Previous verdict: {verdict['verdict']}.\n"
        "Work on the smallest safe scope only and satisfy the original acceptance criteria.\n\n"
        f"{checkpoint_reassignment_note(run_dir)}\n"
        f"Original instruction:\n{source_job.get('instruction', '')}"
    )
    payload["files"] = narrowed_files
    payload["owner_role"] = owner_role
    payload["force_worker_mode"] = "managed_single_file" if len(narrowed_files) == 1 and payload.get("require_change", False) else "auto"
    if os.environ.get("AI_COMPANY_EXECUTION_MOCK", "0") == "1":
        payload["mock_status"] = "SUCCESS"
    new_path = jobs_dir / f"{new_id}.json"
    write_json(new_path, payload)
    return new_path


def build_summary(run_dir: Path, execution_log: list[dict], reviewer: dict, reassignment_count: int) -> dict:
    accepted = reviewer.get("accepted_count", 0)
    total = reviewer.get("verdict_count", 0)
    failure_families: dict[str, int] = {}
    contract_events = read_json(run_dir / "ai_company" / "contract_validation_report.json").get("events", [])
    for event in contract_events:
        family = event.get("failure_family", "")
        if family:
            failure_families[family] = failure_families.get(family, 0) + 1
    return {
        "run_id": run_dir.name,
        "execution_jobs_run": len(execution_log),
        "reassignment_count": reassignment_count,
        "accepted_count": accepted,
        "reviewer_verdict_count": total,
        "acceptance_rate": round(accepted / total, 3) if total else 0.0,
        "execution_log": execution_log,
        "contract_invalid_count": sum(1 for event in contract_events if not event.get("ok", False)),
        "failure_families": failure_families,
    }


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: run_ai_company_execution.py <run_dir> [out_file]")
    run_dir = Path(sys.argv[1]).resolve()
    out_file = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else run_dir / "ai_company" / "execution_summary.json"
    scripts_dir = Path(__file__).resolve().parent
    meeting_path = run_dir / "ai_company" / "meeting_decision.json"
    meeting = read_json(meeting_path)
    assignments = meeting.get("task_assignments", [])
    job_map = sync_assignments_to_jobs(run_dir, assignments)

    execution_log: list[dict] = []
    non_review_tasks = [item for item in assignments if item.get("owner_role") != "reviewer_worker"]
    for item in non_review_tasks:
        job_path = job_map.get(item["task_id"])
        if not job_path:
            continue
        execute_job(run_dir, scripts_dir, job_path)
        write_claim_ledger(run_dir)
        execution_log.append({"task_id": item["task_id"], "owner_role": item["owner_role"], "mode": "initial"})

    write_claim_ledger(run_dir)
    reviewer = run_reviewer(run_dir, scripts_dir)
    reassignment_count = 0
    max_reassign = int(os.environ.get("AI_COMPANY_MAX_REASSIGNMENTS_PER_RUN", "1"))
    attempt = 1
    while attempt <= max_reassign:
        actionable = [
            verdict for verdict in reviewer.get("verdicts", [])
            if verdict.get("verdict") in {"REPLAN_REQUIRED", "REPAIR_REQUIRED", "FALSE_SUCCESS_BLOCKED"} and not verdict["task_id"].endswith("-review")
        ]
        if not actionable:
            break
        for verdict in actionable:
            source_path = job_map.get(verdict["task_id"])
            if not source_path:
                continue
            source_job = read_json(source_path)
            reassigned_job_path = create_reassignment_job(run_dir, source_job, verdict, attempt)
            job_map[reassigned_job_path.stem] = reassigned_job_path
            job_map[read_json(reassigned_job_path)["id"]] = reassigned_job_path
            execute_job(run_dir, scripts_dir, reassigned_job_path)
            write_claim_ledger(run_dir)
            reassignment_count += 1
            execution_log.append(
                {
                    "task_id": read_json(reassigned_job_path)["id"],
                    "owner_role": read_json(reassigned_job_path)["owner_role"],
                    "mode": "reassignment",
                    "source_task_id": verdict["task_id"],
                }
            )
        write_claim_ledger(run_dir)
        reviewer = run_reviewer(run_dir, scripts_dir)
        attempt += 1

    summary = build_summary(run_dir, execution_log, reviewer, reassignment_count)
    write_json(out_file, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
