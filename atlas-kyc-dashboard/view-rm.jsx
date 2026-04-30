/* global React, Icon, MOCK */

/* ============================================================
   View C — RM Client Book
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

function RMView({ cases: propCases, onOpenCase }) {
  const { useState, useMemo } = React;
  const [tier, setTier] = useState("all");
  const [search, setSearch] = useState("");

  const allClients = propCases && propCases.length > 0 ? propCases : MOCK.cases.slice(0, 6);

  const clients = useMemo(() => {
    let list = allClients;
    if (tier !== "all") list = list.filter(c => c.tier === tier);
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(c => (c.client || "").toLowerCase().includes(s));
    }
    return list;
  }, [allClients, tier, search]);

  const parseAum = (v) => { const n = parseFloat(v); return isNaN(n) ? 0 : n; };
  const totalAum = allClients.reduce((s, c) => s + parseAum(c.aum), 0);
  const sorted = [...allClients].sort((a, b) => parseAum(b.aum) - parseAum(a.aum));
  const top3Aum = sorted.slice(0, 3).reduce((s, c) => s + parseAum(c.aum), 0);
  const top3Conc = totalAum > 0 ? Math.round(top3Aum / totalAum * 100) : 0;
  const onTimePct = allClients.length > 0
    ? Math.round(allClients.filter(c => c.risk !== "high").length / allClients.length * 100)
    : 0;

  return (
    <>
      <div className="page-h">
        <div>
          <div className="eyebrow">A. Mercer · Senior RM</div>
          <h1 className="page-title">Client book</h1>
        </div>
        <div className="search" role="search">
          <Icon name="search" aria-hidden="true"/>
          <input placeholder="Search clients…" value={search} onChange={e => setSearch(e.target.value)} style={{ minWidth: 200 }}/>
          {search && <button style={{ background: "none", border: "none", cursor: "pointer", padding: "0 2px", color: "var(--ink-4)" }} onClick={() => setSearch("")}><Icon name="x" size={12}/></button>}
        </div>
      </div>

      <div className="kpi-strip" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <div className="kpi">
          <div className="kpi-label">Total book AUM</div>
          <div className="kpi-value">{totalAum > 0 ? fmtAum(String(totalAum)) : "—"}</div>
          <div className="kpi-sub">{allClients.length} clients · current batch</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">High-risk clients</div>
          <div className="kpi-value">{allClients.filter(c => c.risk === "high").length}</div>
          <div className="kpi-sub">of {allClients.length} total</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Top-3 concentration</div>
          <div className="kpi-value">{top3Conc}%</div>
          <div className="kpi-sub">of book AUM</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">KYC on-time rate</div>
          <div className="kpi-value">{onTimePct}%</div>
          <div className="kpi-sub">non-high-risk · current batch</div>
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
                <div className="stat"><label>AUM</label><b>{fmtAum(c.aum)}</b></div>
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
