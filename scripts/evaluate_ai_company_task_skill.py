from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = ROOT / "tests" / "ai_company_task_skill_cases.json"
OUTPUT_DIR = ROOT / "results" / "ai_company_task_skill"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    cases = read_json(CASES_PATH)["cases"]
    rows = []
    passed = 0
    for case in cases:
        spec_path = ROOT / case["spec"]
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_ai_company_task_harness.py"), str(spec_path), "--mode", case["mode"]],
            check=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        report = json.loads(proc.stdout)
        rows.append(
            {
                "id": case["id"],
                "mode": case["mode"],
                "overall_status": report["overall_status"],
                "pass_rate": report["expectations"]["pass_rate"],
                "meeting_status": report["kpis"]["meeting_status"],
                "accepted_count": report["kpis"]["accepted_count"],
                "reassignment_count": report["kpis"]["reassignment_count"],
                "reviewer_verdict_count": report["kpis"]["reviewer_verdict_count"],
            }
        )
        if report["overall_status"] == "pass":
            passed += 1

    summary = {
        "case_count": len(rows),
        "passed_count": passed,
        "pass_rate": round(passed / len(rows), 3) if rows else 0.0,
        "cases": rows,
    }
    out = OUTPUT_DIR / "task_skill_report.json"
    write_json(out, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
