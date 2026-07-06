from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_ai_company_watchdog import watchdog_once
from subagent_claim_ledger import write_claim_ledger


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class AiCompanyWatchdogTests(unittest.TestCase):
    def make_run(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        run_dir = Path(temp_dir.name) / "run-20260706-000000-watchdog-test"
        (run_dir / "ai_company").mkdir(parents=True)
        (run_dir / "jobs").mkdir()
        (run_dir / "results").mkdir()
        (run_dir / "worktree").mkdir()
        write_json(
            run_dir / "ai_company" / "meeting_decision.json",
            {
                "meeting_status": "MEETING_READY",
                "task_assignments": [
                    {
                        "task_id": "job-001",
                        "owner_role": "synthesis_agent",
                        "scope": ["summary.md"],
                        "depends_on": [],
                    }
                ],
            },
        )
        write_json(
            run_dir / "jobs" / "job-001.json",
            {
                "id": "job-001",
                "title": "Watchdog task",
                "scope_path": str(run_dir / "worktree"),
                "files": ["summary.md"],
                "owner_role": "synthesis_agent",
                "require_change": True,
                "success_check": "summary.md exists",
            },
        )
        return run_dir

    def defaults(self, **overrides: object) -> dict:
        payload = {
            "watchdog_enabled": True,
            "watchdog_interval_sec": 30,
            "watchdog_stale_after_sec": 1,
            "watchdog_max_repair_attempts_per_task": 1,
            "watchdog_max_total_actions_per_run": 3,
            "watchdog_require_final_artifact_verify": True,
        }
        payload.update(overrides)
        return payload

    def write_success_artifacts(self, run_dir: Path) -> None:
        raw = run_dir / "results" / "job-001.raw.txt"
        raw.write_text("- Completed summary with evidence.\n", encoding="utf-8")
        (run_dir / "results" / "job-001.test.txt").write_text("ok\n", encoding="utf-8")
        (run_dir / "worktree" / "summary.md").write_text("- good summary\nTakeaway: ok\n", encoding="utf-8")
        write_json(
            run_dir / "results" / "job-001.status.json",
            {
                "id": "job-001",
                "status": "SUCCESS",
                "scope_path": str(run_dir / "worktree"),
                "files": ["summary.md"],
                "owner_role": "synthesis_agent",
                "actual_changed_files": ["summary.md"],
                "actual_changed_count": 1,
                "verification_note": "success",
                "raw_file": str(raw),
                "test_output_file": str(run_dir / "results" / "job-001.test.txt"),
                "key_claims": [{"claim": "Summary was created from bounded evidence."}],
            },
        )
        ledger = write_claim_ledger(run_dir)
        write_json(
            run_dir / "ai_company" / "reviewer_verdicts.json",
            {
                "verdicts": [
                    {
                        "task_id": "job-001",
                        "owner_role": "synthesis_agent",
                        "verdict": "ACCEPTED",
                        "evidence": ["status_file:job-001.status.json"],
                        "repair_action": "",
                        "replan_required": False,
                    }
                ],
                "accepted_count": 1,
                "verdict_count": 1,
                "claim_ledger_metrics": ledger["metrics"],
            },
        )
        write_json(
            run_dir / "ai_company" / "artifact_verify_report.json",
            {"parsed": {"all_passed": True, "score": 1.0, "checks": {"ok": True}}},
        )

    def test_happy_path_no_action(self) -> None:
        run_dir = self.make_run()
        self.write_success_artifacts(run_dir)

        report = watchdog_once(run_dir, self.defaults())

        self.assertEqual(report["watchdog_status"], "healthy")
        self.assertEqual(report["repair_attempts_used"], 0)
        self.assertEqual(report["events"], [])

    def test_missing_status_file_creates_fallback(self) -> None:
        run_dir = self.make_run()

        report = watchdog_once(run_dir, self.defaults(watchdog_require_final_artifact_verify=False))
        status = json.loads((run_dir / "results" / "job-001.status.json").read_text(encoding="utf-8"))

        self.assertTrue(any(item["type"] == "MISSING_STATUS_FILE" for item in report["events"]))
        self.assertEqual(status["detected_by"], "watchdog")
        self.assertEqual(status["failure_reason"], "MISSING_STATUS_FILE")

    def test_stale_running_task_marked_timeout(self) -> None:
        run_dir = self.make_run()
        raw = run_dir / "results" / "job-001.raw.txt"
        raw.write_text("still running\n", encoding="utf-8")
        status_path = run_dir / "results" / "job-001.status.json"
        write_json(
            status_path,
            {
                "id": "job-001",
                "status": "RUNNING",
                "scope_path": str(run_dir / "worktree"),
                "files": ["summary.md"],
                "owner_role": "synthesis_agent",
                "verification_note": "running",
                "raw_file": str(raw),
            },
        )
        old = time.time() - 10
        os.utime(status_path, (old, old))

        report = watchdog_once(run_dir, self.defaults(watchdog_require_final_artifact_verify=False))
        repaired = json.loads(status_path.read_text(encoding="utf-8"))

        self.assertTrue(any(item["type"] == "STALE_RUNNING_TASK" for item in report["events"]))
        self.assertEqual(repaired["status"], "CHILD_TIMEOUT")
        self.assertEqual(repaired["failure_reason"], "STALE_RUNNING_TASK")

    def test_missing_reviewer_is_regenerated(self) -> None:
        run_dir = self.make_run()
        self.write_success_artifacts(run_dir)
        (run_dir / "ai_company" / "reviewer_verdicts.json").unlink()

        report = watchdog_once(run_dir, self.defaults())
        reviewer = json.loads((run_dir / "ai_company" / "reviewer_verdicts.json").read_text(encoding="utf-8"))

        self.assertTrue(any(item["type"] == "REVIEWER_MISSING" for item in report["events"]))
        self.assertEqual(reviewer["verdict_count"], 1)

    def test_claim_ledger_missing_is_rebuilt(self) -> None:
        run_dir = self.make_run()
        self.write_success_artifacts(run_dir)
        (run_dir / "ai_company" / "subagent_claim_ledger.json").unlink()

        report = watchdog_once(run_dir, self.defaults())

        self.assertTrue((run_dir / "ai_company" / "subagent_claim_ledger.json").exists())
        self.assertNotIn("CLAIM_LEDGER_MISSING_OR_INVALID", [item["type"] for item in report["events"]])

    def test_post_verify_missing_escalates_when_not_repairable(self) -> None:
        run_dir = self.make_run()
        self.write_success_artifacts(run_dir)
        (run_dir / "ai_company" / "artifact_verify_report.json").unlink()

        report = watchdog_once(run_dir, self.defaults(watchdog_max_total_actions_per_run=0))

        self.assertEqual(report["watchdog_status"], "escalated")
        self.assertTrue(any(item["type"] == "FINAL_NOT_PASS" for item in report["events"]))


if __name__ == "__main__":
    unittest.main()
