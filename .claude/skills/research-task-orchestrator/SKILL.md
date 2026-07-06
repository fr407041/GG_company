---
name: research-task-orchestrator
description: Run bounded multi-agent research or analysis tasks through Claude Code plus router with a meeting phase, compact evidence preparation, small child-job dispatch, artifact verification, and an installable web dashboard. Use when Codex needs to turn an open-ended research request into a measurable workflow that avoids token overflow, detects false success, records meeting decisions/task assignment/KPI results, or installs/starts/uses the bundled ai-company dashboard.
---

# Research Task Orchestrator

Use this skill to run a reusable `ai-company` style workflow without sending broad context to a child worker.

The skill also bundles a lightweight web dashboard. Installing the skill alone is enough to install the dashboard into a project workspace on first use.

## Workflow

1. Define a bounded task.
2. Prepare compact evidence files before dispatch.
3. Run a short meeting to converge on owners, scope, and fallback.
4. Dispatch only small jobs to child workers.
5. Verify the final artifact with explicit checks and score thresholds.

## Required behavior

- Never ask a child worker to read an entire repo or large folder.
- Keep each non-review task at 3 files or fewer.
- Prefer deterministic prep scripts over live browsing inside child workers.
- Require a post-verify step with `all_passed=true` before considering the run successful.
- Require every accepted subagent result to have at least one key claim with traceable evidence refs.
- Record meeting output in structured JSON so stop hooks and KPI checks can validate it.
- Enable the main-agent memory guard for token-overflow-prone, long-running, large research, or multi-round analysis tasks.
- When a user asks for the web UI, dashboard, monitor, or latest run view, install the bundled dashboard if it is not already present.
- When a user asks to monitor a run, check whether work is stuck, or recover a silent failure, run the main-agent watchdog instead of relying on dashboard display alone.
- Do not install Claude Code, Claude Code Router, or model services. This skill assumes those already exist in the company Ubuntu environment.

## Repo entrypoints

- Generic spec example:
  - `docs/ai_specs/common-research-summary-example.json`
- Generic prep script:
  - `scripts/prepare_common_research_case.py`
- Generic artifact verifier:
  - `scripts/verify_common_research_artifact.py`
- Generic runner:
  - `scripts/run_common_research_with_router.sh`
- Generic goal check:
  - `scripts/check_common_research_goal.js`
- Simple Web GUI docs:
  - `docs/common_research_orchestrator_zh-TW.md`
- Bundled Simple Web GUI payload:
  - `assets/agent_os_mvp/`
- Dashboard scripts:
  - `scripts/install_dashboard.sh`
  - `scripts/start_dashboard.sh`
  - `scripts/stop_dashboard.sh`
  - `scripts/smoke_dashboard.sh`
- Main-agent memory guard:
  - `scripts/main_agent_memory_guard.py`
- Subagent claim ledger:
  - `scripts/subagent_claim_ledger.py`
- Main-agent watchdog:
  - `scripts/run_ai_company_watchdog.py`

## How to use the generic pattern

1. Copy `tests/fixtures/ai_company_common_research_case` to a new case directory.
2. Replace `research_brief.md`, `evidence_summary.txt`, and `artifact_requirements.json` with the new task inputs.
3. Duplicate `docs/ai_specs/common-research-summary-example.json` and point `scope_subdir` plus `scope_copy_from` at the new case directory.
4. Keep the worker template as `summary_markdown` unless a broader file-edit task is really needed.
5. Run the spec through the generic runner.

## Web Dashboard

Use the bundled single-page Web GUI when you need a low-dependency monitor for:
- current run status
- active agents
- final result credibility
- expandable technical details only when needed

Design rules:
- Keep the default view to one page.
- Show only three primary sections first: current status, who is working, and whether the result is trustworthy.
- Keep meeting traces, prompts, raw output, and logs behind expandable details.
- Use the existing FastAPI + React + SQLite stack only. Do not introduce extra dashboard frameworks unless there is a strong reason.

Dashboard installation flow:

1. Locate the project root. Prefer `AI_COMPANY_PROJECT_ROOT` when set; otherwise use the current git root; otherwise use the current working directory.
2. If `./agent_os_mvp/backend/.venv` or `./agent_os_mvp/frontend/node_modules` is missing, run:

```bash
bash .claude/skills/research-task-orchestrator/scripts/install_dashboard.sh
```

3. Start the dashboard with:

```bash
bash .claude/skills/research-task-orchestrator/scripts/start_dashboard.sh
```

4. Show the user:
   - Backend health: `http://127.0.0.1:8010/health`
   - Frontend URL: `http://127.0.0.1:5174`
   - Artifacts root: `results/ai_company_task_harness`

If the dashboard opens with zero runs, explain that no compatible run artifacts have been generated yet. Do not describe that as a dashboard failure.

Stop the dashboard with:

```bash
bash .claude/skills/research-task-orchestrator/scripts/stop_dashboard.sh
```

Run a minimal dashboard check with:

```bash
bash .claude/skills/research-task-orchestrator/scripts/smoke_dashboard.sh
```

## Stop and replan conditions

- Child output mentions context-window or output-token errors.
- Router returns empty, partial, or transport-failure responses.
- A subagent summary contains a key claim without an evidence ref.
- Reviewer marks `REPLAN_REQUIRED`, `REPAIR_REQUIRED`, or `FALSE_SUCCESS_BLOCKED`.
- Artifact verification score is below the required threshold.

When any of these happens, reduce scope first. Do not retry the same broad job unchanged.

## Main Agent Watchdog

Use the watchdog to detect silent run failures that are not obvious from a chat response.

Run one check:

```bash
python3 scripts/run_ai_company_watchdog.py <run_dir> --once
```

Monitor the latest run continuously:

```bash
python3 scripts/run_ai_company_watchdog.py --watch
```

The watchdog writes:
- `ai_company/watchdog_report.json`
- `ai_company/watchdog_events.jsonl`
- `ai_company/heartbeat.json`

Watchdog responsibilities:
- detect missing status files
- mark stale non-terminal tasks as `CHILD_TIMEOUT`
- regenerate reviewer verdicts when missing or incomplete
- rebuild claim ledger and verify accepted claims still have evidence
- rerun final artifact verification when possible
- escalate with `WATCHDOG_ESCALATION_REQUIRED` when bounded recovery cannot make the run trustworthy

The watchdog must stay bounded. It must not loop forever, install tools, change router/model settings, or replay large raw logs into main context.

## Main Agent Memory Guard

Use the phase-gate memory guard to prevent the master process from carrying too much accumulated context.

The guard runs after:
- `after_materialize`
- `after_prep`
- `after_meeting`
- `after_execution`
- `after_post_verify`

Each gate estimates portable context pressure from run artifacts with `estimated_tokens = ceil(chars / 4)`. If the estimate exceeds `main_agent_memory_token_threshold`, write:
- `ai_company/main_agent_memory_checkpoint.md`
- `ai_company/main_agent_memory_checkpoint.json`
- `ai_company/main_agent_memory_guard_report.json`

The checkpoint must include:
- goal
- current phase
- decisions
- active tasks
- completed tasks
- failures
- open risks
- next recommended action
- files/artifacts map

When a checkpoint exists:
- Use it as condensed prior state for meeting and reassignment decisions.
- Do not replay full prior logs into prompts.
- Do not pass the checkpoint to child workers as broad context unless a specific bounded task requires one short excerpt.

Default thresholds live in `configs/ai_company/task_harness.defaults.json`.

## Subagent Summary Evidence Contract

Keep subagent handoff short, but never make the main agent rely on summary text alone.

Every subagent result must be represented in `ai_company/subagent_claim_ledger.json` with:
- `summary`: 3-5 sentence bounded handoff
- `key_claims`: one or more concrete claims
- `evidence_refs`: raw/status/file/source references for each claim
- `confidence`: `high`, `medium`, or `low`
- `limitations`: missing evidence, uncertainty, or known weak points
- `handoff_next`: the suggested next main-agent action

Reviewer rules:
- An accepted subagent result must have at least one key claim.
- Every key claim must have at least one evidence ref.
- A success response with missing evidence must be blocked as `FALSE_SUCCESS_BLOCKED` or repaired before acceptance.
- If a confident summary is stronger than the available evidence, mark an uncertainty gap and request repair.

Main-agent rules:
- Read the claim ledger first when replanning.
- Use raw output only for traceability, not as default main context.
- When a memory checkpoint exists, preserve the claim ledger inside the checkpoint so later phases can continue from claims plus evidence refs instead of full logs.

## Company Ubuntu Install Model

For company rollout, publish the whole `.claude/skills/research-task-orchestrator` folder. Users should not need a separate dashboard zip.

The first dashboard install may run `python3 -m venv`, `pip install -r requirements.txt`, and `npm install`. These commands are limited to the local `agent_os_mvp` dashboard directory.

## References

- Read `references/spec-pattern.md` when creating a new generic research spec.
- Read `references/kpi-checklist.md` when deciding what success criteria and score thresholds to enforce.

## Validation

After creating or changing this skill, run:

```bash
python C:/Users/fr407/.codex/skills/.system/skill-creator/scripts/quick_validate.py .claude/skills/research-task-orchestrator
```
