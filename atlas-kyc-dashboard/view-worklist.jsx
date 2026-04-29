/* global React, Icon, RiskBar, Spark, MOCK */

/* ============================================================
   View A — Compliance Worklist (case queue)
   Decluttered: 3 KPIs, simpler table, no bottom-of-page noise.
   ============================================================ */
function WorklistView({ onOpenCase, search }) {
  const { useState, useMemo } = React;
  const [filter, setFilter] = useState("all"); // all | needs-me | overdue | high

  const cases = useMemo(() => {
    let list = MOCK.cases.slice();
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(c =>
        c.client.toLowerCase().includes(s) ||
        c.id.toLowerCase().includes(s) ||
        c.rm.toLowerCase().includes(s)
      );
    }
    if (filter === "needs-me")  list = list.filter(c => c.status === "Dual-approval" || c.status === "Pending review");
    if (filter === "overdue")   list = list.filter(c => c.sla.tone === "bad");
    if (filter === "high")      list = list.filter(c => c.risk === "high");
    return list;
  }, [search, filter]);

  const kpis = [
    { label: "Open cases", value: "47", sub: "across the team" },
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
            <div className="kpi-value" style={{ color: k.tone === "bad" ? "var(--bad)" : "inherit" }}>{k.value}</div>
            <div className="kpi-sub">{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="section-h" style={{ marginTop: 8 }}>
        <h3>Active queue</h3>
        <div className="chips">
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
