# GG_company

Company-ready AI-company orchestration package for `Claude Code + Claude Code Router + open-source LLM` on Ubuntu.

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

## Company Ubuntu quick install

Copy or keep this repository in the project that already has Claude Code + Claude Code Router configured.

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

## Run a minimal mock flow

```bash
python3 scripts/run_ai_company_task_harness.py docs/ai_specs/common-research-summary-example.json --mode mock
python3 scripts/run_ai_company_watchdog.py --once
```

Run artifacts are written to:

```text
results/ai_company_task_harness/
```

The dashboard reads that folder when launched in the same project root.

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
