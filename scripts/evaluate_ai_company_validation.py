from __future__ import annotations

import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = ROOT / "tests" / "ai_company_validation_cases.json"
TARGETS_PATH = ROOT / "tests" / "ai_company_kpi_targets.json"
OUTPUT_DIR = ROOT / "results" / "ai_company_validation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(read_text(path))


def exists(path: Path) -> bool:
    return path.exists()


def nonempty(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def contains(path: Path, needle: str) -> bool:
    return exists(path) and needle in read_text(path)


def as_int(value: object) -> int:
    if value in (None, "", False):
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value))
    except ValueError:
        return 0


def as_float(value: object) -> float:
    if value in (None, "", False):
        return 0.0
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def evaluate() -> dict:
    scenarios = read_json(CASES_PATH)["scenarios"]
    targets = read_json(TARGETS_PATH)["targets"]
    total_weight = sum(float(item["weight"]) for item in scenarios)

    playbook_root = ROOT / "deliverables" / "codex-claude-server-playbook"
    scripts_dir = playbook_root / "scripts"
    orchestrator_root = playbook_root / "orchestrator-claude"
    limit_root = playbook_root / "orchestrator-claude-limit-tests"
    baseline_results = playbook_root / "TEST_RESULTS_2026-06-27.zh-TW.md"
    stress_results = playbook_root / "TEST_RESULTS_2026-06-27_STRESS.zh-TW.md"
    quickstart = playbook_root / "COMPANY_CLAUDE_ROUTER_QUICKSTART.zh-TW.md"
    company_matrix = playbook_root / "COMPANY_TEST_MATRIX.zh-TW.md"
    pure_mode_spec = playbook_root / "CLAUDE_ROUTER_PURE_MODE_SPEC.zh-TW.md"

    readiness_report = ROOT / "results" / "task_agent_readiness" / "task_agent_readiness_report.json"
    readiness_doc = ROOT / "docs" / "COMPANY_TASK_AGENT_READINESS_CHECKLIST.zh-TW.md"
    ai_goal_doc = ROOT / "docs" / "AI_COMPANY_GOAL.zh-TW.md"
    ai_checklist = ROOT / "docs" / "AI_COMPANY_VALIDATION_CHECKLIST.zh-TW.md"
    meeting_doc = ROOT / "docs" / "AI_COMPANY_MEETING_PROTOCOL.zh-TW.md"
    reviewer_doc = ROOT / "docs" / "AI_COMPANY_REVIEWER_WORKER_SPEC.zh-TW.md"

    meeting_scenarios = ROOT / "tests" / "ai_company_meeting_scenarios.json"
    meeting_schema = ROOT / "configs" / "ai_company" / "meeting_decision.schema.json"
    task_schema = ROOT / "configs" / "ai_company" / "task_assignment.schema.json"
    reviewer_schema = ROOT / "configs" / "ai_company" / "reviewer_verdict.schema.json"
    meeting_example = ROOT / "configs" / "ai_company" / "meeting_decision.example.json"
    reviewer_example = ROOT / "configs" / "ai_company" / "reviewer_verdict.example.json"
    materialized_root = ROOT / "results" / "ai_company_materialized"
    multi_agent_meeting_report = OUTPUT_DIR / "multi_agent_meeting_report.json"
    execution_report = OUTPUT_DIR / "ai_company_execution_report.json"

    sens_bundle = ROOT / "sens_analysis" / "results" / "delivery_bundle" / "sens_v2_company_delivery"
    sens_raw = ROOT / "sens_analysis" / "results" / "sens_v2_mixed_pilot" / "raw_output.txt"

    orchestrate_script = scripts_dir / "orchestrate_claude_to_claude.sh"
    worker_script = scripts_dir / "worker_claude_router.sh"
    worker_single_script = scripts_dir / "worker_claude_router_managed_single_file.sh"
    common_script = scripts_dir / "claude_router_common.sh"

    summary_files = sorted(orchestrator_root.glob("run-*/summary.json"))
    now_ts = time.time()
    recent_summary_files = [path for path in summary_files if (now_ts - path.stat().st_mtime) <= 86400]
    limit_status_files = sorted(limit_root.glob("run-*/results/*.status.json"))
    failure_case_scripts = sorted(scripts_dir.glob("evaluate_claude_*.sh"))

    aggregate = {
        "runs": 0,
        "workers_run": 0,
        "workers_overflowed": 0,
        "workers_failed": 0,
        "workers_need_replan": 0,
        "workers_with_verified_changes": 0,
        "workers_false_success_blocked": 0,
        "workers_router_errors": 0,
        "workers_timed_out": 0,
        "overflow_retries": 0,
        "fail_replan_attempts": 0,
        "workers_failed_replanned": 0,
        "replan_loop_guard_hit": 0,
        "child_invocation_limit_hit": 0,
        "max_files_in_job_max": 0.0,
        "breadth_reduction_percent_max": 0.0,
    }

    for path in summary_files:
        data = read_json(path)
        metrics = data.get("metrics", {})
        aggregate["runs"] += 1
        aggregate["workers_run"] += as_int(metrics.get("workers_run"))
        aggregate["workers_overflowed"] += as_int(metrics.get("workers_overflowed"))
        aggregate["workers_failed"] += as_int(metrics.get("workers_failed"))
        aggregate["workers_need_replan"] += as_int(metrics.get("workers_need_replan"))
        aggregate["workers_with_verified_changes"] += as_int(metrics.get("workers_with_verified_changes"))
        aggregate["workers_false_success_blocked"] += as_int(metrics.get("workers_false_success_blocked"))
        aggregate["workers_router_errors"] += as_int(metrics.get("workers_router_errors"))
        aggregate["workers_timed_out"] += as_int(metrics.get("workers_timed_out"))
        aggregate["overflow_retries"] += as_int(metrics.get("overflow_retries"))
        aggregate["fail_replan_attempts"] += as_int(metrics.get("fail_replan_attempts"))
        aggregate["workers_failed_replanned"] += as_int(metrics.get("workers_failed_replanned"))
        aggregate["replan_loop_guard_hit"] += as_int(metrics.get("replan_loop_guard_hit"))
        aggregate["child_invocation_limit_hit"] += as_int(metrics.get("child_invocation_limit_hit"))
        aggregate["max_files_in_job_max"] = max(aggregate["max_files_in_job_max"], as_float(metrics.get("max_files_in_job")))
        aggregate["breadth_reduction_percent_max"] = max(
            aggregate["breadth_reduction_percent_max"], as_float(metrics.get("breadth_reduction_percent"))
        )

    limit_statuses = [read_json(path) for path in limit_status_files]
    readiness = read_json(readiness_report) if exists(readiness_report) else {}
    stress_text = read_text(stress_results) if exists(stress_results) else ""

    def stress_has(*needles: str) -> bool:
        return all(needle in stress_text for needle in needles)

    results: dict[str, dict[str, str]] = {}

    results["architecture_chain"] = {
        "status": "pass" if all(exists(p) for p in [orchestrate_script, worker_script, worker_single_script, common_script]) and aggregate["runs"] >= 1 else "fail",
        "reason": "Master orchestrator and Claude worker scripts exist and historical orchestrator runs are present.",
    }

    role_markers = ["main orchestrator", "worker Claude agent"]
    reviewer_present = contains(orchestrate_script, "verification_note") and contains(orchestrate_script, "workers_false_success_blocked")
    role_doc_ok = contains(ai_goal_doc, "Master orchestrator") and contains(ai_goal_doc, "Planner worker") and contains(ai_goal_doc, "Executor worker")
    meeting_script = ROOT / "scripts" / "run_ai_company_meeting.py"
    multi_agent_role_ok = all(contains(meeting_script, role) for role in ["meeting_coordinator", "planner_agent", "risk_reviewer", "decision_agent"])
    results["role_definition"] = {
        "status": "pass" if all(marker in read_text(orchestrate_script) for marker in role_markers) and role_doc_ok and multi_agent_role_ok else "partial",
        "reason": "Master, planner, executor, and multi-agent meeting roles are explicitly defined in scripts and goal docs.",
    }

    status_markers = ["OVERFLOW_DETECTED", "ROUTER_ERROR", "CHILD_TIMEOUT", "NEEDS_REPLAN", "CHILD_LIMIT_REACHED", "FAILED"]
    results["status_code_contract"] = {
        "status": "pass" if all(marker in read_text(orchestrate_script) for marker in status_markers) else "fail",
        "reason": "The orchestrator must branch on explicit worker status codes rather than free-form text.",
    }

    bounded_ok = aggregate["breadth_reduction_percent_max"] >= 60.0 and aggregate["max_files_in_job_max"] <= targets["max_task_scope_files"]
    results["bounded_task_slicing"] = {
        "status": "pass" if bounded_ok else "partial",
        "reason": "Observed runs should show strong breadth reduction and bounded per-job file scope.",
    }

    results["overflow_recovery"] = {
        "status": "pass" if aggregate["workers_overflowed"] >= 1 and aggregate["overflow_retries"] >= 1 and "Reasoning pressure" in stress_text else "fail",
        "reason": "Overflow must be observed and followed by bounded retry / scope reduction.",
    }

    results["timeout_recovery"] = {
        "status": "pass" if aggregate["workers_timed_out"] >= 1 and exists(scripts_dir / "evaluate_claude_timeout_recovery.sh") else "fail",
        "reason": "Timeout must be observed and recovered without killing the main flow.",
    }

    results["needs_replan_recovery"] = {
        "status": "pass" if aggregate["workers_need_replan"] >= 1 and exists(scripts_dir / "evaluate_claude_needs_replan.sh") else "fail",
        "reason": "Workers asking for narrower scope should trigger a replan path.",
    }

    results["loop_guard"] = {
        "status": "pass" if aggregate["replan_loop_guard_hit"] >= 1 and (exists(scripts_dir / "evaluate_claude_replan_loop_guard.sh") or exists(scripts_dir / "evaluate_claude_same_failure_guard.sh")) else "fail",
        "reason": "Repeated failures must stop via loop guards instead of infinite retries.",
    }

    results["false_success_guard"] = {
        "status": "pass" if aggregate["workers_false_success_blocked"] >= 1 and exists(scripts_dir / "evaluate_claude_false_success_guard.sh") else "fail",
        "reason": "Claimed success without verified change must be downgraded to failure.",
    }

    child_limit_success = any(item.get("status") == "SUCCESS" for item in limit_statuses)
    child_limit_blocked = any(item.get("status") == "CHILD_LIMIT_REACHED" for item in limit_statuses)
    results["child_limit_guard"] = {
        "status": "pass" if child_limit_success and child_limit_blocked else "fail",
        "reason": "Child cap tests should show both normal success and guarded child-limit stop behavior.",
    }

    router_coverage = stress_has("Router empty response", "Router partial response", "Router flapping") and stress_text.count("pass=true") >= 6
    results["router_instability_coverage"] = {
        "status": "pass" if router_coverage else "partial",
        "reason": "Router empty / partial / flapping scenarios should be explicitly covered by stress results.",
    }

    results["failure_case_library"] = {
        "status": "pass" if len(failure_case_scripts) >= targets["min_failure_case_scripts"] else "fail",
        "reason": "The repository should include a sizable failure-case script library for guard testing.",
    }

    token_doc_ok = contains(readiness_doc, "token overflow") and contains(ROOT / "sens_analysis" / "README.md", "Token-overflow controls")
    results["token_control_docs"] = {
        "status": "pass" if token_doc_ok else "fail",
        "reason": "Token / context risk controls should be explicitly documented.",
    }

    bundle_files = [
        sens_bundle / "analysis.json",
        sens_bundle / "analysis.md",
        sens_bundle / "evidence_log.json",
        sens_bundle / "evidence_pack_v2.json",
        sens_bundle / "raw_output.txt",
    ]
    audit_ok = all(exists(path) for path in bundle_files) and nonempty(sens_raw) and readiness.get("readiness") == "ready"
    results["audit_artifacts"] = {
        "status": "pass" if audit_ok else "fail",
        "reason": "Non-empty raw output, artifact bundle, and readiness evidence must all be present.",
    }

    results["company_gate"] = {
        "status": "pass" if exists(ai_goal_doc) and exists(ai_checklist) and readiness.get("score_total", 0) >= targets["min_historical_readiness_score"] else "fail",
        "reason": "Company gate requires explicit goal/checklist docs and strong historical readiness evidence.",
    }

    linux_doc_ok = all(exists(path) for path in [quickstart, company_matrix, pure_mode_spec])
    results["linux_delivery_docs"] = {
        "status": "pass" if linux_doc_ok else "partial",
        "reason": "Linux/Ubuntu-oriented quickstart, matrix, and pure-mode guidance should exist.",
    }

    reviewer_role_doc_ok = contains(reviewer_doc, "reviewer_worker") and contains(reviewer_doc, "獨立")
    results["reviewer_role"] = {
        "status": "pass" if reviewer_present and reviewer_role_doc_ok else "partial" if reviewer_present or reviewer_role_doc_ok else "fail",
        "reason": "Reviewer behavior and an explicit independent reviewer role spec should both exist.",
    }

    meeting_protocol_ok = contains(meeting_doc, "meeting_coordinator") and contains(meeting_doc, "decision_agent") and contains(meeting_doc, "discussion_log")
    results["meeting_protocol"] = {
        "status": "pass" if meeting_protocol_ok else "fail",
        "reason": "A bounded multi-agent meeting protocol must define coordinator, planner, risk review, decision roles, and transcript logging.",
    }

    meeting_schema_ok = all(exists(path) for path in [meeting_schema, task_schema, meeting_example])
    meeting_example_json = read_json(meeting_example) if exists(meeting_example) else {}
    assignments = meeting_example_json.get("task_assignments", [])
    materialized_meetings = sorted(materialized_root.glob("run-*/meeting_decision.json"))
    materialized_reviewers = sorted(materialized_root.glob("run-*/reviewer_verdicts.json"))
    materialized_meeting_json = read_json(materialized_meetings[0]) if materialized_meetings else {}
    materialized_assignments = materialized_meeting_json.get("task_assignments", [])
    assignment_complete = bool(assignments) and all(
        item.get("task_id")
        and item.get("owner_role")
        and isinstance(item.get("scope"), list)
        and isinstance(item.get("acceptance_criteria"), list)
        and item.get("fallback_plan")
        for item in assignments
    )
    results["meeting_assignment_schema"] = {
        "status": "pass" if meeting_schema_ok and assignment_complete and bool(materialized_assignments) else "fail",
        "reason": "Meeting decisions must include schema, example, and at least one materialized run artifact with explicit owner/scope/acceptance/fallback.",
    }

    bounded_assignment_ok = bool(assignments) and all(len(item.get("scope", [])) <= targets["max_task_scope_files"] for item in assignments)
    bounded_materialized_ok = bool(materialized_assignments) and all(len(item.get("scope", [])) <= targets["max_task_scope_files"] for item in materialized_assignments)
    results["meeting_bounded_rules"] = {
        "status": "pass" if bounded_assignment_ok and bounded_materialized_ok and contains(meeting_doc, "最多 `3` 個檔案") else "partial",
        "reason": "Meeting output should enforce bounded file scope per task.",
    }

    reviewer_schema_ok = all(exists(path) for path in [reviewer_schema, reviewer_example]) and contains(reviewer_doc, "Reviewer 輸出 Schema")
    reviewer_example_json = read_json(reviewer_example) if exists(reviewer_example) else {}
    reviewer_example_valid = all(key in reviewer_example_json for key in ["task_id", "review_status", "owner_role", "verdict", "evidence", "repair_action", "replan_required"])
    materialized_reviewer_json = read_json(materialized_reviewers[0]) if materialized_reviewers else {}
    materialized_verdicts = materialized_reviewer_json.get("verdicts", [])
    results["reviewer_verdict_schema"] = {
        "status": "pass" if reviewer_schema_ok and reviewer_example_valid and bool(materialized_verdicts) else "fail",
        "reason": "Reviewer worker should have schema, example, and at least one materialized verdict artifact from a run.",
    }

    meeting_scenarios_ok = exists(meeting_scenarios) and len(read_json(meeting_scenarios).get("scenarios", [])) >= 6
    results["meeting_scenarios_defined"] = {
        "status": "pass" if meeting_scenarios_ok else "fail",
        "reason": "Meeting / assignment / reviewer scenarios should be explicitly defined for later execution.",
    }

    multi_agent_report = read_json(multi_agent_meeting_report) if exists(multi_agent_meeting_report) else {}
    multi_agent_ready = (
        multi_agent_report.get("meeting_plan_valid_rate", 0.0) >= 1.0
        and multi_agent_report.get("meeting_minutes_presence_rate", 0.0) >= 1.0
        and multi_agent_report.get("discussion_log_coverage_rate", 0.0) >= 1.0
        and multi_agent_report.get("task_assignment_clarity_rate", 0.0) >= 1.0
        and multi_agent_report.get("expected_status_match_rate", 0.0) >= 1.0
    )
    execution_report_json = read_json(execution_report) if exists(execution_report) else {}

    results["live_round_this_turn"] = {
        "status": "pass" if recent_summary_files and materialized_meetings and materialized_reviewers else "partial",
        "reason": "This turn should include at least one recent live orchestration run plus materialized meeting/reviewer artifacts.",
    }

    weighted_score = 0.0
    critical_total = 0
    critical_pass = 0
    passed_count = 0
    scenario_rows = []
    for item in scenarios:
        sid = item["id"]
        status_name = results[sid]["status"]
        fraction = 1.0 if status_name == "pass" else 0.5 if status_name == "partial" else 0.0
        score = float(item["weight"]) * fraction
        weighted_score += score
        if status_name == "pass":
            passed_count += 1
        if item["critical"]:
            critical_total += 1
            if status_name == "pass":
                critical_pass += 1
        scenario_rows.append(
            {
                "id": sid,
                "weight": item["weight"],
                "critical": item["critical"],
                "status": status_name,
                "score": round(score, 1),
                "reason": results[sid]["reason"],
            }
        )

    normalized_score = round((weighted_score / total_weight) * 100, 1) if total_weight else 0.0
    scenario_pass_rate = round(passed_count / len(scenarios), 3) if scenarios else 0.0
    critical_guard_coverage_rate = round(critical_pass / critical_total, 3) if critical_total else 0.0

    kpis = {
        "observed_orchestrator_runs": aggregate["runs"],
        "observed_worker_invocations": aggregate["workers_run"],
        "observed_overflow_events": aggregate["workers_overflowed"],
        "observed_timeout_events": aggregate["workers_timed_out"],
        "observed_needs_replan_events": aggregate["workers_need_replan"],
        "observed_false_success_blocks": aggregate["workers_false_success_blocked"],
        "observed_loop_guard_hits": aggregate["replan_loop_guard_hit"],
        "failure_case_script_count": len(failure_case_scripts),
        "scenario_pass_rate": scenario_pass_rate,
        "critical_guard_coverage_rate": critical_guard_coverage_rate,
        "historical_readiness_score": readiness.get("score_total", 0.0),
        "historical_readiness_ready": readiness.get("readiness") == "ready",
        "nonempty_raw_output_present": nonempty(sens_raw),
        "artifact_bundle_present": all(exists(path) for path in bundle_files),
        "meeting_schema_present": meeting_schema_ok,
        "meeting_assignment_clarity_rate": 1.0 if assignment_complete else 0.0,
        "meeting_bounded_task_rate": 1.0 if bounded_assignment_ok else 0.0,
        "meeting_minutes_presence_rate": multi_agent_report.get("meeting_minutes_presence_rate", 0.0),
        "discussion_log_coverage_rate": multi_agent_report.get("discussion_log_coverage_rate", 0.0),
        "meeting_convergence_rate": multi_agent_report.get("meeting_convergence_rate", 0.0),
        "loop_guard_effectiveness_rate": multi_agent_report.get("loop_guard_effectiveness_rate", 0.0),
        "meeting_expected_status_match_rate": multi_agent_report.get("expected_status_match_rate", 0.0),
        "assignment_routing_rate": execution_report_json.get("assignment_routing_rate", 0.0),
        "reassignment_recovery_rate": execution_report_json.get("reassignment_recovery_rate", 0.0),
        "reviewer_generation_rate": execution_report_json.get("reviewer_generation_rate", 0.0),
        "reviewer_schema_present": reviewer_schema_ok and reviewer_example_valid,
        "materialized_meeting_runs": len(materialized_meetings),
        "materialized_reviewer_runs": len(materialized_reviewers),
        "recent_live_summary_runs": len(recent_summary_files),
        "multi_agent_meeting_report_present": exists(multi_agent_meeting_report),
        "multi_agent_meeting_report_ready": multi_agent_ready,
        "execution_report_present": exists(execution_report),
    }

    gates = {
        "observed_run_floor_met": kpis["observed_orchestrator_runs"] >= targets["min_observed_orchestrator_runs"],
        "failure_case_library_met": kpis["failure_case_script_count"] >= targets["min_failure_case_scripts"],
        "scenario_pass_rate_met": kpis["scenario_pass_rate"] >= targets["min_scenario_pass_rate"],
        "critical_guard_coverage_met": kpis["critical_guard_coverage_rate"] >= targets["min_critical_guard_coverage_rate"],
        "historical_readiness_met": kpis["historical_readiness_score"] >= targets["min_historical_readiness_score"] and kpis["historical_readiness_ready"],
        "raw_output_present": kpis["nonempty_raw_output_present"] if targets["require_nonempty_raw_output"] else True,
        "artifact_bundle_present": kpis["artifact_bundle_present"] if targets["require_artifact_bundle"] else True,
    }

    overall_status = (
        "historically_ready_needs_live_linux_rerun"
        if all(gates.values()) and results["live_round_this_turn"]["status"] != "pass"
        else "ready"
        if all(gates.values())
        else "not_ready"
    )

    return {
        "score_total": normalized_score,
        "score_max": 100,
        "score_raw": round(weighted_score, 1),
        "score_weight_total": round(total_weight, 1),
        "overall_status": overall_status,
        "gates": gates,
        "kpis": kpis,
        "aggregate_metrics": aggregate,
        "scenarios": scenario_rows,
    }


def write_outputs(report: dict) -> None:
    json_path = OUTPUT_DIR / "ai_company_validation_report.json"
    md_path = OUTPUT_DIR / "ai_company_validation_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# AI Company Validation Report",
        "",
        f"- Score: {report['score_total']} / {report['score_max']}",
        f"- Raw weighted score: {report['score_raw']} / {report['score_weight_total']}",
        f"- Overall status: {report['overall_status']}",
        "",
        "## Gates",
        "",
    ]
    for name, value in report["gates"].items():
        lines.append(f"- `{name}`: {'pass' if value else 'fail'}")
    lines += ["", "## KPIs", ""]
    for name, value in report["kpis"].items():
        lines.append(f"- `{name}`: {value}")
    lines += ["", "## Scenarios", "", "| Scenario | Status | Score | Weight | Critical |", "| --- | --- | ---: | ---: | --- |"]
    for row in report["scenarios"]:
        lines.append(f"| {row['id']} | {row['status']} | {row['score']} | {row['weight']} | {'yes' if row['critical'] else 'no'} |")
    lines += ["", "## Notes", ""]
    for row in report["scenarios"]:
        lines.append(f"- `{row['id']}`: {row['reason']}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    report = evaluate()
    write_outputs(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
