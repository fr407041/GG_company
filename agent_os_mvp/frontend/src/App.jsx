import { useEffect, useMemo, useState } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

const emptyMonitor = {
  overview: {
    total_runs: 0,
    pass_count: 0,
    fail_count: 0,
    specs: [],
    active_agents: 0,
    latest_status: 'unknown',
  },
  latest_run: null,
  recent_runs: [],
};

function StatusBadge({ value }) {
  const normalized = String(value || 'unknown').toLowerCase().replace(/\s+/g, '-');
  return <span className={`status-badge status-${normalized}`}>{value || 'unknown'}</span>;
}

function formatDate(value) {
  if (!value) return 'n/a';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-TW', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export default function App() {
  const [monitor, setMonitor] = useState(emptyMonitor);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [selectedRun, setSelectedRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function loadMonitor() {
    try {
      const response = await fetch(`${API_BASE}/api/ai-company-monitor`);
      if (!response.ok) throw new Error(`Monitor load failed: ${response.status}`);
      const data = await response.json();
      setMonitor(data);
      setSelectedRunId((current) => current || data.latest_run?.run_id || '');
      setError('');
    } catch (err) {
      setError(err.message);
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
      setError('');
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadMonitor();
    const timer = window.setInterval(loadMonitor, 15000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (selectedRunId) loadRunDetail(selectedRunId);
  }, [selectedRunId]);

  const run = selectedRun || monitor.latest_run;
  const finalResult = run?.final_result || {};
  const activeAgents = run?.active_agents || [];
  const alerts = run?.alerts || [];

  const topMetrics = useMemo(
    () => [
      { label: '總 run 數', value: monitor.overview.total_runs },
      { label: '成功', value: monitor.overview.pass_count },
      { label: '失敗', value: monitor.overview.fail_count },
      { label: '進行中 agent', value: activeAgents.length || monitor.overview.active_agents },
    ],
    [monitor, activeAgents],
  );

  return (
    <main className="simple-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">AI Company Simple Board</p>
          <h1>一眼看懂這輪任務有沒有正常前進</h1>
          <p className="subcopy">
            只看三件事：現在狀態、誰在工作、結果可信嗎。其他技術細節都放在展開區。
          </p>
        </div>
        <div className="topbar-actions">
          <label className="run-picker">
            <span>選擇 run</span>
            <select value={selectedRunId} onChange={(event) => setSelectedRunId(event.target.value)}>
              {(monitor.recent_runs || []).map((item) => (
                <option key={item.run_id} value={item.run_id}>
                  {item.run_id}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="refresh-button" onClick={loadMonitor}>
            {loading ? '載入中...' : '重新整理'}
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
            <h2>現在狀態</h2>
            <StatusBadge value={run?.overall_status || monitor.overview.latest_status} />
          </div>
          <p className="goal-text">{run?.goal || '尚未讀到 run。'}</p>
          <p className="decision-text">{run?.decision_summary || '尚未讀到結論。'}</p>
          <div className="mini-grid">
            <div>
              <span>Spec</span>
              <strong>{run?.spec_id || 'n/a'}</strong>
            </div>
            <div>
              <span>開始時間</span>
              <strong>{formatDate(run?.started_at)}</strong>
            </div>
            <div>
              <span>會議狀態</span>
              <strong>{run?.meeting_status || 'n/a'}</strong>
            </div>
            <div>
              <span>Artifact 分數</span>
              <strong>{finalResult.artifact_score ?? 'n/a'}</strong>
            </div>
          </div>
        </div>

        <div className="hero-alerts card">
          <div className="card-header">
            <h2>告警</h2>
          </div>
          <div className="alert-stack">
            {alerts.length === 0 ? <p className="muted">沒有告警。</p> : null}
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
            <h2>誰在工作</h2>
            <span className="helper-text">{activeAgents.length} 個 active agent</span>
          </div>
          {activeAgents.length === 0 ? <p className="muted">目前沒有進行中的 agent。</p> : null}
          <div className="agent-list">
            {activeAgents.map((agent) => (
              <article key={agent.task_id} className="agent-item">
                <div className="agent-topline">
                  <strong>{agent.role}</strong>
                  <StatusBadge value={agent.status} />
                </div>
                <p>Task: {agent.task_id}</p>
                <p>Scope: {(agent.scope || []).join(', ') || 'n/a'}</p>
                <p>Next step: {agent.fallback_plan || '依 acceptance criteria 繼續推進'}</p>
              </article>
            ))}
          </div>
        </article>

        <article className="card">
          <div className="card-header">
            <h2>結果可信嗎</h2>
            <span className="helper-text">
              {Object.values(finalResult.artifact_checks || {}).filter(Boolean).length}/
              {Object.keys(finalResult.artifact_checks || {}).length} checks
            </span>
          </div>
          <pre className="summary-box">{finalResult.summary_markdown || '尚未產生 summary。'}</pre>
          <div className="check-list">
            {Object.entries(finalResult.artifact_checks || {}).map(([key, value]) => (
              <div key={key} className={`check-item ${value ? 'check-pass' : 'check-fail'}`}>
                <span>{key}</span>
                <strong>{value ? 'pass' : 'fail'}</strong>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="details-section">
        <details className="detail-card">
          <summary>展開會議與任務細節</summary>
          <div className="detail-body">
            <h3>會議討論</h3>
            {(run?.meeting?.discussion_log || []).map((item, index) => (
              <article key={`${item.role}-${index}`} className="detail-item">
                <strong>Round {item.round} · {item.role}</strong>
                <p>{item.summary}</p>
                <ul>
                  {(item.proposed_actions || []).map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </details>

        <details className="detail-card">
          <summary>展開 prompt / raw output / exec log</summary>
          <div className="detail-body">
            {(run?.status_details || []).map((item) => (
              <article key={item.id} className="detail-item">
                <strong>{item.id} · {item.owner_role} · {item.status}</strong>
                <details>
                  <summary>Prompt</summary>
                  <pre>{item.prompt_excerpt || 'No prompt artifact.'}</pre>
                </details>
                <details>
                  <summary>Raw Output</summary>
                  <pre>{item.raw_excerpt || 'No raw output artifact.'}</pre>
                </details>
                <details>
                  <summary>Exec Log</summary>
                  <pre>{item.exec_log_excerpt || 'No exec log artifact.'}</pre>
                </details>
              </article>
            ))}
          </div>
        </details>
      </section>
    </main>
  );
}
