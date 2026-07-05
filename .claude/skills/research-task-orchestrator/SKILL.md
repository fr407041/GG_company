# Research Task Orchestrator

Use this skill when you want Claude Code to run a bounded multi-agent research or execution flow without letting meetings, prompts, or retries grow unbounded.

## What this skill should do
- Classify the incoming task.
- Attach the right pipeline automatically.
- Trigger a bounded meeting only when needed.
- Assign explicit owners and fallback handlers.
- Keep an event log and decision trace.
- Prefer narrow child tasks over one giant prompt.
- Surface status through a Simple Web GUI backed by SQLite.

## UI expectation
The default screen should stay minimal with three primary sections:
- current status
- active agents
- result trustworthiness

Everything else should be expandable detail, not homepage clutter.

## Required files
- `docs/common_research_orchestrator_zh-TW.md`
- `docs/goals/ai_company_autopilot_goal.md`
- `configs/ai_company/*.autopilot.json`
- `scripts/check_ai_company_autopilot_goal.js`
- `agent_os_mvp/backend/app/services/ai_company_monitor.py`
- `agent_os_mvp/frontend/src/App.jsx`

## Rules
- Do not let meeting discussion become an infinite loop.
- Do not keep retrying the same oversized prompt after overflow.
- Detect router empty response, partial response, timeout, and false success.
- Replan into a narrower task when the previous attempt is too broad.
- Preserve evidence, owner, and decision trace for review.

## References
- `references/kpi-checklist.md`
- `references/spec-pattern.md`
- `agents/openai.yaml`
