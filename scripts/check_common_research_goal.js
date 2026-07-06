#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SPEC_ID = "common-research-summary-example";
const RESULTS_ROOT = path.join(ROOT, "results", "ai_company_task_harness");

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function findLatestRun() {
  if (!fs.existsSync(RESULTS_ROOT)) {
    throw new Error("results root does not exist");
  }
  const entries = fs
    .readdirSync(RESULTS_ROOT, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name.endsWith(`-${SPEC_ID}`))
    .map((entry) => entry.name)
    .sort();
  if (!entries.length) {
    throw new Error(`no runs found for ${SPEC_ID}`);
  }
  return path.join(RESULTS_ROOT, entries[entries.length - 1]);
}

function main() {
  const runDir = findLatestRun();
  const reportPath = path.join(runDir, "ai_company", "task_harness_report.json");
  const report = loadJson(reportPath);
  const artifactScore = report.kpis?.artifact_verify?.parsed?.score ?? 0;
  if (report.overall_status !== "pass") {
    throw new Error(`latest run is not pass: ${report.overall_status}`);
  }
  const output = {
    run_dir: runDir,
    overall_status: report.overall_status,
    artifact_score: artifactScore,
    accepted_count: report.kpis?.accepted_count ?? 0,
    failure_family_counts: report.kpis?.failure_family_counts ?? {},
  };
  process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);
}

try {
  main();
} catch (error) {
  console.error(error.message || String(error));
  process.exit(1);
}
