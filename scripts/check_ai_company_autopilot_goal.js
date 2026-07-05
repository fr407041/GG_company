const fs = require('fs');
const path = require('path');

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(process.cwd(), relativePath), 'utf8'));
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const requiredFiles = [
  'docs/goals/ai_company_autopilot_goal.md',
  'configs/ai_company/kpi.autopilot.json',
  'configs/ai_company/test_matrix.autopilot.json',
  'configs/ai_company/event_schema.autopilot.json',
  'configs/ai_company/pipeline_rules.autopilot.json',
  'configs/ai_company/meeting_triggers.autopilot.json',
  'configs/ai_company/agent_assignment_rules.autopilot.json',
  'scripts/check_ai_company_autopilot_goal.js',
  'docs/common_research_orchestrator_zh-TW.md',
  '.claude/skills/research-task-orchestrator/SKILL.md',
  'agent_os_mvp/backend/app/services/ai_company_monitor.py',
  'agent_os_mvp/frontend/src/App.jsx'
];

for (const file of requiredFiles) {
  assert(fs.existsSync(path.join(process.cwd(), file)), `Missing required file: ${file}`);
}

const kpi = readJson('configs/ai_company/kpi.autopilot.json');
const matrix = readJson('configs/ai_company/test_matrix.autopilot.json');
const eventSchema = readJson('configs/ai_company/event_schema.autopilot.json');
const pipelineRules = readJson('configs/ai_company/pipeline_rules.autopilot.json');
const meetingRules = readJson('configs/ai_company/meeting_triggers.autopilot.json');
const agentRules = readJson('configs/ai_company/agent_assignment_rules.autopilot.json');
const goalDoc = fs.readFileSync(path.join(process.cwd(), 'docs/goals/ai_company_autopilot_goal.md'), 'utf8');
const skillDoc = fs.readFileSync(path.join(process.cwd(), '.claude/skills/research-task-orchestrator/SKILL.md'), 'utf8');
const guiDoc = fs.readFileSync(path.join(process.cwd(), 'agent_os_mvp/frontend/src/App.jsx'), 'utf8');
const monitorDoc = fs.readFileSync(path.join(process.cwd(), 'agent_os_mvp/backend/app/services/ai_company_monitor.py'), 'utf8');

const kpiCategories = Object.keys(kpi.kpi_categories || {});
assert(kpiCategories.includes('automation'), 'KPI missing automation');
assert(kpiCategories.includes('stability'), 'KPI missing stability');
assert(kpiCategories.includes('traceability'), 'KPI missing traceability');
assert(kpiCategories.includes('quality'), 'KPI missing quality');
assert(kpiCategories.includes('usability'), 'KPI missing usability');

assert(Array.isArray(matrix.cases) && matrix.cases.length >= 8, 'Test matrix must contain at least 8 cases');
assert((eventSchema.required_events || []).includes('pipeline_attached'), 'Event schema must include pipeline_attached');
assert(Array.isArray(pipelineRules.pipelines) && pipelineRules.pipelines.length >= 4, 'Need at least 4 pipelines');
assert(Array.isArray(meetingRules.trigger_rules) && meetingRules.trigger_rules.length >= 4, 'Need at least 4 meeting triggers');
assert(Array.isArray(agentRules.assignment_rules) && agentRules.assignment_rules.length >= 4, 'Need at least 4 agent assignment rules');

assert(goalDoc.includes('current status'), 'Goal doc must mention current status');
assert(goalDoc.includes('active agents'), 'Goal doc must mention active agents');
assert(goalDoc.includes('result trustworthiness'), 'Goal doc must mention result trustworthiness');

assert(skillDoc.toLowerCase().includes('simple web gui'), 'Skill must mention simple web gui');
assert(skillDoc.toLowerCase().includes('sqlite'), 'Skill must mention SQLite');
assert(skillDoc.toLowerCase().includes('three primary sections'), 'Skill must mention three primary sections');

assert(guiDoc.includes('現在狀態'), 'GUI must include 現在狀態');
assert(guiDoc.includes('誰在工作'), 'GUI must include 誰在工作');
assert(guiDoc.includes('結果可信嗎'), 'GUI must include 結果可信嗎');

assert(monitorDoc.includes('sync_ai_company_runs'), 'Monitor must include sync_ai_company_runs');
assert(monitorDoc.includes('ai_company_runs'), 'Monitor must reference ai_company_runs');
assert(monitorDoc.includes('collect_ai_company_monitor'), 'Monitor must include collect_ai_company_monitor');

console.log(JSON.stringify({
  status: 'pass',
  kpi_categories: kpiCategories.length,
  test_cases: matrix.cases.length,
  pipelines: pipelineRules.pipelines.length,
  meeting_triggers: meetingRules.trigger_rules.length,
  default_screen_sections: 3
}, null, 2));
