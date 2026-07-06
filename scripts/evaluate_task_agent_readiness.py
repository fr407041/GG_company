from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_PATH = ROOT / "tests" / "task_agent_readiness_scenarios.json"
OUTPUT_DIR = ROOT / "results" / "task_agent_readiness"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(read_text(path))


def exists(path: Path) -> bool:
    return path.exists()


def nonempty(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def evaluate() -> dict:
    scenarios = read_json(SCENARIOS_PATH)["scenarios"]
    score_weight_total = sum(float(item["weight"]) for item in scenarios)

    readme = ROOT / "sens_analysis" / "README.md"
    process_notes = ROOT / "sens_analysis" / "PROCESS_NOTES.md"
    audit = ROOT / "sens_analysis" / "OBJECTIVE_AUDIT.zh-TW.md"
    status = ROOT / "sens_analysis" / "SENS_V2_STATUS.zh-TW.md"
    manifest = ROOT / "sens_analysis" / "DELIVERY_MANIFEST.zh-TW.md"
    checklist = ROOT / "docs" / "COMPANY_TASK_AGENT_READINESS_CHECKLIST.zh-TW.md"
    scoring_doc = ROOT / "docs" / "TASK_AGENT_SCORING_STANDARD.zh-TW.md"

    analysis = ROOT / "sens_analysis" / "results" / "sens_v2_mixed_pilot" / "analysis.json"
    evidence_pack = ROOT / "sens_analysis" / "results" / "sens_v2_mixed_pilot" / "evidence_pack_v2.json"
    evidence_log = ROOT / "sens_analysis" / "results" / "sens_v2_mixed_pilot" / "evidence_log.json"
    raw_output = ROOT / "sens_analysis" / "results" / "sens_v2_mixed_pilot" / "raw_output.txt"
    docker_matrix = ROOT / "sens_analysis" / "results" / "source_access_matrix" / "docker-ubuntu22.json"
    bundle_dir = ROOT / "sens_analysis" / "results" / "delivery_bundle" / "sens_v2_company_delivery"
    runner_sh = ROOT / "sens_analysis" / "run_sens_v2_mixed.sh"
    runner_ps1 = ROOT / "sens_analysis" / "run_sens_v2_mixed_in_docker.ps1"
    mixed_py = ROOT / "sens_analysis" / "run_sens_v2_mixed.py"

    analysis_json = read_json(analysis) if exists(analysis) else {}
    evidence_json = read_json(evidence_pack) if exists(evidence_pack) else {}
    docker_json = read_json(docker_matrix) if exists(docker_matrix) else {}

    def has_all(paths: list[Path]) -> bool:
        return all(exists(p) for p in paths)

    def contains(path: Path, needle: str) -> bool:
        return exists(path) and needle in read_text(path)

    results = {}

    results["baseline_versions"] = {
        "status": "pass" if has_all([readme, process_notes, runner_sh, runner_ps1, mixed_py]) else "fail",
        "reason": "Core docs and runner files exist.",
    }

    results["router_chain_smoke"] = {
        "status": "pass" if contains(process_notes, "returned `OK`") else "fail",
        "reason": "Process notes record Ubuntu router smoke success.",
    }

    results["model_discovery"] = {
        "status": "pass" if contains(process_notes, "qwen2.5-coder:3b") or contains(readme, "qwen2.5-coder:3b") else "partial",
        "reason": "Known local model inventory is documented.",
    }

    results["bounded_task_success"] = {
        "status": "pass" if nonempty(raw_output) else "fail",
        "reason": "The bounded task must produce non-empty raw model output.",
    }

    schema_ok = (
        isinstance(analysis_json.get("primary_sources_used"), list)
        and isinstance(analysis_json.get("source_downgrades"), list)
        and "verdict" in analysis_json
        and "confidence" in analysis_json
        and "score_10" in analysis_json
    )
    results["schema_enforcement"] = {
        "status": "pass" if schema_ok else "fail",
        "reason": "analysis.json must conform to the bounded final schema.",
    }

    evidence_ok = bool(evidence_json.get("source_policy_alignment")) and bool(evidence_json.get("generated_from")) and nonempty(evidence_log)
    results["evidence_traceability"] = {
        "status": "pass" if evidence_ok else "fail",
        "reason": "Final outputs must trace back to evidence artifacts and source pack.",
    }

    downgrade_ok = any(item.get("preferred_type") == "Reuters" for item in analysis_json.get("source_downgrades", []))
    results["downgrade_logging"] = {
        "status": "pass" if downgrade_ok else "fail",
        "reason": "Unavailable high-trust sources must be explicitly downgraded.",
    }

    mismatch_ok = any(row.get("runtime_mismatch") for row in docker_json.get("checks", [])) if docker_json else False
    results["runtime_mismatch_logging"] = {
        "status": "pass" if mismatch_ok else "partial",
        "reason": "Runtime mismatch should be observable when source access differs by environment.",
    }

    timeout_ok = contains(mixed_py, "CLAUDE_CALL_TIMEOUT_SEC") and contains(runner_sh, "CLAUDE_CALL_TIMEOUT_SEC") and contains(runner_ps1, "ClaudeCallTimeoutSec")
    results["timeout_guard"] = {
        "status": "pass" if timeout_ok else "fail",
        "reason": "Timeout controls must exist in code and runner entrypoints.",
    }

    fallback_ok = contains(mixed_py, "fallback_analysis") and contains(mixed_py, "guard_grounded_language")
    results["fallback_recovery"] = {
        "status": "pass" if fallback_ok else "fail",
        "reason": "Fallback and grounded-language guards must exist.",
    }

    stabilization_ok = contains(process_notes, "signal-only") or contains(readme, "signal JSON") or contains(mixed_py, "commercial_signal")
    results["small_model_stabilization"] = {
        "status": "pass" if stabilization_ok else "fail",
        "reason": "Small-model stabilization strategy should be explicitly implemented.",
    }

    reproducible_ok = contains(status, "run_sens_v2_mixed_in_docker.ps1") and contains(manifest, "run_sens_v2_mixed_in_docker.ps1")
    results["reproducible_entrypoint"] = {
        "status": "pass" if reproducible_ok else "partial",
        "reason": "The evaluation path must expose a stable rerun command.",
    }

    bundle_files = [
        bundle_dir / "analysis.json",
        bundle_dir / "analysis.md",
        bundle_dir / "evidence_log.json",
        bundle_dir / "evidence_pack_v2.json",
        bundle_dir / "raw_output.txt",
        bundle_dir / "README.md",
        bundle_dir / "OBJECTIVE_AUDIT.zh-TW.md",
        bundle_dir / "SENS_V2_STATUS.zh-TW.md",
    ]
    results["artifact_bundle"] = {
        "status": "pass" if has_all(bundle_files) else "fail",
        "reason": "Delivery bundle must include core evidence, outputs, and audit docs.",
    }

    failure_visible_ok = contains(audit, "downgrade") and contains(process_notes, "403") and contains(process_notes, "blocked")
    results["failure_non_silent"] = {
        "status": "pass" if failure_visible_ok else "partial",
        "reason": "Known failures and constraints must be documented rather than hidden.",
    }

    generality_ok = contains(readme, "bounded autonomous research flow") and contains(checklist, "通用任務代理")
    results["task_generality"] = {
        "status": "pass" if generality_ok else "partial",
        "reason": "System framing should emphasize reusable task-agent behavior, not only one domain.",
    }

    adoption_gate_ok = contains(scoring_doc, ">= 85") and contains(scoring_doc, "Critical Gate")
    results["adoption_gate"] = {
        "status": "pass" if adoption_gate_ok else "fail",
        "reason": "Adoption must require score thresholds and critical gates.",
    }

    total = 0.0
    critical_failures = []
    rows = []
    for scenario in scenarios:
        sid = scenario["id"]
        weight = float(scenario["weight"])
        status_name = results[sid]["status"]
        fraction = 1.0 if status_name == "pass" else 0.5 if status_name == "partial" else 0.0
        score = weight * fraction
        total += score
        if scenario["critical"] and status_name != "pass":
            critical_failures.append(sid)
        rows.append(
            {
                "id": sid,
                "weight": weight,
                "critical": scenario["critical"],
                "status": status_name,
                "score": round(score, 1),
                "reason": results[sid]["reason"],
            }
        )

    normalized_total = round((total / score_weight_total) * 100, 1) if score_weight_total else 0.0
    readiness = "ready" if normalized_total >= 85 and not critical_failures else "conditionally_ready" if normalized_total >= 70 and not critical_failures else "not_ready"

    return {
        "score_total": normalized_total,
        "score_max": 100,
        "score_raw": round(total, 1),
        "score_weight_total": round(score_weight_total, 1),
        "readiness": readiness,
        "critical_failures": critical_failures,
        "scenarios": rows,
    }


def write_outputs(report: dict) -> None:
    json_path = OUTPUT_DIR / "task_agent_readiness_report.json"
    md_path = OUTPUT_DIR / "task_agent_readiness_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Task Agent Readiness Report",
        "",
        f"- Score: {report['score_total']} / {report['score_max']}",
        f"- Raw weighted score: {report['score_raw']} / {report['score_weight_total']}",
        f"- Readiness: {report['readiness']}",
        f"- Critical failures: {', '.join(report['critical_failures']) if report['critical_failures'] else 'none'}",
        "",
        "| Scenario | Status | Score | Weight | Critical |",
        "| --- | --- | ---: | ---: | --- |",
    ]
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
