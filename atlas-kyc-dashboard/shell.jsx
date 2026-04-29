/* global React, Icon, MOCK */

/* ============================================================
   Sidebar
   ============================================================ */
function Sidebar({ active, onNav, collapsed, role, onRoleChange }) {
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
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="sb-brand">
        <div className="sb-mark">A</div>
        {!collapsed && <div className="sb-name">Atlas Compliance<small>Private Wealth · KYC</small></div>}
      </div>
      <div className="sb-section">
        {!collapsed && <div className="sb-section-h">Workspaces</div>}
        {items.map(it => (
          <button key={it.id} className="sb-link" aria-current={active === it.id} onClick={() => onNav(it.id)}>
            <span className="sb-icon"><Icon name={it.icon}/></span>
            <span>{it.label}</span>
            {it.pill && <span className="pill tnum">{it.pill}</span>}
          </button>
        ))}
      </div>
      <div className="sb-section">
        {!collapsed && <div className="sb-section-h">Compliance</div>}
        {compliance.map(it => (
          <button key={it.id} className="sb-link" onClick={() => {}} aria-disabled="true">
            <span className="sb-icon"><Icon name={it.icon}/></span>
            <span>{it.label}</span>
            {it.pill && <span className="pill tnum">{it.pill}</span>}
          </button>
        ))}
      </div>
      {isAdmin && (
        <div className="sb-section">
          {!collapsed && <div className="sb-section-h"><span className="adm-dot"/>Administration</div>}
          {admin.map(it => (
            <button key={it.id} className="sb-link adm" aria-current={active === it.id} onClick={() => onNav(it.id)}>
              <span className="sb-icon"><Icon name={it.icon}/></span>
              <span>{it.label}</span>
              {it.pill && <span className="pill tnum">{it.pill}</span>}
            </button>
          ))}
        </div>
      )}
      <div className="sb-foot">
        <div className="avatar" style={isAdmin ? { background: "linear-gradient(135deg, oklch(60% 0.18 265), oklch(48% 0.20 290))" } : null}>{isAdmin ? "ML" : "JM"}</div>
        {!collapsed && (
          <div className="sb-foot-meta" style={{ flex: 1, minWidth: 0 }}>
            <b>{isAdmin ? "M. Lyons" : "J. Marlow"}</b>
            <small>{isAdmin ? "Compliance Admin" : "Senior KYC Analyst"}</small>
          </div>
        )}
        {!collapsed && (
          <button className="role-switch" onClick={() => onRoleChange(isAdmin ? "banker" : "admin")} title="Switch role" aria-label="Switch role">
            <Icon name="refresh" size={13}/>
          </button>
        )}
      </div>
    </aside>
  );
}

/* ============================================================
   Topbar
   ============================================================ */
function Topbar({ title, crumbs, search, setSearch, role, view }) {
  const adminViews = new Set(["audit", "ruleset", "system"]);
  const isAdmin = role === "admin";
  const inAdmin = adminViews.has(view);
  const placeholder = inAdmin
    ? (view === "audit" ? "Search events, users, hashes…" :
       view === "ruleset" ? "Search rules, jurisdictions, versions…" :
       "Search datasets, prompts, integrations…")
    : view === "batch" ? "Search files in current batch…"
    : "Search clients, case IDs, RMs…";
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
      <div className="tb-spacer"/>
      <div className="search" role="search">
        <Icon name="search" aria-hidden="true"/>
        <label htmlFor="global-search" className="sr-only">{placeholder}</label>
        <input id="global-search" placeholder={placeholder} value={search} onChange={e => setSearch(e.target.value)} />
        <kbd aria-hidden="true">⌘K</kbd>
      </div>
      {!inAdmin && view !== "batch" && <>
        <button className="tb-btn" aria-label="Open filters"><Icon name="filter" aria-hidden="true"/> Filters</button>
        <button className="tb-btn" aria-label="Export view"><Icon name="download" aria-hidden="true"/> Export</button>
        <button className="tb-btn primary" aria-label="Create new case"><Icon name="plus" aria-hidden="true"/> New case</button>
      </>}
      {inAdmin && view === "audit" && <>
        <button className="tb-btn"><Icon name="filter"/> Filters</button>
        <button className="tb-btn"><Icon name="download"/> Export CSV</button>
      </>}
      {inAdmin && view === "ruleset" && <>
        <button className="tb-btn"><Icon name="file"/> Diff</button>
        <button className="tb-btn primary"><Icon name="plus"/> Propose change</button>
      </>}
      {inAdmin && view === "system" && <>
        <button className="tb-btn"><Icon name="refresh"/> Refresh</button>
        <button className="tb-btn"><Icon name="download"/> Status report</button>
      </>}
    </div>
  );
}

/* ============================================================
   Tiny inline charts
   ============================================================ */
function Spark({ values, w = 80, h = 28, color = "currentColor" }) {
  const max = Math.max(...values), min = Math.min(...values);
  const range = (max - min) || 1;
  const step = w / (values.length - 1);
  const pts = values.map((v, i) => `${i * step},${h - ((v - min) / range) * (h - 4) - 2}`).join(" ");
  return (
    <svg width={w} height={h} className="kpi-spark" aria-hidden="true">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"/>
    </svg>
  );
}

function RiskBar({ level, score }) {
  const map = { low: { c: "risk-low", n: 1 }, medium: { c: "risk-medium", n: 3 }, high: { c: "risk-high", n: 5 } };
  const m = map[level] || map.low;
  return (
    <span className={`row-flex gap-sm`}>
      <span className={`risk-bar r-${m.n} ${m.c}`}><i/><i/><i/><i/><i/></span>
      <span className="tnum" style={{ fontSize: 12.5, color: "var(--ink-2)" }}>{score}</span>
    </span>
  );
}

window.Sidebar = Sidebar;
window.Topbar = Topbar;
window.Spark = Spark;
window.RiskBar = RiskBar;
