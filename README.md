# GG_company

A minimal AI-company autopilot package for `Claude Code + router + open-source model` usage.

This repository contains only the necessary files to:

- define autopilot rules for pipeline, meeting, event log, and agent assignment
- provide a simple one-page Web GUI
- back the GUI with FastAPI + SQLite
- bundle a project-local Claude skill and goal manifest
- document installation and usage in Chinese

## Structure

- `agent_os_mvp/backend/`
  - FastAPI backend
  - SQLite sync for run summaries
  - APIs:
    - `GET /health`
    - `GET /api/ai-company-monitor`
    - `GET /api/ai-company-monitor/runs/{run_id}`
- `agent_os_mvp/frontend/`
  - Vite + React single-page GUI
- `configs/ai_company/`
  - autopilot rules, KPI spec, and test matrix
- `docs/`
  - installation, usage, and goal docs
- `.claude/`
  - project-local skill and goal manifest
- `scripts/check_ai_company_autopilot_goal.js`
  - validates the goal package

## Design Principles

- Keep the default UI simple.
- Show only three primary sections first:
  - current status
  - active agents
  - result trustworthiness
- Keep technical details expandable.
- Use low dependencies and SQLite only.

## Quick Start

### Backend

```bash
cd agent_os_mvp/backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd agent_os_mvp/frontend
npm install
npm run dev
```

### Goal Package Check

```bash
node scripts/check_ai_company_autopilot_goal.js
```

## Main Docs

- `docs/common_research_orchestrator_zh-TW.md`
- `docs/goals/ai_company_autopilot_goal.md`
- `.claude/skills/research-task-orchestrator/SKILL.md`
