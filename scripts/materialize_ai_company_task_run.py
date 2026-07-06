from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_company_contracts import guard_input_spec, write_guard_report

ROOT = Path(__file__).resolve().parent.parent
RUN_ROOT = ROOT / "results" / "ai_company_task_runs"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_run_id(spec_id: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return f"run-{stamp}-{spec_id}"


def materialize_run(spec_path: Path, out_root: Path | None = None) -> Path:
    spec = read_json(spec_path)
    run_root = out_root or RUN_ROOT
    run_root.mkdir(parents=True, exist_ok=True)

    run_id = build_run_id(spec["id"])
    run_dir = run_root / run_id
    jobs_dir = run_dir / "jobs"
    results_dir = run_dir / "results"
    ai_company_dir = run_dir / "ai_company"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    ai_company_dir.mkdir(parents=True, exist_ok=True)

    input_guard = guard_input_spec(spec, spec_path)
    write_guard_report(run_dir, "input_guard_report.json", input_guard)

    scope_subdir = str(spec.get("scope_subdir", "."))
    scope_path = (ROOT / scope_subdir).resolve()
    if spec.get("scope_copy_from"):
        source_scope = (ROOT / str(spec["scope_copy_from"])).resolve()
        scope_path = run_dir / "worktree"
        shutil.copytree(source_scope, scope_path)
    jobs = spec.get("jobs", [])

    plan = {
        "strategy": spec.get("strategy", "Use bounded planning before dispatch."),
        "jobs": jobs,
    }
    write_json(run_dir / "plan.json", plan)

    for job in jobs:
        payload = dict(job)
        payload["scope_path"] = str(scope_path)
        payload.setdefault("require_change", False)
        payload.setdefault("test_command", "")
        write_json(jobs_dir / f"{payload['id']}.json", payload)

    summary = {
        "run_id": run_id,
        "task": spec["goal"],
        "scope_path": str(scope_path),
        "strategy": spec.get("strategy", "Use bounded planning before dispatch."),
        "worker_mode": "task_harness",
        "planner_exit": 0,
        "planner_parse_ok": True,
        "plan_json_file": str((run_dir / "plan.json").resolve()),
        "jobs_dir": str(jobs_dir.resolve()),
        "results_dir": str(results_dir.resolve()),
        "spec_file": str(spec_path.resolve()),
        "expectations": spec.get("expectations", {}),
        "metrics": {
            "total_files_in_scope": sum(len(job.get("files", [])) for job in jobs),
            "compact_inventory_files": sum(len(job.get("files", [])) for job in jobs),
            "initial_planned_jobs": len(jobs),
            "planned_jobs_after_retries": len(jobs),
            "avg_files_per_job": f"{(sum(len(job.get('files', [])) for job in jobs) / len(jobs)):.2f}" if jobs else "0.00",
            "max_files_in_job": max((len(job.get("files", [])) for job in jobs), default=0),
            "prompt_injection_block_count": len(input_guard.get("flagged_jobs", [])),
        },
    }
    write_json(run_dir / "summary.json", summary)
    return run_dir


def main() -> None:
    import sys

    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: materialize_ai_company_task_run.py <spec_path> [out_root]")
    spec_path = Path(sys.argv[1]).resolve()
    out_root = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else None
    run_dir = materialize_run(spec_path, out_root)
    print(json.dumps({"run_dir": str(run_dir)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
