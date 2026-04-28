"""
kyc_dashboard/banker_html.py
Standalone HTML/React builder for the Banker dashboard.
No Streamlit dependency — safe to import from Flask sidecar threads.
"""
from __future__ import annotations

import json
from typing import Any, Dict


def build_banker_html(initial_data: Dict[str, Any]) -> str:
    """Return a complete standalone HTML page for the Banker KYC dashboard."""
    data_json = json.dumps(initial_data, default=str, ensure_ascii=False)

    css = r"""
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; font-family: "Helvetica Neue", Helvetica, Arial, ui-sans-serif, system-ui, sans-serif; background: #f6f6f8; -webkit-font-smoothing: antialiased; }
:root {
  --bg:#ffffff; --bg-elev:#fbfbfc; --bg-sunken:#f6f6f8; --bg-hover:#f3f3f6; --bg-active:#eeeef3;
  --line:#ececf0; --line-strong:#d8d8e0;
  --ink:#0e1014; --ink-2:#2a2d35; --ink-3:#4a4e59; --ink-4:#6a6e79; --ink-5:#8a8e98;
  --accent:#3b5bdb; --accent-soft:#eef1ff; --accent-ink:#2f4abf;
  --ok:#2b9a48; --ok-soft:#eafbee;
  --warn:#c07700; --warn-soft:#fff9e1; --warn-text:#8a5900;
  --bad:#c22828; --bad-soft:#fff1f0;
  --info:#1864ab; --info-soft:#e7f5ff;
  --risk-med:#b07a00;
  --radius:8px; --radius-sm:6px; --radius-lg:12px;
  --shadow-sm:0 1px 2px rgba(15,17,22,.05),0 0 0 1px rgba(15,17,22,.03);
  --shadow-md:0 2px 8px rgba(15,17,22,.09),0 0 0 1px rgba(15,17,22,.04);
  --d-row:44px; --d-pad:16px; --d-gap:16px; --d-text:14px;
  --font-mono:"SF Mono",Menlo,Consolas,monospace;
}
button { font:inherit; color:inherit; cursor:pointer; border:0; background:none; padding:0; }
input, textarea, select { font:inherit; color:inherit; }
.tnum  { font-variant-numeric:tabular-nums; }
.mono  { font-family:var(--font-mono); font-variant-numeric:tabular-nums; }
.muted { color:var(--ink-3); }
.eyebrow { font-size:11px; letter-spacing:.08em; text-transform:uppercase; color:var(--ink-4); font-weight:500; }
.row-flex { display:flex; align-items:center; gap:10px; }
.row-flex.gap-sm { gap:6px; }
.row-flex.between { justify-content:space-between; }
.col-flex { display:flex; flex-direction:column; gap:var(--d-gap); }
.divider  { height:1px; background:var(--line); margin:var(--d-gap) 0; }
.page-h   { display:flex; align-items:flex-end; justify-content:space-between; gap:24px; margin-bottom:20px; }
.page-title { font-size:22px; font-weight:600; letter-spacing:-.02em; margin:4px 0; color:var(--ink); }
.page-sub   { color:var(--ink-3); font-size:13.5px; }
.section-h  { display:flex; align-items:center; justify-content:space-between; margin:6px 0 12px; }
.section-h h3 { margin:0; font-size:14px; font-weight:600; color:var(--ink); }
.section-h .meta { color:var(--ink-4); font-size:12px; }
.card { background:var(--bg); border:1px solid var(--line); border-radius:var(--radius-lg); box-shadow:var(--shadow-sm); overflow:hidden; margin-bottom:14px; }
.card-pad { padding:var(--d-pad) calc(var(--d-pad) + 4px); }
.card-h { display:flex; align-items:center; justify-content:space-between; padding:14px 18px; border-bottom:1px solid var(--line); }
.card-h h3 { margin:0; font-size:13.5px; font-weight:600; letter-spacing:-.005em; color:var(--ink); }
.card-h .meta { color:var(--ink-4); font-size:12px; }
.kpi-strip { display:grid; grid-template-columns:repeat(4,1fr); gap:var(--d-gap); margin-bottom:var(--d-gap); }
.kpi { background:var(--bg); border:1px solid var(--line); border-radius:var(--radius-lg); padding:16px 18px 18px; position:relative; overflow:hidden; }
.kpi-label { font-size:12px; color:var(--ink-3); display:flex; align-items:center; gap:6px; }
.kpi-value { font-size:28px; font-weight:600; letter-spacing:-.025em; margin-top:6px; font-variant-numeric:tabular-nums; color:var(--ink); }
.kpi-sub   { font-size:12px; color:var(--ink-4); margin-top:2px; }
.kpi-delta { display:inline-flex; align-items:center; gap:3px; font-size:11.5px; padding:2px 6px; border-radius:4px; margin-left:8px; vertical-align:3px; font-variant-numeric:tabular-nums; }
.kpi-delta.up   { color:var(--ok);   background:var(--ok-soft); }
.kpi-delta.down { color:var(--bad);  background:var(--bad-soft); }
.badge { display:inline-flex; align-items:center; gap:5px; padding:2px 8px; border-radius:999px; font-size:11.5px; font-weight:500; line-height:1.5; white-space:nowrap; }
.badge .dot { width:6px; height:6px; border-radius:50%; background:currentColor; flex:0 0 auto; }
.b-ok     { color:var(--ok);         background:var(--ok-soft); }
.b-warn   { color:var(--warn-text);  background:var(--warn-soft); }
.b-bad    { color:var(--bad);        background:var(--bad-soft); }
.b-info   { color:var(--info);       background:var(--info-soft); }
.b-mute   { color:var(--ink-3);      background:var(--bg-sunken); }
.b-accent { color:var(--accent-ink); background:var(--accent-soft); }
.risk-bar { display:inline-grid; grid-template-columns:repeat(5,4px); gap:2px; vertical-align:middle; margin-right:6px; }
.risk-bar i { height:10px; border-radius:1px; background:var(--bg-active); display:block; }
.risk-bar.r-1 i:nth-child(-n+1),.risk-bar.r-2 i:nth-child(-n+2),.risk-bar.r-3 i:nth-child(-n+3),.risk-bar.r-4 i:nth-child(-n+4),.risk-bar.r-5 i:nth-child(-n+5) { background:currentColor; }
.risk-low    { color:var(--ok); }
.risk-medium { color:var(--risk-med); }
.risk-high   { color:var(--bad); }
.tbl { width:100%; border-collapse:collapse; }
.tbl thead th { text-align:left; font-weight:500; font-size:11.5px; color:var(--ink-4); text-transform:uppercase; letter-spacing:.06em; padding:10px 14px; border-bottom:1px solid var(--line); background:var(--bg-elev); position:sticky; top:0; z-index:1; }
.tbl tbody td { padding:0 14px; height:var(--d-row); border-bottom:1px solid var(--line); font-size:var(--d-text); vertical-align:middle; color:var(--ink); }
.tbl tbody tr:last-child td { border-bottom:0; }
.tbl tbody tr { cursor:pointer; transition:background .12s; }
.tbl tbody tr:hover { background:var(--bg-hover); }
.tbl tbody tr[data-selected="true"] { background:var(--accent-soft); }
.cell-id { font-family:var(--font-mono); color:var(--ink-3); font-size:12px; }
.cell-client { display:flex; align-items:center; gap:10px; }
.cell-client .ini { width:28px; height:28px; border-radius:50%; background:var(--bg-active); color:var(--ink-2); display:grid; place-items:center; font-size:11px; font-weight:600; letter-spacing:0; flex:0 0 auto; }
.cell-client b { font-weight:500; display:block; line-height:1.2; }
.cell-client small { color:var(--ink-4); font-size:11.5px; }
.cell-num { font-variant-numeric:tabular-nums; font-family:var(--font-mono); }
.sla { display:inline-flex; align-items:center; gap:6px; font-variant-numeric:tabular-nums; font-size:12.5px; }
.sla.ok   { color:var(--ok); }
.sla.warn { color:var(--risk-med); }
.sla.bad  { color:var(--bad); }
.chips { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.chip { display:inline-flex; align-items:center; gap:6px; height:28px; padding:0 10px; border:1px solid var(--line); border-radius:999px; background:var(--bg); color:var(--ink-2); font-size:12.5px; transition:background .1s,border-color .1s,color .1s; }
.chip:hover { background:var(--bg-hover); }
.chip[data-active="true"] { border-color:var(--ink); background:var(--ink); color:var(--bg); }
.search { display:flex; align-items:center; gap:8px; background:var(--bg-sunken); border:1px solid var(--line); border-radius:8px; padding:0 12px; height:34px; color:var(--ink-3); transition:border-color .15s,box-shadow .15s; }
.search:focus-within { border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); color:var(--ink); }
.search input { background:none; border:0; outline:0; flex:1; font-size:13.5px; min-width:0; }
.flag-row { display:flex; align-items:center; justify-content:space-between; padding:10px 14px; border-top:1px solid var(--line); transition:background .12s; }
.flag-row:first-child { border-top:0; }
.flag-row:hover { background:var(--bg-hover); }
.flag-row .left { display:flex; align-items:center; gap:12px; min-width:0; flex:1; }
.flag-row .ico { width:28px; height:28px; border-radius:7px; background:var(--bg-sunken); display:grid; place-items:center; flex:0 0 auto; font-size:13px; color:var(--ink-4); }
.flag-row .ico.bad  { background:var(--bad-soft);  color:var(--bad); }
.flag-row .ico.warn { background:var(--warn-soft); color:var(--warn-text); }
.flag-row .ico.info { background:var(--info-soft); color:var(--info); }
.flag-row .ico.ok   { background:var(--ok-soft);   color:var(--ok); }
.flag-row .t { font-size:13px; font-weight:500; color:var(--ink); }
.flag-row .s { font-size:12px; color:var(--ink-3); }
.tabs-priority { display:flex; align-items:stretch; gap:8px; padding-bottom:0; border-bottom:1px solid var(--line); margin-bottom:var(--d-gap); }
.tabs-priority .tab-primary { display:inline-flex; align-items:center; gap:8px; padding:10px 14px 10px 12px; background:var(--ink); color:var(--bg); border:1px solid var(--ink); border-radius:var(--radius) var(--radius) 0 0; font-size:13.5px; font-weight:600; cursor:pointer; margin-bottom:-1px; box-shadow:var(--shadow-sm); }
.tabs-priority .tab-primary:hover { opacity:.9; }
.tabs-priority .tab-pill { margin-left:4px; background:rgba(255,255,255,.18); color:var(--bg); font-size:11px; font-weight:500; padding:2px 8px; border-radius:999px; }
.tabs-priority .tabs-divider { width:1px; background:var(--line); margin:6px 6px 0; }
.tabs-priority .tab-secondary { padding:10px; background:transparent; border:0; border-bottom:2px solid transparent; color:var(--ink-4); font-size:12.5px; font-weight:500; cursor:pointer; margin-bottom:-1px; }
.tabs-priority .tab-secondary:hover { color:var(--ink-2); }
.tabs-priority .tab-secondary[aria-current="true"] { color:var(--ink); border-color:var(--ink); }
.approval { border:1px solid var(--line); border-radius:var(--radius-lg); background:var(--bg); padding:16px; display:flex; flex-direction:column; gap:12px; box-shadow:var(--shadow-sm); }
.approval h4 { margin:0; font-size:13px; font-weight:600; }
.approval .grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.approval textarea { width:100%; border:1px solid var(--line); background:var(--bg-sunken); border-radius:8px; padding:10px 12px; resize:vertical; font-size:13px; min-height:70px; outline:0; transition:border-color .15s,box-shadow .15s; color:var(--ink); }
.approval textarea:focus { border-color:var(--accent); background:var(--bg); box-shadow:0 0 0 3px var(--accent-soft); }
.btn { display:inline-flex; align-items:center; justify-content:center; gap:6px; height:36px; padding:0 14px; border-radius:8px; font-size:13.5px; font-weight:500; border:1px solid var(--line); background:var(--bg); color:var(--ink); transition:background .12s,border-color .12s; cursor:pointer; }
.btn:hover { background:var(--bg-hover); }
.btn:disabled { opacity:.4; cursor:not-allowed; }
.btn.primary { background:var(--ink); color:var(--bg); border-color:var(--ink); }
.btn.primary:hover { background:var(--ink-2); }
.btn.danger  { color:var(--bad); border-color:var(--bad-soft); background:var(--bad-soft); }
.btn.danger:hover { background:#fce4e4; }
.btn.success { color:var(--ok); border-color:var(--ok-soft); background:var(--ok-soft); }
.btn.success:hover { background:#d8f5e1; }
.btn.ghost { background:transparent; border-color:transparent; }
.btn.ghost:hover { background:var(--bg-hover); }
.btn.full  { width:100%; }
.approver { display:flex; align-items:center; gap:10px; padding:10px; border:1px dashed var(--line); border-radius:8px; font-size:12.5px; }
.approver.signed { border-style:solid; background:var(--ok-soft); border-color:transparent; }
.avatar { width:30px; height:30px; border-radius:50%; background:linear-gradient(135deg,#7b8fff,#5a6fee); display:grid; place-items:center; color:white; font-size:11px; font-weight:600; flex:0 0 auto; }
.detail-grid { display:grid; grid-template-columns:minmax(0,1fr) 320px; gap:var(--d-gap); }
::-webkit-scrollbar { width:8px; height:8px; }
::-webkit-scrollbar-thumb { background:var(--line-strong); border-radius:999px; border:2px solid var(--bg-sunken); }
::-webkit-scrollbar-track { background:transparent; }
/* Toolbar */
.toolbar { display:flex; align-items:center; gap:10px; padding:10px 20px; background:var(--bg); border-bottom:1px solid var(--line); box-shadow:var(--shadow-sm); position:sticky; top:0; z-index:10; }
.toolbar select { height:34px; padding:0 10px; border:1px solid var(--line-strong); border-radius:8px; background:var(--bg-sunken); color:var(--ink); font-size:13px; outline:0; min-width:160px; }
.toolbar select:focus { border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); }
.toolbar .sync-note { margin-left:auto; font-size:12px; color:var(--ink-4); }
/* Drop zone */
.drop-zone { border:2px dashed var(--line-strong); border-radius:var(--radius-lg); padding:40px 24px; text-align:center; background:var(--bg-elev); transition:border-color .15s,background .15s; cursor:pointer; }
.drop-zone.over { border-color:var(--accent); background:var(--accent-soft); }
.drop-zone .drop-icon { font-size:32px; margin-bottom:10px; color:var(--ink-4); }
.drop-zone .drop-label { font-size:14px; font-weight:500; color:var(--ink); margin-bottom:4px; }
.drop-zone .drop-sub { font-size:12.5px; color:var(--ink-4); margin-bottom:16px; }
/* Upload row */
.upload-row { display:flex; align-items:center; justify-content:space-between; padding:10px 14px; border-top:1px solid var(--line); }
.upload-row .fname { font-size:13px; font-weight:500; color:var(--ink); max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.upload-row .fmeta { font-size:11.5px; color:var(--ink-4); margin-top:2px; }
/* Empty state */
.empty-state { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:80px 24px; text-align:center; color:var(--ink-4); }
.empty-state .es-icon { font-size:40px; margin-bottom:14px; }
.empty-state .es-title { font-size:15px; font-weight:600; color:var(--ink); margin-bottom:6px; }
.empty-state .es-sub { font-size:13px; max-width:320px; line-height:1.5; }
"""

    react_code = r"""
const { useState, useMemo, useCallback } = React;
const INIT = window.__INITIAL_DATA__;
const SIDECAR = INIT.sidecarUrl || "http://127.0.0.1:8000";

function Icon({ name, size = 14, color = "currentColor" }) {
  const s = { width: size, height: size };
  const p = { fill: "none", stroke: color, strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", ...s };
  if (name === "check")    return <svg {...p} viewBox="0 0 16 16"><polyline points="2,8 6,12 14,4"/></svg>;
  if (name === "flag")     return <svg {...p} viewBox="0 0 16 16"><path d="M3 2v12M3 2h8l-2 4 2 4H3"/></svg>;
  if (name === "x")        return <svg {...p} viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>;
  if (name === "file")     return <svg {...p} viewBox="0 0 16 16"><path d="M4 2h5l3 3v9H4z"/><path d="M9 2v3h3"/><line x1="6" y1="8" x2="10" y2="8"/><line x1="6" y1="11" x2="10" y2="11"/></svg>;
  if (name === "chevronL") return <svg {...p} viewBox="0 0 16 16"><polyline points="10,3 5,8 10,13"/></svg>;
  if (name === "upload")   return <svg {...p} viewBox="0 0 16 16"><polyline points="8,11 8,3"/><polyline points="4,7 8,3 12,7"/><line x1="3" y1="13" x2="13" y2="13"/></svg>;
  if (name === "search")   return <svg {...p} viewBox="0 0 16 16"><circle cx="7" cy="7" r="4"/><line x1="10.5" y1="10.5" x2="14" y2="14"/></svg>;
  if (name === "escalate") return <svg {...p} viewBox="0 0 16 16"><polyline points="8,12 8,4"/><polyline points="4,8 8,4 12,8"/></svg>;
  return <span style={{fontSize:size}}>{name}</span>;
}

function RiskBar({ risk, score }) {
  const n = { low: 1, medium: 3, high: 5 }[risk] || 1;
  const cls = risk === "low" ? "risk-low" : risk === "medium" ? "risk-medium" : "risk-high";
  return (
    <span className="row-flex gap-sm">
      <span className={`risk-bar r-${n} ${cls}`}><i/><i/><i/><i/><i/></span>
      <span className="tnum" style={{fontSize:12.5,color:"var(--ink-4)"}}>{score}</span>
    </span>
  );
}

function KpiStrip({ kpis, cols = 4 }) {
  const cards = [
    { label:"Open cases",      value: kpis.total,          sub:"in current queue run" },
    { label:"Pass rate",       value: kpis.passRate + "%", sub:`${kpis.passCount} customers cleared` },
    { label:"Require review",  value: kpis.reviewCount,    sub:"REJECT or REVIEW disposition",
      delta: kpis.failCount > 0 ? { cls:"down", text:`${kpis.failCount} hard fail` } : null },
    { label:"Avg. confidence", value: kpis.avgScore,       sub:"out of 100" },
  ];
  return (
    <div className="kpi-strip" style={{gridTemplateColumns:`repeat(${cols},1fr)`}}>
      {cards.map((c, i) => (
        <div className="kpi" key={i}>
          <div className="kpi-label">{c.label}</div>
          <div className="kpi-value">
            {c.value}
            {c.delta && <span className={`kpi-delta ${c.delta.cls}`}>{c.delta.text}</span>}
          </div>
          <div className="kpi-sub">{c.sub}</div>
        </div>
      ))}
    </div>
  );
}

function Toolbar({ institutions, onRun, onUpload, loading, runAt }) {
  const [selInst, setSelInst] = useState(institutions[0]?.id || "");
  return (
    <div className="toolbar">
      <select value={selInst} onChange={e => setSelInst(e.target.value)}>
        <option value="">All institutions</option>
        {institutions.map(i => <option key={i.id} value={i.id}>{i.label}</option>)}
      </select>
      <button className="btn primary" onClick={() => onRun(selInst)} disabled={loading}>
        {loading ? "Running…" : "Run queue"}
      </button>
      <button className="btn ghost" onClick={onUpload} style={{gap:6}}>
        <Icon name="upload" size={13}/> Batch upload
      </button>
      {runAt && <span className="sync-note">Last sync {runAt}</span>}
    </div>
  );
}

function CasePanel({ c, onBack }) {
  const [tab, setTab]           = useState("reconcile");
  const [signoffA, setSignoffA] = useState(false);
  const [signoffB, setSignoffB] = useState(false);
  const [note, setNote]         = useState("");
  const [decision, setDecision] = useState(null);

  if (!c) return null;

  const badgeCls   = c.status==="Escalated" ? "b-bad" : c.status==="Dual-approval" ? "b-accent" : c.status==="Cleared" ? "b-ok" : c.status==="Awaiting docs" ? "b-warn" : "b-mute";
  const totalFlags = c.rejectRules.length + c.reviewRules.length;

  return (
    <div>
      <div className="page-h" style={{marginBottom:12}}>
        <div>
          <div className="row-flex" style={{marginBottom:6}}>
            <button className="btn ghost" onClick={onBack} style={{height:28,padding:"0 8px",gap:4}}>
              <Icon name="chevronL" size={12}/> Back
            </button>
            <span className="cell-id mono">{c.id}</span>
          </div>
          <h1 className="page-title" style={{fontSize:18,marginBottom:2}}>{c.client}</h1>
          <div className="page-sub">{c.tier} · {c.type} · {c.jurisdiction} · RM {(c.rm||"").split(" — ")[1]||(c.rm||"")}</div>
        </div>
        <div><span className={`badge ${badgeCls}`}><span className="dot"/>{c.status}</span></div>
      </div>

      <div className="kpi-strip" style={{gridTemplateColumns:"repeat(3,1fr)",marginBottom:12}}>
        <div className="kpi">
          <div className="kpi-label">Risk score</div>
          <div className="kpi-value">{c.riskScore}<span className="muted" style={{fontSize:14,marginLeft:4}}>/100</span></div>
          <div className="kpi-sub" style={{marginTop:6}}><RiskBar risk={c.risk} score={c.risk.toUpperCase()}/></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Entity type</div>
          <div className="kpi-value" style={{fontSize:16,paddingTop:6}}>{c.type}</div>
          <div className="kpi-sub">{c.jurisdiction}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Open flags</div>
          <div className="kpi-value">{totalFlags}</div>
          <div className="kpi-sub" style={{whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>
            {totalFlags > 0 ? (c.rejectRules[0]||c.reviewRules[0]).name : "No flags"}
          </div>
        </div>
      </div>

      <div className="tabs-priority">
        <button className="tab-primary" aria-current={tab==="reconcile"} onClick={()=>setTab("reconcile")}>
          <Icon name="check" size={13}/> Reconcile &amp; status
          {totalFlags > 0 && <span className="tab-pill">{totalFlags} to review</span>}
        </button>
        <span className="tabs-divider"/>
        <button className="tab-secondary" aria-current={tab==="overview"} onClick={()=>setTab("overview")}>Overview</button>
        <button className="tab-secondary" aria-current={tab==="documents"} onClick={()=>setTab("documents")}>Documents</button>
      </div>

      <div className="detail-grid">
        <div>
          {tab==="overview" && (
            <div className="card">
              <div className="card-h"><h3>KYC dimensions</h3><span className="meta">click to drill in</span></div>
              {c.dimensions.map((d,i) => (
                <div className="flag-row" key={d.key} style={{borderTop:i?"1px solid var(--line)":"0"}}>
                  <div className="left">
                    <div className={`ico ${d.tone==="ok"?"ok":d.tone==="bad"?"bad":"warn"}`}>
                      <Icon name={d.tone==="ok"?"check":"flag"}/>
                    </div>
                    <div><div className="t">{d.title}</div><div className="s">{d.sub}</div></div>
                  </div>
                  <span className={`badge ${d.tone==="ok"?"b-ok":d.tone==="bad"?"b-bad":"b-warn"}`}>
                    <span className="dot"/>{d.tone==="ok"?"Pass":d.tone==="bad"?"Fail":"Attention"} · {d.score}
                  </span>
                </div>
              ))}
              {c.dimensions.length===0 && <div style={{padding:"24px 16px",color:"var(--ink-4)",fontSize:13}}>No dimension scores available</div>}
            </div>
          )}
          {tab==="documents" && (
            <div className="card">
              <div className="card-h"><h3>Documents</h3><span className="meta">on file</span></div>
              {[
                {n:"Identity document",s:"On file"},{n:"Proof of address",s:"On file"},{n:"Source of wealth documentation",s:"On file"},
              ].map((d,i) => (
                <div className="flag-row" key={i} style={{borderTop:i?"1px solid var(--line)":"0"}}>
                  <div className="left"><div className="ico"><Icon name="file"/></div><div><div className="t">{d.n}</div></div></div>
                  <span className="badge b-ok"><span className="dot"/>{d.s}</span>
                </div>
              ))}
            </div>
          )}
          {tab==="reconcile" && (
            <>
              {totalFlags > 0 && (
                <div className="card">
                  <div className="card-h"><h3>What needs attention</h3><span className="meta">{totalFlags} triggered</span></div>
                  {c.rejectRules.map((r,i) => (
                    <div className="flag-row" key={"rej"+i}>
                      <div className="left"><div className="ico bad"><Icon name="x"/></div><div><div className="t">{r.name}</div><div className="s">{r.desc}</div></div></div>
                      <span className="badge b-bad"><span className="dot"/>Hard Reject</span>
                    </div>
                  ))}
                  {c.reviewRules.map((r,i) => (
                    <div className="flag-row" key={"rev"+i}>
                      <div className="left"><div className="ico warn"><Icon name="flag"/></div><div><div className="t">{r.name}</div><div className="s">{r.desc}</div></div></div>
                      <span className="badge b-warn"><span className="dot"/>Review</span>
                    </div>
                  ))}
                </div>
              )}
              {c.rationale && (
                <div className="card">
                  <div className="card-h"><h3>Decision rationale</h3></div>
                  <div style={{padding:"12px 16px",fontSize:13,color:"var(--ink-3)",lineHeight:1.6}}>{c.rationale}</div>
                </div>
              )}
              <div className="approval">
                <h4>Dual-approval workflow</h4>
                {decision && (
                  <div className={`badge ${decision==="approved"?"b-ok":decision==="rejected"?"b-bad":"b-warn"}`} style={{alignSelf:"flex-start"}}>
                    <span className="dot"/>{decision==="approved"?"Approved":decision==="rejected"?"Rejected":"Escalated"}
                  </div>
                )}
                <div className="grid">
                  <div className={`approver ${signoffA?"signed":""}`}>
                    <div className="avatar">1A</div>
                    <div style={{flex:1}}>
                      <div style={{fontWeight:500,fontSize:12.5}}>{signoffA?"✓ Signed":"Pending sign-off"}</div>
                      <div style={{fontSize:11.5,color:"var(--ink-4)"}}>Relationship Manager</div>
                    </div>
                    {!signoffA && <button className="btn" style={{height:28,padding:"0 10px",fontSize:12.5}} onClick={()=>setSignoffA(true)}>Sign</button>}
                  </div>
                  <div className={`approver ${signoffB?"signed":""}`}>
                    <div className="avatar">2B</div>
                    <div style={{flex:1}}>
                      <div style={{fontWeight:500,fontSize:12.5}}>{signoffB?"✓ Signed":"Pending sign-off"}</div>
                      <div style={{fontSize:11.5,color:"var(--ink-4)"}}>Compliance Officer</div>
                    </div>
                    {!signoffB && <button className="btn" style={{height:28,padding:"0 10px",fontSize:12.5}} onClick={()=>setSignoffB(true)}>Sign</button>}
                  </div>
                </div>
                <textarea placeholder="Decision note…" value={note} onChange={e=>setNote(e.target.value)}/>
                <div className="grid">
                  <button className="btn success full" disabled={!signoffA||!signoffB} onClick={()=>setDecision("approved")}>Approve</button>
                  <button className="btn danger full" onClick={()=>setDecision("rejected")}>Reject</button>
                </div>
                <button className="btn ghost full" style={{borderColor:"var(--line)"}} onClick={()=>setDecision("escalated")}>
                  <Icon name="escalate" size={13}/> Escalate for review
                </button>
              </div>
            </>
          )}
        </div>
        <div/>
      </div>
    </div>
  );
}

function WorklistView({ data, onOpenCase }) {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");

  const cases = useMemo(() => {
    let list = data.cases || [];
    if (filter === "review") list = list.filter(c => c.status==="Pending review"||c.status==="Dual-approval");
    if (filter === "high")   list = list.filter(c => c.risk==="high");
    if (filter === "pass")   list = list.filter(c => c.status==="Cleared");
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(c => c.client.toLowerCase().includes(q) || c.id.toLowerCase().includes(q));
    }
    return list;
  }, [filter, search, data]);

  const chips = [{v:"all",l:"All"},{v:"review",l:"Needs review"},{v:"high",l:"High risk"},{v:"pass",l:"Cleared"}];

  return (
    <>
      <div className="page-h" style={{marginBottom:16}}>
        <div>
          <div className="eyebrow">Worklist</div>
          <h1 className="page-title">KYC case queue</h1>
          <div className="page-sub">High Net Worth Individuals · {data.runAt}</div>
        </div>
      </div>
      <KpiStrip kpis={data.kpis}/>
      <div className="section-h" style={{marginTop:8}}>
        <h3>Active queue</h3>
        <div style={{display:"flex",alignItems:"center",gap:12}}>
          <div className="chips">
            {chips.map(c => (
              <button key={c.v} className="chip" data-active={filter===c.v} onClick={()=>setFilter(c.v)}>{c.l}</button>
            ))}
          </div>
          <div className="search" style={{width:220}}>
            <Icon name="search"/>
            <input placeholder="Search clients, IDs…" value={search} onChange={e=>setSearch(e.target.value)}/>
          </div>
        </div>
      </div>
      <div className="card">
        <div style={{overflowX:"auto"}}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Client</th><th style={{width:140}}>Risk</th><th>Action needed</th><th style={{width:120}}>Due</th>
              </tr>
            </thead>
            <tbody>
              {cases.map(c => {
                const bc = c.status==="Escalated"?"b-bad":c.status==="Dual-approval"?"b-accent":c.status==="Cleared"?"b-ok":c.status==="Awaiting docs"?"b-warn":"b-mute";
                return (
                  <tr key={c.id} onClick={()=>onOpenCase(c)}>
                    <td>
                      <div className="cell-client">
                        <div className="ini">{c.ini}</div>
                        <div><b>{c.client}</b><small>{c.tier} · {c.jurisdiction}</small></div>
                      </div>
                    </td>
                    <td><RiskBar risk={c.risk} score={c.riskScore}/></td>
                    <td><span className={`badge ${bc}`}><span className="dot"/>{c.status}</span></td>
                    <td><span className={`sla ${c.sla.tone}`}>{c.sla.label}</span></td>
                  </tr>
                );
              })}
              {cases.length===0 && (
                <tr><td colSpan={4} style={{textAlign:"center",padding:"32px 0",color:"var(--ink-4)"}}>No cases match the current filter</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function BatchUploadView({ onBack }) {
  const [files, setFiles]       = useState([]);
  const [dsType, setDsType]     = useState("customers");
  const [results, setResults]   = useState([]);
  const [loading, setLoading]   = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const addFiles = useCallback(newFiles => {
    setFiles(prev => [...prev, ...Array.from(newFiles)]);
  }, []);

  const handleDrop = e => {
    e.preventDefault(); setDragOver(false);
    addFiles(e.dataTransfer.files);
  };

  const handleProcess = async () => {
    if (files.length === 0) return;
    setLoading(true); setResults([]);
    const form = new FormData();
    form.append("dataset_type", dsType);
    files.forEach(f => form.append("files", f));
    try {
      const res  = await fetch(SIDECAR + "/api/upload-docs", { method: "POST", body: form });
      const json = await res.json();
      setResults(json.results || []);
    } catch {
      setResults(files.map(f => ({ filename: f.name, status: "error", error: "Sidecar unreachable" })));
    }
    setLoading(false);
  };

  const dsOptions = [
    {v:"customers",l:"Customers"},{v:"screenings",l:"Screenings"},
    {v:"id_verifications",l:"ID Verifications"},{v:"transactions",l:"Transactions"},{v:"documents",l:"Documents"},
  ];

  return (
    <div>
      <div className="page-h" style={{marginBottom:16}}>
        <div>
          <div className="eyebrow">Documents</div>
          <h1 className="page-title">Batch document upload</h1>
          <div className="page-sub">Upload KYC documents for OCR extraction and structured processing</div>
        </div>
        <button className="btn ghost" onClick={onBack} style={{height:32,gap:4}}>
          <Icon name="chevronL" size={12}/> Back to queue
        </button>
      </div>
      <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:16}}>
        <span style={{fontSize:13,color:"var(--ink-3)"}}>Document type:</span>
        <select value={dsType} onChange={e=>setDsType(e.target.value)}
          style={{height:32,padding:"0 10px",border:"1px solid var(--line-strong)",borderRadius:8,background:"var(--bg-sunken)",fontSize:13,outline:0}}>
          {dsOptions.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
      </div>
      <div className={`drop-zone${dragOver?" over":""}`}
        onDragOver={e=>{e.preventDefault();setDragOver(true);}}
        onDragLeave={()=>setDragOver(false)} onDrop={handleDrop}>
        <div className="drop-icon">↑</div>
        <div className="drop-label">Drop files here to upload</div>
        <div className="drop-sub">PDF, images (PNG/JPG), CSV, Excel, JSON — all accepted</div>
        <label className="btn primary" style={{cursor:"pointer"}}>
          Browse files
          <input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.csv,.xlsx,.xls,.json,.jsonl"
            onChange={e=>addFiles(e.target.files)} style={{display:"none"}}/>
        </label>
      </div>
      {files.length > 0 && (
        <div className="card" style={{marginTop:14}}>
          <div className="card-h">
            <h3>{files.length} file{files.length>1?"s":""} selected</h3>
            {results.length===0 && <span className="meta">Ready to process</span>}
            {results.length>0 && <span className="meta" style={{color:"var(--ok)"}}>{results.filter(r=>r.status==="ok").length} processed · {results.filter(r=>r.status==="error").length} failed</span>}
          </div>
          {files.map((f,i) => {
            const res = results[i];
            return (
              <div className="upload-row" key={i}>
                <div style={{display:"flex",alignItems:"center",gap:10,minWidth:0,flex:1}}>
                  <div className="ico"><Icon name="file" size={13}/></div>
                  <div style={{minWidth:0}}>
                    <div className="fname">{f.name}</div>
                    <div className="fmeta">{(f.size/1024).toFixed(1)} KB</div>
                  </div>
                </div>
                {loading && !res && <span className="badge b-mute"><span className="dot"/>Processing…</span>}
                {res && res.status==="ok"   && <span className="badge b-ok"><span className="dot"/>{res.rows} rows</span>}
                {res && res.status==="error" && <span className="badge b-bad" title={res.error}><span className="dot"/>Error</span>}
              </div>
            );
          })}
          <div style={{padding:"12px 14px",borderTop:"1px solid var(--line)",display:"flex",alignItems:"center",gap:12}}>
            <button className="btn primary" onClick={handleProcess} disabled={loading}>
              {loading ? "Processing…" : `Process ${files.length} file${files.length>1?"s":""}`}
            </button>
            <button className="btn ghost" onClick={()=>{setFiles([]);setResults([]);}} disabled={loading}>Clear</button>
            {results.some(r=>r.status==="ok") && (
              <span style={{fontSize:12,color:"var(--ok)"}}>
                ✓ {results.filter(r=>r.status==="ok").length} file{results.filter(r=>r.status==="ok").length>1?"s":""} written to data store
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  const [view, setView]             = useState("worklist");
  const [data, setData]             = useState(
    INIT.cases && INIT.cases.length > 0
      ? { cases: INIT.cases, kpis: INIT.kpis || {}, batchId: INIT.batchId || "", runAt: INIT.runAt || "pre-loaded" }
      : null
  );
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState(null);
  const [activeCase, setActiveCase] = useState(null);

  const runQueue = useCallback(async institutionId => {
    setLoading(true); setError(null);
    try {
      const res  = await fetch(SIDECAR + "/api/run-batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ institution_id: institutionId || null }),
      });
      const json = await res.json();
      if (!json.ok) throw new Error(json.error || "Batch failed");
      setData(json); setView("worklist");
    } catch (err) {
      setError(err.message || "Could not reach KYC backend. Is it running?");
    }
    setLoading(false);
  }, []);

  const openCase = c  => { setActiveCase(c); setView("case"); };
  const goBack   = () => setView("worklist");
  const goUpload = () => setView("upload");

  return (
    <div style={{height:"100vh",background:"var(--bg-sunken)",display:"flex",flexDirection:"column",overflow:"hidden"}}>
      <Toolbar institutions={INIT.institutions||[]} onRun={runQueue} onUpload={goUpload} loading={loading} runAt={data?.runAt||null}/>
      <div style={{flex:1,padding:"20px 24px",overflowY:"auto"}}>
        {error && (
          <div style={{background:"var(--bad-soft)",border:"1px solid var(--bad)",borderRadius:8,padding:"12px 16px",color:"var(--bad)",fontSize:13,marginBottom:16}}>
            {error}
          </div>
        )}
        {view==="upload"   && <BatchUploadView onBack={goBack}/>}
        {view==="worklist" && !data && !loading && (
          <div className="empty-state">
            <div className="es-icon">▶</div>
            <div className="es-title">Queue not yet run</div>
            <div className="es-sub">Select an institution and click <strong>Run queue</strong> to evaluate all customers and populate the dashboard.</div>
          </div>
        )}
        {view==="worklist" && loading && (
          <div className="empty-state">
            <div className="es-icon" style={{animation:"spin 1s linear infinite"}}>⟳</div>
            <div className="es-title">Running KYC batch…</div>
            <div className="es-sub">Evaluating all customers against the active ruleset. This may take a moment.</div>
          </div>
        )}
        {view==="worklist" && data && !loading && <WorklistView data={data} onOpenCase={openCase}/>}
        {view==="case"     && <CasePanel c={activeCase} onBack={goBack}/>}
      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App/>);
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KYC Operations Dashboard</title>
<style>
{css}
@keyframes spin {{ to {{ transform:rotate(360deg); }} }}
</style>
</head>
<body style="margin:0;padding:0;height:100vh;overflow:hidden;">
<div id="root" style="height:100%;display:flex;flex-direction:column;overflow:hidden;"></div>
<script>window.__INITIAL_DATA__ = {data_json};</script>
<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<script type="text/babel" data-presets="react">
{react_code}
</script>
</body>
</html>"""
