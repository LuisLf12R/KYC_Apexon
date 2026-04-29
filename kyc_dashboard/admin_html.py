"""
kyc_dashboard/admin_html.py
Unified KYC Dashboard — exact replica of Atlas design with auth layer.
Supports both 'admin' and 'banker' roles using your original components.
"""
from __future__ import annotations

import json
from typing import Any, Dict


def build_unified_dashboard_html(config: Dict[str, Any]) -> str:
    """Return complete standalone HTML using exact Atlas design + auth."""
    config_json = json.dumps(config, default=str, ensure_ascii=False)

    # ============================================================
    # CSS: Exact copy from atlas-kyc-dashboard/styles.css
    # ============================================================
    css = r"""
/* ============================================================
   KYC HNWI Dashboard — design tokens
   Modern fintech: clean white, indigo accent, slate neutrals.
   ============================================================ */

:root {
  /* Light theme defaults */
  --bg: #ffffff;
  --bg-elev: #fbfbfc;
  --bg-sunken: #f6f6f8;
  --bg-hover: #f3f3f6;
  --bg-active: #eeeef3;

  --line: #ececf0;
  --line-strong: #d8d8e0;

  --ink: #0e1014;
  --ink-2: #2a2d35;
  --ink-3: #4a4e59;
  --ink-4: #6a6e79;
  --ink-5: #8a8e98;

  --accent: oklch(48% 0.18 265);
  --accent-soft: oklch(96% 0.03 265);
  --accent-ink: oklch(38% 0.16 265);

  --ok:   oklch(48% 0.14 155);
  --ok-soft: oklch(96% 0.04 155);
  --warn: oklch(54% 0.14 60);
  --warn-soft: oklch(96% 0.05 80);
  --bad:  oklch(50% 0.20 27);
  --bad-soft: oklch(96% 0.04 27);
  --info: oklch(50% 0.14 240);
  --info-soft: oklch(96% 0.03 230);

  --d-row: 44px;
  --d-pad: 16px;
  --d-gap: 16px;
  --d-text: 14px;

  --radius: 8px;
  --radius-sm: 6px;
  --radius-lg: 12px;

  --shadow-sm: 0 1px 1px rgba(15, 17, 22, 0.04), 0 1px 0 rgba(15, 17, 22, 0.02);
  --shadow-md: 0 1px 2px rgba(15, 17, 22, 0.06), 0 4px 12px rgba(15, 17, 22, 0.04);
  --shadow-lg: 0 4px 12px rgba(15, 17, 22, 0.08), 0 24px 48px rgba(15, 17, 22, 0.10);

  --font-sans: "Helvetica Neue", "Helvetica", "Arial", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "Geist Mono", "JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; font-family: var(--font-sans); background: var(--bg-sunken); -webkit-font-smoothing: antialiased; }
button { font: inherit; color: inherit; cursor: pointer; border: 0; background: none; padding: 0; }
input, textarea, select { font: inherit; color: inherit; }

.tnum { font-variant-numeric: tabular-nums; }
.mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
.muted { color: var(--ink-3); }
.eyebrow { font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-4); font-weight: 500; }
.row-flex { display: flex; align-items: center; gap: 10px; }
.row-flex.gap-sm { gap: 6px; }
.col-flex { display: flex; flex-direction: column; gap: var(--d-gap); }

.page-h { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 20px; }
.page-title { font-size: 22px; font-weight: 600; letter-spacing: -0.02em; margin: 4px 0; color: var(--ink); }
.page-sub { color: var(--ink-3); font-size: 13.5px; }

.section-h { display: flex; align-items: center; justify-content: space-between; margin: 6px 0 12px; }
.section-h h3 { margin: 0; font-size: 14px; font-weight: 600; color: var(--ink); }

.card { background: var(--bg); border: 1px solid var(--line); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); overflow: hidden; margin-bottom: 14px; }
.card-h { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--line); }
.card-h h3 { margin: 0; font-size: 13.5px; font-weight: 600; color: var(--ink); }

.kpi-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--d-gap); margin-bottom: var(--d-gap); }
.kpi { background: var(--bg); border: 1px solid var(--line); border-radius: var(--radius-lg); padding: 16px 18px 18px; position: relative; }
.kpi-label { font-size: 12px; color: var(--ink-3); display: flex; align-items: center; gap: 6px; }
.kpi-value { font-size: 28px; font-weight: 600; letter-spacing: -0.025em; margin-top: 6px; font-variant-numeric: tabular-nums; color: var(--ink); }
.kpi-sub { font-size: 12px; color: var(--ink-4); margin-top: 2px; }

.badge { display: inline-flex; align-items: center; gap: 5px; padding: 2px 8px; border-radius: 999px; font-size: 11.5px; font-weight: 500; line-height: 1.5; white-space: nowrap; }
.badge .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex: 0 0 auto; }
.b-ok { color: var(--ok); background: var(--ok-soft); }
.b-warn { color: var(--warn); background: var(--warn-soft); }
.b-bad { color: var(--bad); background: var(--bad-soft); }
.b-accent { color: var(--accent-ink); background: var(--accent-soft); }
.b-mute { color: var(--ink-3); background: var(--bg-sunken); }

.risk-bar { display: inline-grid; grid-template-columns: repeat(5, 4px); gap: 2px; vertical-align: middle; margin-right: 6px; }
.risk-bar i { height: 10px; border-radius: 1px; background: var(--bg-active); display: block; }
.risk-bar.r-1 i:nth-child(-n+1), .risk-bar.r-2 i:nth-child(-n+2), .risk-bar.r-3 i:nth-child(-n+3), .risk-bar.r-4 i:nth-child(-n+4), .risk-bar.r-5 i:nth-child(-n+5) { background: currentColor; }
.risk-low { color: var(--ok); }
.risk-medium { color: oklch(54% 0.14 60); }
.risk-high { color: var(--bad); }

.tbl { width: 100%; border-collapse: collapse; }
.tbl thead th { text-align: left; font-weight: 500; font-size: 11.5px; color: var(--ink-4); text-transform: uppercase; letter-spacing: 0.06em; padding: 10px 14px; border-bottom: 1px solid var(--line); background: var(--bg-elev); position: sticky; top: 0; z-index: 1; }
.tbl tbody td { padding: 0 14px; height: var(--d-row); border-bottom: 1px solid var(--line); font-size: var(--d-text); vertical-align: middle; color: var(--ink); }
.tbl tbody tr:last-child td { border-bottom: 0; }
.tbl tbody tr { cursor: pointer; transition: background 0.12s; }
.tbl tbody tr:hover { background: var(--bg-hover); }

.cell-client { display: flex; align-items: center; gap: 10px; }
.cell-client .ini { width: 28px; height: 28px; border-radius: 50%; background: var(--bg-active); color: var(--ink-2); display: grid; place-items: center; font-size: 11px; font-weight: 600; flex: 0 0 auto; }
.cell-client b { font-weight: 500; display: block; line-height: 1.2; }
.cell-client small { color: var(--ink-4); font-size: 11.5px; }
.cell-num { font-variant-numeric: tabular-nums; font-family: var(--font-mono); }

.sla { display: inline-flex; align-items: center; gap: 6px; font-variant-numeric: tabular-nums; font-size: 12.5px; }
.sla.ok { color: var(--ok); }
.sla.warn { color: oklch(54% 0.14 60); }
.sla.bad { color: var(--bad); }

.chips { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.chip { display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 10px; border: 1px solid var(--line); border-radius: 999px; background: var(--bg); color: var(--ink-2); font-size: 12.5px; transition: background 0.1s, border-color 0.1s, color 0.1s; }
.chip:hover { background: var(--bg-hover); }
.chip[data-active="true"] { border-color: var(--ink); background: var(--ink); color: var(--bg); }

.btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; height: 36px; padding: 0 14px; border-radius: 8px; font-size: 13.5px; font-weight: 500; border: 1px solid var(--line); background: var(--bg); color: var(--ink); transition: background 0.12s, border-color 0.12s; cursor: pointer; }
.btn:hover { background: var(--bg-hover); }
.btn.primary { background: var(--ink); color: var(--bg); border-color: var(--ink); }
.btn.primary:hover { background: var(--ink-2); }

.sidebar { width: 240px; background: var(--ink); color: var(--bg); display: flex; flex-direction: column; overflow-y: auto; }
.sb-brand { padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.1); }
.sb-mark { width: 32px; height: 32px; background: var(--accent); color: var(--bg); display: grid; place-items: center; border-radius: 6px; font-weight: 600; font-size: 16px; margin-bottom: 12px; }
.sb-name { font-size: 14px; font-weight: 600; color: var(--bg); }
.sb-name small { display: block; font-size: 11px; opacity: 0.7; margin-top: 2px; }

.sb-section { padding: 8px 0; margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.1); }
.sb-section-h { padding: 8px 14px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; color: rgba(255,255,255,0.5); font-weight: 600; }
.sb-link { display: flex; align-items: center; gap: 10px; padding: 10px 14px; color: var(--bg); font-size: 13.5px; cursor: pointer; transition: background 0.12s; border-left: 3px solid transparent; margin: 0 6px 0 0; }
.sb-link:hover { background: rgba(255,255,255,0.1); }
.sb-link[aria-current="true"] { background: rgba(255,255,255,0.15); border-left-color: var(--accent); }
.sb-icon { width: 18px; height: 18px; flex: 0 0 auto; display: flex; align-items: center; justify-content: center; }
.pill { margin-left: auto; font-size: 11px; padding: 2px 8px; background: rgba(255,255,255,0.15); border-radius: 999px; }

.sb-foot { padding: 12px; border-top: 1px solid rgba(255,255,255,0.1); display: flex; align-items: center; gap: 8px; margin-top: auto; }
.avatar { width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, oklch(60% 0.18 265), oklch(48% 0.20 290)); display: grid; place-items: center; color: white; font-size: 11px; font-weight: 600; flex: 0 0 auto; }
.sb-foot-meta { flex: 1; min-width: 0; }
.sb-foot-meta b { display: block; color: var(--bg); font-size: 13px; line-height: 1.2; }
.sb-foot-meta small { display: block; font-size: 11px; opacity: 0.7; margin-top: 2px; }

.topbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 20px; background: var(--bg); border-bottom: 1px solid var(--line); box-shadow: var(--shadow-sm); }
.crumbs { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--ink-3); }
.crumbs b { color: var(--ink); font-weight: 600; }
.crumbs .sep { opacity: 0.5; }
.role-tag { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; background: var(--accent-soft); color: var(--accent-ink); border-radius: 6px; font-size: 11px; font-weight: 500; margin-left: 8px; }

.search { display: flex; align-items: center; gap: 8px; background: var(--bg-sunken); border: 1px solid var(--line); border-radius: 8px; padding: 0 12px; height: 34px; color: var(--ink-3); transition: border-color 0.15s, box-shadow 0.15s; }
.search:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); color: var(--ink); }
.search input { background: none; border: 0; outline: 0; flex: 1; font-size: 13.5px; min-width: 0; }
.search kbd { font-size: 11px; color: var(--ink-4); }

.tb-btn { display: inline-flex; align-items: center; gap: 6px; height: 34px; padding: 0 12px; border: 1px solid var(--line); border-radius: 6px; font-size: 13px; font-weight: 500; background: var(--bg); color: var(--ink); transition: background 0.12s; cursor: pointer; }
.tb-btn:hover { background: var(--bg-hover); }
.tb-btn.primary { background: var(--ink); color: var(--bg); border-color: var(--ink); }

.app { display: flex; height: 100vh; }
.main { display: flex; flex-direction: column; flex: 1; overflow: hidden; }
.content { flex: 1; padding: 20px 24px; overflow-y: auto; background: var(--bg-sunken); }

/* Login page */
.login-container { height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg-sunken); }
.login-card { background: var(--bg); border: 1px solid var(--line); border-radius: var(--radius-lg); box-shadow: var(--shadow-md); padding: 40px; width: 100%; max-width: 360px; }
.login-card h1 { font-size: 24px; font-weight: 600; margin-bottom: 8px; color: var(--ink); text-align: center; }
.login-card .subtitle { font-size: 13.5px; color: var(--ink-3); text-align: center; margin-bottom: 24px; }
.login-field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
.login-field label { font-size: 12px; font-weight: 500; color: var(--ink-2); }
.login-field input { height: 40px; padding: 0 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--bg-sunken); font-size: 14px; outline: 0; transition: border-color 0.15s, box-shadow 0.15s; }
.login-field input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
.login-error { background: var(--bad-soft); border: 1px solid var(--bad); color: var(--bad); padding: 10px 12px; border-radius: 6px; font-size: 12px; margin-bottom: 16px; }

.tbl-wrap { overflow-x: auto; }

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: var(--line-strong); border-radius: 999px; border: 2px solid var(--bg-sunken); }
::-webkit-scrollbar-track { background: transparent; }

@keyframes spin { to { transform: rotate(360deg); } }
"""

    # ============================================================
    # React Code: Auth + Layout + Views
    # ============================================================
    react_code = r"""
const { useState, useEffect, useMemo, useCallback } = React;
const CONFIG = window.__CONFIG__;
const API = CONFIG.apiUrl || "http://127.0.0.1:8000";

/* ============================================================
   Icons (exact from atlas-kyc-dashboard/icons.jsx)
   ============================================================ */
const iconPaths = {
  inbox: <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><polyline points="22 12 18 12 15 21 9 21 6 12 2 12"/><path d="M6 12L2 6h20l-4 6"/></svg>,
  users: <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx={9} cy={7} r={4}/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
  audit: <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M9 11l3 3L22 4"/><path d="M21 12a9 9 0 1 1 0-18 9 9 0 0 1 0 18z"/></svg>,
  shield: <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  settings: <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><circle cx={12} cy={12} r={3}/><path d="M12 1v6m0 6v6M4.22 4.22l4.24 4.24m5.08 5.08l4.24 4.24M1 12h6m6 0h6m-17.78 7.78l4.24-4.24m5.08-5.08l4.24-4.24"/></svg>,
  search: <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><circle cx={11} cy={11} r={8}/><path d="m21 21-4.35-4.35"/></svg>,
  filter: <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>,
  download: <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1={12} y1={15} x2={12} y2={3}/></svg>,
  plus: <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><line x1={12} y1={5} x2={12} y2={19}/><line x1={5} y1={12} x2={19} y2={12}/></svg>,
  refresh: <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36M20.49 15a9 9 0 0 1-14.85 3.36"/></svg>,
};

function Icon({ name, size = 18, color = "currentColor" }) {
  const paths = iconPaths;
  if (!paths[name]) return <span>{name}</span>;
  const svg = paths[name];
  return React.cloneElement(svg, { width: size, height: size, stroke: color });
}

function RiskBar({ level, score }) {
  const map = { low: { c: "risk-low", n: 1 }, medium: { c: "risk-medium", n: 3 }, high: { c: "risk-high", n: 5 } };
  const m = map[level] || map.low;
  return (
    <span className="row-flex gap-sm">
      <span className={`risk-bar r-${m.n} ${m.c}`}><i/><i/><i/><i/><i/></span>
      <span className="tnum" style={{fontSize:12.5,color:"var(--ink-2)"}}>{score}</span>
    </span>
  );
}

/* ============================================================
   Login View
   ============================================================ */
function LoginView({ onLogin }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = useCallback(async () => {
    setError(""); setLoading(true);
    try {
      const res = await fetch(API + "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) throw new Error("Invalid credentials");
      const json = await res.json();
      if (typeof window !== "undefined" && window.localStorage) {
        localStorage.setItem("auth_token", json.token);
        localStorage.setItem("auth_role", json.role);
      }
      onLogin(json.token, json.role);
    } catch (err) {
      setError(err.message || "Login failed");
    }
    setLoading(false);
  }, [username, password, onLogin]);

  const handleKeyPress = (e) => { if (e.key === "Enter") handleLogin(); };

  return (
    <div className="login-container">
      <div className="login-card">
        <h1>Atlas Compliance</h1>
        <div className="subtitle">KYC Dashboard</div>
        {error && <div className="login-error">{error}</div>}
        <div className="login-field">
          <label>Username</label>
          <input type="text" value={username} onChange={e => setUsername(e.target.value)} onKeyPress={handleKeyPress} disabled={loading} placeholder="admin or banker"/>
        </div>
        <div className="login-field">
          <label>Password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} onKeyPress={handleKeyPress} disabled={loading} placeholder="Enter password"/>
        </div>
        <button className="btn primary" style={{width:"100%"}} onClick={handleLogin} disabled={loading}>
          {loading ? "Logging in…" : "Sign in"}
        </button>
        <div style={{marginTop:16,fontSize:12,color:"var(--ink-4)",textAlign:"center"}}>
          Demo: admin/admin123 or banker/banker123
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Sidebar (exact from atlas-kyc-dashboard/shell.jsx)
   ============================================================ */
function Sidebar({ active, onNav, role, onLogout }) {
  const isAdmin = role === "admin";
  const items = [
    { id: "worklist", icon: "inbox", label: "Worklist", pill: "47" },
    { id: "rm", icon: "users", label: "Client book" },
    { id: "case", icon: "case", label: "Case detail" },
    { id: "batch", icon: "upload", label: "Batch upload" },
  ];
  const compliance = [
    { id: "alerts", icon: "bell", label: "Alerts", pill: "7", disabled: true },
    { id: "monitoring", icon: "eye", label: "Periodic review", pill: "12", disabled: true },
  ];
  const admin = [
    { id: "audit", icon: "audit", label: "Audit trail", pill: "12.8k" },
    { id: "ruleset", icon: "shield", label: "Ruleset & policy", pill: "1" },
    { id: "system", icon: "settings", label: "System info" },
  ];

  return (
    <aside className="sidebar">
      <div className="sb-brand">
        <div className="sb-mark">A</div>
        <div className="sb-name">Atlas Compliance<small>Private Wealth · KYC</small></div>
      </div>
      <div className="sb-section">
        <div className="sb-section-h">Workspaces</div>
        {items.map(it => (
          <button key={it.id} className="sb-link" aria-current={active === it.id} onClick={() => onNav(it.id)}>
            <span className="sb-icon"><Icon name={it.icon}/></span>
            <span>{it.label}</span>
            {it.pill && <span className="pill tnum">{it.pill}</span>}
          </button>
        ))}
      </div>
      <div className="sb-section">
        <div className="sb-section-h">Compliance</div>
        {compliance.map(it => (
          <button key={it.id} className="sb-link" onClick={() => {}} aria-disabled="true" style={{opacity:0.5}}>
            <span className="sb-icon"><Icon name={it.icon}/></span>
            <span>{it.label}</span>
            {it.pill && <span className="pill tnum">{it.pill}</span>}
          </button>
        ))}
      </div>
      {isAdmin && (
        <div className="sb-section">
          <div className="sb-section-h">Administration</div>
          {admin.map(it => (
            <button key={it.id} className="sb-link" aria-current={active === it.id} onClick={() => onNav(it.id)}>
              <span className="sb-icon"><Icon name={it.icon}/></span>
              <span>{it.label}</span>
              {it.pill && <span className="pill tnum">{it.pill}</span>}
            </button>
          ))}
        </div>
      )}
      <div className="sb-foot">
        <div className="avatar" style={isAdmin ? { background: "linear-gradient(135deg, oklch(60% 0.18 265), oklch(48% 0.20 290))" } : null}>{isAdmin ? "ML" : "JM"}</div>
        <div className="sb-foot-meta">
          <b>{isAdmin ? "M. Lyons" : "J. Marlow"}</b>
          <small>{isAdmin ? "Compliance Admin" : "Senior KYC Analyst"}</small>
        </div>
        <button className="sb-link" onClick={onLogout} style={{marginLeft:"auto",padding:"0 8px"}}>
          <Icon name="refresh" size={13}/>
        </button>
      </div>
    </aside>
  );
}

/* ============================================================
   Topbar (exact from atlas-kyc-dashboard/shell.jsx)
   ============================================================ */
function Topbar({ crumbs, search, setSearch, role, view }) {
  const adminViews = new Set(["audit", "ruleset", "system"]);
  const isAdmin = role === "admin";
  const inAdmin = adminViews.has(view);

  return (
    <div className="topbar">
      <div className="crumbs">
        {crumbs.map((c, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="sep">/</span>}
            {i === crumbs.length - 1 ? <b>{c}</b> : <span>{c}</span>}
          </React.Fragment>
        ))}
        {isAdmin && <span className="role-tag"><Icon name="shield" size={11}/> Admin</span>}
      </div>
      <div style={{flex:1}}/>
      <div className="search">
        <Icon name="search" size={16}/>
        <input placeholder="Search…" value={search} onChange={e => setSearch(e.target.value)} style={{flex:1}}/>
      </div>
      {!inAdmin && <>
        <button className="tb-btn"><Icon name="filter" size={16}/> Filters</button>
        <button className="tb-btn"><Icon name="download" size={16}/> Export</button>
        <button className="tb-btn primary"><Icon name="plus" size={16}/> New case</button>
      </>}
    </div>
  );
}

/* ============================================================
   Worklist View (exact from atlas-kyc-dashboard/view-worklist.jsx)
   ============================================================ */
function WorklistView({ cases, search, role }) {
  const { useState, useMemo } = React;
  const [filter, setFilter] = useState("all");

  const filtered = useMemo(() => {
    let list = cases || [];
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(c => c.client.toLowerCase().includes(s) || c.id.toLowerCase().includes(s));
    }
    if (filter === "needs-me") list = list.filter(c => c.status === "Dual-approval" || c.status === "Pending review");
    if (filter === "overdue") list = list.filter(c => c.sla.tone === "bad");
    if (filter === "high") list = list.filter(c => c.risk === "high");
    return list;
  }, [search, filter, cases]);

  const kpis = [
    { label: "Open cases", value: cases?.length || "0", sub: "across the team" },
    { label: "Pending docs", value: "12", sub: "awaiting client upload" },
    { label: "Ready to approve", value: "8", sub: "reconciled, awaiting sign-off" },
    { label: "Avg. cycle time", value: "3.4d", sub: "rolling 30 days" },
  ];

  return (
    <>
      <div className="page-h">
        <div>
          <div className="eyebrow">Worklist</div>
          <h1 className="page-title">KYC case queue</h1>
          <div className="page-sub">High Net Worth Individuals · Mon, 27 Apr 2026</div>
        </div>
      </div>

      <div className="kpi-strip" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        {kpis.map((k, i) => (
          <div className="kpi" key={i}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value">{k.value}</div>
            <div className="kpi-sub">{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="section-h" style={{ marginTop: 8 }}>
        <h3>Active queue</h3>
        <div className="chips">
          {[
            { v: "all", l: "All" },
            { v: "needs-me", l: "Needs my action" },
            { v: "overdue", l: "Overdue" },
            { v: "high", l: "High risk" },
          ].map(c => (
            <button key={c.v} className="chip" data-active={filter === c.v} onClick={() => setFilter(c.v)}>{c.l}</button>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>Client</th>
                <th style={{ width: 140 }}>AUM</th>
                <th style={{ width: 130 }}>Risk</th>
                <th>Action needed</th>
                <th style={{ width: 140 }}>Due</th>
                {role === "admin" && <th style={{width:120}}>Admin action</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 8).map(c => (
                <tr key={c.id}>
                  <td>
                    <div className="cell-client">
                      <div className="ini">{c.ini}</div>
                      <div>
                        <b>{c.client}</b>
                        <small>{c.tier} · {c.jurisdiction}</small>
                      </div>
                    </div>
                  </td>
                  <td className="cell-num">${c.aum}M</td>
                  <td><RiskBar level={c.risk} score={c.riskScore}/></td>
                  <td>
                    <span className={`badge ${
                      c.status === "Escalated" ? "b-bad" :
                      c.status === "Dual-approval" ? "b-accent" :
                      c.status === "Awaiting docs" ? "b-warn" : "b-mute"
                    }`}>
                      <span className="dot"/>{c.status}
                    </span>
                  </td>
                  <td>
                    <span className={`sla ${c.sla.tone}`}>{c.sla.label}</span>
                  </td>
                  {role === "admin" && (
                    <td>
                      <button className="btn" style={{fontSize:12,padding:"0 8px",height:28}}>Approve</button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

/* ============================================================
   Audit Trail View (exact from atlas-kyc-dashboard/view-audit.jsx)
   ============================================================ */
function AuditView() {
  const { useState, useEffect } = React;
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAudit = async () => {
      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
        const res = await fetch(API + "/api/audit", {
          headers: { "Authorization": `Bearer ${token}` },
        });
        if (res.ok) {
          const json = await res.json();
          setLogs(json.logs || []);
        }
      } catch (err) {
        console.error("Audit fetch error:", err);
      }
      setLoading(false);
    };
    fetchAudit();
  }, []);

  return (
    <>
      <div className="page-h">
        <div>
          <div className="eyebrow">Administration</div>
          <h1 className="page-title">Audit trail</h1>
          <div className="page-sub">Immutable log of every interaction with the application</div>
        </div>
      </div>

      <div className="card">
        {loading ? (
          <div style={{padding:"32px",textAlign:"center",color:"var(--ink-4)"}}>Loading audit logs…</div>
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{width:160}}>Timestamp</th>
                  <th style={{width:80}}>User</th>
                  <th style={{width:80}}>Role</th>
                  <th style={{width:140}}>Action</th>
                  <th>Description</th>
                  <th style={{width:120}}>Customer ID</th>
                </tr>
              </thead>
              <tbody>
                {logs.slice(0, 50).map((log, i) => (
                  <tr key={i}>
                    <td className="tnum" style={{fontSize:12}}>{new Date(log.timestamp).toLocaleString()}</td>
                    <td style={{fontSize:12}}>{log.user}</td>
                    <td><span className="badge b-accent">{log.role}</span></td>
                    <td style={{fontSize:12,fontWeight:500}}>{log.action}</td>
                    <td style={{fontSize:12,color:"var(--ink-3)"}}>{log.description}</td>
                    <td className="cell-num">{log.customer_id || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

/* ============================================================
   Main App
   ============================================================ */
function App() {
  const [isAuthed, setIsAuthed] = useState(false);
  const [token, setToken] = useState(null);
  const [role, setRole] = useState(null);
  const [view, setView] = useState("worklist");
  const [cases, setCases] = useState([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined" && window.localStorage) {
      const storedToken = localStorage.getItem("auth_token");
      const storedRole = localStorage.getItem("auth_role");
      if (storedToken && storedRole) {
        setToken(storedToken);
        setRole(storedRole);
        setIsAuthed(true);
        loadCases(storedToken);
      }
    }
  }, []);

  const loadCases = useCallback(async (authToken) => {
    try {
      const res = await fetch(API + "/api/kyc/batch", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`,
        },
        body: JSON.stringify({ institution_id: "bank_001" }),
      });
      if (res.ok) {
        const json = await res.json();
        setCases(json.results || []);
      }
    } catch (err) {
      console.error("Failed to load cases:", err);
    }
  }, []);

  const handleLogin = useCallback((newToken, newRole) => {
    setToken(newToken);
    setRole(newRole);
    setIsAuthed(true);
    setView("worklist");
    loadCases(newToken);
  }, [loadCases]);

  const handleLogout = useCallback(async () => {
    try {
      await fetch(API + "/api/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
    } catch {}
    if (typeof window !== "undefined" && window.localStorage) {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_role");
    }
    setIsAuthed(false);
    setToken(null);
    setRole(null);
    setCases([]);
  }, [token]);

  if (!isAuthed) {
    return <LoginView onLogin={handleLogin}/>;
  }

  const crumbs = {
    worklist: ["Compliance", "Private Wealth", "Worklist"],
    rm: ["Relationship Management", "Client book"],
    case: ["Compliance", "Cases", "—"],
    batch: ["Operations", "Batch upload"],
    audit: ["Administration", "Audit trail"],
    ruleset: ["Administration", "Ruleset & policy"],
    system: ["Administration", "System information"],
  };

  return (
    <div className="app">
      <Sidebar active={view} onNav={setView} role={role} onLogout={handleLogout}/>
      <div className="main">
        <Topbar crumbs={crumbs[view] || []} search={search} setSearch={setSearch} role={role} view={view}/>
        <div className="content">
          {view === "worklist" && <WorklistView cases={cases} search={search} role={role}/>}
          {view === "audit" && <AuditView/>}
          {view !== "worklist" && view !== "audit" && (
            <div style={{padding:"40px",textAlign:"center",color:"var(--ink-4)"}}>
              View "{view}" not yet implemented
            </div>
          )}
        </div>
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
<title>Atlas Compliance — KYC Dashboard</title>
<style>
{css}
</style>
</head>
<body>
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
