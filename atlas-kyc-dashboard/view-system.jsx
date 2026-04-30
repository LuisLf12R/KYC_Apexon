/* global React, Icon, MOCK */

/* ============================================================
   System Information — admin view
   ============================================================ */
function SystemView() {
  return (
    <div>
      <div className="page-h">
        <div>
          <div className="eyebrow">Administration</div>
          <h1 className="page-title">System information</h1>
          <div className="page-sub">Runtime, datasets, prompts, integrations and security posture for the KYC tool. Read-only — changes go through change management.</div>
        </div>
        <div className="row-flex">
          <button className="btn"><Icon name="refresh"/> Refresh</button>
          <button className="btn"><Icon name="download"/> Export status</button>
        </div>
      </div>

      {/* Health strip */}
      <div className="kpi-strip">
        <div className="kpi"><div className="kpi-label"><Icon name="check"/> Service health</div><div className="kpi-value" style={{ color: "var(--ok)" }}>Healthy</div><div className="kpi-sub">All 6 services reporting</div></div>
        <div className="kpi"><div className="kpi-label"><Icon name="clock"/> Uptime (30d)</div><div className="kpi-value">99.987%</div><div className="kpi-sub">SLO 99.95% · 4m 12s downtime</div></div>
        <div className="kpi"><div className="kpi-label"><Icon name="bolt"/> Model latency p95</div><div className="kpi-value">1.84s</div><div className="kpi-sub">target ≤ 3s · <span className="kpi-delta up">↓ 6%</span></div></div>
        <div className="kpi"><div className="kpi-label"><Icon name="shield"/> Last security scan</div><div className="kpi-value" style={{ fontSize: 22 }}>2026-04-28</div><div className="kpi-sub">0 critical · 2 medium</div></div>
      </div>

      {/* Two columns */}
      <div className="split-1-1">
        {/* Datasets */}
        <div className="card">
          <div className="card-h"><h3>Datasets</h3><span className="meta">7 sources · 4 live</span></div>
          <table className="tbl">
            <thead>
              <tr><th>Source</th><th style={{ width: 120 }}>Records</th><th style={{ width: 130 }}>Refreshed</th><th style={{ width: 90 }}>Status</th></tr>
            </thead>
            <tbody>
              {MOCK.datasets.map((d, i) => (
                <tr key={i}>
                  <td><b style={{ fontWeight: 500 }}>{d.name}</b><div style={{ fontSize: 11.5, color: "var(--ink-4)" }}>{d.kind}</div></td>
                  <td className="mono">{d.n}</td>
                  <td className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>{d.refreshed}</td>
                  <td>
                    {d.status === "ok" && <span className="badge b-ok"><span className="dot"/>live</span>}
                    {d.status === "warn" && <span className="badge b-warn"><span className="dot"/>stale</span>}
                    {d.status === "off" && <span className="badge b-mute">off</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Active prompts */}
        <div className="card">
          <div className="card-h"><h3>Active prompts</h3><span className="meta">3 in production · model claude-haiku-4-5</span></div>
          <ul className="prompt-list">
            {MOCK.prompts.map((p, i) => (
              <li key={i}>
                <div className="row-flex" style={{ gap: 8 }}>
                  <span className="badge b-ok mono" style={{ fontSize: 11 }}>{p.id}</span>
                  <span className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)" }}>{p.v} ({p.date})</span>
                </div>
                <p className="muted" style={{ fontSize: 13, margin: "8px 0 0", textWrap: "pretty" }}>{p.desc}</p>
                <div className="row-flex" style={{ marginTop: 10, gap: 14, fontSize: 12, color: "var(--ink-4)" }}>
                  <span><Icon name="bolt"/> {p.calls} calls (24h)</span>
                  <span><Icon name="clock"/> p95 {p.lat}</span>
                  <span style={{ marginLeft: "auto" }}><a className="lnk">View prompt</a> · <a className="lnk">Diff</a></span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Runtime + integrations */}
      <div className="split-1-1" style={{ marginTop: "var(--d-gap)" }}>
        <div className="card">
          <div className="card-h"><h3>Runtime</h3><span className="meta">production · us-east</span></div>
          <div className="kv-grid">
            <div><span>Hosting</span><b>Render.com · Starter plan</b></div>
            <div><span>Framework</span><b>FastAPI 0.115 / Python 3.12</b></div>
            <div><span>Active ruleset</span><b className="mono"><span className="badge b-accent mono" style={{ fontSize: 10.5 }}>kyc-rules-v2.1</span></b></div>
            <div><span>Live URL</span><b>kyc-apexon.onrender.com</b></div>
            <div><span>Build</span><b className="mono">eda192f · 2026-04-30</b></div>
            <div><span>Replicas</span><b>1 / 1 healthy</b></div>
            <div><span>Storage</span><b>tempfile (session-scoped)</b></div>
            <div><span>Auth</span><b>In-memory sessions (RBAC)</b></div>
          </div>
        </div>

        <div className="card">
          <div className="card-h"><h3>Session & data policy</h3><span className="meta">FFIEC / PSD2 / GDPR</span></div>
          <div className="card-pad" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div className="policy-row">
              <Icon name="clock"/>
              <div><b>Session timeout</b><div className="muted">15 min idle (FFIEC / PSD2). Warning shown at 13 min. Re-authentication after timeout.</div></div>
            </div>
            <div className="policy-row">
              <Icon name="shield"/>
              <div><b>PII handling</b><div className="muted">PII clears from memory on session end. Audit trail stores metadata only — no payload PII at rest.</div></div>
            </div>
            <div className="policy-row">
              <Icon name="audit"/>
              <div><b>Audit retention</b><div className="muted">7 years (FFIEC). Append-only · SHA-256 hash chain · daily Merkle root anchored to KMS.</div></div>
            </div>
            <div className="policy-row">
              <Icon name="globe"/>
              <div><b>Data residency</b><div className="muted">EU-only processing. No data egress to non-adequate jurisdictions per GDPR Art. 45.</div></div>
            </div>
            <div className="policy-row">
              <Icon name="users"/>
              <div><b>Access control</b><div className="muted">RBAC · 4 roles (Admin · MLRO · Analyst · RM). SSO via Okta · MFA mandatory.</div></div>
            </div>
          </div>
        </div>
      </div>

      {/* Integrations */}
      <div className="card" style={{ marginTop: "var(--d-gap)" }}>
        <div className="card-h"><h3>Integrations</h3><span className="meta">{MOCK.integrations.length} endpoints · auto-discovered</span></div>
        <table className="tbl">
          <thead>
            <tr><th>Service</th><th style={{ width: 130 }}>Category</th><th style={{ width: 160 }}>Purpose</th><th style={{ width: 230 }}>Endpoint</th><th style={{ width: 120 }}>Last call</th><th style={{ width: 100 }}>Status</th></tr>
          </thead>
          <tbody>
            {MOCK.integrations.map((r, i) => (
              <tr key={i}>
                <td><b style={{ fontWeight: 500 }}>{r.name}</b></td>
                <td><span className="badge b-mute">{r.category}</span></td>
                <td className="muted" style={{ fontSize: 12.5 }}>{r.purpose}</td>
                <td className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)" }}>{r.endpoint}</td>
                <td className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>{r.lastCall}</td>
                <td>
                  {r.status === "ok"   && <span className="badge b-ok"><span className="dot"/>healthy</span>}
                  {r.status === "warn" && <span className="badge b-warn"><span className="dot"/>degraded</span>}
                  {r.status === "off"  && <span className="badge b-mute">off</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="sysfoot">
        <span><b>Hosting:</b> Render.com</span>
        <span className="sep">|</span>
        <span><b>Framework:</b> FastAPI / Python 3.12</span>
        <span className="sep">|</span>
        <span><b>Ruleset:</b> <span className="badge b-ok mono" style={{ fontSize: 10.5 }}>kyc-rules-v2.1</span></span>
        <span className="sep">|</span>
        <span><b>Timeout:</b> 15 min (FFIEC / PSD2) · <b>Warning at:</b> 13 min</span>
        <div style={{ width: "100%", marginTop: 6, color: "var(--ink-4)", fontSize: 12 }}>PII clears from memory on session end. Audit trail stores metadata only.</div>
      </div>
    </div>
  );
}

window.SystemView = SystemView;
