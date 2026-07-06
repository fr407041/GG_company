from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from main_agent_memory_guard import run_guard  # noqa: E402
from run_ai_company_execution import create_reassignment_job  # noqa: E402
from run_ai_company_meeting import build_meeting_decision  # noqa: E402


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class MainAgentMemoryGuardTest(unittest.TestCase):
    def make_run(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix="memory-guard-test-"))
        run_dir = root / "run-20260706-000000-memory"
        (run_dir / "ai_company").mkdir(parents=True)
        (run_dir / "jobs").mkdir()
        (run_dir / "results").mkdir()
        write_json(
            run_dir / "summary.json",
            {
                "run_id": run_dir.name,
                "task": "Validate memory guard behavior",
                "strategy": "Keep main-agent state compact.",
            },
        )
        write_json(run_dir / "plan.json", {"strategy": "Use bounded checkpointing.", "jobs": []})
        write_json(
            run_dir / "ai_company" / "meeting_decision.json",
            {
                "decision_summary": "Proceed with bounded execution.",
                "convergence_reason": "Scope is small enough.",
                "open_risks": ["token overflow on long runs"],
            },
        )
        write_json(
            run_dir / "jobs" / "job-001.json",
            {
                "id": "job-001",
                "title": "Do one thing",
                "files": ["summary.md"],
                "success_check": "summary exists",
            },
        )
        return run_dir

    def test_small_run_does_not_create_checkpoint(self) -> None:
        run_dir = self.make_run()
        entry = run_guard(
            run_dir,
            "after_materialize",
            True,
            token_threshold=24000,
            hard_threshold=32000,
            excerpt_chars=1200,
            checkpoint_max_chars=8000,
            checkpoint_dir_name="ai_company",
        )
        self.assertFalse(entry["checkpoint_created"])
        self.assertFalse((run_dir / "ai_company" / "main_agent_memory_checkpoint.json").exists())

    def test_large_run_creates_checkpoint_with_required_sections(self) -> None:
        run_dir = self.make_run()
        long_text = "reasoning pressure " * 10000
        (run_dir / "results" / "job-001.raw.txt").write_text(long_text, encoding="utf-8")
        write_json(
            run_dir / "results" / "job-001.status.json",
            {
                "id": "job-001",
                "status": "OVERFLOW_DETECTED",
                "verification_note": "simulated overflow",
            },
        )

        entry = run_guard(
            run_dir,
            "after_execution",
            True,
            token_threshold=1000,
            hard_threshold=2000,
            excerpt_chars=12000,
            checkpoint_max_chars=4000,
            checkpoint_dir_name="ai_company",
        )

        self.assertTrue(entry["checkpoint_created"])
        self.assertTrue(entry["hard_limit_exceeded"])
        checkpoint_path = run_dir / "ai_company" / "main_agent_memory_checkpoint.json"
        markdown_path = run_dir / "ai_company" / "main_agent_memory_checkpoint.md"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual("Validate memory guard behavior", checkpoint["goal"])
        self.assertIn("Proceed with bounded execution.", checkpoint["decisions"])
        self.assertEqual("job-001", checkpoint["failures"][0]["task_id"])
        self.assertIn("Next Recommended Action", markdown)
        self.assertLessEqual(len(checkpoint["condensed_state"]), 4012)

    def test_report_accumulates_phase_entries_and_kpis(self) -> None:
        run_dir = self.make_run()
        run_guard(run_dir, "after_materialize", True, 24000, 32000, 1200, 8000, "ai_company")
        (run_dir / "results" / "job-001.prompt.txt").write_text("x" * 10000, encoding="utf-8")
        run_guard(run_dir, "after_meeting", True, 1000, 2000, 10000, 2000, "ai_company")

        report = json.loads((run_dir / "ai_company" / "main_agent_memory_guard_report.json").read_text(encoding="utf-8"))
        self.assertEqual(2, len(report["entries"]))
        self.assertEqual(1, report["memory_checkpoint_count"])
        self.assertGreaterEqual(report["max_estimated_main_agent_tokens"], 2500)
        self.assertLess(report["checkpoint_compression_rate"], 1.0)

    def test_meeting_uses_existing_checkpoint_as_condensed_state(self) -> None:
        run_dir = self.make_run()
        (run_dir / "results" / "job-001.raw.txt").write_text("pressure " * 10000, encoding="utf-8")
        run_guard(run_dir, "after_execution", True, 1000, 2000, 12000, 4000, "ai_company")

        meeting = build_meeting_decision(run_dir, "fallback task")
        constraints = "\n".join(meeting["constraints"])
        actions = "\n".join(
            action
            for entry in meeting["discussion_log"]
            for action in entry.get("proposed_actions", [])
        )

        self.assertIn("main-agent memory checkpoint", constraints)
        self.assertIn("Use main-agent memory checkpoint as condensed prior state", actions)
        self.assertIn("long runs", "\n".join(meeting["open_risks"]))

    def test_reassignment_instruction_references_checkpoint_without_replaying_logs(self) -> None:
        run_dir = self.make_run()
        source_job = {
            "id": "job-001",
            "title": "Repair one output",
            "instruction": "Original narrow instruction.",
            "files": ["summary.md"],
            "owner_role": "executor_docs",
            "require_change": True,
            "scope_path": str(run_dir),
        }
        write_json(run_dir / "jobs" / "job-001.json", source_job)
        (run_dir / "results" / "job-001.raw.txt").write_text("pressure " * 10000, encoding="utf-8")
        run_guard(run_dir, "after_execution", True, 1000, 2000, 12000, 4000, "ai_company")

        reassigned_path = create_reassignment_job(
            run_dir,
            source_job,
            {"task_id": "job-001", "verdict": "REPLAN_REQUIRED"},
            1,
        )
        reassigned = json.loads(reassigned_path.read_text(encoding="utf-8"))

        self.assertIn("MAIN_AGENT_MEMORY_CHECKPOINT_AVAILABLE", reassigned["instruction"])
        self.assertIn("main_agent_memory_checkpoint.md", reassigned["instruction"])
        self.assertIn("Next recommended action", reassigned["instruction"])
        self.assertIn("Do not request or replay full prior logs", reassigned["instruction"])


if __name__ == "__main__":
    unittest.main()
