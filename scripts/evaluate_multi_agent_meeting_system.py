from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from run_ai_company_meeting import build_meeting_decision


ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = ROOT / "tests" / "ai_company_multi_agent_cases.json"
OUTPUT_DIR = ROOT / "results" / "ai_company_validation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_case_run(base_dir: Path, case: dict) -> Path:
    run_dir = base_dir / case["id"]
    jobs_dir = run_dir / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "run_id": case["id"],
        "task": case["task"],
        "strategy": case["strategy"],
        "metrics": case.get("summary_metrics", {}),
    }
    plan = {
        "strategy": case["strategy"],
        "jobs": case["jobs"],
    }
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "plan.json", plan)
    for job in case["jobs"]:
        write_json(jobs_dir / f"{job['id']}.json", job)
    return run_dir


def evaluate() -> dict:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    tmp_root = Path(tempfile.mkdtemp(prefix="ai-company-meeting-", dir=str(ROOT / "tmp")))

    total = len(cases)
    schema_valid = 0
    minutes_present = 0
    discussion_recorded = 0
    assignment_complete = 0
    bounded_assignments = 0
    converged = 0
    loop_guard_good = 0
    loop_guard_cases = 0
    expected_status_hit = 0
    case_rows = []

    try:
        for case in cases:
            run_dir = build_case_run(tmp_root, case)
            meeting = build_meeting_decision(run_dir, case["task"])

            has_minutes = bool(meeting.get("meeting_minutes"))
            has_discussion = bool(meeting.get("discussion_log")) and len(meeting["discussion_log"]) >= 4
            complete = all(
                item.get("task_id")
                and item.get("owner_role")
                and isinstance(item.get("scope"), list)
                and isinstance(item.get("acceptance_criteria"), list)
                and item.get("fallback_plan")
                for item in meeting.get("task_assignments", [])
            )
            bounded = all(len(item.get("scope", [])) <= 3 for item in meeting.get("task_assignments", []))
            rounds_ok = int(meeting.get("rounds_used", 99)) <= int(case["expect_rounds_lte"])
            status_ok = meeting.get("meeting_status") == case["expect_status"]

            if all(key in meeting for key in ["meeting_id", "meeting_status", "goal", "meeting_minutes", "discussion_log", "task_assignments"]):
                schema_valid += 1
            if has_minutes:
                minutes_present += 1
            if has_discussion:
                discussion_recorded += 1
            if complete:
                assignment_complete += 1
            if bounded:
                bounded_assignments += 1
            if meeting.get("meeting_status") in {"MEETING_READY", "MEETING_NEEDS_REPLAN"} and rounds_ok:
                converged += 1
            if case["expect_status"] == "MEETING_NEEDS_REPLAN":
                loop_guard_cases += 1
                if meeting.get("meeting_status") == "MEETING_NEEDS_REPLAN" and rounds_ok:
                    loop_guard_good += 1
            if status_ok:
                expected_status_hit += 1

            case_rows.append(
                {
                    "id": case["id"],
                    "meeting_status": meeting.get("meeting_status"),
                    "rounds_used": meeting.get("rounds_used"),
                    "task_count": len(meeting.get("task_assignments", [])),
                    "discussion_entries": len(meeting.get("discussion_log", [])),
                    "status_matches_expectation": status_ok,
                }
            )
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    report = {
        "meeting_plan_valid_rate": round(schema_valid / total, 3) if total else 0.0,
        "meeting_minutes_presence_rate": round(minutes_present / total, 3) if total else 0.0,
        "discussion_log_coverage_rate": round(discussion_recorded / total, 3) if total else 0.0,
        "task_assignment_clarity_rate": round(assignment_complete / total, 3) if total else 0.0,
        "bounded_task_rate": round(bounded_assignments / total, 3) if total else 0.0,
        "meeting_convergence_rate": round(converged / total, 3) if total else 0.0,
        "loop_guard_effectiveness_rate": round(loop_guard_good / loop_guard_cases, 3) if loop_guard_cases else 0.0,
        "expected_status_match_rate": round(expected_status_hit / total, 3) if total else 0.0,
        "cases": case_rows,
    }
    return report


def main() -> None:
    report = evaluate()
    out = OUTPUT_DIR / "multi_agent_meeting_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
