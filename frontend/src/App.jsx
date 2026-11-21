import { useEffect, useState } from "react";

const api = (path, opts) => fetch(`/api${path}`, opts).then((r) => r.json());

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function ScoreRing({ score }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const tone = score >= 85 ? "good" : score >= 60 ? "mid" : "bad";
  return (
    <svg className={`ring ${tone}`} viewBox="0 0 120 120" role="img" aria-label={`Score ${score} of 100`}>
      <circle cx="60" cy="60" r={r} className="ring-bg" />
      <circle cx="60" cy="60" r={r} className="ring-fg"
        strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)} />
      <text x="60" y="66" textAnchor="middle">{score}</text>
    </svg>
  );
}

function Sparkline({ history }) {
  if (!history || history.length < 2) return null;
  const w = 120, h = 32;
  const pts = history.map((d, i) => `${(i / (history.length - 1)) * w},${h - (d.score / 100) * h}`).join(" ");
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} aria-label="Score, last 7 days">
      <polyline points={pts} />
    </svg>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState({});
  const [done, setDone] = useState({});
  const [toast, setToast] = useState(null);

  const run = async () => {
    setLoading(true);
    setDone({});
    try {
      setData(await api("/checkup"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { run(); }, []);

  const fix = async (checkId) => {
    setBusy((b) => ({ ...b, [checkId]: true }));
    const res = await api(`/fix/${checkId}`, { method: "POST" });
    setBusy((b) => ({ ...b, [checkId]: false }));
    if (res.ok) {
      setDone((d) => ({ ...d, [checkId]: res.message }));
      setData((d) => ({ ...d, stats: res.stats }));
      setToast(`+${Math.round(res.minutes_per_week)} min/week saved`);
      setTimeout(() => setToast(null), 2500);
    } else {
      setToast(res.message || res.detail);
      setTimeout(() => setToast(null), 3500);
    }
  };

  const toggleDemo = async () => {
    await api("/demo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !data?.demo?.enabled }),
    });
    run();
  };

  if (loading && !data) {
    return (
      <main className="shell center">
        <div className="pulse" />
        <p className="muted">Checking your laptop…</p>
      </main>
    );
  }

  const { score, brief, checks, stats, timing, demo } = data;
  const delta = stats.yesterday_score != null ? score - stats.yesterday_score : null;

  return (
    <main className="shell">
      <header className="top">
        <div>
          <p className="muted small">{new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}</p>
          <h1>{greeting()}.</h1>
        </div>
        <button className={`chip ${demo.enabled ? "on" : ""}`} onClick={toggleDemo} title="Inject faults for the demo">
          Demo {demo.enabled ? "on" : "off"}
        </button>
      </header>

      <section className="hero card">
        <ScoreRing score={score} />
        <div className="hero-text">
          <h2>{brief.headline}</h2>
          <p className="muted small">
            Checked in {timing.checks_s}s
            {delta != null && <> · {delta >= 0 ? "▲" : "▼"} {Math.abs(delta)} vs yesterday</>}
            {" · "}{brief.source === "claude" ? "AI brief" : "offline brief"}
          </p>
        </div>
      </section>

      <section className="stats">
        <div className="card stat">
          <span className="big">{stats.minutes_saved_week}</span>
          <span className="muted small">min saved this week</span>
        </div>
        <div className="card stat">
          <span className="big">{stats.streak_days}</span>
          <span className="muted small">day streak</span>
        </div>
        <div className="card stat">
          <Sparkline history={stats.history} />
          <span className="muted small">last 7 days</span>
        </div>
      </section>

      {brief.actions.length > 0 && (
        <section>
          <h3>Worth fixing now</h3>
          <ul className="actions">
            {brief.actions.map((a) => {
              const check = checks.find((c) => c.id === a.check_id);
              return (
                <li key={a.check_id} className={`card action ${check?.status} ${done[a.check_id] ? "fixed" : ""}`}>
                  <div>
                    <p className="label">{check?.title}</p>
                    <p>{done[a.check_id] || a.message}</p>
                    {!done[a.check_id] && check?.minutes_per_week > 0 && (
                      <p className="muted small">Costs you ~{check.minutes_per_week} min/week</p>
                    )}
                  </div>
                  {done[a.check_id] ? (
                    <span className="ok-mark" aria-label="Fixed">✓</span>
                  ) : a.fix_id ? (
                    <button className="primary" disabled={busy[a.check_id]} onClick={() => fix(a.check_id)}>
                      {busy[a.check_id] ? "Fixing…" : "Fix"}
                    </button>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section className="card tip">
        <p className="label">Today</p>
        <p>{brief.tip}</p>
      </section>

      <details className="all">
        <summary>All checks ({checks.length})</summary>
        <ul>
          {checks.map((c) => (
            <li key={c.id}><span className={`dot ${c.status}`} />{c.title}: <span className="muted">{c.detail}</span></li>
          ))}
        </ul>
      </details>

      <footer>
        <button className="ghost" onClick={run} disabled={loading}>{loading ? "Checking…" : "Run again"}</button>
      </footer>

      {toast && <div className="toast" role="status">{toast}</div>}
    </main>
  );
}
