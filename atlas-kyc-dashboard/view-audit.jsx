/* global React, Icon, MOCK */

/* ============================================================
   Audit Trail — admin view
   ============================================================ */
function AuditView({ search, logs: propLogs }) {
  const { useState, useMemo } = React;
  const [selected, setSelected] = useState(null);
  // range filter is display-only; server-side time-range filtering is not yet implemented
  const [activeFilters, setActiveFilters] = useState({ role: "all", action: "all", range: "24h" });

  const rows = propLogs || MOCK.audit;
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter(r => {
      if (activeFilters.role !== "all" && r.role.toLowerCase() !== activeFilters.role) return false;
      if (activeFilters.action !== "all" && r.actionGroup !== activeFilters.action) return false;
      if (!q) return true;
      return (r.user + r.action + r.description + (r.customerId || "") + (r.batchId || "") + (r.eventHash || "")).toLowerCase().includes(q);
    });
  }, [rows, search, activeFilters]);

  return (
    <div>
      <div className="page-h">
        <div>
          <div className="eyebrow">Administration</div>
          <h1 className="page-title">Audit trail</h1>
          <div className="page-sub">Immutable log of every interaction with the application — UI, API, ruleset, prompts, model calls. Append-only · SHA-256 hash chain · 7-year retention (FFIEC).</div>
        </div>
        <div className="row-flex">
          <button className="btn"><Icon name="download"/> Export CSV</button>
          <button className="btn"><Icon name="shield"/> Verify chain</button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="kpi-strip">
        <div className="kpi">
          <div className="kpi-label"><Icon name="shield"/> Hash chain</div>
          <div className="kpi-value" style={{ color: "var(--ok)", fontSize: 24 }}>Intact</div>
          <div className="kpi-sub">Last verified 12 min ago · {64} blocks</div>
        </div>
        <div className="kpi">
          <div className="kpi-label"><Icon name="users"/> Active sessions</div>
          <div className="kpi-value">23</div>
          <div className="kpi-sub">9 analysts · 4 admins · 10 RM</div>
        </div>
        <div className="kpi">
          <div className="kpi-label"><Icon name="flag"/> Failed authn (24h)</div>
          <div className="kpi-value">2</div>
          <div className="kpi-sub">0 lockouts · 0 anomalies</div>
        </div>
        <div className="kpi">
          <div className="kpi-label"><Icon name="audit"/> Retention</div>
          <div className="kpi-value" style={{ fontSize: 24 }}>7y / FFIEC</div>
          <div className="kpi-sub">Append-only · KMS-anchored</div>
        </div>
      </div>

      {/* Filters */}
      <div className="card filter-card">
        <div className="filter-row">
          <FilterGroup label="Role" value={activeFilters.role} onChange={v => setActiveFilters({...activeFilters, role: v})}
            options={[{v:"all",l:"All"},{v:"admin",l:"Admin"},{v:"analyst",l:"Analyst"},{v:"rm",l:"RM"},{v:"system",l:"System"}]}/>
          <FilterGroup label="Action" value={activeFilters.action} onChange={v => setActiveFilters({...activeFilters, action: v})}
            options={[{v:"all",l:"All"},{v:"auth",l:"Auth"},{v:"case",l:"Case"},{v:"ruleset",l:"Ruleset"},{v:"export",l:"Export"},{v:"system",l:"System"}]}/>
          <div className="filter-field">
            <label className="filter-label">Range</label>
            <select className="filter-select" value={activeFilters.range} onChange={e => setActiveFilters({...activeFilters, range: e.target.value})}>
              <option value="1h">Last 1 hour</option>
              <option value="24h">Last 24 hours</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
              <option value="all">All time</option>
            </select>
          </div>
          <div style={{ marginLeft: "auto", color: "var(--ink-4)", fontSize: 12 }}>
            <b className="tnum" style={{ color: "var(--ink-2)" }}>{filtered.length}</b> of <span className="tnum">{rows.length}</span> events
          </div>
        </div>
      </div>

      {/* Audit table */}
      <div className="audit-layout">
        <div className="card audit-table-card">
          <div className="tbl-wrap">
            <table className="tbl audit-tbl">
              <thead>
                <tr>
                  <th style={{ width: 168 }}>Timestamp</th>
                  <th style={{ width: 88 }}>User</th>
                  <th style={{ width: 72 }}>Role</th>
                  <th style={{ width: 168 }}>Action</th>
                  <th>Description</th>
                  <th style={{ width: 110 }}>Customer ID</th>
                  <th style={{ width: 90 }}>Batch ID</th>
                  <th style={{ width: 100 }}>Prompt ver.</th>
                  <th style={{ width: 110 }}>Ruleset</th>
                  <th style={{ width: 92 }}>Event hash</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r, i) => (
                  <tr key={i} onClick={() => setSelected(r)} data-selected={selected && selected.id === r.id}>
                    <td className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)" }}>{r.timestamp}</td>
                    <td>{r.user}</td>
                    <td><span className={`badge b-${roleTone(r.role)}`}>{r.role}</span></td>
                    <td className="mono" style={{ fontSize: 12 }}><span className={`audit-action ${r.actionGroup}`}>{r.action}</span></td>
                    <td style={{ color: "var(--ink-2)" }}>{r.description}</td>
                    <td className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)" }}>{r.customerId || "—"}</td>
                    <td className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)" }}>{r.batchId || "—"}</td>
                    <td className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)" }}>{r.promptVersion || "—"}</td>
                    <td><span className="badge b-mute mono" style={{ fontSize: 10.5 }}>{r.ruleset}</span></td>
                    <td className="mono" style={{ fontSize: 11, color: "var(--ink-4)" }}>{(r.eventHash || "").slice(0, 8) || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Detail drawer */}
        <aside className="audit-drawer card">
          {selected ? <AuditDetail event={selected} onClose={() => setSelected(null)}/> :
            <div className="audit-empty">
              <div className="audit-empty-ico"><Icon name="audit" size={20}/></div>
              <div style={{ fontWeight: 500, marginTop: 10 }}>Select an event</div>
              <div style={{ color: "var(--ink-4)", fontSize: 12.5, marginTop: 4, maxWidth: 220 }}>Click any row to inspect headers, payload diff and the cryptographic chain proof.</div>
            </div>
          }
        </aside>
      </div>
    </div>
  );
}

function FilterGroup({ label, value, onChange, options }) {
  return (
    <div className="filter-field">
      <label className="filter-label">{label}</label>
      <div className="seg">
        {options.map(o => (
          <button key={o.v} className="seg-btn" data-active={value === o.v} onClick={() => onChange(o.v)}>{o.l}</button>
        ))}
      </div>
    </div>
  );
}

function roleTone(role) {
  return { Admin: "accent", Analyst: "info", RM: "mute", System: "warn" }[role] || "mute";
}

function AuditDetail({ event, onClose }) {
  return (
    <div className="audit-detail">
      <div className="audit-detail-h">
        <div>
          <div className="eyebrow">Event</div>
          <div style={{ fontSize: 14, fontWeight: 600, fontFamily: "var(--font-mono)", marginTop: 2 }}>{event.action}</div>
        </div>
        <button className="btn ghost" onClick={onClose} aria-label="Close"><Icon name="x"/></button>
      </div>
      <div className="audit-meta">
        <div><span>When</span><b className="mono">{event.timestamp}</b></div>
        <div><span>Actor</span><b>{event.user} <span className="muted">({event.role})</span></b></div>
        <div><span>Source</span><b className="mono">{event.source || "ui-app"}</b></div>
        <div><span>IP</span><b className="mono">{event.ip || "10.42.18.114"}</b></div>
        <div><span>Session</span><b className="mono">{event.session || "sess_2QNk4f8h…"}</b></div>
        <div><span>Trace</span><b className="mono">{event.trace || "tr_a8f3e1c2"}</b></div>
      </div>

      <div className="eyebrow" style={{ marginTop: 18 }}>Description</div>
      <div style={{ fontSize: 13, color: "var(--ink-2)", marginTop: 6 }}>{event.description}</div>

      {event.payload && <>
        <div className="eyebrow" style={{ marginTop: 18 }}>Payload</div>
        <pre className="audit-pre">{JSON.stringify(event.payload, null, 2)}</pre>
      </>}

      <div className="eyebrow" style={{ marginTop: 18 }}>Hash chain proof</div>
      <div className="hash-chain">
        <div className="hash-row"><span>prev</span><code>{event.prevHash}</code></div>
        <div className="hash-row current"><span>this</span><code>{event.eventHash}</code></div>
        <div className="hash-row"><span>next</span><code>{event.nextHash}</code></div>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
        <button className="btn" style={{ flex: 1 }}><Icon name="shield"/> Verify</button>
        <button className="btn" style={{ flex: 1 }}><Icon name="link"/> Permalink</button>
      </div>
    </div>
  );
}

window.AuditView = AuditView;
