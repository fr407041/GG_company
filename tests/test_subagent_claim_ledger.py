from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from main_agent_memory_guard import run_guard
from run_ai_company_execution import create_reassignment_job
from run_ai_company_reviewer_worker import build_reviewer_payload
from subagent_claim_ledger import build_claim_ledger, validate_claim_contract, write_claim_ledger


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class SubagentClaimLedgerTests(unittest.TestCase):
    def make_run(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        run_dir = Path(temp_dir.name) / "run-claim-ledger-test"
        (run_dir / "results").mkdir(parents=True)
        (run_dir / "jobs").mkdir(parents=True)
        (run_dir / "ai_company").mkdir(parents=True)
        write_json(run_dir / "summary.json", {"task": "Test claim ledger handoff"})
        write_json(run_dir / "plan.json", {"strategy": "bounded claim validation"})
        return run_dir

    def write_success_status(self, run_dir: Path, task_id: str = "job-001") -> Path:
        raw = run_dir / "results" / f"{task_id}.raw.txt"
        raw.write_text("- The worker found a bounded result backed by this raw artifact.\n", encoding="utf-8")
        status = {
            "id": task_id,
            "status": "SUCCESS",
            "scope_path": str(run_dir / "worktree"),
            "files": ["summary.md"],
            "owner_role": "synthesis_agent",
            "actual_changed_files": ["summary.md"],
            "actual_changed_count": 1,
            "verification_note": "mock success",
            "raw_file": str(raw),
            "test_output_file": str(run_dir / "results" / f"{task_id}.test.txt"),
            "confidence": "medium",
        }
        (run_dir / "results" / f"{task_id}.test.txt").write_text("ok\n", encoding="utf-8")
        write_json(run_dir / "results" / f"{task_id}.status.json", status)
        return run_dir / "results" / f"{task_id}.status.json"

    def test_success_status_creates_claim_with_evidence(self) -> None:
        run_dir = self.make_run()
        self.write_success_status(run_dir)

        ledger = write_claim_ledger(run_dir)
        contract = validate_claim_contract(ledger, {"job-001"})

        self.assertGreaterEqual(ledger["metrics"]["claim_count"], 1)
        self.assertEqual(ledger["metrics"]["claim_coverage_rate"], 1.0)
        self.assertTrue(contract["accepted_tasks_have_claim"])
        self.assertTrue(contract["all_claims_have_evidence"])

    def test_reviewer_blocks_success_claim_without_evidence(self) -> None:
        run_dir = self.make_run()
        status_path = self.write_success_status(run_dir)
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status["key_claims"] = [{"claim": "The worker claims success without backing evidence.", "evidence_refs": []}]
        write_json(status_path, status)

        reviewer = build_reviewer_payload(run_dir)

        self.assertEqual(reviewer["accepted_count"], 0)
        self.assertEqual(reviewer["false_success_blocked_count"], 1)
        self.assertEqual(reviewer["verdicts"][0]["verdict"], "FALSE_SUCCESS_BLOCKED")
        self.assertIn("claim_contract_issue:missing_evidence", reviewer["verdicts"][0]["evidence"])

    def test_reviewer_requires_claims_for_success(self) -> None:
        run_dir = self.make_run()
        raw = run_dir / "results" / "job-001.raw.txt"
        raw.write_text("short\n", encoding="utf-8")
        write_json(
            run_dir / "results" / "job-001.status.json",
            {
                "id": "job-001",
                "status": "SUCCESS",
                "scope_path": str(run_dir / "worktree"),
                "files": [],
                "owner_role": "synthesis_agent",
                "actual_changed_files": [],
                "actual_changed_count": 0,
                "verification_note": "",
                "raw_file": str(raw),
            },
        )

        reviewer = build_reviewer_payload(run_dir)

        self.assertEqual(reviewer["accepted_count"], 0)
        self.assertEqual(reviewer["verdicts"][0]["verdict"], "REPAIR_REQUIRED")
        self.assertIn("claim_count:0", reviewer["verdicts"][0]["evidence"])

    def test_checkpoint_preserves_claim_ledger(self) -> None:
        run_dir = self.make_run()
        self.write_success_status(run_dir)
        write_claim_ledger(run_dir)

        report = run_guard(
            run_dir=run_dir,
            phase="after_execution",
            enabled=True,
            token_threshold=1,
            hard_threshold=2,
            excerpt_chars=2000,
            checkpoint_max_chars=2000,
            checkpoint_dir_name="ai_company",
        )
        checkpoint = json.loads((run_dir / "ai_company" / "main_agent_memory_checkpoint.json").read_text(encoding="utf-8"))

        self.assertTrue(report["checkpoint_created"])
        self.assertIn("claim_ledger", checkpoint)
        self.assertGreaterEqual(checkpoint["claim_ledger"]["metrics"]["claim_count"], 1)

    def test_reassignment_instruction_references_claim_ledger(self) -> None:
        run_dir = self.make_run()
        self.write_success_status(run_dir)
        write_claim_ledger(run_dir)
        source_job = {
            "id": "job-001",
            "title": "Repair task",
            "instruction": "Original instruction",
            "files": ["summary.md"],
            "owner_role": "synthesis_agent",
            "require_change": True,
        }
        verdict = {"task_id": "job-001", "verdict": "REPAIR_REQUIRED"}

        path = create_reassignment_job(run_dir, source_job, verdict, 1)
        payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertIn("Claim ledger file:", payload["instruction"])
        self.assertIn("Do not replay full raw logs", payload["instruction"])


if __name__ == "__main__":
    unittest.main()
