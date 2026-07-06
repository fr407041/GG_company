# AI Company Autopilot Goal

## Objective

Build an AI-company orchestration core for `Claude Code + router + open-source model` usage so that a new task can automatically:

- classify task type
- attach a suitable pipeline
- trigger a meeting when needed
- assign agents without manual per-task selection
- emit a unified event log
- preserve a decision trace that can power a simple decision cockpit

The default Web GUI must stay simple:
- one page
- three primary sections only:
  - current status
  - active agents
  - result trustworthiness
- technical details remain expandable

## Build Scope

### Layer 1: Core Build

- unified event schema
- pipeline schema and attachment rules
- auto-meeting trigger rules
- auto-agent assignment rules
- SQLite-backed run summary and monitor payload
- simple Web GUI backed by the above data

### Layer 2: Validation

- KPI spec
- test matrix
- goal check script
- bounded validation commands

## Success Criteria

This goal is complete only when:

- the goal package files exist
- the monitor backend and simple GUI build successfully
- the goal check script passes
- the KPI and test-matrix specs are present and structurally valid

## Deliverables

- `configs/ai_company/kpi.autopilot.json`
- `configs/ai_company/test_matrix.autopilot.json`
- `configs/ai_company/event_schema.autopilot.json`
- `configs/ai_company/pipeline_rules.autopilot.json`
- `configs/ai_company/meeting_triggers.autopilot.json`
- `configs/ai_company/agent_assignment_rules.autopilot.json`
- `scripts/check_ai_company_autopilot_goal.js`
- `.claude/goal/active-goal.json`
- `docs/common_research_orchestrator_zh-TW.md`
- `.claude/skills/research-task-orchestrator/SKILL.md`
