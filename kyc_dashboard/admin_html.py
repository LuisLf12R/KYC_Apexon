"""
kyc_dashboard/admin_html.py
Serves the exact Atlas KYC dashboard with an auth layer injected on top.
All design files are loaded from atlas-kyc-dashboard/ and inlined.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

ATLAS_DIR = Path(__file__).parent.parent / "atlas-kyc-dashboard"


def _read(filename: str) -> str:
    return (ATLAS_DIR / filename).read_text(encoding="utf-8")


def build_unified_dashboard_html(config: Dict[str, Any]) -> str:
    config_json = json.dumps(config, default=str, ensure_ascii=False)

    css        = _read("styles.css")
    data_js    = _read("data.js")
    icons_jsx  = _read("icons.jsx")
    shell_jsx  = _read("shell.jsx")
    wl_jsx     = _read("view-worklist.jsx")
    port_jsx   = _read("view-portfolio.jsx")
    rm_jsx     = _read("view-rm.jsx")
    case_jsx   = _read("view-case.jsx")
    batch_jsx  = _read("view-batch.jsx")
    audit_jsx  = _read("view-audit.jsx")
    ruleset_jsx= _read("view-ruleset.jsx")
    system_jsx = _read("view-system.jsx")
    tweaks_jsx = _read("tweaks-panel.jsx")

    # Auth layer + App replacement (replaces the inline <script> in KYC Dashboard.html)
    auth_app = r"""
    const { useState, useEffect } = React;
    const API = (window.__CONFIG__ || {}).apiUrl || "http://127.0.0.1:8000";

    /* ── Login screen ── */
    function LoginView({ onLogin }) {
      const [username, setUsername] = React.useState("admin");
      const [password, setPassword] = React.useState("");
      const [error, setError]       = React.useState("");
      const [loading, setLoading]   = React.useState(false);

      const submit = async () => {
        setError(""); setLoading(true);
        try {
          const res = await fetch(API + "/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
          });
          if (!res.ok) throw new Error("Invalid credentials");
          const data = await res.json();
          localStorage.setItem("auth_token", data.token);
          localStorage.setItem("auth_role",  data.role);
          onLogin(data.token, data.role);
        } catch (e) {
          setError(e.message || "Login failed");
        }
        setLoading(false);
      };

      return (
        <div className="login-wrap">
          <div className="login-card">
            <div className="sb-mark" style={{margin:"0 auto 16px",width:40,height:40,fontSize:20}}>A</div>
            <h1 style={{fontSize:22,fontWeight:600,textAlign:"center",marginBottom:4}}>Atlas Compliance</h1>
            <p style={{fontSize:13,color:"var(--ink-4)",textAlign:"center",marginBottom:24}}>KYC Dashboard · Private Wealth</p>
            {error && <div className="login-error">{error}</div>}
            <div className="login-field">
              <label>Username</label>
              <input type="text" value={username} onChange={e=>setUsername(e.target.value)}
                onKeyDown={e=>e.key==="Enter"&&submit()} disabled={loading} autoFocus/>
            </div>
            <div className="login-field">
              <label>Password</label>
              <input type="password" value={password} onChange={e=>setPassword(e.target.value)}
                onKeyDown={e=>e.key==="Enter"&&submit()} disabled={loading}/>
            </div>
            <button className="btn primary" style={{width:"100%",marginTop:8}} onClick={submit} disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </button>
            <p style={{marginTop:14,fontSize:11.5,color:"var(--ink-5)",textAlign:"center"}}>
              admin / admin123 &nbsp;·&nbsp; banker / banker123
            </p>
          </div>
        </div>
      );
    }

    /* ── Auth-aware App (replaces the original App from KYC Dashboard.html) ── */
    const TWEAK_DEFAULTS = {
      "theme": "light", "density": "comfortable", "sidebar": "expanded",
      "role": "banker",
      "panel_identity": true, "panel_aml": true, "panel_ubo": true,
      "panel_sow": true, "panel_crs": true, "panel_monitoring": true
    };

    function App() {
      const [authed,    setAuthed]    = useState(false);
      const [authToken, setAuthToken] = useState(null);
      const [authRole,  setAuthRole]  = useState("banker");

      // Restore session from localStorage
      useEffect(() => {
        const t = localStorage.getItem("auth_token");
        const r = localStorage.getItem("auth_role");
        if (t && r) { setAuthToken(t); setAuthRole(r); setAuthed(true); }
      }, []);

      const handleLogin = (token, role) => {
        setAuthToken(token); setAuthRole(role); setAuthed(true);
      };

      const handleLogout = async () => {
        try {
          await fetch(API + "/api/auth/logout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: authToken }),
          });
        } catch (_) {}
        localStorage.removeItem("auth_token");
        localStorage.removeItem("auth_role");
        setAuthed(false); setAuthToken(null);
      };

      if (!authed) return <LoginView onLogin={handleLogin}/>;

      return <AuthenticatedApp role={authRole} onLogout={handleLogout}/>;
    }

    function AuthenticatedApp({ role, onLogout }) {
      const [tweaks, setTweak] = useTweaks({ ...TWEAK_DEFAULTS, role });
      const [view,       setView]       = useState(role === "admin" ? "audit" : "worklist");
      const [search,     setSearch]     = useState("");
      const [activeCase, setActiveCase] = useState(null);
      const [summary,    setSummary]    = useState({});
      const [cases,      setCases]      = useState(null);
      const [kpis,       setKpis]       = useState({});
      const [auditLogs,  setAuditLogs]  = useState(null);

      useEffect(() => {
        document.documentElement.setAttribute("data-theme",   tweaks.theme);
        document.documentElement.setAttribute("data-density", tweaks.density);
      }, [tweaks.theme, tweaks.density]);

      const loadCases = React.useCallback(async (authToken) => {
        try {
          // Fetch first available institution then run batch
          const instRes = await fetch(API + "/api/institutions", {
            headers: { Authorization: `Bearer ${authToken}` },
          });
          let instId = "bank_001";
          if (instRes.ok) {
            const instList = await instRes.json();
            if (Array.isArray(instList) && instList.length > 0) instId = instList[0].id;
          }
          const res = await fetch(API + "/api/kyc/batch", {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
            body: JSON.stringify({ institution_id: instId }),
          });
          if (res.ok) {
            const json = await res.json();
            setCases(json.results || []);
            setKpis(json.summary || {});
          }
        } catch (err) {
          console.error("Failed to load cases:", err);
        }
      }, [API]);

      const loadAudit = React.useCallback(async () => {
        try {
          const res = await fetch(API + "/api/audit", {
            headers: { Authorization: `Bearer ${localStorage.getItem("auth_token")}` },
          });
          if (res.ok) {
            const json = await res.json();
            setAuditLogs(json.logs || []);
          }
        } catch (_) {}
      }, [API]);

      const handleNav = React.useCallback((newView) => {
        if (newView === "audit") loadAudit();
        setView(newView);
      }, [loadAudit]);

      // Reload cases whenever the worklist view becomes active
      useEffect(() => {
        if (view === "worklist") {
          loadCases(localStorage.getItem("auth_token"));
        }
      }, [view, loadCases]);

      const handleApprove = React.useCallback((caseId) => {
        const tok = localStorage.getItem("auth_token");
        fetch(API + "/api/kyc/approve/" + caseId, {
          method: "POST",
          headers: { Authorization: `Bearer ${tok}` },
        }).then(res => {
          if (!res.ok) { console.error("Approve failed", res.status); return; }
          return loadCases(tok);
        }).catch(err => console.error("Approve error:", err));
      }, [loadCases, API]);

      const handleReject = React.useCallback((caseId) => {
        const tok = localStorage.getItem("auth_token");
        fetch(API + "/api/kyc/reject/" + caseId, {
          method: "POST",
          headers: { Authorization: `Bearer ${tok}` },
        }).then(res => {
          if (!res.ok) { console.error("Reject failed", res.status); return; }
          return loadCases(tok);
        }).catch(err => console.error("Reject error:", err));
      }, [loadCases, API]);

      const openCase = (c) => { setActiveCase(c); setView("case"); };
      const back = () => setView("worklist");

      const panels = {
        identity:   tweaks.panel_identity,  aml:        tweaks.panel_aml,
        ubo:        tweaks.panel_ubo,        sow:        tweaks.panel_sow,
        crs:        tweaks.panel_crs,        monitoring: tweaks.panel_monitoring,
      };

      const crumbsByView = {
        worklist: ["Compliance", "Private Wealth", "Worklist"],
        rm:       ["Relationship Management", "Client book"],
        case:     ["Compliance", "Cases", activeCase ? activeCase.id : "—"],
        batch:    ["Operations", "Batch upload"],
        audit:    ["Administration", "Audit trail"],
        ruleset:  ["Administration", "Ruleset & policy"],
        system:   ["Administration", "System information"],
      };

      return (
        <div className="app" data-sidebar={tweaks.sidebar} data-role={role}>
          <Sidebar active={view} onNav={handleNav} collapsed={tweaks.sidebar === "collapsed"}
                   role={role} onRoleChange={onLogout}/>
          <div className="main">
            <Topbar title="" crumbs={crumbsByView[view]} search={search} setSearch={setSearch}
                    role={role} view={view}/>
            <div className="content">
              <div className="content-wide">
                {view === "worklist" && (
                  <WorklistView
                    search={search}
                    onOpenCase={openCase}
                    cases={cases}
                    kpiData={Object.keys(kpis).length ? kpis : null}
                    onApprove={handleApprove}
                    onReject={handleReject}
                  />
                )}
                {view === "rm"       && <RMView        search={search} onOpenCase={openCase}/>}
                {view === "case"     && <CaseDetail    caseData={activeCase || MOCK.cases[0]} onBack={back} panels={panels} setPanels={()=>{}}/>}
                {view === "batch" && (
                  <BatchView onBatchComplete={(newCases, newSummary) => {
                    setCases(newCases);
                    setSummary(newSummary);
                    setView("worklist");
                  }}/>
                )}
                {view === "audit" && <AuditView search={search} logs={auditLogs}/>}
                {view === "ruleset"  && <RulesetView/>}
                {view === "system"   && <SystemView/>}
              </div>
            </div>
          </div>

          <TweaksPanel title="Tweaks">
            <TweakSection title="Appearance">
              <TweakRadio label="Theme" value={tweaks.theme} onChange={v=>setTweak("theme",v)}
                options={[{value:"light",label:"Light"},{value:"dark",label:"Dark"}]}/>
              <TweakRadio label="Density" value={tweaks.density} onChange={v=>setTweak("density",v)}
                options={[{value:"compact",label:"Compact"},{value:"cozy",label:"Cozy"},{value:"comfortable",label:"Comfy"}]}/>
              <TweakRadio label="Sidebar" value={tweaks.sidebar} onChange={v=>setTweak("sidebar",v)}
                options={[{value:"expanded",label:"Expanded"},{value:"collapsed",label:"Collapsed"}]}/>
            </TweakSection>
            <TweakSection title="Case detail panels">
              <TweakToggle label="Identity"         value={tweaks.panel_identity}   onChange={v=>setTweak("panel_identity",v)}/>
              <TweakToggle label="AML / PEP"        value={tweaks.panel_aml}        onChange={v=>setTweak("panel_aml",v)}/>
              <TweakToggle label="UBO"              value={tweaks.panel_ubo}        onChange={v=>setTweak("panel_ubo",v)}/>
              <TweakToggle label="Source of Wealth" value={tweaks.panel_sow}        onChange={v=>setTweak("panel_sow",v)}/>
              <TweakToggle label="CRS / FATCA"      value={tweaks.panel_crs}        onChange={v=>setTweak("panel_crs",v)}/>
              <TweakToggle label="Periodic review"  value={tweaks.panel_monitoring} onChange={v=>setTweak("panel_monitoring",v)}/>
            </TweakSection>
          </TweaksPanel>
        </div>
      );
    }

    ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
    """

    login_css = """
.login-wrap {
  height: 100vh; display: flex; align-items: center; justify-content: center;
  background: var(--bg-sunken);
}
.login-card {
  background: var(--bg); border: 1px solid var(--line);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-md);
  padding: 40px; width: 100%; max-width: 360px;
}
.login-field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
.login-field label { font-size: 12px; font-weight: 500; color: var(--ink-2); }
.login-field input {
  height: 40px; padding: 0 12px; border: 1px solid var(--line);
  border-radius: 8px; background: var(--bg-sunken); font-size: 14px; outline: 0;
  transition: border-color .15s, box-shadow .15s;
}
.login-field input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
.login-error {
  background: var(--bad-soft); border: 1px solid var(--bad); color: var(--bad);
  padding: 10px 12px; border-radius: 6px; font-size: 12px; margin-bottom: 16px;
}
"""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Atlas — KYC Dashboard</title>
  <style>html, body, #root {{ height: 100%; }}</style>
  <style>{css}</style>
  <style>{login_css}</style>
  <script src="https://unpkg.com/react@18.3.1/umd/react.development.js" crossorigin="anonymous"></script>
  <script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" crossorigin="anonymous"></script>
  <script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js" crossorigin="anonymous"></script>
</head>
<body>
  <div id="root"></div>
  <script>window.__CONFIG__ = {config_json};</script>
  <script>{data_js}</script>
  <script type="text/babel">{icons_jsx}</script>
  <script type="text/babel">{shell_jsx}</script>
  <script type="text/babel">{wl_jsx}</script>
  <script type="text/babel">{port_jsx}</script>
  <script type="text/babel">{rm_jsx}</script>
  <script type="text/babel">{case_jsx}</script>
  <script type="text/babel">{batch_jsx}</script>
  <script type="text/babel">{audit_jsx}</script>
  <script type="text/babel">{ruleset_jsx}</script>
  <script type="text/babel">{system_jsx}</script>
  <script type="text/babel">{tweaks_jsx}</script>
  <script type="text/babel" data-presets="react">
{auth_app}
  </script>
</body>
</html>"""
