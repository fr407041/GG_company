---
name: ai-company-task-validator
description: Run bounded ai-company style task planning, reviewer gating, and KPI validation for generic tasks. Use when Claude needs to validate a multi-agent task flow, stress timeout or replan recovery, or produce a measurable KPI report for a repository task without overfocusing on a single domain example.
---

# AI Company Task Validator

Run the generic task harness instead of hand-assembling meeting, execution, and reviewer steps.

## Use

1. Read the task spec from `docs/ai_specs/*.json`.
2. If the request is deterministic or a fast sanity check, run mock mode:

```bash
python scripts/run_ai_company_task_harness.py docs/ai_specs/general-task-mock-success.json --mode mock
```

3. If the request needs real router plus open-source model behavior, run live mode from a Linux environment that already has the Claude router stack available:

```bash
python scripts/run_ai_company_task_harness.py docs/ai_specs/general-task-live-bounded.json --mode live
```

4. To evaluate the packaged sample cases and get one aggregate KPI file, run:

```bash
python scripts/evaluate_ai_company_task_skill.py
```

5. For a more realistic coding-task stress case with a real bug and unit tests, run:

```bash
python scripts/run_ai_company_task_harness.py docs/ai_specs/complex-coding-live.json --mode live
```

## Rules

- Keep every task at 3 files or fewer.
- Prefer generic repository tasks over domain-specific demos unless the user explicitly asks for a domain case.
- Treat `CHILD_TIMEOUT`, `ROUTER_ERROR`, `OVERFLOW_DETECTED`, and `NEEDS_REPLAN` as recoverable reviewer-visible states, not silent failures.
- Report KPI fields from `ai_company/task_harness_report.json` or `results/ai_company_task_skill/task_skill_report.json`.
- If live mode is unavailable on the current host, state that clearly and fall back to mock mode or an existing Linux runner.

## Files

- `scripts/run_ai_company_task_harness.py`: end-to-end generic task runner.
- `scripts/evaluate_ai_company_task_skill.py`: sample-case KPI evaluator.
- `configs/ai_company/task_harness.defaults.json`: centralized knobs for rounds, reassignments, and timeouts.
- `docs/ai_specs/*.json`: reusable generic task specs.
