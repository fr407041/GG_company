# GG_company

A minimal AI-company autopilot package for `Claude Code + router + open-source model` usage.

This repository now includes a practical dashboard bundle under `agent_os_mvp/` so a company Ubuntu or Windows environment can:

- run `Claude Code + Claude Code Router` as usual
- keep task results under `results/ai_company_task_harness`
- launch a small FastAPI + SQLite + React dashboard
- review meeting output, agent assignment, alert signals, and artifact checks from the browser

## Main Folders

- `agent_os_mvp/`
  - lightweight dashboard package
  - FastAPI backend
  - Vite + React frontend
  - Windows startup helpers
  - Linux startup helpers
- `configs/ai_company/`
  - autopilot rules, KPI spec, and test matrix
- `docs/`
  - installation, usage, and goal docs
- `.claude/`
  - project-local skill and goal manifest

## Start Here

- English package overview:
  - `agent_os_mvp/README.md`
- Chinese install and usage guide:
  - `agent_os_mvp/README.zh-TW.md`

## Dashboard Capabilities

The dashboard is designed to visualize run artifacts that already exist, not to replace `claude` or `ccr`.

It shows:

- latest run status
- meeting summary
- active agents
- alert signals such as overflow, router error, timeout, and artifact regression
- summary output and artifact verification checks
- prompt, raw output, and execution logs

## Quick Start

### Backend

```bash
cd agent_os_mvp/backend
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8010
```

### Frontend

```bash
cd agent_os_mvp/frontend
npm install
VITE_API_BASE_URL=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5174
```

Open:

- `http://127.0.0.1:5174/`

## Company Usage Model

Recommended flow:

1. install and validate `Claude Code` and `Claude Code Router`
2. run the task orchestration with your open-source model or router upstream
3. keep results under `results/ai_company_task_harness`
4. start `agent_os_mvp`
5. inspect run health and trustworthiness from the web UI

## Notes

- do not commit `.venv`, `node_modules`, `dist`, or runtime logs
- the dashboard does not download models
- the dashboard does not modify your router config
- it only reads existing artifacts and visualizes them
