import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8010";
const BOARD_STATES = ["running", "waiting", "done", "failed", "idle"];
const TABS = ["Overview", "Agents", "Guards", "Artifacts", "Runs", "Debug"];

const emptyMonitor = {
  overview: {
    total_runs: 0,
    pass_count: 0,
    fail_count: 0,
    unknown_count: 0,
    specs: [],
    latest_status: "unknown",
  },
  all_runs_summary: {
    total_runs: 0,
    pass_count: 0,
    fail_count: 0,
    unknown_count: 0,
    status_breakdown: { pass: 0, fail: 0, unknown: 0 },
    unknown_runs: [],
  },
  selected_run_preview: null,
  latest_run: null,
  recent_runs: [],
};

function normalizeToken(value) {
  return String(value || "unknown")
    .trim()
    .toLowerCase()
    .replace(/[_\s]+/g, "-");
}

function humanizeStatus(value) {
  const raw = String(value || "unknown").trim();
  if (!raw) return "Unknown";
  return raw
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatFailureFamily(value) {
  return humanizeStatus(value || "none");
}

function StatusBadge({ value, tone }) {
  const normalized = normalizeToken(tone || value);
  return <span className={`status-badge status-${normalized}`}>{humanizeStatus(value)}</span>;
}

function StageDot({ status }) {
  return <span className={`stage-dot stage-${normalizeToken(status)}`} aria-hidden="true" />;
}

function formatDate(value) {
  if (!value) return "not available yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function renderList(items) {
  if (!items || items.length === 0) return "not available yet";
  return items.join(", ");
}

function renderCount(value) {
  return value ?? "n/a";
}

function fallbackText(value) {
  return value || "No explicit fallback plan recorded.";
}

function isHealthyStatus(value) {
  return ["pass", "accepted", "complete", "completed", "healthy", "success", "done", "meeting_ready"].includes(
    normalizeToken(value).replace(/-/g, "_"),
  );
}

function isFailedStatus(value) {
  return [
    "fail",
    "failed",
    "red",
    "blocked",
    "escalated",
    "false-success-blocked",
    "repair-required",
    "replan-required",
    "output-policy-blocked",
    "schema-invalid",
    "input-policy-blocked",
    "worker-runtime-missing",
  ].includes(normalizeToken(value));
}

function deriveRunHealth(run, summary) {
  if (!run && !summary) {
    return {
      status: "unknown",
      label: "Waiting for run data",
      summary: "No selected run is available yet.",
      nextAction: "Create or select a run to inspect the pipeline.",
    };
  }

  const watchdogStatus = normalizeToken(run?.watchdog?.watchdog_status);
  const contractFailed = run?.contract_validation?.all_passed === false;
  const inputBlocked = Boolean(run?.input_guard?.blocked);
  const outputBlocked = Number(run?.output_guard?.policy_blocked_count || 0) > 0;
  const failedAgents = Number(summary?.failed_agent_count || run?.failed_agent_count || 0);
  const overallStatus = run?.overall_status || summary?.overall_status;
  const expectedReplanPassed = Boolean(run?.expected_replan_passed || summary?.expected_replan_passed);

  if (inputBlocked) {
    return {
      status: "blocked",
      label: "Input blocked",
      summary: "The run was stopped before execution because the request failed input guard checks.",
      nextAction: "Open Guards and inspect input guard errors before rerunning.",
    };
  }
  if (watchdogStatus === "escalated") {
    return {
      status: "blocked",
      label: "Watchdog escalated",
      summary: "The watchdog found a condition that needs manual attention.",
      nextAction: "Open Guards and Debug to review watchdog events and affected tasks.",
    };
  }
  if (expectedReplanPassed && !contractFailed && !outputBlocked && !isFailedStatus(overallStatus)) {
    return {
      status: "healthy",
      label: "Pass with expected replan",
      summary: run?.run_semantics?.summary || "This run intentionally exercised replan and still passed all expectations.",
      nextAction: "Open Run Story or Agents if you want to see how the replan recovered.",
    };
  }
  if (contractFailed || outputBlocked || failedAgents > 0 || isFailedStatus(overallStatus)) {
    return {
      status: "attention",
      label: "Needs attention",
      summary: "The run completed enough to inspect, but one or more gates found a problem.",
      nextAction: "Start with What Needs Attention, then open the highlighted stage.",
    };
  }
  if (isHealthyStatus(overallStatus)) {
    return {
      status: "healthy",
      label: "Healthy",
      summary: "The selected run looks clean across execution, review, and guard checks.",
      nextAction: "Review the Run Story or Artifacts if you need supporting evidence.",
    };
  }
  return {
    status: "unknown",
    label: "Status unclear",
    summary: "The run is present, but the final status is not conclusive yet.",
    nextAction: "Refresh the monitor or open Debug for raw run artifacts.",
  };
}

function stageStatusFromBoolean(ok, missingStatus = "not-run") {
  if (ok === true) return "pass";
  if (ok === false) return "fail";
  return missingStatus;
}

function derivePipelineStages(run) {
  const inputGuard = run?.input_guard || {};
  const outputGuard = run?.output_guard || {};
  const contract = run?.contract_validation || {};
  const watchdog = run?.watchdog || {};
  const executionCount = Number(run?.execution_jobs_run ?? run?.execution_log?.length ?? 0);
  const acceptedCount = Number(run?.final_result?.accepted_count ?? 0);
  const verdictCount = Number(run?.review_verdicts?.length ?? 0);
  const failedAgents = Number(run?.failed_agent_count || 0);
  const artifactScore = run?.final_result?.artifact_score;
  const expectedReplanPassed = Boolean(run?.expected_replan_passed);

  return [
    {
      id: "input",
      name: "Input Guard",
      status: inputGuard.blocked ? "fail" : inputGuard.errors?.length ? "warning" : run ? "pass" : "not-run",
      summary: inputGuard.blocked
        ? `${inputGuard.errors?.length || 1} input issue found`
        : "Request shape and scope look acceptable.",
      action: inputGuard.blocked ? "Inspect input guard errors." : "No action needed.",
    },
    {
      id: "meeting",
      name: "Meeting",
      status: run?.meeting_status === "MEETING_READY" ? "pass" : run?.meeting_status ? "warning" : "not-run",
      summary: run?.convergence_reason || run?.decision_summary || "Meeting decision is not available yet.",
      action: run?.meeting_status === "MEETING_READY" ? "Plan is dispatchable." : "Review meeting log.",
    },
    {
      id: "execution",
      name: "Execution",
      status: expectedReplanPassed && failedAgents > 0 ? "warning" : failedAgents > 0 ? "fail" : executionCount > 0 ? "pass" : "not-run",
      summary: expectedReplanPassed
        ? `${executionCount} jobs recorded; expected replan was exercised and the run passed.`
        : `${executionCount} execution job${executionCount === 1 ? "" : "s"} recorded.`,
      action: expectedReplanPassed
        ? "Open Agents to inspect the replan path if needed."
        : failedAgents > 0
          ? "Open Agents to find the failing task."
          : "Check artifacts if evidence is needed.",
    },
    {
      id: "reviewer",
      name: "Reviewer",
      status: verdictCount === 0 ? "not-run" : acceptedCount === verdictCount ? "pass" : acceptedCount > 0 ? "warning" : "fail",
      summary: `${acceptedCount}/${verdictCount || 0} verdicts accepted.`,
      action: acceptedCount === verdictCount && verdictCount > 0 ? "Review passed." : "Open Guards for verdict details.",
    },
    {
      id: "output",
      name: "Output Guard",
      status:
        Number(outputGuard.policy_blocked_count || 0) > 0
          ? "fail"
          : stageStatusFromBoolean(outputGuard.artifact_all_passed, artifactScore == null ? "not-run" : "warning"),
      summary:
        Number(outputGuard.policy_blocked_count || 0) > 0
          ? `${outputGuard.policy_blocked_count} policy block${outputGuard.policy_blocked_count === 1 ? "" : "s"}`
          : artifactScore == null
            ? "Artifact verification is not available yet."
            : `Artifact score ${artifactScore}`,
      action: Number(outputGuard.policy_blocked_count || 0) > 0 ? "Open Guards to see blocked output." : "Open Artifacts.",
    },
    {
      id: "watchdog",
      name: "Watchdog",
      status:
        normalizeToken(watchdog.watchdog_status) === "escalated"
          ? "fail"
          : normalizeToken(watchdog.watchdog_status) === "healthy"
            ? "pass"
            : watchdog.watchdog_status
              ? "warning"
              : "not-run",
      summary: watchdog.last_action ? `Last action: ${watchdog.last_action}` : "Watchdog has not reported yet.",
      action: normalizeToken(watchdog.watchdog_status) === "escalated" ? "Review watchdog events." : "No escalation.",
    },
    {
      id: "contract",
      name: "Contracts",
      status: contract.all_passed === false ? "fail" : contract.events?.length ? "pass" : "not-run",
      summary: `${contract.events?.length || 0} contract event${contract.events?.length === 1 ? "" : "s"} recorded.`,
      action: contract.all_passed === false ? "Open Debug for contract events." : "Contracts are quiet.",
    },
  ];
}

function deriveAttentionItems(run) {
  const items = [];
  const push = (severity, title, detail, action, source = "") => {
    items.push({ severity, title, detail, action, source });
  };

  if (!run) {
    push("warning", "Run detail unavailable", "The monitor has not loaded a selected run yet.", "Refresh or choose another run.");
    return items;
  }
  const expectedReplanPassed = Boolean(run.expected_replan_passed);

  if (run.input_guard?.blocked) {
    push(
      "critical",
      "Input guard blocked the run",
      (run.input_guard.errors || []).join("; ") || "The request failed input validation.",
      "Fix the spec or instruction before rerunning.",
      "Input Guard",
    );
  }

  if (run.watchdog?.watchdog_status === "escalated") {
    push(
      "critical",
      "Watchdog escalation",
      run.watchdog.last_action || "The watchdog found a condition that needs manual handling.",
      "Open Debug and inspect watchdog events.",
      "Watchdog",
    );
  }

  if (run.contract_validation?.all_passed === false) {
    const failed = (run.contract_validation.events || []).filter((item) => item.ok === false);
    push(
      "critical",
      "Contract validation failed",
      `${failed.length || 1} artifact contract check${failed.length === 1 ? "" : "s"} failed.`,
      "Open Debug and review contract events.",
      "Contracts",
    );
  }

  if (Number(run.output_guard?.policy_blocked_count || 0) > 0) {
    push(
      "high",
      "Output policy blocked a result",
      `${run.output_guard.policy_blocked_count} output guard issue${run.output_guard.policy_blocked_count === 1 ? "" : "s"} found.`,
      "Open Guards and review the blocked verdict.",
      "Output Guard",
    );
  }

  if (expectedReplanPassed) {
    push(
      "low",
      "Expected replan passed",
      run.run_semantics?.summary || "The run contains replan signals, but the harness expected that behavior and passed.",
      "Open Agents only if you want to inspect the replan handoff.",
      "Run Semantics",
    );
  }

  (run.failures_by_agent || []).forEach((agent) => {
    if (expectedReplanPassed) {
      return;
    }
    const firstFailure = agent.failures?.[0];
    push(
      "high",
      `${agent.role} has ${agent.failure_count} failure${agent.failure_count === 1 ? "" : "s"}`,
      firstFailure
        ? `${firstFailure.task_id}: ${formatFailureFamily(firstFailure.failure_family)}`
        : "A failed task has no detailed failure record.",
      firstFailure?.recommended_next_action || firstFailure?.fallback_plan || "Open Agents for task context.",
      "Agent",
    );
  });

  (run.alerts || [])
    .filter((alert) => normalizeToken(alert.type) !== "healthy" && !(expectedReplanPassed && normalizeToken(alert.type) === "expected-replan-passed"))
    .forEach((alert) => {
      push(alert.severity === "red" ? "high" : "medium", alert.title, alert.detail, "Inspect the matching pipeline stage.", "Alert");
    });

  if (items.length === 0) {
    push("low", "No urgent attention items", "The selected run has no current blocker.", "Use Artifacts for evidence or Runs for history.");
  }

  const order = { critical: 0, high: 1, medium: 2, warning: 3, low: 4 };
  return items.sort((a, b) => order[a.severity] - order[b.severity]);
}

function deriveBeginnerSummary(health, stages) {
  const failedStage = stages.find((stage) => stage.status === "fail");
  if (failedStage) {
    return `Start at ${failedStage.name}: ${failedStage.summary}`;
  }
  if (health.status === "healthy") {
    return "This run looks healthy. The pipeline completed without a blocker.";
  }
  return health.summary;
}

function collectAgentTasks(board) {
  return BOARD_STATES.flatMap((state) =>
    (board?.[state] || []).map((item) => ({
      ...item,
      state,
    })),
  );
}

function JsonBlock({ value }) {
  return <pre className="code-block">{JSON.stringify(value || {}, null, 2)}</pre>;
}

function EmptyState({ children = "No data available yet." }) {
  return <p className="empty-state">{children}</p>;
}

export default function App() {
  const [monitor, setMonitor] = useState(emptyMonitor);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedRun, setSelectedRun] = useState(null);
  const [monitorLoading, setMonitorLoading] = useState(true);
  const [runDetailLoading, setRunDetailLoading] = useState(false);
  const [monitorError, setMonitorError] = useState("");
  const [runDetailError, setRunDetailError] = useState("");
  const [mode, setMode] = useState("beginner");
  const [activeTab, setActiveTab] = useState("Overview");

  async function loadMonitor() {
    try {
      const response = await fetch(`${API_BASE}/api/ai-company-monitor`);
      if (!response.ok) throw new Error(`Monitor load failed: ${response.status}`);
      const data = await response.json();
      setMonitor(data);
      setSelectedRunId((current) => current || data.selected_run_preview?.run_id || data.latest_run?.run_id || "");
      setMonitorError("");
    } catch (err) {
      setMonitorError(err.message || "Failed to load monitor");
    } finally {
      setMonitorLoading(false);
    }
  }

  async function loadRunDetail(runId) {
    if (!runId) return;
    setRunDetailLoading(true);
    setRunDetailError("");
    setSelectedRun(null);
    try {
      const response = await fetch(`${API_BASE}/api/ai-company-monitor/runs/${runId}`);
      if (!response.ok) throw new Error(`Run detail load failed: ${response.status}`);
      const data = await response.json();
      setSelectedRun(data);
    } catch (err) {
      setRunDetailError(err.message || "Failed to load run detail");
    } finally {
      setRunDetailLoading(false);
    }
  }

  useEffect(() => {
    loadMonitor();
    const timer = window.setInterval(loadMonitor, 15000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (selectedRunId) {
      loadRunDetail(selectedRunId);
    }
  }, [selectedRunId]);

  const hasExplicitSelection = Boolean(selectedRunId);
  const run = hasExplicitSelection ? selectedRun : monitor.latest_run;
  const selectedRunSummary = hasExplicitSelection
    ? selectedRun?.selected_run_summary || null
    : monitor.selected_run_preview;
  const allRunsSummary = monitor.all_runs_summary || emptyMonitor.all_runs_summary;
  const board = run?.agent_state_board || {};
  const agentTasks = useMemo(() => collectAgentTasks(board), [board]);
  const finalResult = run?.final_result || {};
  const watchdog = run?.watchdog || {};
  const claimLedger = run?.claim_ledger || {};
  const claimMetrics = run?.claim_ledger_metrics || claimLedger.metrics || {};
  const claims = claimLedger.claims || [];
  const failuresByAgent = run?.failures_by_agent || [];
  const failureSummary = run?.failure_summary || {};
  const recentFailureTrend = run?.recent_agent_failure_trend || [];
  const reliabilitySnapshot = run?.agent_reliability_snapshot || [];
  const unknownRuns = allRunsSummary.unknown_runs || [];
  const statusDetails = run?.status_details || [];

  const runHealth = useMemo(() => deriveRunHealth(run, selectedRunSummary), [run, selectedRunSummary]);
  const pipelineStages = useMemo(() => derivePipelineStages(run), [run]);
  const attentionItems = useMemo(() => deriveAttentionItems(run), [run]);
  const beginnerSummary = useMemo(() => deriveBeginnerSummary(runHealth, pipelineStages), [runHealth, pipelineStages]);

  const boardSummary = useMemo(
    () =>
      BOARD_STATES.map((state) => ({
        state,
        title: humanizeStatus(state),
        items: board[state] || [],
      })),
    [board],
  );

  const allRunsStatusText = `${allRunsSummary.pass_count} pass / ${allRunsSummary.fail_count} fail / ${allRunsSummary.unknown_count} unknown`;
  const currentRunStatusText = selectedRunSummary
    ? `${selectedRunSummary.done_agent_count} done / ${selectedRunSummary.waiting_agent_count} waiting / ${selectedRunSummary.running_agent_count} running / ${selectedRunSummary.failed_agent_count} failed`
    : "Run detail not available yet";

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="identity-block">
          <p className="eyebrow">AI Company Dashboard</p>
          <h1>Run Operations</h1>
          <p className="subcopy">{beginnerSummary}</p>
        </div>

        <div className="topbar-actions">
          <label className="run-picker">
            <span>Select run</span>
            <select value={selectedRunId} onChange={(event) => setSelectedRunId(event.target.value)}>
              {(monitor.recent_runs || []).map((item) => (
                <option key={item.run_id} value={item.run_id}>
                  {item.run_id}
                </option>
              ))}
            </select>
          </label>

          <div className="mode-switch" aria-label="Dashboard detail level">
            {["beginner", "expert"].map((item) => (
              <button
                key={item}
                type="button"
                className={mode === item ? "active" : ""}
                onClick={() => setMode(item)}
              >
                {humanizeStatus(item)}
              </button>
            ))}
          </div>

          <button type="button" className="refresh-button" onClick={loadMonitor}>
            {monitorLoading ? "Loading" : "Refresh"}
          </button>
        </div>
      </header>

      {monitorError ? <p className="error-banner">{monitorError}</p> : null}
      {runDetailError ? <p className="error-banner">{runDetailError}</p> : null}

      <section className="first-screen">
        <article className={`overview-panel panel health-${runHealth.status}`}>
          <div className="panel-header">
            <div>
              <span className="section-label">Run Overview</span>
              <h2>{runHealth.label}</h2>
            </div>
            <StatusBadge value={runHealth.status} />
          </div>

          {runDetailLoading ? <EmptyState>Loading selected run details...</EmptyState> : null}
          {!runDetailLoading && !run ? <EmptyState>No selected run is available yet.</EmptyState> : null}

          {run ? (
            <>
              <p className="goal-text">{run.goal || "No run goal is available."}</p>
              <p className="decision-text">{runHealth.summary}</p>
              <div className="next-action">
                <span>Next</span>
                <strong>{runHealth.nextAction}</strong>
              </div>
              <dl className="fact-grid">
                <div>
                  <dt>Run</dt>
                  <dd>{run.run_id || selectedRunId || "not available yet"}</dd>
                </div>
                <div>
                  <dt>Spec</dt>
                  <dd>{run.spec_id || "not available yet"}</dd>
                </div>
                <div>
                  <dt>Started</dt>
                  <dd>{formatDate(run.started_at)}</dd>
                </div>
                <div>
                  <dt>Current state</dt>
                  <dd>{currentRunStatusText}</dd>
                </div>
              </dl>
            </>
          ) : null}
        </article>

        <article className="attention-panel panel">
          <div className="panel-header">
            <div>
              <span className="section-label">What Needs Attention</span>
              <h2>{attentionItems[0]?.title || "No urgent items"}</h2>
            </div>
            <span className="count-pill">{attentionItems.length}</span>
          </div>
          <div className="attention-list">
            {attentionItems.map((item, index) => (
              <article key={`${item.title}-${index}`} className={`attention-item severity-${item.severity}`}>
                <div>
                  <span>{item.source || humanizeStatus(item.severity)}</span>
                  <strong>{item.title}</strong>
                </div>
                <p>{item.detail}</p>
                <small>{item.action}</small>
              </article>
            ))}
          </div>
        </article>

        <article className="pipeline-panel panel">
          <div className="panel-header">
            <div>
              <span className="section-label">Pipeline Timeline</span>
              <h2>Where the run stands</h2>
            </div>
            <StatusBadge value={run?.overall_status || monitor.overview.latest_status} />
          </div>
          <div className="pipeline-list">
            {pipelineStages.map((stage) => (
              <article key={stage.id} className={`pipeline-stage pipeline-${normalizeToken(stage.status)}`}>
                <StageDot status={stage.status} />
                <div>
                  <div className="stage-title">
                    <strong>{stage.name}</strong>
                    <StatusBadge value={stage.status} />
                  </div>
                  <p>{stage.summary}</p>
                  {mode === "expert" ? <small>{stage.action}</small> : null}
                </div>
              </article>
            ))}
          </div>
        </article>
      </section>

      <section className="run-story panel">
        <div className="panel-header">
          <div>
            <span className="section-label">Run Story</span>
            <h2>One pass through the system</h2>
          </div>
          <span className="helper-text">{allRunsStatusText}</span>
        </div>
        <div className="story-grid">
          <article>
            <span>Meeting</span>
            <strong>{run?.meeting_status || "not available yet"}</strong>
            <p>{run?.decision_summary || "No meeting summary recorded yet."}</p>
          </article>
          <article>
            <span>Execution</span>
            <strong>{renderCount(run?.execution_jobs_run || run?.execution_log?.length || 0)} jobs</strong>
            <p>{selectedRunSummary ? currentRunStatusText : "No selected run summary yet."}</p>
          </article>
          <article>
            <span>Reviewer</span>
            <strong>{renderCount(finalResult.accepted_count)} accepted</strong>
            <p>{(run?.review_verdicts || []).length} verdicts recorded.</p>
          </article>
          <article>
            <span>Artifact</span>
            <strong>{finalResult.artifact_score ?? "n/a"}</strong>
            <p>{Object.keys(finalResult.artifact_checks || {}).length} checks available.</p>
          </article>
          <article>
            <span>Watchdog</span>
            <strong>{humanizeStatus(watchdog.watchdog_status || "not-run")}</strong>
            <p>{watchdog.last_action || "No watchdog action recorded."}</p>
          </article>
        </div>
      </section>

      <section className="workspace">
        <nav className="tabs" aria-label="Dashboard sections">
          {TABS.map((tab) => (
            <button key={tab} type="button" className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
              {tab}
            </button>
          ))}
        </nav>

        {activeTab === "Overview" ? (
          <section className="tab-panel overview-grid">
            <article className="panel">
              <div className="panel-header">
                <h2>All runs</h2>
                <span className="helper-text">{allRunsStatusText}</span>
              </div>
              <div className="metric-grid">
                <div>
                  <span>Total</span>
                  <strong>{renderCount(allRunsSummary.total_runs)}</strong>
                </div>
                <div>
                  <span>Pass</span>
                  <strong>{renderCount(allRunsSummary.pass_count)}</strong>
                </div>
                <div>
                  <span>Fail</span>
                  <strong>{renderCount(allRunsSummary.fail_count)}</strong>
                </div>
                <div>
                  <span>Unknown</span>
                  <strong>{renderCount(allRunsSummary.unknown_count)}</strong>
                </div>
              </div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <h2>Result trustworthiness</h2>
                <span className="helper-text">
                  {Object.values(finalResult.artifact_checks || {}).filter(Boolean).length}/
                  {Object.keys(finalResult.artifact_checks || {}).length} checks
                </span>
              </div>
              <pre className="summary-box">{finalResult.summary_markdown || "No summary has been generated yet."}</pre>
            </article>
          </section>
        ) : null}

        {activeTab === "Agents" ? (
          <section className="tab-panel">
            <div className="panel">
              <div className="panel-header">
                <h2>Agent tasks</h2>
                <span className="helper-text">{agentTasks.length} visible tasks</span>
              </div>
              {agentTasks.length === 0 ? <EmptyState>No agent task state is available for this run.</EmptyState> : null}
              <div className="agent-task-grid">
                {agentTasks.map((item) => (
                  <article key={`${item.state}-${item.role}-${item.task_id || "none"}`} className={`agent-task status-line-${normalizeToken(item.state)}`}>
                    <div className="agent-topline">
                      <strong>{item.role}</strong>
                      <StatusBadge value={item.state} />
                    </div>
                    <p>Task: {item.task_id || "not available yet"}</p>
                    <p>Scope: {renderList(item.scope)}</p>
                    <p>Depends on: {renderList(item.depends_on)}</p>
                    {item.failure_reason ? <p>Failure: {item.failure_reason}</p> : null}
                    {item.verification_note ? <p>Note: {item.verification_note}</p> : null}
                    {item.fallback_plan ? <p>Fallback: {item.fallback_plan}</p> : null}
                  </article>
                ))}
              </div>
            </div>

            {mode === "expert" ? (
              <div className="panel">
                <div className="panel-header">
                  <h2>State board</h2>
                  <span className="helper-text">Expert view</span>
                </div>
                <div className="state-board">
                  {boardSummary.map((lane) => (
                    <section key={lane.state} className={`state-lane state-${normalizeToken(lane.state)}`}>
                      <div className="lane-header">
                        <h3>{lane.title}</h3>
                        <span>{lane.items.length}</span>
                      </div>
                      {lane.items.length === 0 ? <p className="empty-state">None</p> : null}
                      {lane.items.map((item) => (
                        <article key={`${lane.state}-${item.role}-${item.task_id || "none"}`} className="compact-task">
                          <strong>{item.role}</strong>
                          <p>{item.task_id || "n/a"}</p>
                        </article>
                      ))}
                    </section>
                  ))}
                </div>
              </div>
            ) : null}
          </section>
        ) : null}

        {activeTab === "Guards" ? (
          <section className="tab-panel guards-grid">
            <article className="panel">
              <div className="panel-header">
                <h2>Guard reports</h2>
                <StatusBadge value={runHealth.status} />
              </div>
              <div className="guard-list">
                <div>
                  <strong>Input Guard</strong>
                  <p>{run?.input_guard?.blocked ? "Blocked before execution." : "No input block recorded."}</p>
                  <small>{(run?.input_guard?.errors || []).join("; ") || "No input errors."}</small>
                </div>
                <div>
                  <strong>Output Guard</strong>
                  <p>{Number(run?.output_guard?.policy_blocked_count || 0)} policy blocks</p>
                  <small>{run?.output_guard?.artifact_failure_category || "No artifact failure category."}</small>
                </div>
                <div>
                  <strong>Contracts</strong>
                  <p>{run?.contract_validation?.all_passed === false ? "Contract failure found." : "No contract failure reported."}</p>
                  <small>{run?.contract_validation?.events?.length || 0} events</small>
                </div>
              </div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <h2>Failure families</h2>
                <span className="helper-text">Current run</span>
              </div>
              <div className="failure-summary-grid">
                {Object.entries(failureSummary).map(([family, count]) => (
                  <div key={family} className={`failure-family-card ${count > 0 ? "hot" : ""}`}>
                    <span>{formatFailureFamily(family)}</span>
                    <strong>{count}</strong>
                  </div>
                ))}
              </div>
            </article>

            <article className="panel full-span">
              <div className="panel-header">
                <h2>Failures by agent</h2>
                <span className="helper-text">{failuresByAgent.length} agents</span>
              </div>
              {failuresByAgent.length === 0 ? <EmptyState>No failed tasks in this run.</EmptyState> : null}
              <div className="detail-stack">
                {failuresByAgent.map((agent) => (
                  <article key={agent.role} className="detail-item">
                    <strong>
                      {agent.role} / {agent.failure_count} failure{agent.failure_count > 1 ? "s" : ""}
                    </strong>
                    {agent.failures.map((failure) => (
                      <div key={failure.task_id} className="sub-detail-block">
                        <p>Task: {failure.task_id}</p>
                        <p>Family: {formatFailureFamily(failure.failure_family)}</p>
                        <p>Status: {failure.status || "n/a"}</p>
                        <p>Verdict: {failure.verdict || "n/a"}</p>
                        <p>Verification note: {failure.verification_note || "n/a"}</p>
                        {failure.recommended_next_action ? <p>Next action: {failure.recommended_next_action}</p> : null}
                        <p>Fallback: {fallbackText(failure.fallback_plan)}</p>
                      </div>
                    ))}
                  </article>
                ))}
              </div>
            </article>
          </section>
        ) : null}

        {activeTab === "Artifacts" ? (
          <section className="tab-panel artifacts-grid">
            <article className="panel">
              <div className="panel-header">
                <h2>Artifact checks</h2>
                <span className="helper-text">{finalResult.artifact_score ?? "n/a"} score</span>
              </div>
              <div className="check-list">
                {Object.keys(finalResult.artifact_checks || {}).length === 0 ? <EmptyState>No artifact checks are available.</EmptyState> : null}
                {Object.entries(finalResult.artifact_checks || {}).map(([key, value]) => (
                  <div key={key} className={`check-item ${value ? "pass" : "fail"}`}>
                    <span>{humanizeStatus(key)}</span>
                    <strong>{value ? "pass" : "fail"}</strong>
                  </div>
                ))}
              </div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <h2>Claims and evidence</h2>
                <span className="helper-text">{claimMetrics.claim_count ?? 0} claims</span>
              </div>
              <p className="muted">
                Coverage {claimMetrics.claim_coverage_rate ?? 0} / uncertainty gaps {claimMetrics.uncertainty_gap_count ?? 0}
              </p>
              <div className="detail-stack">
                {claims.length === 0 ? <EmptyState>No subagent claim ledger has been generated for this run.</EmptyState> : null}
                {claims.map((claim) => (
                  <article key={claim.claim_id} className="detail-item">
                    <strong>
                      {claim.task_id} / {claim.confidence || "unknown"} confidence
                    </strong>
                    <p>{claim.claim}</p>
                    <p>Evidence refs: {(claim.evidence_refs || []).map((item) => `${item.type}:${item.path}`).join(", ") || "missing"}</p>
                    {claim.limitations?.length ? <p>Limitations: {claim.limitations.join("; ")}</p> : null}
                  </article>
                ))}
              </div>
            </article>

            <article className="panel full-span">
              <div className="panel-header">
                <h2>Status artifacts</h2>
                <span className="helper-text">{statusDetails.length} records</span>
              </div>
              {statusDetails.length === 0 ? <EmptyState>No status artifacts are available.</EmptyState> : null}
              <div className="artifact-list">
                {statusDetails.map((item) => (
                  <article key={item.id} className="artifact-item">
                    <div className="artifact-header">
                      <strong>{item.id}</strong>
                      <StatusBadge value={item.status} />
                    </div>
                    <p>{item.verification_note || "No verification note."}</p>
                    {mode === "expert" ? (
                      <details>
                        <summary>Raw output</summary>
                        <pre>{item.raw_excerpt || "No raw output artifact."}</pre>
                      </details>
                    ) : null}
                  </article>
                ))}
              </div>
            </article>
          </section>
        ) : null}

        {activeTab === "Runs" ? (
          <section className="tab-panel">
            <div className="panel">
              <div className="panel-header">
                <h2>Recent runs</h2>
                <span className="helper-text">{monitor.recent_runs?.length || 0} shown</span>
              </div>
              <div className="run-list">
                {(monitor.recent_runs || []).map((item) => (
                  <button
                    key={item.run_id}
                    type="button"
                    className={`run-row ${item.run_id === selectedRunId ? "active" : ""}`}
                    onClick={() => setSelectedRunId(item.run_id)}
                  >
                    <div>
                      <strong>{item.run_id}</strong>
                      <p>{item.goal}</p>
                    </div>
                    <div className="run-row-meta">
                      <StatusBadge value={item.overall_status} />
                      <span>{item.done_agent_count} done</span>
                      <span>{item.failed_agent_count} failed</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {unknownRuns.length > 0 ? (
              <div className="panel">
                <div className="panel-header">
                  <h2>Unknown runs</h2>
                  <span className="helper-text">{unknownRuns.length} unresolved</span>
                </div>
                <div className="detail-stack">
                  {unknownRuns.map((item) => (
                    <article key={item.run_id} className="detail-item">
                      <strong>{item.run_id}</strong>
                      <p>Started: {formatDate(item.started_at)}</p>
                      <p>Stored status: {item.stored_status || "missing"}</p>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
          </section>
        ) : null}

        {activeTab === "Debug" ? (
          <section className="tab-panel debug-grid">
            <article className="panel">
              <div className="panel-header">
                <h2>Watchdog</h2>
                <StatusBadge value={watchdog.watchdog_status || "not-run"} />
              </div>
              <dl className="fact-grid compact">
                <div>
                  <dt>Last check</dt>
                  <dd>{watchdog.last_check_at ? formatDate(watchdog.last_check_at) : "n/a"}</dd>
                </div>
                <div>
                  <dt>Last action</dt>
                  <dd>{watchdog.last_action || "n/a"}</dd>
                </div>
                <div>
                  <dt>Stale tasks</dt>
                  <dd>{watchdog.stale_task_count ?? "n/a"}</dd>
                </div>
                <div>
                  <dt>Repairs used</dt>
                  <dd>{watchdog.repair_attempts_used ?? "n/a"}</dd>
                </div>
              </dl>
            </article>

            <article className="panel">
              <div className="panel-header">
                <h2>Agent reliability</h2>
                <span className="helper-text">{reliabilitySnapshot.length} agents</span>
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Agent</th>
                      <th>Total</th>
                      <th>Success</th>
                      <th>Fail</th>
                      <th>Family</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reliabilitySnapshot.map((row) => (
                      <tr key={row.role}>
                        <td>{row.role}</td>
                        <td>{row.total_assignments}</td>
                        <td>{row.success_count}</td>
                        <td>{row.fail_count}</td>
                        <td>{formatFailureFamily(row.most_common_failure_family)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="panel full-span">
              <div className="panel-header">
                <h2>Recent failure trend</h2>
                <span className="helper-text">{recentFailureTrend.length} rows</span>
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Agent</th>
                      <th>Failed runs</th>
                      <th>Total failures</th>
                      <th>Most common family</th>
                      <th>Last failed run</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentFailureTrend.map((row) => (
                      <tr key={row.role}>
                        <td>{row.role}</td>
                        <td>{row.failed_runs}</td>
                        <td>{row.failure_count}</td>
                        <td>{formatFailureFamily(row.most_common_failure_family)}</td>
                        <td>{row.last_failed_run_id || "n/a"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="panel full-span">
              <div className="panel-header">
                <h2>Guard JSON</h2>
                <span className="helper-text">Raw monitor payload slices</span>
              </div>
              <details open>
                <summary>Input guard</summary>
                <JsonBlock value={run?.input_guard} />
              </details>
              <details>
                <summary>Output guard</summary>
                <JsonBlock value={run?.output_guard} />
              </details>
              <details>
                <summary>Contract validation</summary>
                <JsonBlock value={run?.contract_validation} />
              </details>
            </article>

            <article className="panel full-span">
              <div className="panel-header">
                <h2>Prompt, raw output, and execution log</h2>
                <span className="helper-text">{statusDetails.length} artifacts</span>
              </div>
              <div className="detail-stack">
                {statusDetails.map((item) => (
                  <article key={item.id} className="detail-item">
                    <strong>
                      {item.id} / {item.owner_role} / {item.status}
                    </strong>
                    <details>
                      <summary>Prompt</summary>
                      <pre>{item.prompt_excerpt || "No prompt artifact."}</pre>
                    </details>
                    <details>
                      <summary>Raw output</summary>
                      <pre>{item.raw_excerpt || "No raw output artifact."}</pre>
                    </details>
                    <details>
                      <summary>Execution log</summary>
                      <pre>{item.exec_log_excerpt || "No execution log artifact."}</pre>
                    </details>
                  </article>
                ))}
              </div>
            </article>
          </section>
        ) : null}
      </section>
    </main>
  );
}
