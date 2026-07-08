from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCORECARD_ROOT = ROOT / "results" / "llm_model_evaluation"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_scorecard_path(defaults: dict[str, Any]) -> str:
    configured = str(defaults.get("latest_model_scorecard_path", "") or "").strip()
    if configured:
        path = (ROOT / configured).resolve()
        if path.exists():
            return str(path)
    if not SCORECARD_ROOT.exists():
        return ""
    candidates = sorted(SCORECARD_ROOT.glob("*/model_scorecard.json"), key=lambda item: item.parent.name, reverse=True)
    return str(candidates[0]) if candidates else ""


def scorecard_entry_for_model(scorecard_path: str, model_name: str) -> dict[str, Any]:
    if not scorecard_path or not model_name:
        return {}
    path = Path(scorecard_path)
    if not path.exists():
        return {}
    payload = read_json(path)
    for item in payload.get("models", []):
        if item.get("model") == model_name:
            return {
                "overall_score": item.get("overall_score"),
                "tier": item.get("tier", ""),
                "best_for": item.get("best_for", ""),
                "recommended_next_action": item.get("recommended_next_action", ""),
            }
    return {}


def build_llm_reliability_report(run_dir: Path, defaults: dict[str, Any], reviewer: dict[str, Any] | None = None) -> dict[str, Any]:
    statuses = [read_json(path) for path in sorted((run_dir / "results").glob("*.status.json"))]
    reviewer = reviewer or {}
    recommended = str(defaults.get("recommended_live_model") or defaults.get("live_model", ""))
    fallback_model = str(defaults.get("live_model", ""))
    observed_models = sorted({str(item.get("model_name", "") or fallback_model) for item in statuses if item})
    model_name = observed_models[0] if len(observed_models) == 1 else (fallback_model if fallback_model else "")
    scorecard = latest_scorecard_path(defaults)
    accepted_ids = {
        str(item.get("task_id", ""))
        for item in reviewer.get("verdicts", [])
        if item.get("verdict") == "ACCEPTED"
    }

    repair_attempted = [item for item in statuses if item.get("repair_attempted")]
    repair_successful = [item for item in statuses if item.get("repair_successful")]
    format_recovered = [item for item in statuses if item.get("format_recovery_used")]
    rate_limited = [item for item in statuses if "llm_rate_limit_wait_sec" in item]
    rate_limit_timeouts = [item for item in statuses if item.get("failure_family") == "LLM_RATE_LIMIT_TIMEOUT"]
    total_rate_limit_wait = round(sum(float(item.get("llm_rate_limit_wait_sec", 0.0) or 0.0) for item in statuses), 3)
    require_change = [item for item in statuses if item.get("require_change")]
    require_change_passed = [
        item
        for item in require_change
        if item.get("status") == "SUCCESS"
        and item.get("test_exit_code") == 0
        and item.get("actual_changed_count", 0) > 0
        and str(item.get("id", "")) in accepted_ids
    ]
    failure_families: dict[str, int] = {}
    for item in statuses:
        family = str(item.get("failure_family", "") or "")
        if family:
            failure_families[family] = failure_families.get(family, 0) + 1

    return {
        "run_id": run_dir.name,
        "model_name": model_name,
        "observed_models": observed_models,
        "recommended_live_model": recommended,
        "is_recommended_model": bool(model_name and recommended and model_name == recommended),
        "model_candidates": defaults.get("model_candidates", []),
        "latest_scorecard_path": scorecard,
        "scorecard_model_snapshot": scorecard_entry_for_model(scorecard, model_name),
        "status_count": len(statuses),
        "accepted_count": int(reviewer.get("accepted_count", 0)),
        "repair_attempted_count": len(repair_attempted),
        "repair_successful_count": len(repair_successful),
        "format_recovery_count": len(format_recovered),
        "rate_limited_task_count": len(rate_limited),
        "rate_limit_timeout_count": len(rate_limit_timeouts),
        "total_rate_limit_wait_sec": total_rate_limit_wait,
        "max_rate_limit_request_count_window": max(
            [int(item.get("llm_rate_limit_request_count_window", 0) or 0) for item in statuses] or [0]
        ),
        "require_change_count": len(require_change),
        "require_change_accepted_pass_count": len(require_change_passed),
        "failure_families": failure_families,
        "tasks": [
            {
                "id": item.get("id", ""),
                "status": item.get("status", ""),
                "model_name": item.get("model_name", model_name),
                "require_change": bool(item.get("require_change", False)),
                "test_exit_code": item.get("test_exit_code"),
                "actual_changed_count": item.get("actual_changed_count", 0),
                "repair_attempted": bool(item.get("repair_attempted", False)),
                "repair_successful": bool(item.get("repair_successful", False)),
                "format_recovery_used": bool(item.get("format_recovery_used", False)),
                "llm_rate_limit_wait_sec": float(item.get("llm_rate_limit_wait_sec", 0.0) or 0.0),
                "llm_rate_limit_permit_acquired": bool(item.get("llm_rate_limit_permit_acquired", True)),
                "llm_rate_limit_request_count_window": int(item.get("llm_rate_limit_request_count_window", 0) or 0),
                "failure_family": item.get("failure_family", ""),
                "accepted_by_reviewer": str(item.get("id", "")) in accepted_ids,
            }
            for item in statuses
        ],
    }


def write_llm_reliability_report(run_dir: Path, defaults: dict[str, Any], reviewer: dict[str, Any] | None = None) -> dict[str, Any]:
    report = build_llm_reliability_report(run_dir, defaults, reviewer)
    path = run_dir / "ai_company" / "llm_reliability_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
