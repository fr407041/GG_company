# GG_company

Company-ready AI-company orchestration package for `Claude Code + Claude Code Router + open-source LLM` on Ubuntu, with bounded multi-agent planning, reviewer gates, watchdog recovery, and harness-level contract validation.

This repository intentionally excludes Docker test assets, local model downloads, runtime logs, `results/`, `tmp/`, `.venv`, and `node_modules`.

## What is included

- `.claude/skills/research-task-orchestrator/`
  - main AI-company skill
  - bundled dashboard source under `assets/agent_os_mvp/`
  - dashboard install/start/stop/smoke scripts
- `scripts/`
  - task harness
  - meeting / execution / reviewer workers
  - watchdog
  - memory guard
  - claim ledger
  - input / output guardrails
  - contract validation helpers
  - local worker adapters
  - validation helpers
- `configs/ai_company/`
  - task defaults
  - schemas
  - KPI and assignment rules
- `agent_os_mvp/`
  - standalone dashboard source for development or direct launch
- `docs/`
  - Chinese usage and validation docs
- `tests/`
  - regression tests for watchdog, claim ledger, memory guard, and orchestration contracts

## Quickstart levels

### 1. Minimum mock run

This path is the smallest reproducible regression setup. It does not require live model access.

```bash
python3 scripts/run_ai_company_task_harness.py docs/ai_specs/common-research-summary-example.json --mode mock
python3 scripts/run_ai_company_watchdog.py --once
```

Core run artifacts are written to:

```text
results/ai_company_task_harness/
```

Each run now includes:

```text
ai_company/input_guard_report.json
ai_company/output_guard_report.json
ai_company/contract_validation_report.json
```

### 2. Minimum live-ready setup

Copy or keep this repository in the project that already has Claude Code + Claude Code Router configured.

Required runtime assumptions:

- `claude` and/or `ccr` available in PATH, or
- `AI_COMPANY_WORKER_SCRIPTS_DIR` pointing to project-specific worker scripts

The repository now bundles local worker adapters under `scripts/`:

- `worker_claude_router.sh`
- `worker_claude_router_managed_single_file.sh`
- `worker_claude_router_summary_template.sh`

These adapters provide a portable execution entrypoint and explicit failure reporting. If live runtime wiring is still missing, runs fail fast with `WORKER_RUNTIME_MISSING` instead of silently falling through.

### 3. Dashboard install / run

Install dashboard from the skill package:

```bash
bash .claude/skills/research-task-orchestrator/scripts/install_dashboard.sh
```

Start dashboard:

```bash
bash .claude/skills/research-task-orchestrator/scripts/start_dashboard.sh
```

Open:

```text
http://127.0.0.1:5174
```

Backend health:

```text
http://127.0.0.1:8010/health
```

The dashboard reads `results/ai_company_task_harness/` when launched in the same project root and now surfaces input guard, output guard, and contract validation artifacts through the monitor backend.

Simple dashboard guide:

```text
docs/DASHBOARD_USAGE.zh-TW.md
```

## Skill usage from Claude Code

Example prompts:

```text
Use the research-task-orchestrator skill to install the dashboard.
Use the research-task-orchestrator skill to run this bounded task and show the latest run in the dashboard.
Use the research-task-orchestrator skill to monitor the latest run with the watchdog.
```

## Safety notes

- Do not commit real API keys or passwords.
- Use dummy keys or runtime environment variables only.
- This package does not install Claude Code, Claude Code Router, or any model.
- This package assumes your company Ubuntu environment already has router/open-source LLM access.
- Suspicious instructions such as prompt-injection attempts are blocked before execution and recorded in `input_guard_report.json`.
- Malformed output, schema-invalid artifacts, and missing worker runtime are recorded as structured failure families instead of being treated as implicit success.
