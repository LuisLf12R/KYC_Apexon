/* global React, Icon, MOCK */

/* ============================================================
   Ruleset versions — admin view
   Active ruleset JSON viewer + changelog + dual-approval override flow
   ============================================================ */
function RulesetView() {
  const { useState, useEffect } = React;
  const [tab, setTab] = useState("active");
  const [showOverride, setShowOverride] = useState(false);
  const [rulesData, setRulesData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/ruleset")
      .then(r => r.ok ? r.json() : null)
      .then(d => { setRulesData(d); setLoading(false); })
      .catch(() => setLoading(false));
    try {
      fetch("/api/audit/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "NAV_RULESET", description: "Opened Ruleset & policy view" }),
      });
    } catch (_) {}
  }, []);

  const activeVersion = rulesData ? (rulesData.version || "kyc-rules-v2.1") : "kyc-rules-v2.1";
  const effectiveDate = rulesData ? (rulesData.effective_date || "2026-01-01") : "2026-01-01";
  const jsonText = rulesData ? JSON.stringify(rulesData, null, 2) : (loading ? "Loading…" : "{}");
  const jurisdictions = rulesData ? Object.values(rulesData.jurisdictions || {}) : [];
  const hardRejectRules = rulesData ? (rulesData.hard_reject_rules || []) : [];
  const reviewRules = rulesData ? (rulesData.review_rules || []) : [];
  const totalRules = hardRejectRules.length + reviewRules.length;

  return (
    <div>
      <div className="page-h">
        <div>
          <div className="eyebrow">Administration</div>
          <h1 className="page-title">Ruleset & policy</h1>
          <div className="page-sub">Validate and update the active ruleset used for new queue runs. Changes require dual approval and a logged override reason.</div>
        </div>
        <div className="row-flex">
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", marginRight: 8 }}>
            <span style={{ fontSize: 11.5, color: "var(--ink-4)" }}>Active file</span>
            <span className="mono" style={{ fontSize: 13, fontWeight: 500 }}>kyc_rules_v2.0.json</span>
          </div>
          <button className="btn" style={{ whiteSpace: "nowrap" }} onClick={() => { setLoading(true); fetch("/api/ruleset").then(r=>r.ok?r.json():null).then(d=>{setRulesData(d);setLoading(false);}).catch(()=>setLoading(false)); }}><Icon name="refresh"/> Reload file</button>
          <button className="btn primary" style={{ whiteSpace: "nowrap" }} onClick={() => setShowOverride(true)}><Icon name="plus"/> Propose change</button>
        </div>
      </div>

      {/* Status strip */}
      <div className="ruleset-status">
        <div className="rs-stat">
          <span className="eyebrow">Active version</span>
          <div className="row-flex" style={{ gap: 8, marginTop: 4 }}>
            <span className="badge b-accent mono">{activeVersion}</span>
            <span className="badge b-ok"><span className="dot"/>Production</span>
          </div>
        </div>
        <div className="rs-stat">
          <span className="eyebrow">Effective</span>
          <div className="mono" style={{ fontSize: 13, marginTop: 4 }}>{effectiveDate}</div>
        </div>
        <div className="rs-stat">
          <span className="eyebrow">Last change</span>
          <div className="mono" style={{ fontSize: 13, marginTop: 4 }}>
            {rulesData && rulesData.changelog && rulesData.changelog[0]
              ? `${rulesData.changelog[0].date} · ${rulesData.changelog[0].reviewed_by || rulesData.changelog[0].author}`
              : "2026-04-19 · NYU RegTech"}
          </div>
        </div>
        <div className="rs-stat">
          <span className="eyebrow">Pending approvals</span>
          <div className="row-flex" style={{ gap: 8, marginTop: 4 }}>
            <span className="badge b-warn"><span className="dot"/>1 awaiting</span>
            <span style={{ fontSize: 12, color: "var(--ink-3)" }}>kyc-rules-v2.2-draft</span>
          </div>
        </div>
        <div className="rs-stat">
          <span className="eyebrow">Validation</span>
          <div className="row-flex" style={{ gap: 6, marginTop: 4, color: "var(--ok)", fontSize: 12.5, fontWeight: 500 }}>
            <Icon name="check"/> {totalRules > 0 ? `${totalRules} rules · ${jurisdictions.length} jurisdictions · OK` : "142 rules · 8 jurisdictions · OK"}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ marginTop: 8 }}>
        <button onClick={() => setTab("active")} aria-current={tab === "active"}>Active ruleset</button>
        <button onClick={() => setTab("changelog")} aria-current={tab === "changelog"}>Changelog</button>
        <button onClick={() => setTab("approvals")} aria-current={tab === "approvals"}>Pending approvals <span className="audit-pill">1</span></button>
        <button onClick={() => setTab("history")} aria-current={tab === "history"}>Override log</button>
      </div>

      {tab === "active"    && <RulesetActive jsonText={jsonText} jurisdictions={jurisdictions} hardRejectRules={hardRejectRules} reviewRules={reviewRules} loading={loading} onPropose={() => setShowOverride(true)}/>}
      {tab === "changelog" && <RulesetChangelog items={rulesData && rulesData.changelog ? rulesData.changelog : null}/>}
      {tab === "approvals" && <RulesetApprovals/>}
      {tab === "history"   && <RulesetOverrideLog/>}

      {showOverride && <OverrideModal onClose={() => setShowOverride(false)}/>}
    </div>
  );
}

function RulesetActive({ jsonText, jurisdictions, hardRejectRules, reviewRules, loading, onPropose }) {
  const JURISDICTION_NOTES = {
    USA: "Reg-K · OFAC SDN", GBR: "60-day doc expiry", EU: "180-day rescreen",
    CHE: "180-day rescreen", SGP: "MAS 30-day velocity", HKG: "SFC 10% UBO",
    AUS: "AUSTRAC TTR", CHN: "Deferred post-v1", CAN: "FINTRAC", UAE: "CBUAE", IND: "RBI",
  };
  const jList = jurisdictions.length > 0
    ? jurisdictions.map(j => ({
        code: j.jurisdiction_code,
        note: JURISDICTION_NOTES[j.jurisdiction_code] || (j.regulators || []).join(", "),
        count: Object.keys(j.dimension_overrides || {}).length + (j.additional_hard_reject_rules || []).length + (j.additional_review_rules || []).length,
        deferred: j.jurisdiction_code === "CHN",
      }))
    : [
        { code: "USA", note: "Reg-K · OFAC SDN", count: 38 }, { code: "GBR", note: "60-day doc expiry", count: 22 },
        { code: "EU",  note: "180-day rescreen",  count: 19 }, { code: "CHE", note: "180-day rescreen",  count: 17 },
        { code: "SGP", note: "MAS 30-day velocity", count: 14 }, { code: "HKG", note: "SFC 10% UBO",   count: 16 },
        { code: "AUS", note: "AUSTRAC TTR", count: 11 }, { code: "CHN", note: "Deferred post-v1", count: 0, deferred: true },
      ];

  return (
    <div className="ruleset-grid">
      <div className="card">
        <div className="card-h">
          <h3>Active ruleset JSON <span className="muted" style={{ fontWeight: 400, marginLeft: 8 }}>kyc_rules_v2.0.json</span></h3>
          <div className="row-flex">
            <button className="btn ghost"><Icon name="download"/> Download</button>
            <button className="btn ghost"><Icon name="expand"/> Fullscreen</button>
          </div>
        </div>
        <div className="json-editor">
          <div className="json-gutter">
            {jsonText.split("\n").map((_, i) => <div key={i}>{i + 1}</div>)}
          </div>
          {loading
            ? <pre className="json-body" style={{ color: "var(--ink-4)" }}>Loading ruleset…</pre>
            : <pre className="json-body" dangerouslySetInnerHTML={{ __html: highlightJson(jsonText) }}/>
          }
        </div>
        <div className="ruleset-foot">
          <div className="row-flex" style={{ gap: 8 }}>
            <button className="btn"><Icon name="check"/> Validate draft</button>
            <span style={{ fontSize: 12, color: "var(--ink-4)" }}>
              {hardRejectRules.length + reviewRules.length} rules · 0 errors · 2 warnings
            </span>
          </div>
          <div className="row-flex" style={{ gap: 8 }}>
            <button className="btn ghost">Discard</button>
            <button className="btn primary" onClick={onPropose}><Icon name="arrowRight"/> Propose change</button>
          </div>
        </div>
      </div>

      <aside className="col-flex" style={{ gap: 16 }}>
        <div className="card">
          <div className="card-h"><h3>Jurisdiction overlays</h3><span className="meta">{jList.length} active</span></div>
          <ul className="overlay-list">
            {jList.map(j => (
              <li key={j.code}>
                <span className="mono ovl-code">{j.code}</span>
                <span className="ovl-note">{j.note}</span>
                <span className={`badge ${j.deferred ? "b-mute" : "b-info"} mono`} style={{ fontSize: 10.5 }}>
                  {j.deferred ? "deferred" : j.count > 0 ? `${j.count} overrides` : "base rules"}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {(hardRejectRules.length > 0 || reviewRules.length > 0) && (
          <div className="card">
            <div className="card-h"><h3>Rule summary</h3><span className="meta">from loaded ruleset</span></div>
            <div className="card-pad">
              <div className="meter-row">
                <span>Hard reject</span>
                <div className="meter"><i style={{ width: `${Math.min(hardRejectRules.length * 20, 100)}%`, background: "var(--bad)" }}/></div>
                <b className="mono">{hardRejectRules.length}</b>
              </div>
              <div className="meter-row">
                <span>Review triggers</span>
                <div className="meter"><i style={{ width: `${Math.min(reviewRules.length * 10, 100)}%` }}/></div>
                <b className="mono">{reviewRules.length}</b>
              </div>
            </div>
          </div>
        )}

        <div className="card">
          <div className="card-h"><h3>Active in queue</h3><span className="meta">last 24h</span></div>
          <div className="card-pad">
            <div className="meter-row"><span>kyc-rules-v2.1</span><div className="meter"><i style={{ width: "94%" }}/></div><b className="mono">94%</b></div>
            <div className="meter-row"><span>kyc-rules-v2.0</span><div className="meter"><i style={{ width: "5%", background: "var(--warn)" }}/></div><b className="mono">5%</b></div>
            <div className="meter-row"><span>kyc-rules-v1.1</span><div className="meter"><i style={{ width: "1%", background: "var(--ink-4)" }}/></div><b className="mono">1%</b></div>
          </div>
        </div>
      </aside>
    </div>
  );
}

function RulesetChangelog({ items }) {
  const fallback = [
    { version: "v2.1", date: "2026-04-19", author: "NYU RegTech", change: "Phase 3: jurisdiction-aware ruleset. Eight jurisdiction overlays added: USA, GBR, EU, CHE, SGP, HKG, AUS. HKG SFC 10% UBO threshold; SGP MAS 30-day velocity window; EU/CHE 180-day rescreening interval; GBR 60-day doc expiry warning. China deferred post-v1.", state: "active" },
    { version: "v2.0", date: "2026-03-02", author: "NYU RegTech", change: "Baseline lifted from v1.1. Introduced FATF Recommendations and Wolfsberg Private Banking Principles as foundation. Added structured risk-tiering matrix.", state: "superseded" },
    { version: "v1.1", date: "2026-01-15", author: "Compliance WG", change: "Added adverse media weighting, refined PEP exposure decay (12-month half-life). Introduced UBO 25% disclosure threshold per FATF R10.", state: "superseded" },
    { version: "v1.0", date: "2025-11-08", author: "Compliance WG", change: "Initial production ruleset. AML, sanctions, PEP and basic KYC checks. Single-jurisdiction (US-only).", state: "superseded" },
  ];
  const rows = items && items.length > 0
    ? items.map((it, idx) => ({ version: it.version, date: it.date, author: it.reviewed_by || it.author, change: it.change, state: idx === 0 ? "active" : "superseded" }))
    : fallback;

  return (
    <div className="card">
      <div className="card-h"><h3>Changelog</h3><span className="meta">{rows.length} versions · most recent first</span></div>
      {rows.map((it, i) => (
        <div key={i} className="changelog-item">
          <div className="changelog-l">
            <div className="row-flex" style={{ gap: 8 }}>
              <span className="badge b-accent mono">{it.version}</span>
              {it.state === "active"      && <span className="badge b-ok"><span className="dot"/>active</span>}
              {it.state === "superseded"  && <span className="badge b-mute">superseded</span>}
            </div>
            <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", marginTop: 6 }}>{it.date}</div>
            <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>by {it.author}</div>
          </div>
          <div className="changelog-r">
            <p style={{ margin: 0, fontSize: 13.5, color: "var(--ink-2)", textWrap: "pretty" }}>{it.change}</p>
            <div className="row-flex" style={{ marginTop: 10, gap: 6 }}>
              <button className="btn ghost" style={{ height: 28, padding: "0 10px", fontSize: 12 }}>View JSON</button>
              <button className="btn ghost" style={{ height: 28, padding: "0 10px", fontSize: 12 }}>Diff to active</button>
              <button className="btn ghost" style={{ height: 28, padding: "0 10px", fontSize: 12 }}>Audit (24)</button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function RulesetApprovals() {
  return (
    <div className="card">
      <div className="card-h">
        <h3>Pending approvals <span className="muted" style={{ fontWeight: 400, marginLeft: 6 }}>(1)</span></h3>
        <span className="meta">Two-person rule · SOX §404 / FFIEC</span>
      </div>
      <div className="approval-card">
        <div className="approval-card-h">
          <div>
            <div className="row-flex" style={{ gap: 8 }}>
              <span className="badge b-accent mono">v2.2-draft</span>
              <span className="badge b-warn"><span className="dot"/>1 of 2 signatures</span>
              <span style={{ fontSize: 12, color: "var(--ink-4)" }}>Proposed 2026-04-29 · 11:42 UTC</span>
            </div>
            <h4 style={{ margin: "10px 0 4px", fontSize: 16, fontWeight: 600 }}>Lower SGP MAS velocity threshold from 30 to 14 days</h4>
            <p className="muted" style={{ fontSize: 13, margin: 0, maxWidth: 720, textWrap: "pretty" }}>
              MAS Notice 626 §6.3 update (Apr 2026) tightened velocity-monitoring window for non-resident HNWI booking centres. Applies to Singapore booking centre only; expected to raise alert volume by ~6%.
            </p>
          </div>
          <div className="row-flex">
            <button className="btn">View diff</button>
            <button className="btn">Justification</button>
          </div>
        </div>

        <div className="diff-block">
          <div className="diff-h">
            <span>Rule <code className="mono">SGP.velocity.window</code></span>
            <span className="mono" style={{ color: "var(--ink-4)", fontSize: 11.5 }}>+1 / −1 lines</span>
          </div>
          <pre className="diff-body">
<span className="diff-removed">- "window_days": 30,</span>
<span className="diff-added">+ "window_days": 14,</span>
            {"  \"applies_to\": [\"SGP\"],"}{"\n"}
            {"  \"trigger\": \"velocity_score >= 0.72\","}
          </pre>
        </div>

        <div className="approval-row">
          <div className="approver-tile signed">
            <div className="avatar">SR</div>
            <div>
              <b>S. Rahimi</b>
              <small className="muted">Head of Compliance · signed 2026-04-29 11:43</small>
            </div>
            <span className="badge b-ok" style={{ marginLeft: "auto" }}><Icon name="check"/> approved</span>
          </div>
          <div className="approver-tile pending">
            <div className="avatar" style={{ background: "var(--bg-active)", color: "var(--ink-3)" }}>?</div>
            <div>
              <b>Awaiting second approver</b>
              <small className="muted">Required: MLRO or Deputy MLRO · expires in 22h</small>
            </div>
            <button className="btn primary" style={{ marginLeft: "auto" }}>Approve</button>
            <button className="btn danger">Reject</button>
          </div>
        </div>

        <div className="override-reason">
          <div className="eyebrow">Override reason · logged immutably</div>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--ink-2)", textWrap: "pretty" }}>
            "Regulatory tightening (MAS Notice 626 §6.3) requires a 14-day velocity window for non-resident HNWI booking centres effective Q3 2026. Implementation ahead of grace period to avoid backlog."
          </p>
          <div className="row-flex" style={{ marginTop: 8, gap: 12, fontSize: 11.5, color: "var(--ink-4)" }}>
            <span>evt_8f3a2e1c</span>
            <span>hash 0b622eb27409…</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function RulesetOverrideLog() {
  const log = [
    { date: "2026-04-19 14:02", v: "v2.1", reason: "FATF mutual evaluation findings — added 8 jurisdiction overlays.", approvers: ["S. Rahimi", "M. Costa"], state: "approved" },
    { date: "2026-03-02 09:14", v: "v2.0", reason: "Baseline lift to FATF + Wolfsberg foundations; structured risk-tier matrix.", approvers: ["S. Rahimi", "L. Chen"], state: "approved" },
    { date: "2026-02-11 16:48", v: "v1.1-rc2", reason: "Proposed lower UBO threshold to 10% globally — rejected, scoped to HKG only via overlay.", approvers: ["S. Rahimi"], state: "rejected" },
    { date: "2026-01-15 10:30", v: "v1.1", reason: "Added adverse media weighting and PEP decay model.", approvers: ["S. Rahimi", "M. Costa"], state: "approved" },
  ];
  return (
    <div className="card">
      <div className="card-h"><h3>Override log</h3><span className="meta">All ruleset changes · immutable</span></div>
      <table className="tbl">
        <thead>
          <tr>
            <th style={{ width: 160 }}>When</th>
            <th style={{ width: 120 }}>Version</th>
            <th>Reason</th>
            <th style={{ width: 220 }}>Approvers</th>
            <th style={{ width: 120 }}>State</th>
          </tr>
        </thead>
        <tbody>
          {log.map((l, i) => (
            <tr key={i}>
              <td className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>{l.date}</td>
              <td><span className="badge b-accent mono">{l.v}</span></td>
              <td style={{ color: "var(--ink-2)" }}>{l.reason}</td>
              <td>{l.approvers.join(" · ")}</td>
              <td>
                {l.state === "approved" && <span className="badge b-ok"><span className="dot"/>approved</span>}
                {l.state === "rejected" && <span className="badge b-bad"><span className="dot"/>rejected</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OverrideModal({ onClose }) {
  return (
    <div className="modal-scrim" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-h">
          <div>
            <div className="eyebrow">Propose ruleset change</div>
            <h3 style={{ margin: "6px 0 2px", fontSize: 17, fontWeight: 600 }}>Override requires dual approval</h3>
            <div className="muted" style={{ fontSize: 13 }}>Per SOX §404 / FFIEC — two distinct approvers required, including MLRO or deputy.</div>
          </div>
          <button className="btn ghost" onClick={onClose}><Icon name="x"/></button>
        </div>
        <div className="modal-body">
          <label className="lbl">Title</label>
          <input className="inp" defaultValue="Lower SGP MAS velocity threshold from 30 to 14 days"/>

          <label className="lbl">Override reason <span className="muted" style={{ fontWeight: 400 }}>(immutable, logged with hash)</span></label>
          <textarea className="inp" rows="4" defaultValue="Regulatory tightening (MAS Notice 626 §6.3) requires a 14-day velocity window for non-resident HNWI booking centres effective Q3 2026."/>

          <div className="grid-2">
            <div>
              <label className="lbl">Effective date</label>
              <input className="inp mono" defaultValue="2026-05-15"/>
            </div>
            <div>
              <label className="lbl">Scope</label>
              <input className="inp" defaultValue="SGP only · booking centre = singapore"/>
            </div>
          </div>

          <label className="lbl">Required approvers</label>
          <div className="approver-pick">
            <span className="pick-row"><span className="dot accent"/>You · M. Lyons (Admin)<span style={{ marginLeft: "auto", color: "var(--ink-4)", fontSize: 12 }}>proposer</span></span>
            <span className="pick-row"><span className="dot ok"/>S. Rahimi · Head of Compliance<span style={{ marginLeft: "auto", color: "var(--ok)", fontSize: 12 }}>auto-notify</span></span>
            <span className="pick-row"><span className="dot warn"/>2nd approver — choose: MLRO / Deputy MLRO<span style={{ marginLeft: "auto", color: "var(--ink-4)", fontSize: 12 }}>required</span></span>
          </div>

          <div className="callout">
            <Icon name="shield"/>
            <div><b>Two-person rule.</b> This change cannot be applied until both approvers sign. The override reason and signatures are written to the audit trail and cannot be edited.</div>
          </div>
        </div>
        <div className="modal-foot">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary"><Icon name="arrowRight"/> Submit for approval</button>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Light JSON syntax highlight
   ============================================================ */
function highlightJson(json) {
  return json
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/("(?:\\.|[^"\\])*")\s*:/g, '<span class="jk">$1</span>:')
    .replace(/:\s*("(?:\\.|[^"\\])*")/g, ': <span class="js">$1</span>')
    .replace(/:\s*(true|false|null)/g, ': <span class="jb">$1</span>')
    .replace(/:\s*(-?\d+\.?\d*)/g, ': <span class="jn">$1</span>');
}

window.RulesetView = RulesetView;
