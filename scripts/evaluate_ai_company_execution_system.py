from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = ROOT / "tests" / "ai_company_execution_cases.json"
OUTPUT_DIR = ROOT / "results" / "ai_company_validation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_case_run(base_dir: Path, case: dict) -> Path:
    run_dir = base_dir / case["id"]
    jobs_dir = run_dir / "jobs"
    ai_company_dir = run_dir / "ai_company"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    ai_company_dir.mkdir(parents=True, exist_ok=True)

    write_json(run_dir / "summary.json", {"run_id": case["id"], "task": case["meeting"]["goal"], "strategy": "mock execution"})
    write_json(run_dir / "plan.json", {"strategy": "mock execution", "jobs": case["jobs"]})
    write_json(ai_company_dir / "meeting_decision.json", case["meeting"])
    for job in case["jobs"]:
        payload = dict(job)
        payload["scope_path"] = str(run_dir)
        payload["test_command"] = ""
        payload["require_change"] = False
        write_json(jobs_dir / f"{job['id']}.json", payload)
        for file_name in payload["files"]:
            target = run_dir / file_name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_text("seed\n", encoding="utf-8")
    return run_dir


def evaluate() -> dict:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    tmp_root = Path(tempfile.mkdtemp(prefix="ai-company-exec-", dir=str(ROOT / "tmp")))
    rows = []
    assignment_routed = 0
    reassignment_worked = 0
    reviewer_generated = 0
    try:
        for case in cases:
            run_dir = build_case_run(tmp_root, case)
            env = os.environ.copy()
            env["AI_COMPANY_EXECUTION_MOCK"] = "1"
            env["AI_COMPANY_MAX_REASSIGNMENTS_PER_RUN"] = "1"
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "run_ai_company_execution.py"), str(run_dir)],
                check=True,
                env=env,
                cwd=ROOT,
            )
            execution_summary = json.loads((run_dir / "ai_company" / "execution_summary.json").read_text(encoding="utf-8"))
            reviewer = json.loads((run_dir / "ai_company" / "reviewer_verdicts.json").read_text(encoding="utf-8"))
            initial_roles = [item["owner_role"] for item in execution_summary["execution_log"] if item["mode"] == "initial"]
            if initial_roles:
                assignment_routed += 1
            if execution_summary["reassignment_count"] == case["expect_reassignment_count"]:
                reassignment_worked += 1
            if reviewer.get("verdict_count", 0) >= 1:
                reviewer_generated += 1
            rows.append(
                {
                    "id": case["id"],
                    "initial_roles": initial_roles,
                    "reassignment_count": execution_summary["reassignment_count"],
                    "acceptance_rate": execution_summary["acceptance_rate"],
                    "reviewer_verdict_count": reviewer.get("verdict_count", 0),
                    "acceptance_matches_expectation": execution_summary["acceptance_rate"] == case["expect_acceptance_rate"],
                    "reassignment_matches_expectation": execution_summary["reassignment_count"] == case["expect_reassignment_count"],
                }
            )
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    total = len(cases)
    report = {
        "assignment_routing_rate": round(assignment_routed / total, 3) if total else 0.0,
        "reassignment_recovery_rate": round(reassignment_worked / total, 3) if total else 0.0,
        "reviewer_generation_rate": round(reviewer_generated / total, 3) if total else 0.0,
        "cases": rows,
    }
    return report


def main() -> None:
    report = evaluate()
    out = OUTPUT_DIR / "ai_company_execution_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
