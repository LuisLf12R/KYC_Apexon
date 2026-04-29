/* global React, Icon, RiskBar, Spark, MOCK */

/* ============================================================
   View B — Portfolio overview (executive lens) — decluttered.
   ============================================================ */
function PortfolioView({ search }) {
  const kpis = [
    { label: "HNWI clients", value: "1,284", sub: "active book" },
    { label: "Assets under KYC", value: "$24.6B", sub: "total" },
    { label: "High-risk segment", value: "8.4%", sub: "108 clients", tone: "bad" },
  ];

  return (
    <>
      <div className="page-h">
        <div>
          <div className="eyebrow">Portfolio</div>
          <h1 className="page-title">HNWI book overview</h1>
          <div className="page-sub">Aggregate compliance posture · last 90 days</div>
        </div>
      </div>

      <div className="kpi-strip" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
        {kpis.map((k, i) => (
          <div className="kpi" key={i}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value" style={{ color: k.tone === "bad" ? "var(--bad)" : "inherit" }}>{k.value}</div>
            <div className="kpi-sub">{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="section-h" style={{ marginTop: 8 }}>
        <h3>Risk distribution</h3>
        <span className="meta">1,284 clients</span>
      </div>

      <div className="card">
        <div className="card-pad">
          {[
            { l: "Low risk",    c: "var(--ok)",                n: 892, p: 69 },
            { l: "Medium risk", c: "oklch(58% 0.14 75)",       n: 284, p: 22 },
            { l: "High risk",   c: "var(--bad)",               n: 108, p: 9  },
          ].map((r, i) => (
            <div key={i} style={{ marginBottom: i === 2 ? 0 : 18 }}>
              <div className="row-flex between" style={{ marginBottom: 8 }}>
                <span style={{ fontSize: 14 }}>
                  <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 3, background: r.c, marginRight: 10, verticalAlign: "middle" }}/>
                  {r.l}
                </span>
                <span className="tnum muted" style={{ fontSize: 13 }}>{r.n} clients · {r.p}%</span>
              </div>
              <div style={{ height: 8, background: "var(--bg-active)", borderRadius: 4, overflow: "hidden" }}>
                <div style={{ width: r.p + "%", height: "100%", background: r.c }}/>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ height: "var(--d-gap)" }}/>

      <div className="section-h">
        <h3>What needs attention</h3>
        <span className="meta">unresolved compliance items</span>
      </div>

      <div className="card">
        {[
          { ico: "shield", tone: "bad",  t: "Sanctions list update — 2 matches", s: "OFAC SDN delta · 14 minutes ago" },
          { ico: "globe",  tone: "warn", t: "CRS deadline approaching",          s: "9 clients · 21 days remaining" },
          { ico: "flag",   tone: "bad",  t: "Adverse media — Client M",          s: "Reuters · regional outlet" },
          { ico: "link",   tone: "warn", t: "UBO registry change — Client T",    s: "Companies House update detected" },
        ].map((a, i) => (
          <div className="flag-row" key={i}>
            <div className="left">
              <div className={`ico ${a.tone}`}><Icon name={a.ico}/></div>
              <div>
                <div className="t">{a.t}</div>
                <div className="s">{a.s}</div>
              </div>
            </div>
            <button className="tb-btn">Review</button>
          </div>
        ))}
      </div>
    </>
  );
}

window.PortfolioView = PortfolioView;
