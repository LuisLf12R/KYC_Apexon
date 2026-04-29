/* global React, Icon, MOCK */

/* ============================================================
   View C — RM Client Book — decluttered to 6 cards, fewer stats.
   ============================================================ */
function RMView({ search, onOpenCase }) {
  const { useState, useMemo } = React;
  const [tier, setTier] = useState("all");
  const clients = useMemo(() => {
    let list = MOCK.cases.slice(0, 6);
    if (tier !== "all") list = list.filter(c => c.tier === tier);
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(c => c.client.toLowerCase().includes(s));
    }
    return list;
  }, [tier, search]);

  return (
    <>
      <div className="page-h">
        <div>
          <div className="eyebrow">A. Mercer · Senior RM</div>
          <h1 className="page-title">Client book</h1>
        </div>
        <div className="row-flex">
          <button className="tb-btn primary"><Icon name="plus"/> Onboard client</button>
        </div>
      </div>

      <div className="kpi-strip" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <div className="kpi">
          <div className="kpi-label">Net new AUM</div>
          <div className="kpi-value">+$18.4M</div>
          <div className="kpi-sub">QTD · 142% of target</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Wallet share</div>
          <div className="kpi-value">61%</div>
          <div className="kpi-sub">est. across book</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Top-3 concentration</div>
          <div className="kpi-value">48%</div>
          <div className="kpi-sub">of book AUM</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">KYC refresh on-time</div>
          <div className="kpi-value">89%</div>
          <div className="kpi-sub">trailing 12 months</div>
        </div>
      </div>

      <div className="section-h">
        <div className="chips">
          {["all", "Wealth", "UHNW", "Family Office"].map(t => (
            <button key={t} className="chip" data-active={tier === t} onClick={() => setTier(t)}>
              {t === "all" ? "All tiers" : t}
            </button>
          ))}
        </div>
        <span className="meta">{clients.length} shown</span>
      </div>

      <div className="client-grid">
        {clients.map(c => {
          const fresh = c.risk === "high"   ? { c: "var(--bad)",          l: "Review due" } :
                        c.risk === "medium" ? { c: "oklch(58% 0.14 75)",  l: "Refresh in 30d" } :
                                              { c: "var(--ok)",           l: "Up to date" };
          return (
            <div className="client-card" key={c.id} onClick={() => onOpenCase(c)}>
              <div className="top">
                <div className="ini-lg">{c.ini}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="name">{c.client}</div>
                  <div className="meta">{c.tier} · {c.jurisdiction}</div>
                </div>
                <span className={`badge ${c.risk === "high" ? "b-bad" : c.risk === "medium" ? "b-warn" : "b-ok"}`}>
                  <span className="dot"/>{c.risk}
                </span>
              </div>
              <div className="stats" style={{ gridTemplateColumns: "1fr 1fr" }}>
                <div className="stat"><label>AUM</label><b>${c.aum}M</b></div>
                <div className="stat"><label>Next review</label><b style={{ fontSize: 13, fontWeight: 400 }} className="tnum">{c.nextReview}</b></div>
              </div>
              <div className="row">
                <div className="kyc-fresh">
                  <span className="dot" style={{ background: fresh.c }}/>{fresh.l}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

window.RMView = RMView;
