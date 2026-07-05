import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8010";

const emptyMonitor = {
  overview: {
    total_runs: 0,
    pass_count: 0,
    fail_count: 0,
    specs: [],
    active_agents: 0,
    latest_status: "unknown",
  },
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

export default function App() {
  const [monitor, setMonitor] = useState(emptyMonitor);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedRun, setSelectedRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadMonitor() {
    try {
      const response = await fetch(`${API_BASE}/api/ai-company-monitor`);
      if (!response.ok) throw new Error(`Monitor load failed: ${response.status}`);
      const data = await response.json();
      setMonitor(data);
      setSelectedRunId((current) => current || data.latest_run?.run_id || "");
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load monitor");
    } finally {
      setLoading(false);
    }
  }

  async function loadRunDetail(runId) {
    if (!runId) return;
    try {
      const response = await fetch(`${API_BASE}/api/ai-company-monitor/runs/${runId}`);
      if (!response.ok) throw new Error(`Run detail load failed: ${response.status}`);
      const data = await response.json();
      setSelectedRun(data);
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load run detail");
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

  const run = selectedRun || monitor.latest_run;
  const finalResult = run?.final_result || {};
  const activeAgents = run?.active_agents || [];
  const alerts = run?.alerts || [];

  const topMetrics = useMemo(
    () => [
      { label: "Total runs", value: monitor.overview.total_runs },
      { label: "Pass", value: monitor.overview.pass_count },
      { label: "Fail", value: monitor.overview.fail_count },
      { label: "Active agents", value: activeAgents.length || monitor.overview.active_agents },
    ],
    [monitor, activeAgents],
  );

  return (
    <main className="simple-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">AI Company Dashboard</p>
          <h1>Mission Control</h1>
          <p className="subcopy">
            This dashboard focuses on the latest run, including meeting conclusions, task assignment,
            execution status, artifact checks, and alert signals for the multi-agent workflow.
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
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </header>

      {error ? <p className="error-banner">{error}</p> : null}

      <section className="metric-row">
        {topMetrics.map((item) => (
          <article key={item.label} className="metric-card">
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        ))}
      </section>

      <section className="hero-status">
        <div className="hero-main card">
          <div className="card-header">
            <h2>Latest status</h2>
            <StatusBadge value={run?.overall_status || monitor.overview.latest_status} />
          </div>

          <p className="goal-text">{run?.goal || "No run is available yet."}</p>
          <p className="decision-text">{run?.decision_summary || "No decision summary has been recorded yet."}</p>

          <div className="mini-grid">
            <div>
              <span>Spec</span>
              <strong>{run?.spec_id || "n/a"}</strong>
            </div>
            <div>
              <span>Started</span>
              <strong>{formatDate(run?.started_at)}</strong>
            </div>
            <div>
              <span>Meeting status</span>
              <strong>{run?.meeting_status || "n/a"}</strong>
            </div>
            <div>
              <span>Artifact score</span>
              <strong>{finalResult.artifact_score ?? "n/a"}</strong>
            </div>
          </div>
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

      <section className="main-grid">
        <article className="card">
          <div className="card-header">
            <h2>Active agents</h2>
            <span className="helper-text">{activeAgents.length} in progress</span>
          </div>
          {activeAgents.length === 0 ? <p className="muted">No active agents right now.</p> : null}
          <div className="agent-list">
            {activeAgents.map((agent) => (
              <article key={agent.task_id} className="agent-item">
                <div className="agent-topline">
                  <strong>{agent.role}</strong>
                  <StatusBadge value={agent.status} />
                </div>
                <p>Task: {agent.task_id}</p>
                <p>Scope: {renderList(agent.scope)}</p>
                <p>Next step: {agent.fallback_plan || "Finish within the acceptance criteria and report back."}</p>
              </article>
            ))}
          </div>
        </article>

        <article className="card">
          <div className="card-header">
            <h2>Summary and checks</h2>
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
      </section>

      <section className="details-section">
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
                    <span>{item.artifact_score ?? "n/a"}</span>
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
