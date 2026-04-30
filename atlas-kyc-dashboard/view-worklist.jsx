/* global React, Icon, RiskBar, Spark, MOCK */

/* ============================================================
   View A — Compliance Worklist (case queue)
   Decluttered: 3 KPIs, simpler table, no bottom-of-page noise.
   ============================================================ */
function fmtAum(v) {
  const n = parseFloat(v);
  if (!v || isNaN(n) || n === 0) return "—";
  if (n >= 1e12) return "$" + (n / 1e12).toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "T";
  if (n >= 1e9)  return "$" + (n / 1e9).toLocaleString("en-US",  { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "B";
  if (n >= 1e6)  return "$" + (n / 1e6).toLocaleString("en-US",  { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "M";
  if (n >= 1e3)  return "$" + (n / 1e3).toLocaleString("en-US",  { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "K";
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function WorklistView({ onOpenCase, cases: propCases, kpiData, onApprove, onReject }) {
  const { useState, useMemo } = React;
  const [filter, setFilter] = useState("all"); // all | needs-me | overdue | high
  const [search, setSearch] = useState("");

  const source = propCases || MOCK.cases;

  const cases = useMemo(() => {
    let list = source.slice();
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(c =>
        c.client.toLowerCase().includes(s) ||
        c.id.toLowerCase().includes(s) ||
        (c.rm || "").toLowerCase().includes(s)
      );
    }
    if (filter === "needs-me")  list = list.filter(c => c.status === "Dual-approval" || c.status === "Pending review");
    if (filter === "overdue")   list = list.filter(c => c.sla.tone === "bad");
    if (filter === "high")      list = list.filter(c => c.risk === "high");
    return list;
  }, [source, search, filter]);

  const kpis = kpiData ? [
    { label: "Open cases",       value: String(kpiData.total      ?? 0), sub: "across the team" },
    { label: "Flagged",          value: String(kpiData.flagged    ?? 0), sub: "escalated or rejected" },
    { label: "Ready to approve", value: String(kpiData.reviewCount ?? 0), sub: "awaiting sign-off" },
    { label: "Pass rate",        value: `${kpiData.passRate ?? 0}%`,      sub: "in this batch" },
  ] : [
    { label: "Open cases",       value: "47",   sub: "across the team" },
    { label: "Pending docs",     value: "12",   sub: "awaiting client upload" },
    { label: "Ready to approve", value: "8",    sub: "reconciled, awaiting sign-off" },
    { label: "Avg. cycle time",  value: "3.4d", sub: "rolling 30 days" },
  ];

  return (
    <>
      <div className="page-h">
        <div>
          <div className="eyebrow">Worklist</div>
          <h1 className="page-title">KYC case queue</h1>
          <div className="page-sub">High Net Worth Individuals · {new Date().toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short", year: "numeric" })}</div>
        </div>
      </div>

      <div className="kpi-strip" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        {kpis.map((k, i) => (
          <div className="kpi" key={i}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value" style={{ color: k.tone === "bad" ? "var(--bad)" : "inherit" }}>{k.value}</div>
            <div className="kpi-sub">{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="section-h" style={{ marginTop: 8, gap: 16 }}>
        <h3>Active queue</h3>
        <div className="chips" style={{ marginLeft: 8 }}>
          {[
            { v: "all",      l: "All" },
            { v: "needs-me", l: "Needs my action" },
            { v: "overdue",  l: "Overdue" },
            { v: "high",     l: "High risk" },
          ].map(c => (
            <button key={c.v} className="chip" data-active={filter === c.v}
              onClick={() => setFilter(c.v)}>{c.l}</button>
          ))}
        </div>
        <div className="search" role="search" style={{ marginLeft: "auto" }}>
          <Icon name="search" aria-hidden="true"/>
          <input placeholder="Search clients, case IDs, RMs…" value={search} onChange={e => setSearch(e.target.value)} style={{ minWidth: 220 }}/>
          {search && <button style={{ background: "none", border: "none", cursor: "pointer", padding: "0 2px", color: "var(--ink-4)" }} onClick={() => setSearch("")}><Icon name="x" size={12}/></button>}
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
                {(onApprove || onReject) && <th style={{ width: 160 }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {cases.slice(0, 8).map(c => (
                <tr key={c.id} onClick={() => onOpenCase(c)}>
                  <td>
                    <div className="cell-client">
                      <div className="ini">{c.ini}</div>
                      <div>
                        <b>{c.client}</b>
                        <small>{c.tier} · {c.jurisdiction}</small>
                      </div>
                    </div>
                  </td>
                  <td className="cell-num">{fmtAum(c.aum)}</td>
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
                  {(onApprove || onReject) && (
                    <td>
                      <div className="row-flex" style={{ gap: 6 }}>
                        {onApprove && c.status !== "Cleared" && (
                          <button className="btn" style={{ height: 26, padding: "0 10px", fontSize: 12 }}
                            onClick={e => { e.stopPropagation(); onApprove(c.id); }}>
                            Approve
                          </button>
                        )}
                        {onReject && c.status !== "Escalated" && (
                          <button className="btn" style={{ height: 26, padding: "0 10px", fontSize: 12, color: "var(--bad)", borderColor: "var(--bad)" }}
                            onClick={e => { e.stopPropagation(); onReject(c.id); }}>
                            Reject
                          </button>
                        )}
                      </div>
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

window.WorklistView = WorklistView;
