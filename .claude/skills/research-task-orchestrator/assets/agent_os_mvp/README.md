# Agent OS MVP Dashboard

This folder contains a lightweight dashboard package for viewing AI-company style runs produced by `Claude Code + router + open-source LLM` workflows.

It is intentionally small:

- FastAPI backend
- SQLite storage
- React + Vite frontend
- minimal Windows startup scripts
- minimal Linux startup scripts

## What This Package Expects

The dashboard does not run `claude` or `ccr` by itself.

It reads run artifacts that already exist under a workspace such as:

- `results/ai_company_task_harness/...`
- `ai_company/task_harness_report.json`
- `ai_company/meeting_decision.json`
- `ai_company/reviewer_verdicts.json`

The backend sync logic already knows how to read these artifacts and present:

- latest run status
- meeting summary
- active agents
- alerts such as overflow or router errors
- artifact verification results

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

### Frontend

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5174
```

Windows CMD:

```cmd
cd frontend
npm install
set VITE_API_BASE_URL=http://127.0.0.1:8010
npm run dev -- --host 127.0.0.1 --port 5174
```

Open:

- `http://127.0.0.1:5174/`

## Helper Scripts

Windows:

- `start-dashboard.cmd`
- `start-dashboard.ps1`
- `stop-dashboard.ps1`

Linux:

- `start-dashboard.sh`
- `stop-dashboard.sh`

## Company Integration Notes

This package is designed to sit next to an existing `Claude Code + router` setup.

Recommended usage pattern:

1. keep `claude` and `ccr` installed in the company Ubuntu environment
2. run your orchestrated tasks as usual
3. store results under `results/ai_company_task_harness`
4. start this dashboard package
5. inspect run health and artifact quality from the web UI

## Main API

- `GET /health`
- `GET /api/ai-company-monitor`
- `GET /api/ai-company-monitor/runs/{run_id}`
- `GET /api/dashboard`

## Files You Normally Keep

Keep:

- `backend/app/**`
- `backend/requirements.txt`
- `frontend/src/**`
- `frontend/package.json`
- `frontend/vite.config.js`
- startup scripts

Do not commit local runtime outputs:

- `backend/.venv/`
- `frontend/node_modules/`
- `frontend/dist/`
- `logs/`
