"""
kyc_dashboard/admin_html.py
Unified dashboard for both Admin and Banker roles with auth layer.
Single HTML/React builder supporting login, role-based navigation, and three main views:
  - Worklist (Banker + Admin)
  - Approval Queue (Admin only)
  - Audit Trail (Admin only)
"""
from __future__ import annotations

import json
from typing import Any, Dict


def build_unified_dashboard_html(config: Dict[str, Any]) -> str:
    """Return a complete standalone HTML page for the unified KYC dashboard."""
    config_json = json.dumps(config, default=str, ensure_ascii=False)

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
.kpi-strip { display:grid; grid-template-columns:repeat(3,1fr); gap:var(--d-gap); margin-bottom:var(--d-gap); }
.kpi { background:var(--bg); border:1px solid var(--line); border-radius:var(--radius-lg); padding:16px 18px 18px; position:relative; overflow:hidden; }
.kpi-label { font-size:12px; color:var(--ink-3); display:flex; align-items:center; gap:6px; }
.kpi-value { font-size:28px; font-weight:600; letter-spacing:-.025em; margin-top:6px; font-variant-numeric:tabular-nums; color:var(--ink); }
.kpi-sub   { font-size:12px; color:var(--ink-4); margin-top:2px; }
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
.btn.sm { height:32px; padding:0 10px; font-size:12.5px; }
.avatar { width:30px; height:30px; border-radius:50%; background:linear-gradient(135deg,#7b8fff,#5a6fee); display:grid; place-items:center; color:white; font-size:11px; font-weight:600; flex:0 0 auto; }
.login-container { height:100vh; display:flex; align-items:center; justify-content:center; background:var(--bg-sunken); }
.login-card { background:var(--bg); border:1px solid var(--line); border-radius:var(--radius-lg); box-shadow:var(--shadow-md); padding:40px; width:100%; max-width:360px; }
.login-card h1 { font-size:24px; font-weight:600; margin-bottom:8px; color:var(--ink); text-align:center; }
.login-card .subtitle { font-size:13.5px; color:var(--ink-3); text-align:center; margin-bottom:24px; }
.login-field { display:flex; flex-direction:column; gap:6px; margin-bottom:16px; }
.login-field label { font-size:12px; font-weight:500; color:var(--ink-2); }
.login-field input { height:40px; padding:0 12px; border:1px solid var(--line); border-radius:8px; background:var(--bg-sunken); font-size:14px; outline:0; transition:border-color .15s,box-shadow .15s; }
.login-field input:focus { border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); }
.login-error { background:var(--bad-soft); border:1px solid var(--bad); color:var(--bad); padding:10px 12px; border-radius:6px; font-size:12px; margin-bottom:16px; }
.app-layout { display:flex; height:100vh; }
.sidebar { width:240px; background:var(--ink); color:var(--bg); display:flex; flex-direction:column; overflow-y:auto; border-right:1px solid var(--line); }
.sidebar-brand { padding:16px; border-bottom:1px solid rgba(255,255,255,.1); }
.sidebar-brand h2 { font-size:14px; font-weight:600; margin:0 0 4px; }
.sidebar-brand .sub { font-size:11px; opacity:.7; }
.sidebar-nav { flex:1; padding:8px 0; }
.sidebar-nav-item { display:flex; align-items:center; gap:10px; padding:10px 14px; color:var(--bg); font-size:13.5px; cursor:pointer; transition:background .12s; border-left:3px solid transparent; margin:0 6px 0 0; }
.sidebar-nav-item:hover { background:rgba(255,255,255,.1); }
.sidebar-nav-item[data-active="true"] { background:rgba(255,255,255,.15); border-left-color:var(--accent); }
.sidebar-section { padding:8px 0; margin-top:8px; border-top:1px solid rgba(255,255,255,.1); }
.sidebar-section-label { padding:8px 14px; font-size:10px; text-transform:uppercase; letter-spacing:.08em; color:rgba(255,255,255,.5); font-weight:600; }
.sidebar-icon { width:18px; height:18px; flex:0 0 auto; }
.sidebar-foot { padding:12px; border-top:1px solid rgba(255,255,255,.1); display:flex; align-items:center; gap:8px; }
.sidebar-foot .avatar { width:32px; height:32px; flex:0 0 auto; background:linear-gradient(135deg,#ffa644,#ff8844); }
.main-content { flex:1; display:flex; flex-direction:column; overflow:hidden; }
.topbar { display:flex; align-items:center; justify-content:space-between; padding:12px 20px; background:var(--bg); border-bottom:1px solid var(--line); }
.topbar-left { display:flex; align-items:center; gap:16px; }
.topbar-title { font-size:15px; font-weight:600; color:var(--ink); }
.topbar-role { display:inline-flex; align-items:center; gap:6px; padding:4px 10px; background:var(--accent-soft); color:var(--accent-ink); border-radius:6px; font-size:11px; font-weight:500; }
.topbar-right { display:flex; align-items:center; gap:12px; }
.content-wrapper { flex:1; padding:20px 24px; overflow-y:auto; background:var(--bg-sunken); }
.empty-state { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:80px 24px; text-align:center; color:var(--ink-4); }
.empty-state .es-icon { font-size:40px; margin-bottom:14px; }
.empty-state .es-title { font-size:15px; font-weight:600; color:var(--ink); margin-bottom:6px; }
.empty-state .es-sub { font-size:13px; max-width:320px; line-height:1.5; }
.filter-bar { display:flex; align-items:center; gap:12px; margin-bottom:16px; background:var(--bg); padding:12px 16px; border-radius:8px; border:1px solid var(--line); }
.filter-bar select { height:32px; padding:0 10px; border:1px solid var(--line); border-radius:6px; background:var(--bg-sunken); font-size:12.5px; outline:0; min-width:140px; }
.filter-bar select:focus { border-color:var(--accent); }
.pagination { display:flex; align-items:center; justify-content:space-between; padding:12px 16px; border-top:1px solid var(--line); font-size:12px; color:var(--ink-3); }
.pagination-nav { display:flex; gap:4px; }
.pagination-nav button { height:28px; padding:0 8px; border:1px solid var(--line); border-radius:4px; background:var(--bg); cursor:pointer; transition:background .12s; font-size:12px; }
.pagination-nav button:hover { background:var(--bg-hover); }
.pagination-nav button:disabled { opacity:.4; cursor:not-allowed; }
::-webkit-scrollbar { width:8px; height:8px; }
::-webkit-scrollbar-thumb { background:var(--line-strong); border-radius:999px; border:2px solid var(--bg-sunken); }
::-webkit-scrollbar-track { background:transparent; }
@keyframes spin { to { transform:rotate(360deg); } }
"""

    react_code = r"""
const { useState, useEffect, useMemo, useCallback } = React;
const CONFIG = window.__CONFIG__;
const API = CONFIG.apiUrl || "http://127.0.0.1:8000";
function Icon({ name, size = 16, color = "currentColor" }) {
  const icons = {
    inbox:    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2}><polyline points="22 12 18 12 15 21 9 21 6 12 2 12"/><path d="M6 12L2 6h20l-4 6"/></svg>,
    check:    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2}><polyline points="20 6 9 17 4 12"/></svg>,
    x:        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
    info:     <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2}><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>,
    flag:     <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2}><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1"/></svg>,
    logout:   <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>,
  };
  return icons[name] || <span>{name}</span>;
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
function LoginView({ onLogin }) { const [username, setUsername] = useState("admin"); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  const handleLogin = useCallback(async () => { setError(""); setLoading(true); try { const res = await fetch(API + "/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }), }); if (!res.ok) throw new Error("Invalid credentials"); const json = await res.json(); if (typeof window !== "undefined" && window.localStorage) { localStorage.setItem("auth_token", json.token); localStorage.setItem("auth_role", json.role); } onLogin(json.token, json.role);} catch (err) { setError(err.message || "Login failed"); } setLoading(false); }, [username, password, onLogin]);
  const handleKeyPress = (e) => { if (e.key === "Enter") handleLogin(); };
  return (<div className="login-container"><div className="login-card"><h1>Atlas KYC</h1><div className="subtitle">Unified compliance dashboard</div>{error && <div className="login-error">{error}</div>}<div className="login-field"><label>Username</label><input type="text" value={username} onChange={e => setUsername(e.target.value)} onKeyPress={handleKeyPress} disabled={loading} placeholder="admin or banker"/></div><div className="login-field"><label>Password</label><input type="password" value={password} onChange={e => setPassword(e.target.value)} onKeyPress={handleKeyPress} disabled={loading} placeholder="Enter password"/></div><button className="btn primary" style={{width:"100%"}} onClick={handleLogin} disabled={loading}>{loading ? "Logging in…" : "Sign in"}</button><div style={{marginTop:16,fontSize:12,color:"var(--ink-4)",textAlign:"center"}}>Demo users: admin/admin123, banker/banker123</div></div></div>);
}
function WorklistView({ token, cases, role }) { const [filter, setFilter] = useState("all"); const [search, setSearch] = useState(""); const [actions, setActions] = useState({});
  const filtered = useMemo(() => { let list = cases || []; if (filter === "pending") list = list.filter(c => c.status === "Dual-approval" || c.status === "Pending review"); if (filter === "approved") list = list.filter(c => c.status === "Cleared"); if (filter === "rejected") list = list.filter(c => c.status === "Escalated"); if (search) { const q = search.toLowerCase(); list = list.filter(c => c.client.toLowerCase().includes(q) || c.id.toLowerCase().includes(q)); } return list; }, [cases, filter, search]);
  const handleAction = useCallback((caseId, action) => { setActions(prev => ({ ...prev, [caseId]: action })); setTimeout(() => setActions(prev => ({ ...prev, [caseId]: null })), 2000); }, []);
  const totalCustomers = cases?.length || 0; const flaggedCount = cases?.filter(c => c.status !== "Cleared").length || 0; const approvalRate = totalCustomers > 0 ? Math.round(100 * (totalCustomers - flaggedCount) / totalCustomers) : 0;
  return (<><div className="page-h"><div><div className="eyebrow">Compliance</div><h1 className="page-title">KYC Worklist</h1><div className="page-sub">BFSI Institutions · Case queue</div></div></div><div className="kpi-strip"><div className="kpi"><div className="kpi-label">Total customers</div><div className="kpi-value">{totalCustomers}</div><div className="kpi-sub">in current batch</div></div><div className="kpi"><div className="kpi-label">% Flagged</div><div className="kpi-value">{flaggedCount > 0 ? Math.round(100 * flaggedCount / totalCustomers) : 0}%</div><div className="kpi-sub">{flaggedCount} customers</div></div><div className="kpi"><div className="kpi-label">Approval rate</div><div className="kpi-value">{approvalRate}%</div><div className="kpi-sub">ready to clear</div></div></div><div className="section-h" style={{marginTop:12}}><h3>Active queue</h3><div style={{display:"flex",alignItems:"center",gap:12}}><div className="chips">{[{v:"all",l:"All"},{v:"pending",l:"Pending approval"},{v:"approved",l:"Approved"},{v:"rejected",l:"Rejected"}].map(c => (<button key={c.v} className="chip" data-active={filter===c.v} onClick={()=>setFilter(c.v)}>{c.l}</button>))}</div><div className="search" style={{width:220}}><Icon name="inbox" size={14}/><input placeholder="Search…" value={search} onChange={e=>setSearch(e.target.value)}/></div></div></div><div className="card"><div style={{overflowX:"auto"}}><table className="tbl"><thead><tr><th>Customer ID</th><th>Name</th><th style={{width:120}}>Risk score</th><th style={{width:110}}>Status</th><th style={{width:100}}>Last review</th>{role === "Admin" && <th style={{width:200}}>Actions</th>}</tr></thead><tbody>{filtered.map(c => { const bc = c.status==="Escalated"?"b-bad":c.status==="Dual-approval"?"b-accent":c.status==="Cleared"?"b-ok":"b-warn"; const actionState = actions[c.id]; return (<tr key={c.id}><td className="cell-id">{c.id}</td><td><div className="cell-client"><div className="ini">{c.ini}</div><div><b>{c.client}</b></div></div></td><td><RiskBar risk={c.risk} score={c.riskScore}/></td><td><span className={`badge ${bc}`}><span className="dot"/>{c.status}</span></td><td className="cell-num">{c.lastReview || "—"}</td>{role === "Admin" && (<td>{actionState ? (<span style={{color:"var(--ok)",fontWeight:500,fontSize:12}}>{actionState} ✓</span>) : (<div style={{display:"flex",gap:4}}><button className="btn success sm" onClick={()=>handleAction(c.id,"Approved")}>Approve</button><button className="btn danger sm" onClick={()=>handleAction(c.id,"Rejected")}>Reject</button></div>)}</td>)}</tr>); })}{filtered.length===0 && (<tr><td colSpan={role==="Admin"?6:5} style={{textAlign:"center",padding:"32px 0",color:"var(--ink-4)"}}>No cases match filters</td></tr>)}</tbody></table></div></div></>);
}
function ApprovalQueueView({ cases }) { const [actions, setActions] = useState({}); const approvalCases = useMemo(() => (cases || []).filter(c => c.status === "Dual-approval"), [cases]); const handleSign = useCallback((caseId) => { setActions(prev => ({ ...prev, [caseId]: "Approved" })); setTimeout(() => setActions(prev => ({ ...prev, [caseId]: null })), 2000); }, []); return (<><div className="page-h"><div><div className="eyebrow">Administration</div><h1 className="page-title">Approval Queue</h1><div className="page-sub">Cases awaiting dual signature approval</div></div></div><div className="kpi-strip"><div className="kpi"><div className="kpi-label">Pending approval</div><div className="kpi-value">{approvalCases.length}</div><div className="kpi-sub">awaiting 2nd signature</div></div><div className="kpi"><div className="kpi-label">Avg wait time</div><div className="kpi-value">2.3h</div><div className="kpi-sub">since first approval</div></div><div className="kpi"><div className="kpi-label">SLA compliance</div><div className="kpi-value">94%</div><div className="kpi-sub">within 4h window</div></div></div><div className="card"><div style={{overflowX:"auto"}}><table className="tbl"><thead><tr><th>Customer ID</th><th>Name</th><th style={{width:120}}>Risk score</th><th style={{width:140}}>First approval</th><th style={{width:200}}>Action</th></tr></thead><tbody>{approvalCases.map(c => (<tr key={c.id}><td className="cell-id">{c.id}</td><td><div className="cell-client"><div className="ini">{c.ini}</div><div><b>{c.client}</b></div></div></td><td><RiskBar risk={c.risk} score={c.riskScore}/></td><td style={{fontSize:12,color:"var(--ink-3)"}}>12m ago</td><td>{actions[c.id] === "Approved" ? (<span style={{color:"var(--ok)",fontWeight:500,fontSize:12}}>Approved ✓</span>) : (<button className="btn success sm" onClick={()=>handleSign(c.id)}>Sign & approve</button>)}</td></tr>))}{approvalCases.length===0 && (<tr><td colSpan={5} style={{textAlign:"center",padding:"32px 0",color:"var(--ink-4)"}}>No cases awaiting approval</td></tr>)}</tbody></table></div></div></>); }
function AuditTrailView() { const [page, setPage] = useState(0); const [logs, setLogs] = useState([]); const [loading, setLoading] = useState(true); const [filter, setFilter] = useState("all"); const pageSize = 50; useEffect(() => { const fetchAudit = async () => { setLoading(true); try { const token = localStorage.getItem("auth_token"); const res = await fetch(API + "/api/audit", { headers: { "Authorization": `Bearer ${token}` }, }); if (!res.ok) throw new Error("Failed to fetch audit logs"); const json = await res.json(); setLogs(json.logs || []); } catch (err) { console.error("Audit fetch error:", err); setLogs([]);} setLoading(false); }; fetchAudit(); }, []); const filtered = useMemo(() => { let list = logs; if (filter !== "all") list = list.filter(l => l.role === filter); return list; }, [logs, filter]); const paginated = filtered.slice(page * pageSize, (page + 1) * pageSize); const totalPages = Math.ceil(filtered.length / pageSize); return (<><div className="page-h"><div><div className="eyebrow">Administration</div><h1 className="page-title">Audit trail</h1><div className="page-sub">Immutable log of all system activities and user actions</div></div></div><div className="filter-bar"><span style={{fontSize:12,color:"var(--ink-3)"}}>Filter by:</span><select value={filter} onChange={e => {setFilter(e.target.value); setPage(0);}}><option value="all">All users</option><option value="Admin">Admin</option><option value="Analyst">Analyst</option><option value="Banker">Banker</option></select><div style={{marginLeft:"auto",fontSize:12,color:"var(--ink-4)"}}><b className="tnum">{filtered.length}</b> events ({page+1} of {Math.max(1,totalPages)})</div></div><div className="card">{loading ? (<div style={{padding:"32px",textAlign:"center",color:"var(--ink-4)"}}>Loading audit logs…</div>) : (<><div style={{overflowX:"auto"}}><table className="tbl"><thead><tr><th style={{width:160}}>Timestamp</th><th style={{width:80}}>User</th><th style={{width:80}}>Role</th><th style={{width:140}}>Action</th><th>Description</th><th style={{width:120}}>Customer ID</th></tr></thead><tbody>{paginated.map((log, i) => (<tr key={i}><td className="tnum" style={{fontSize:12}}>{new Date(log.timestamp).toLocaleString()}</td><td style={{fontSize:12}}>{log.user}</td><td><span className="badge b-accent">{log.role}</span></td><td style={{fontSize:12,fontWeight:500}}>{log.action}</td><td style={{fontSize:12,color:"var(--ink-3)"}}>{log.description}</td><td className="cell-id">{log.customer_id || "—"}</td></tr>))}{paginated.length===0 && (<tr><td colSpan={6} style={{textAlign:"center",padding:"32px 0",color:"var(--ink-4)"}}>No audit logs found</td></tr>)}</tbody></table></div>{totalPages > 1 && (<div className="pagination"><span style={{fontSize:12}}>Showing {paginated.length} of {filtered.length} events</span><div className="pagination-nav"><button onClick={() => setPage(0)} disabled={page === 0}>First</button><button onClick={() => setPage(p => Math.max(0,p-1))} disabled={page === 0}>Prev</button><span style={{padding:"0 8px"}}>{page+1}/{totalPages}</span><button onClick={() => setPage(p => Math.min(totalPages-1,p+1))} disabled={page >= totalPages-1}>Next</button><button onClick={() => setPage(totalPages-1)} disabled={page >= totalPages-1}>Last</button></div></div>)}</>)}</div></>); }
function App() { const [isAuthed, setIsAuthed] = useState(false); const [token, setToken] = useState(null); const [role, setRole] = useState(null); const [view, setView] = useState("worklist"); const [cases, setCases] = useState([]); const [loading, setLoading] = useState(false);
  useEffect(() => { if (typeof window !== "undefined" && window.localStorage) { const storedToken = localStorage.getItem("auth_token"); const storedRole = localStorage.getItem("auth_role"); if (storedToken && storedRole) { setToken(storedToken); setRole(storedRole); setIsAuthed(true); loadCases(storedToken);} } }, []);
  const loadCases = useCallback(async (authToken) => { setLoading(true); try { const res = await fetch(API + "/api/kyc/batch", { method: "POST", headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}`, }, body: JSON.stringify({ institution_id: "bank_001" }), }); if (res.ok) { const json = await res.json(); setCases(json.results || []);} } catch (err) { console.error("Failed to load cases:", err);} setLoading(false); }, []);
  const handleLogin = useCallback((newToken, newRole) => { if (typeof window !== "undefined" && window.localStorage) { localStorage.setItem("auth_token", newToken); localStorage.setItem("auth_role", newRole); } setToken(newToken); setRole(newRole); setIsAuthed(true); setView("worklist"); loadCases(newToken); }, [loadCases]);
  const handleLogout = useCallback(async () => { try { await fetch(API + "/api/auth/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }), }); } catch {} if (typeof window !== "undefined" && window.localStorage) { localStorage.removeItem("auth_token"); localStorage.removeItem("auth_role"); } setIsAuthed(false); setToken(null); setRole(null); setCases([]); }, [token]);
  if (!isAuthed) return <LoginView onLogin={handleLogin}/>; const isAdmin = role === "Admin";
  return (<div className="app-layout"><div className="sidebar"><div className="sidebar-brand"><h2>Atlas KYC</h2><div className="sub">Compliance · {role}</div></div><nav className="sidebar-nav"><button className="sidebar-nav-item" data-active={view === "worklist"} onClick={() => setView("worklist")}><Icon name="inbox" size={16}/>Worklist</button>{isAdmin && (<><div className="sidebar-section"><div className="sidebar-section-label">Administration</div><button className="sidebar-nav-item" data-active={view === "approval"} onClick={() => setView("approval")}><Icon name="check" size={16}/>Approval queue</button><button className="sidebar-nav-item" data-active={view === "audit"} onClick={() => setView("audit")}><Icon name="flag" size={16}/>Audit trail</button></div></>)}</nav><div className="sidebar-foot"><div className="avatar">{role === "Admin" ? "AD" : "BA"}</div><div style={{flex:1,minWidth:0}}><div style={{fontSize:12,fontWeight:500,color:"var(--bg)"}}>{role === "Admin" ? "Administrator" : "Banker"}</div><div style={{fontSize:10,color:"rgba(255,255,255,.6)",marginTop:2}}>{role}</div></div><button className="btn ghost" onClick={handleLogout} title="Logout" style={{padding:4,height:28}}><Icon name="logout" size={14} color="var(--bg)"/></button></div></div><div className="main-content"><div className="topbar"><div className="topbar-left"><div className="topbar-title">{view === "worklist" && "KYC Worklist"}{view === "approval" && "Approval Queue"}{view === "audit" && "Audit Trail"}</div></div><div className="topbar-right"><span className="topbar-role"><Icon name="check" size={12}/>{role}</span></div></div><div className="content-wrapper">{loading && view === "worklist" && (<div className="empty-state"><div className="es-icon">⟳</div><div className="es-title">Loading cases…</div></div>)}{!loading && view === "worklist" && <WorklistView token={token} cases={cases} role={role}/>}{view === "approval" && isAdmin && <ApprovalQueueView cases={cases}/>}{view === "audit" && isAdmin && <AuditTrailView/>}</div></div></div>);
}
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App/>);
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Atlas KYC — Unified Compliance Dashboard</title>
<style>
{css}
</style>
</head>
<body style="margin:0;padding:0;height:100vh;overflow:hidden;">
<div id="root" style="height:100%;"></div>
<script>window.__CONFIG__ = {config_json};</script>
<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<script type="text/babel" data-presets="react">
{react_code}
</script>
</body>
</html>"""
