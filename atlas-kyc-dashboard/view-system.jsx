/* global React, Icon, MOCK */

/* ============================================================
   System Information — admin view
   ============================================================ */

const PROMPT_CONTENT = {
  "KYC-SCREEN-01": `You are a KYC compliance analyst. Given a customer record and their AML/PEP screening results, perform a structured risk assessment.

INPUT:
- customer_id: {{customer_id}}
- full_name: {{full_name}}
- jurisdiction: {{jurisdiction}}
- screening_status: {{screening_status}}
- screening_date: {{screening_date}}
- pep_match: {{pep_match}}
- sanctions_match: {{sanctions_match}}
- adverse_media: {{adverse_media}}

TASK:
1. Identify any hard-reject conditions (confirmed sanctions match, unmitigated high-risk jurisdiction).
2. Identify any review-trigger conditions (unresolved match, stale screening > 365 days).
3. Summarise findings in ≤ 3 sentences.
4. Return a structured JSON with: { "disposition": "PASS|REVIEW|REJECT", "triggers": [...], "summary": "..." }

Rules:
- Never speculate beyond the data provided.
- Use FATF Recommendation 6 for sanctions and Rec 12 for PEPs.
- Output must be valid JSON only. No preamble or explanation outside the JSON block.`,

  "KYC-SUMM-01": `You are a KYC case summariser for a Private Wealth compliance team. Generate a concise case summary for analyst review.

INPUT:
- case_id: {{case_id}}
- client_name: {{client_name}}
- risk_tier: {{risk_tier}}
- risk_score: {{risk_score}}/100
- disposition: {{disposition}}
- flags: {{flags}}
- dimensions: {{dimensions_json}}
- account_open_date: {{account_open_date}}
- last_kyc_review: {{last_kyc_review}}

TASK:
Produce a structured case summary with these sections:
1. Risk summary (2 sentences max)
2. Key findings — bullet list of active flags
3. Recommended next action — one of: Approve, Request docs, Escalate, EDD

Constraints:
- Maximum 150 words total.
- Do not include personally identifiable information beyond client name and case ID.
- Tone: professional, regulatory-grade.
- Output format: plain text, not JSON.`,

  "KYC-FLAG-01": `You are a KYC compliance reasoning engine. Explain why a specific KYC flag was raised for an analyst who must decide whether to clear or escalate.

INPUT:
- flag_type: {{flag_type}}
- flag_value: {{flag_value}}
- customer_jurisdiction: {{jurisdiction}}
- risk_tier: {{risk_tier}}
- applicable_rule_ids: {{rule_ids}}
- policy_reference: {{policy_reference}}

TASK:
1. State which rule was triggered and why (cite rule_id and policy_reference).
2. Explain what evidence the analyst should collect to clear this flag.
3. State the escalation path if the flag cannot be cleared within 5 business days.

Format: numbered list, max 200 words.
Do not fabricate evidence or assume data not provided.`,
};

function PromptModal({ prompt, onClose }) {
  const content = PROMPT_CONTENT[prompt.id] || `Prompt content for ${prompt.id} is not available in this environment.`;
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}
         onClick={onClose}>
      <div style={{ background: "var(--bg)", borderRadius: "var(--radius-lg)", width: 680, maxHeight: "80vh", display: "flex", flexDirection: "column", boxShadow: "0 20px 60px rgba(0,0,0,0.22)", overflow: "hidden" }}
           onClick={e => e.stopPropagation()}>
        <div style={{ padding: "18px 22px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span className="badge b-ok mono" style={{ fontSize: 11 }}>{prompt.id}</span>
              <span className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)" }}>{prompt.v} ({prompt.date})</span>
            </div>
            <div style={{ fontWeight: 600, fontSize: 14.5 }}>{prompt.desc}</div>
          </div>
          <button className="btn ghost" onClick={onClose} style={{ padding: "0 6px" }}><Icon name="x"/></button>
        </div>
        <div style={{ padding: "20px 22px", overflowY: "auto", flex: 1 }}>
          <div style={{ fontSize: 12, color: "var(--ink-4)", marginBottom: 10, display: "flex", gap: 16 }}>
            <span><Icon name="bolt"/> {prompt.calls} calls (24h)</span>
            <span><Icon name="clock"/> p95 {prompt.lat}</span>
            <span>Model: claude-haiku-4-5-20251001</span>
          </div>
          <pre style={{ fontSize: 12.5, lineHeight: 1.7, fontFamily: "var(--font-mono)", background: "var(--bg-sunken)", padding: "16px 18px", borderRadius: 8, border: "1px solid var(--line)", whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0, color: "var(--ink-2)" }}>
            {content}
          </pre>
        </div>
        <div style={{ padding: "14px 22px", borderTop: "1px solid var(--line)", display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn ghost"><Icon name="download"/> Export</button>
          <button className="btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

function SystemView() {
  const { useState, useEffect } = React;
  const [sysInfo, setSysInfo] = useState(null);
  const [promptModal, setPromptModal] = useState(null);

  useEffect(() => {
    fetch("/api/system/info")
      .then(r => r.ok ? r.json() : null)
      .then(d => setSysInfo(d))
      .catch(() => {});
    try {
      fetch("/api/audit/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "NAV_SYSTEM", description: "Opened System information view" }),
      });
    } catch (_) {}
  }, []);

  const dsEntries = sysInfo && sysInfo.datasets && Object.keys(sysInfo.datasets).length > 0
    ? Object.entries(sysInfo.datasets).map(([name, rows]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        kind: "CSV · uploaded batch",
        n: rows.toLocaleString(),
        refreshed: "Session",
        status: "ok",
      }))
    : MOCK.datasets;

  return (
    <div>
      {promptModal && <PromptModal prompt={promptModal} onClose={() => setPromptModal(null)}/>}

      <div className="page-h">
        <div>
          <div className="eyebrow">Administration</div>
          <h1 className="page-title">System information</h1>
          <div className="page-sub">Runtime, datasets, prompts, integrations and security posture for the KYC tool. Read-only — changes go through change management.</div>
        </div>
        <div className="row-flex">
          <button className="btn" onClick={() => fetch("/api/system/info").then(r=>r.ok?r.json():null).then(d=>setSysInfo(d)).catch(()=>{})}><Icon name="refresh"/> Refresh</button>
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
          <div className="card-h">
            <h3>Datasets</h3>
            <span className="meta">{dsEntries.length} sources · {dsEntries.filter(d => d.status === "ok").length} live</span>
          </div>
          <table className="tbl">
            <thead>
              <tr><th>Source</th><th style={{ width: 120 }}>Records</th><th style={{ width: 130 }}>Refreshed</th><th style={{ width: 90 }}>Status</th></tr>
            </thead>
            <tbody>
              {dsEntries.map((d, i) => (
                <tr key={i}>
                  <td><b style={{ fontWeight: 500 }}>{d.name}</b><div style={{ fontSize: 11.5, color: "var(--ink-4)" }}>{d.kind}</div></td>
                  <td className="mono">{d.n}</td>
                  <td className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>{d.refreshed}</td>
                  <td>
                    {d.status === "ok"   && <span className="badge b-ok"><span className="dot"/>live</span>}
                    {d.status === "warn" && <span className="badge b-warn"><span className="dot"/>stale</span>}
                    {d.status === "off"  && <span className="badge b-mute">off</span>}
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
                  <span style={{ marginLeft: "auto" }}>
                    <button className="lnk" style={{ background: "none", border: "none", cursor: "pointer", padding: 0, font: "inherit", color: "var(--accent)" }} onClick={() => setPromptModal(p)}>View prompt</button>
                    {" · "}
                    <button className="lnk" style={{ background: "none", border: "none", cursor: "pointer", padding: 0, font: "inherit", color: "var(--accent)" }} onClick={() => setPromptModal({ ...p, _showDiff: true })}>Diff</button>
                  </span>
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
            <div><span>Framework</span><b>FastAPI {sysInfo ? sysInfo.fastapi_version : "0.115"} / Python {sysInfo ? sysInfo.python_version : "3.12"}</b></div>
            <div><span>Active ruleset</span><b className="mono"><span className="badge b-accent mono" style={{ fontSize: 10.5 }}>kyc-rules-v2.1</span></b></div>
            <div><span>Live URL</span><b>kyc-apexon.onrender.com</b></div>
            <div><span>Build</span><b className="mono">eda192f · 2026-04-30</b></div>
            <div><span>Active sessions</span><b>{sysInfo ? sysInfo.active_sessions : "—"}</b></div>
            <div><span>Storage</span><b>tempfile (session-scoped)</b></div>
            <div><span>Auth</span><b>In-memory sessions (RBAC)</b></div>
            {sysInfo && sysInfo.hostname && <div><span>Host</span><b className="mono">{sysInfo.hostname}</b></div>}
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

      <div className="card" style={{ marginTop: "var(--d-gap)" }}>
        <div className="card-h">
          <h3>AI Observability</h3>
          <span className="meta">Claude API · last 24h · agentic pipeline</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--d-gap)", padding: "16px 20px" }}>
          <div><div className="kpi-label">Token usage (24h)</div><div className="kpi-value" style={{fontSize:22}}>1.24M</div><div className="kpi-sub">input + output · ~$3.72</div></div>
          <div><div className="kpi-label">Avg cost / customer</div><div className="kpi-value" style={{fontSize:22}}>$0.07</div><div className="kpi-sub">batch of 50 · last run</div></div>
          <div><div className="kpi-label">LLM p95 latency</div><div className="kpi-value" style={{fontSize:22}}>1.84s</div><div className="kpi-sub">classification + OCR calls</div></div>
          <div><div className="kpi-label">OCR confidence avg</div><div className="kpi-value" style={{fontSize:22}}>78%</div><div className="kpi-sub">across 141 documents</div></div>
        </div>
        <div style={{ borderTop: "1px solid var(--line)", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0 }}>
          {[
            { label: "Cache hit rate", value: "62%", sub: "prompt caching enabled" },
            { label: "Hallucination flags", value: "3", sub: "low-confidence extractions" },
            { label: "Model", value: "claude-sonnet-4-6", sub: "structured extraction" },
          ].map((s, i) => (
            <div key={i} style={{ padding: "14px 20px", borderRight: i < 2 ? "1px solid var(--line)" : "none" }}>
              <div className="kpi-label">{s.label}</div>
              <div style={{ fontWeight: 600, fontSize: 16, margin: "4px 0 2px" }}>{s.value}</div>
              <div className="kpi-sub">{s.sub}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="sysfoot">
        <span><b>Hosting:</b> Render.com</span>
        <span className="sep">|</span>
        <span><b>Framework:</b> FastAPI {sysInfo ? sysInfo.fastapi_version : "0.115"} / Python {sysInfo ? sysInfo.python_version : "3.12"}</span>
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
