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

### 1. Recommended first run

Use this first. It is the canonical no-LLM install check and should be boringly reliable on a fresh checkout.

```bash
python3 scripts/verify_ai_company_installation.py
```

If this is a fresh checkout and frontend dependencies are not installed yet, bootstrap the dashboard once before the full check:

```bash
cd agent_os_mvp/frontend && pnpm install
```

For a smaller core-only check:

```bash
python3 scripts/verify_ai_company_installation.py --skip-dashboard --skip-frontend
```

This runs docs encoding, core Python tests, mock success, a watchdog check after mock success, mock replan, dashboard backend tests, and the frontend build. It does not require Claude, Claude Code Router, an API key, or live model access.

Core run artifacts are written to:

```text
results/ai_company_task_harness/
```

### 2. Manual mock run

Use this only when you want to inspect one run step by step.

```bash
python3 scripts/run_ai_company_task_harness.py docs/ai_specs/common-research-summary-example.json --mode mock
python3 scripts/run_ai_company_watchdog.py --once
```

Run the watchdog only after the harness command exits. Watchdog status meanings:

```text
healthy   = no action needed
repairing = bounded repair or regeneration happened
escalated = manual review is required; do not treat this as a green run
```

Each run now includes:

```text
ai_company/input_guard_report.json
ai_company/output_guard_report.json
ai_company/contract_validation_report.json
```

### 3. Minimum live-ready setup

Copy or keep this repository in the project that already has Claude Code + Claude Code Router configured.

Required runtime assumptions:

- `claude` and/or `ccr` available in PATH, or
- `AI_COMPANY_WORKER_SCRIPTS_DIR` pointing to project-specific worker scripts

The repository now bundles local worker adapters under `scripts/`:

- `worker_claude_router.sh`
- `worker_claude_router_managed_single_file.sh`
- `worker_claude_router_summary_template.sh`

These adapters provide a portable execution entrypoint and explicit failure reporting. If live runtime wiring is still missing, runs fail fast with `WORKER_RUNTIME_MISSING` instead of silently falling through.

### 4. Dashboard install / run

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

Windows direct launch:

```powershell
.\agent_os_mvp\start-dashboard.ps1
```

If `8010` or `5174` is already owned by another process, the Windows launcher now fails loudly with the owning PID and command line instead of opening a stale dashboard from another workspace. Use explicit alternate ports when needed:

```powershell
.\agent_os_mvp\start-dashboard.ps1 -BackendPort 8014 -FrontendPort 5180
```

The launcher waits for backend `/health` and frontend HTML before reporting success. Use `.\agent_os_mvp\stop-dashboard.ps1` to stop the recorded child processes.
On success it prints the backend URL, frontend URL, backend/frontend PIDs, log directory, and stop command.

The dashboard reads `results/ai_company_task_harness/` when launched in the same project root and now surfaces input guard, output guard, and contract validation artifacts through the monitor backend.

Simple dashboard guide:

```text
docs/DASHBOARD_USAGE.zh-TW.md
```

## Verification after install or changes

Run the full no-LLM verification suite:

```bash
python3 scripts/verify_ai_company_installation.py
```

This checks documentation encoding, core Python tests, mock success, watchdog health after mock success, mock replan, dashboard backend tests, and the frontend build. It does not require Claude, Claude Code Router, an API key, or live model access. If watchdog returns `escalated`, verification fails instead of reporting a silent green check.

For a smaller core-only check:

```bash
python3 scripts/verify_ai_company_installation.py --skip-dashboard --skip-frontend
```

To run the optional offline live-LLM case with the bundled Docker worker image:

```bash
python3 scripts/verify_ai_company_live_llm.py
```

Or include it in the full verification suite:

```bash
python3 scripts/verify_ai_company_installation.py --include-live-llm
```

The live-LLM check uses local fixtures and does not browse the internet. It requires Docker and a local `claude-ccr:ubuntu22`-compatible image containing `claude` or `ccr`.

To run the optional dashboard browser smoke in an environment with Playwright installed:

```bash
python3 scripts/verify_ai_company_installation.py --include-browser-smoke
```

This launches the backend/frontend on temporary ports, checks `/health` and `/api/ai-company-monitor`, opens the dashboard in a headless browser, verifies the `Run Operations` first screen and the six tabs, then cleans up the child processes.

Score currently available LLM models through the same AI-company live harness:

```bash
python3 scripts/evaluate_llm_models.py --suite smoke
```

Run only the complex coding benchmark:

```bash
python3 scripts/evaluate_llm_models.py --suite complex
```

The complex benchmark only marks a model as coding-capable when the target file change passes tests and the matching task verdict is accepted by the reviewer gate.

Additional reliability suite aliases are available:

- `format-noise`: exercises worker output extraction and format recovery using the live smoke fixture.
- `semantic-edge`: exercises unit/exception edge cases using the complex coding fixture.
- `repair-loop`: exercises bounded repair/reassignment observability using the complex coding fixture.

Current recommended default model for live runs is `qwen3:4b`, based on the latest complex benchmark scorecard. Live runs also write `ai_company/llm_reliability_report.json` so you can see the actual model, repair attempts, format recovery, and scorecard snapshot.

For multiple known models:

```bash
CCR_MODEL_CANDIDATES=qwen3:4b,gemma3:4b,qwen2.5-coder:3b python3 scripts/evaluate_llm_models.py --suite smoke
```

Scorecards are written under:

```text
results/llm_model_evaluation/
```

Scorecard `Best for` labels:

- `coding_direct`: complex coding passed without repair or reassignment.
- `coding_with_repair`: complex coding passed, but only with repair/reassignment gates.
- `summary_only`: bounded smoke/summary tasks are acceptable, but complex coding needs more evidence.
- `not_recommended`: do not use for live AI-company work yet.

Feature-by-feature testing guidance:

```text
docs/TEST_PLAN.zh-TW.md
```

Backend pytest teardown diagnosis:

```bash
cd agent_os_mvp/backend
python -m pytest -q tests/test_agent_engine.py
```

If the test prints a pass summary but does not exit, capture it as a teardown bug with the Python version, OS, and timeout used. Do not assume the root cause until it reproduces in a clean virtual environment.

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
