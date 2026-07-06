import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8010";
const BOARD_STATES = ["running", "waiting", "done", "failed", "idle"];

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

function StatusBadge({ value }) {
  const normalized = String(value || "unknown").toLowerCase().replace(/\s+/g, "-");
  return <span className={`status-badge status-${normalized}`}>{value || "unknown"}</span>;
}

function formatDate(value) {
  if (!value) return "n/a";
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
  if (!items || items.length === 0) return "n/a";
  return items.join(", ");
}

function stateTitle(state) {
  const map = {
    running: "Running",
    waiting: "Waiting",
    done: "Done",
    failed: "Failed",
    idle: "Idle",
  };
  return map[state] || state;
}

function fallbackText(value) {
  return value || "No explicit fallback plan recorded.";
}

function renderCount(value) {
  return value ?? "n/a";
}

export default function App() {
  const [monitor, setMonitor] = useState(emptyMonitor);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedRun, setSelectedRun] = useState(null);
  const [monitorLoading, setMonitorLoading] = useState(true);
  const [runDetailLoading, setRunDetailLoading] = useState(false);
  const [monitorError, setMonitorError] = useState("");
  const [runDetailError, setRunDetailError] = useState("");

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
  const finalResult = run?.final_result || {};
  const alerts = run?.alerts || [];
  const board = run?.agent_state_board || {};
  const failuresByAgent = run?.failures_by_agent || [];
  const failureSummary = run?.failure_summary || {};
  const watchdog = run?.watchdog || {};
  const claimLedger = run?.claim_ledger || {};
  const claimMetrics = run?.claim_ledger_metrics || claimLedger.metrics || {};
  const claims = claimLedger.claims || [];
  const recentFailureTrend = run?.recent_agent_failure_trend || [];
  const reliabilitySnapshot = run?.agent_reliability_snapshot || [];
  const unknownRuns = allRunsSummary.unknown_runs || [];

  const allRunsMetrics = useMemo(
    () => [
      { label: "All runs / Total", value: allRunsSummary.total_runs },
      { label: "All runs / Pass", value: allRunsSummary.pass_count },
      { label: "All runs / Fail", value: allRunsSummary.fail_count },
      { label: "All runs / Unknown", value: allRunsSummary.unknown_count },
    ],
    [allRunsSummary],
  );

  const currentRunMetrics = useMemo(
    () => [
      { label: "Current run / Roster", value: selectedRunSummary?.roster_count },
      { label: "Current run / Done", value: selectedRunSummary?.done_agent_count },
      { label: "Current run / Waiting", value: selectedRunSummary?.waiting_agent_count },
      { label: "Current run / Running", value: selectedRunSummary?.running_agent_count },
      { label: "Current run / Failed", value: selectedRunSummary?.failed_agent_count },
      { label: "Current run / Idle", value: selectedRunSummary?.idle_agent_count },
    ],
    [selectedRunSummary],
  );

  const boardSummary = useMemo(
    () =>
      BOARD_STATES.map((state) => ({
        state,
        title: stateTitle(state),
        items: board[state] || [],
      })),
    [board],
  );

  const allRunsStatusText = `${allRunsSummary.pass_count} pass / ${allRunsSummary.fail_count} fail / ${allRunsSummary.unknown_count} unknown`;
  const currentRunStatusText = selectedRunSummary
    ? `${selectedRunSummary.done_agent_count} done / ${selectedRunSummary.waiting_agent_count} waiting / ${selectedRunSummary.running_agent_count} running / ${selectedRunSummary.failed_agent_count} failed / ${selectedRunSummary.idle_agent_count} idle`
    : null;

  return (
    <main className="simple-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">AI Company Dashboard</p>
          <h1>Mission Control</h1>
          <p className="subcopy">
            Read the historical health of all runs separately from the current selected run, so the numbers always make sense at a glance.
          </p>
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

          <button type="button" className="refresh-button" onClick={loadMonitor}>
            {monitorLoading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </header>

      {monitorError ? <p className="error-banner">{monitorError}</p> : null}
      {runDetailError ? <p className="error-banner">{runDetailError}</p> : null}

      <section className="summary-groups">
        <article className="summary-panel card">
          <div className="card-header">
            <h2>All runs</h2>
            <span className="helper-text">{allRunsStatusText}</span>
          </div>

          <div className="metric-row summary-metrics">
            {allRunsMetrics.map((item) => (
              <article key={item.label} className="metric-card">
                <span>{item.label}</span>
                <strong>{renderCount(item.value)}</strong>
              </article>
            ))}
          </div>

          {allRunsSummary.unknown_count > 0 ? (
            <div className="summary-note summary-note-warning">
              <strong>{allRunsSummary.unknown_count} run has unresolved status.</strong>
              <span>Open “Unknown runs” below to inspect the stored status and run id.</span>
            </div>
          ) : (
            <p className="muted">All historical run counts now come from one consistent database summary.</p>
          )}
        </article>

        <article className="summary-panel card">
          <div className="card-header">
            <h2>Current run</h2>
            {selectedRunSummary ? <StatusBadge value={selectedRunSummary.overall_status} /> : null}
          </div>

          {runDetailLoading ? <p className="unavailable-state">Loading selected run...</p> : null}
          {!runDetailLoading && runDetailError ? <p className="unavailable-state">Run detail unavailable.</p> : null}
          {!runDetailLoading && !runDetailError && !selectedRunSummary ? <p className="unavailable-state">No selected run is available yet.</p> : null}

          {!runDetailLoading && !runDetailError && selectedRunSummary ? (
            <>
              <p className="summary-note-text">{currentRunStatusText}</p>
              <div className="metric-row summary-metrics">
                {currentRunMetrics.map((item) => (
                  <article key={item.label} className="metric-card">
                    <span>{item.label}</span>
                    <strong>{renderCount(item.value)}</strong>
                  </article>
                ))}
              </div>
            </>
          ) : null}
        </article>
      </section>

      <section className="hero-status">
        <div className="hero-main card">
          <div className="card-header">
            <h2>Run health</h2>
            <StatusBadge value={run?.overall_status || monitor.overview.latest_status} />
          </div>

          {run ? (
            <>
              <p className="goal-text">{run.goal || "No run goal is available."}</p>
              <p className="decision-text">{run.decision_summary || "No decision summary has been recorded yet."}</p>

              <div className="mini-grid">
                <div>
                  <span>Spec</span>
                  <strong>{run.spec_id || "n/a"}</strong>
                </div>
                <div>
                  <span>Started</span>
                  <strong>{formatDate(run.started_at)}</strong>
                </div>
                <div>
                  <span>Meeting status</span>
                  <strong>{run.meeting_status || "n/a"}</strong>
                </div>
                <div>
                  <span>Artifact score</span>
                  <strong>{finalResult.artifact_score ?? "n/a"}</strong>
                </div>
              </div>
            </>
          ) : (
            <p className="unavailable-state">Loading selected run details before showing run health.</p>
          )}
        </div>

        <div className="hero-alerts card">
          <div className="card-header">
            <h2>Alerts</h2>
          </div>
          <div className="alert-stack">
            {alerts.length === 0 ? <p className="muted">No alerts at the moment.</p> : null}
            {alerts.map((alert) => (
              <article key={`${alert.type}-${alert.title}`} className={`alert-item alert-${alert.severity}`}>
                <strong>{alert.title}</strong>
                <p>{alert.detail}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="board-section card">
        <div className="card-header">
          <h2>Agent board</h2>
          <span className="helper-text">
            {selectedRunSummary
              ? `${selectedRunSummary.running_agent_count} running / ${selectedRunSummary.waiting_agent_count} waiting / ${selectedRunSummary.done_agent_count} done / ${selectedRunSummary.failed_agent_count} failed / ${selectedRunSummary.idle_agent_count} idle`
              : "Run detail unavailable"}
          </span>
        </div>

        {runDetailLoading ? <p className="unavailable-state">Loading selected run agent states...</p> : null}
        {!runDetailLoading && !run ? <p className="unavailable-state">Run detail unavailable.</p> : null}

        {!runDetailLoading && run ? (
          <div className="board-grid">
            {boardSummary.map((lane) => (
              <section key={lane.state} className={`board-lane lane-${lane.state}`}>
                <div className="lane-header">
                  <h3>{lane.title}</h3>
                  <span>{lane.items.length}</span>
                </div>

                {lane.items.length === 0 ? <p className="lane-empty">None</p> : null}

                <div className="lane-items">
                  {lane.items.map((item) => (
                    <article key={`${lane.state}-${item.role}-${item.task_id || "none"}`} className={`lane-card lane-card-${lane.state}`}>
                      <div className="agent-topline">
                        <strong>{item.role}</strong>
                        <StatusBadge value={item.state} />
                      </div>
                      <p>Task: {item.task_id || "n/a"}</p>
                      <p>Scope: {renderList(item.scope)}</p>
                      <p>Depends on: {renderList(item.depends_on)}</p>
                      {item.verification_note ? <p>Note: {item.verification_note}</p> : null}
                      {item.fallback_plan ? <p>Fallback: {item.fallback_plan}</p> : null}
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : null}
      </section>

      <section className="main-grid">
        <article className="card">
          <div className="card-header">
            <h2>Result trustworthiness</h2>
            <span className="helper-text">
              {Object.values(finalResult.artifact_checks || {}).filter(Boolean).length}/
              {Object.keys(finalResult.artifact_checks || {}).length} checks
            </span>
          </div>

          <pre className="summary-box">{finalResult.summary_markdown || "No summary has been generated yet."}</pre>

          <div className="check-list">
            {Object.entries(finalResult.artifact_checks || {}).map(([key, value]) => (
              <div key={key} className={`check-item ${value ? "check-pass" : "check-fail"}`}>
                <span>{key}</span>
                <strong>{value ? "pass" : "fail"}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="card">
          <div className="card-header">
            <h2>Failure snapshot</h2>
            <span className="helper-text">Current run by family</span>
          </div>
          <div className="failure-summary-grid">
            {Object.entries(failureSummary).map(([family, count]) => (
              <div key={family} className={`failure-family-card ${count > 0 ? "failure-family-hot" : ""}`}>
                <span>{family}</span>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="card">
          <div className="card-header">
            <h2>Watchdog</h2>
            <StatusBadge value={watchdog.watchdog_status || "not-run"} />
          </div>
          <div className="mini-grid">
            <div>
              <span>Last check</span>
              <strong>{watchdog.last_check_at ? formatDate(watchdog.last_check_at) : "n/a"}</strong>
            </div>
            <div>
              <span>Last action</span>
              <strong>{watchdog.last_action || "n/a"}</strong>
            </div>
            <div>
              <span>Stale tasks</span>
              <strong>{watchdog.stale_task_count ?? "n/a"}</strong>
            </div>
            <div>
              <span>Repairs used</span>
              <strong>{watchdog.repair_attempts_used ?? "n/a"}</strong>
            </div>
          </div>
        </article>
      </section>

      <section className="details-section">
        <details className="detail-card" open={claims.length > 0}>
          <summary>Claims / Evidence / Confidence</summary>
          <div className="detail-body">
            <p className="muted">
              Claims: {claimMetrics.claim_count ?? 0} / coverage: {claimMetrics.claim_coverage_rate ?? 0} / uncertainty gaps:{" "}
              {claimMetrics.uncertainty_gap_count ?? 0}
            </p>
            {claims.length === 0 ? <p className="muted">No subagent claim ledger has been generated for this run.</p> : null}
            {claims.map((claim) => (
              <article key={claim.claim_id} className="detail-item">
                <strong>
                  {claim.task_id} / {claim.confidence || "unknown"} confidence
                </strong>
                <p>{claim.claim}</p>
                <p>Evidence refs: {(claim.evidence_refs || []).map((item) => `${item.type}:${item.path}`).join(", ") || "missing"}</p>
                {claim.limitations?.length ? <p>Limitations: {claim.limitations.join("; ")}</p> : null}
                {claim.handoff_next ? <p>Handoff: {claim.handoff_next}</p> : null}
              </article>
            ))}
          </div>
        </details>

        <details className="detail-card" open={unknownRuns.length > 0}>
          <summary>Unknown runs</summary>
          <div className="detail-body">
            {unknownRuns.length === 0 ? <p className="muted">No unresolved historical runs were found.</p> : null}
            {unknownRuns.map((item) => (
              <article key={item.run_id} className="detail-item">
                <strong>{item.run_id}</strong>
                <p>Started: {formatDate(item.started_at)}</p>
                <p>Stored status: {item.stored_status || "missing"}</p>
              </article>
            ))}
          </div>
        </details>

        <details className="detail-card" open={failuresByAgent.length > 0}>
          <summary>Failures by agent</summary>
          <div className="detail-body">
            {failuresByAgent.length === 0 ? <p className="muted">No failed tasks in this run.</p> : null}
            {failuresByAgent.map((agent) => (
              <article key={agent.role} className="detail-item">
                <strong>
                  {agent.role} / {agent.failure_count} failure{agent.failure_count > 1 ? "s" : ""}
                </strong>
                {agent.failures.map((failure) => (
                  <div key={failure.task_id} className="sub-detail-block">
                    <p>Task: {failure.task_id}</p>
                    <p>Family: {failure.failure_family}</p>
                    <p>Status: {failure.status || "n/a"}</p>
                    <p>Verdict: {failure.verdict || "n/a"}</p>
                    <p>Verification note: {failure.verification_note || "n/a"}</p>
                    {failure.detected_by ? <p>Detected by: {failure.detected_by}</p> : null}
                    {failure.failure_reason ? <p>Failure reason: {failure.failure_reason}</p> : null}
                    {failure.recommended_next_action ? <p>Next action: {failure.recommended_next_action}</p> : null}
                    <p>Fallback: {fallbackText(failure.fallback_plan)}</p>
                  </div>
                ))}
              </article>
            ))}
          </div>
        </details>

        <details className="detail-card">
          <summary>Recent agent failure trend</summary>
          <div className="detail-body">
            {recentFailureTrend.length === 0 ? <p className="muted">No recent agent failure trend is available.</p> : null}
            {recentFailureTrend.length > 0 ? (
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
                        <td>{row.most_common_failure_family}</td>
                        <td>{row.last_failed_run_id || "n/a"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            {reliabilitySnapshot.length > 0 ? (
              <>
                <h3>Agent reliability snapshot</h3>
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Agent</th>
                        <th>Total assignments</th>
                        <th>Success</th>
                        <th>Fail</th>
                        <th>Most common family</th>
                        <th>Last failed run</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reliabilitySnapshot.map((row) => (
                        <tr key={row.role}>
                          <td>{row.role}</td>
                          <td>{row.total_assignments}</td>
                          <td>{row.success_count}</td>
                          <td>{row.fail_count}</td>
                          <td>{row.most_common_failure_family}</td>
                          <td>{row.last_failed_run_id || "n/a"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}
          </div>
        </details>

        <details className="detail-card">
          <summary>Meeting log and task assignment</summary>
          <div className="detail-body">
            <h3>Discussion</h3>
            {(run?.meeting?.discussion_log || []).map((item, index) => (
              <article key={`${item.role}-${index}`} className="detail-item">
                <strong>
                  Round {item.round} / {item.role}
                </strong>
                <p>{item.summary}</p>
                <ul>
                  {(item.proposed_actions || []).map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
              </article>
            ))}

            <h3>Assigned tasks</h3>
            {(run?.meeting?.task_assignments || []).map((task) => (
              <article key={task.task_id} className="detail-item">
                <strong>{task.task_id}</strong>
                <p>Owner: {task.owner_role}</p>
                <p>Scope: {renderList(task.scope)}</p>
                <p>Depends on: {renderList(task.depends_on)}</p>
                <p>Fallback: {fallbackText(task.fallback_plan)}</p>
              </article>
            ))}
          </div>
        </details>

        <details className="detail-card">
          <summary>Prompt, raw output, and execution log</summary>
          <div className="detail-body">
            {(run?.status_details || []).map((item) => (
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
        </details>

        <details className="detail-card">
          <summary>Recent runs</summary>
          <div className="detail-body">
            <div className="run-list">
              {(monitor.recent_runs || []).map((item) => (
                <button
                  key={item.run_id}
                  type="button"
                  className={`run-row ${item.run_id === selectedRunId ? "run-row-active" : ""}`}
                  onClick={() => setSelectedRunId(item.run_id)}
                >
                  <div>
                    <strong>{item.run_id}</strong>
                    <p>{item.goal}</p>
                  </div>
                  <div className="run-row-meta">
                    <StatusBadge value={item.overall_status} />
                    <span>{item.roster_count} roster</span>
                    <span>{item.done_agent_count} done</span>
                    <span>{item.waiting_agent_count} waiting</span>
                    <span>{item.running_agent_count} running</span>
                    <span>{item.failed_agent_count} failed</span>
                    <span>{item.idle_agent_count} idle</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </details>
      </section>
    </main>
  );
}
