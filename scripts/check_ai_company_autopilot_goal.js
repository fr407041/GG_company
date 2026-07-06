#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, relativePath), "utf8"));
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function ensureFile(relativePath) {
  assert(fs.existsSync(path.join(ROOT, relativePath)), `Missing required file: ${relativePath}`);
}

function main() {
  const requiredFiles = [
    "docs/goals/ai_company_autopilot_goal.md",
    "configs/ai_company/kpi.autopilot.json",
    "configs/ai_company/test_matrix.autopilot.json",
    "configs/ai_company/event_schema.autopilot.json",
    "configs/ai_company/pipeline_rules.autopilot.json",
    "configs/ai_company/meeting_triggers.autopilot.json",
    "configs/ai_company/agent_assignment_rules.autopilot.json",
    "scripts/check_ai_company_autopilot_goal.js",
    "docs/common_research_orchestrator_zh-TW.md",
    ".claude/skills/research-task-orchestrator/SKILL.md",
    "agent_os_mvp/backend/app/services/ai_company_monitor.py",
    "agent_os_mvp/frontend/src/App.jsx"
  ];
  requiredFiles.forEach(ensureFile);

  const kpi = readJson("configs/ai_company/kpi.autopilot.json");
  const matrix = readJson("configs/ai_company/test_matrix.autopilot.json");
  const eventSchema = readJson("configs/ai_company/event_schema.autopilot.json");
  const pipelineRules = readJson("configs/ai_company/pipeline_rules.autopilot.json");
  const meetingRules = readJson("configs/ai_company/meeting_triggers.autopilot.json");
  const agentRules = readJson("configs/ai_company/agent_assignment_rules.autopilot.json");
  const goalDoc = fs.readFileSync(path.join(ROOT, "docs/goals/ai_company_autopilot_goal.md"), "utf8").toLowerCase();
  const skillDoc = fs.readFileSync(path.join(ROOT, ".claude/skills/research-task-orchestrator/SKILL.md"), "utf8").toLowerCase();
  const gui = fs.readFileSync(path.join(ROOT, "agent_os_mvp/frontend/src/App.jsx"), "utf8");
  const monitor = fs.readFileSync(path.join(ROOT, "agent_os_mvp/backend/app/services/ai_company_monitor.py"), "utf8");

  ["automation", "stability", "traceability", "quality", "usability"].forEach((key) => {
    assert(kpi.categories && kpi.categories[key], `KPI category missing: ${key}`);
  });
  assert(Array.isArray(matrix.cases) && matrix.cases.length >= 8, "Autopilot test matrix must contain at least 8 cases.");
  assert(Array.isArray(eventSchema.required_event_types) && eventSchema.required_event_types.includes("pipeline_attached"), "Event schema missing required event types.");
  assert(Array.isArray(pipelineRules.pipelines) && pipelineRules.pipelines.length >= 4, "Pipeline rules must define at least 4 pipelines.");
  assert(Array.isArray(meetingRules.trigger_rules) && meetingRules.trigger_rules.length >= 4, "Meeting trigger rules are incomplete.");
  assert(Array.isArray(agentRules.rules) && agentRules.rules.length >= 4, "Agent assignment rules are incomplete.");

  ["current status", "active agents", "result trustworthiness"].forEach((phrase) => {
    assert(goalDoc.includes(phrase), `Goal doc missing phrase: ${phrase}`);
  });

  ["simple web gui", "sqlite", "three primary sections"].forEach((phrase) => {
    assert(skillDoc.includes(phrase), `Skill doc missing phrase: ${phrase}`);
  });

  ["現在狀態", "誰在工作", "結果可信嗎"].forEach((phrase) => {
    assert(gui.includes(phrase), `Simple GUI missing section: ${phrase}`);
  });

  ["sync_ai_company_runs", "ai_company_runs", "collect_ai_company_monitor"].forEach((phrase) => {
    assert(monitor.includes(phrase), `Monitor backend missing capability marker: ${phrase}`);
  });

  process.stdout.write(
    `${JSON.stringify(
      {
        status: "pass",
        kpi_categories: 5,
        test_cases: matrix.cases.length,
        pipelines: pipelineRules.pipelines.length,
        meeting_triggers: meetingRules.trigger_rules.length,
        default_screen_sections: 3
      },
      null,
      2
    )}\n`
  );
}

try {
  main();
} catch (error) {
  console.error(error.message || String(error));
  process.exit(1);
}
