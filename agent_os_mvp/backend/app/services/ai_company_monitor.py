from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
RESULTS_ROOT = REPO_ROOT / "results" / "ai_company_task_harness"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _parse_run_started_at(run_name: str) -> str | None:
    match = re.match(r"run-(\d{8})-(\d{6})-", run_name)
    if not match:
        return None
    return datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S").isoformat()


def _shorten(text: str, limit: int = 420) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _severity_from_alert_type(alert_type: str) -> str:
    if alert_type in {"overflow", "router_error", "replan_loop"}:
        return "red"
    if alert_type in {"timeout", "artifact_regression"}:
        return "yellow"
    return "green"


def _build_alerts(report: dict[str, Any]) -> list[dict[str, Any]]:
    kpis = report.get("kpis", {})
    failure_counts = kpis.get("failure_family_counts", {})
    alerts: list[dict[str, Any]] = []

    if failure_counts.get("overflow", 0) > 0:
        alerts.append({
            "type": "overflow",
            "severity": _severity_from_alert_type("overflow"),
            "title": "Token Overflow",
            "detail": f"Overflow count = {failure_counts.get('overflow', 0)}. Narrow child scope before rerun.",
        })
    if failure_counts.get("router", 0) > 0:
        alerts.append({
            "type": "router_error",
            "severity": _severity_from_alert_type("router_error"),
            "title": "Router Error",
            "detail": f"Router error count = {failure_counts.get('router', 0)}. Check model endpoint or partial response handling.",
        })
    if kpis.get("replan_required_count", 0) > 0:
        alerts.append({
            "type": "replan_loop",
            "severity": _severity_from_alert_type("replan_loop"),
            "title": "Replan Pressure",
            "detail": f"Replan required count = {kpis.get('replan_required_count', 0)}. Current task slicing may still be too broad.",
        })
    if failure_counts.get("timeout", 0) > 0:
        alerts.append({
            "type": "timeout",
            "severity": _severity_from_alert_type("timeout"),
            "title": "Timeout",
            "detail": f"Timeout count = {failure_counts.get('timeout', 0)}. Consider reducing context or increasing timeout budget.",
        })

    artifact = kpis.get("artifact_verify", {}).get("parsed", {})
    if artifact and not artifact.get("all_passed", True):
        failed_checks = [key for key, value in artifact.get("checks", {}).items() if not value]
        alerts.append({
            "type": "artifact_regression",
            "severity": _severity_from_alert_type("artifact_regression"),
            "title": "Artifact Check Failed",
            "detail": f"Failed checks: {', '.join(failed_checks) if failed_checks else 'unknown'}",
        })

    if not alerts:
        alerts.append({
            "type": "healthy",
            "severity": "green",
            "title": "Healthy",
            "detail": "No overflow, router error, or replan signal in this run.",
        })
    return alerts


def _read_optional_text(path: Path, limit: int = 12000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[TRUNCATED]\n"


def _workspace_path_to_local(value: str) -> Path:
    if not value:
        return Path()
    return Path(value.replace("/workspace", str(REPO_ROOT).replace("\\", "/")))


def _summarize_run(run_dir: Path) -> dict[str, Any]:
    ai_dir = run_dir / "ai_company"
    report = _load_json(ai_dir / "task_harness_report.json") if (ai_dir / "task_harness_report.json").exists() else {}
    meeting = _load_json(ai_dir / "meeting_decision.json") if (ai_dir / "meeting_decision.json").exists() else {}
    execution = _load_json(ai_dir / "execution_summary.json") if (ai_dir / "execution_summary.json").exists() else {}
    reviewer = _load_json(ai_dir / "reviewer_verdicts.json") if (ai_dir / "reviewer_verdicts.json").exists() else {}
    plan = _load_json(run_dir / "plan.json") if (run_dir / "plan.json").exists() else {}
    summary = _read_text(run_dir / "worktree" / "summary.md") if (run_dir / "worktree" / "summary.md").exists() else ""

    status_records: list[dict[str, Any]] = []
    for status_path in sorted((run_dir / "results").glob("*.status.json")):
        status_records.append(_load_json(status_path))

    status_by_task = {item.get("id"): item for item in status_records}
    verdict_by_task = {item.get("task_id"): item for item in reviewer.get("verdicts", []) if item.get("task_id")}

    agent_activity = []
    for assignment in meeting.get("task_assignments", []):
        task_id = assignment.get("task_id", "")
        role = assignment.get("owner_role", "unknown")
        verdict = verdict_by_task.get(task_id)
        status = status_by_task.get(task_id)
        if verdict:
            activity_state = verdict.get("verdict", "COMPLETE")
        elif status:
            raw_status = status.get("status", "UNKNOWN")
            activity_state = "REVIEW_PENDING" if raw_status == "SUCCESS" and role != "reviewer_worker" else raw_status
        else:
            activity_state = "QUEUED"
        agent_activity.append({
            "task_id": task_id,
            "role": role,
            "phase": "review" if role == "reviewer_worker" else "execution",
            "status": activity_state,
            "scope": assignment.get("scope", []),
            "depends_on": assignment.get("depends_on", []),
            "fallback_plan": assignment.get("fallback_plan", ""),
            "duration_sec": status.get("duration_sec", 0) if status else 0,
        })

    discussion = [{
        "round": item.get("round"),
        "role": item.get("role"),
        "summary": item.get("summary", ""),
        "decision_state": item.get("decision_state", ""),
        "proposed_actions": item.get("proposed_actions", []),
    } for item in meeting.get("discussion_log", [])]

    artifact_verify = report.get("kpis", {}).get("artifact_verify", {}).get("parsed", {})
    alerts = _build_alerts(report)

    status_details = []
    for item in status_records:
        raw_path = _workspace_path_to_local(str(item.get("raw_file", "")))
        prompt_path = raw_path.with_name(raw_path.name.replace(".raw.txt", ".prompt.txt")) if raw_path.name.endswith(".raw.txt") else Path()
        exec_log_path = _workspace_path_to_local(str(item.get("exec_log_file", "")))
        status_details.append({
            "id": item.get("id", ""),
            "status": item.get("status", "UNKNOWN"),
            "owner_role": item.get("owner_role", ""),
            "raw_excerpt": _read_optional_text(raw_path),
            "prompt_excerpt": _read_optional_text(prompt_path),
            "exec_log_excerpt": _read_optional_text(exec_log_path),
        })

    final_result = {
        "summary_markdown": summary,
        "summary_excerpt": _shorten(summary),
        "artifact_score": artifact_verify.get("score"),
        "artifact_checks": artifact_verify.get("checks", {}),
        "accepted_count": report.get("kpis", {}).get("accepted_count", 0),
        "overall_status": report.get("overall_status", "unknown"),
    }

    return {
        "run_id": run_dir.name,
        "spec_id": report.get("spec_id", ""),
        "mode": report.get("mode", ""),
        "overall_status": report.get("overall_status", "unknown"),
        "meeting_status": meeting.get("meeting_status", ""),
        "started_at": _parse_run_started_at(run_dir.name),
        "goal": meeting.get("goal") or report.get("kpis", {}).get("goal", ""),
        "decision_summary": meeting.get("decision_summary", ""),
        "convergence_reason": meeting.get("convergence_reason", ""),
        "alerts": alerts,
        "execution_jobs_run": report.get("kpis", {}).get("execution_jobs_run", 0),
        "replan_required_count": report.get("kpis", {}).get("replan_required_count", 0),
        "active_agents": [item for item in agent_activity if item["status"] not in {"ACCEPTED", "COMPLETE"}],
        "agent_activity": agent_activity,
        "meeting": {
            "rounds_used": meeting.get("rounds_used", 0),
            "round_limit": meeting.get("round_limit", 0),
            "constraints": meeting.get("constraints", []),
            "open_risks": meeting.get("open_risks", []),
            "discussion_log": discussion,
            "task_assignments": meeting.get("task_assignments", []),
            "plan_strategy": plan.get("strategy", ""),
            "plan_jobs": plan.get("jobs", []),
        },
        "review_verdicts": reviewer.get("verdicts", []),
        "execution_log": execution.get("execution_log", []),
        "status_details": status_details,
        "final_result": final_result,
    }


def sync_ai_company_runs(connection: Connection) -> None:
    if not RESULTS_ROOT.exists():
        return
    run_dirs = sorted([path for path in RESULTS_ROOT.iterdir() if path.is_dir()], key=lambda item: item.name, reverse=True)
    synced_at = datetime.now(timezone.utc).isoformat()
    for run_dir in run_dirs[:20]:
        try:
            payload = _summarize_run(run_dir)
        except Exception:
            continue
        connection.execute(
            """
            INSERT INTO ai_company_runs (
                run_id, spec_id, mode, overall_status, started_at, goal, decision_summary,
                meeting_status, artifact_score, active_agent_count, alerts_json, payload_json, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                spec_id = excluded.spec_id,
                mode = excluded.mode,
                overall_status = excluded.overall_status,
                started_at = excluded.started_at,
                goal = excluded.goal,
                decision_summary = excluded.decision_summary,
                meeting_status = excluded.meeting_status,
                artifact_score = excluded.artifact_score,
                active_agent_count = excluded.active_agent_count,
                alerts_json = excluded.alerts_json,
                payload_json = excluded.payload_json,
                synced_at = excluded.synced_at
            """,
            (
                payload["run_id"],
                payload.get("spec_id", ""),
                payload.get("mode", ""),
                payload.get("overall_status", "unknown"),
                payload.get("started_at"),
                payload.get("goal", ""),
                payload.get("decision_summary", ""),
                payload.get("meeting_status", ""),
                payload.get("final_result", {}).get("artifact_score"),
                len(payload.get("active_agents", [])),
                json.dumps(payload.get("alerts", []), ensure_ascii=False),
                json.dumps(payload, ensure_ascii=False),
                synced_at,
            ),
        )
    connection.commit()


def collect_ai_company_monitor(connection: Connection) -> dict[str, Any]:
    sync_ai_company_runs(connection)
    rows = connection.execute(
        """
        SELECT run_id, payload_json, alerts_json
        FROM ai_company_runs
        ORDER BY started_at DESC, run_id DESC
        LIMIT 12
        """
    ).fetchall()
    runs = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        payload["alerts"] = json.loads(row["alerts_json"])
        runs.append(payload)

    counts = Counter(item.get("overall_status", "unknown") for item in runs)
    spec_counts = Counter(item.get("spec_id", "unknown") for item in runs if item.get("spec_id"))
    latest_run = runs[0] if runs else None

    total_runs = connection.execute("SELECT COUNT(*) FROM ai_company_runs").fetchone()[0]
    return {
        "overview": {
            "total_runs": total_runs,
            "pass_count": counts.get("pass", 0),
            "fail_count": counts.get("fail", 0),
            "specs": [{"spec_id": key, "count": value} for key, value in spec_counts.most_common()],
            "active_agents": len(latest_run.get("active_agents", [])) if latest_run else 0,
            "latest_status": latest_run.get("overall_status") if latest_run else "unknown",
        },
        "latest_run": latest_run,
        "recent_runs": [
            {
                "run_id": item["run_id"],
                "spec_id": item.get("spec_id", ""),
                "started_at": item.get("started_at"),
                "overall_status": item.get("overall_status", "unknown"),
                "artifact_score": item.get("final_result", {}).get("artifact_score"),
                "goal": item.get("goal", ""),
                "alerts": item.get("alerts", []),
            }
            for item in runs
        ],
    }


def get_ai_company_run_detail(connection: Connection, run_id: str) -> dict[str, Any]:
    sync_ai_company_runs(connection)
    row = connection.execute(
        "SELECT payload_json, alerts_json FROM ai_company_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if row is None:
        raise FileNotFoundError(run_id)
    payload = json.loads(row["payload_json"])
    payload["alerts"] = json.loads(row["alerts_json"])
    return payload
