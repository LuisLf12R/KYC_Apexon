/* global React, Icon, RiskBar, MOCK */

/* ============================================================
   View D — Case Detail (HNWI deep-dive) — decluttered.
   ============================================================ */
function CaseDetail({ caseData, onBack, panels }) {
  const { useState } = React;
  const c = caseData || MOCK.cases[0];
  const [tab, setTab] = useState("reconcile");
  const [note, setNote] = useState("");
  const [decision, setDecision] = useState(null);
  const [signoffA, setSignoffA] = useState(false);
  const [signoffB, setSignoffB] = useState(false);

  const dimensions = [
    { key: "identity",   title: "Identity verification", tone: "ok",   sub: "Passport verified · OCR 99.2%" },
    { key: "aml",        title: "AML / PEP screening",   tone: "warn", sub: "Close associate match — review" },
    { key: "ubo",        title: "Beneficial ownership",  tone: "warn", sub: "3 layers · PSC confirmation pending" },
    { key: "sow",        title: "Source of Wealth",     tone: "ok",   sub: "Founder exit (2019) · documented" },
    { key: "crs",        title: "CRS / FATCA",          tone: "warn", sub: "Tax residence: GB, CH, AE" },
    { key: "monitoring", title: "Ongoing monitoring",   tone: "ok",   sub: "Annual + event-driven" },
  ];

  return (
    <>
      <div className="page-h">
        <div>
          <div className="row-flex" style={{ marginBottom: 8 }}>
            <button className="btn ghost" onClick={onBack} style={{ height: 28, padding: "0 8px" }}>
              <Icon name="chevronL"/> Back
            </button>
            <span className="cell-id">{c.id}</span>
          </div>
          <h1 className="page-title">{c.client}</h1>
          <div className="page-sub">
            {c.tier} · {c.type} · {c.jurisdiction} · RM {(c.rm || "").split(" — ")[1] || c.rm}
          </div>
        </div>
        <div className="row-flex">
          <span className={`badge ${c.status === "Escalated" ? "b-bad" : c.status === "Dual-approval" ? "b-accent" : "b-mute"}`}>
            <span className="dot"/>{c.status}
          </span>
        </div>
      </div>

      <div className="kpi-strip" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
        <div className="kpi">
          <div className="kpi-label">Risk score</div>
          <div className="kpi-value">{c.riskScore}<span className="muted" style={{ fontSize: 14, marginLeft: 4 }}>/100</span></div>
          <div className="kpi-sub" style={{ marginTop: 6 }}><RiskBar level={c.risk} score={c.risk.toUpperCase()}/></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Assets under mgmt.</div>
          <div className="kpi-value">${c.aum}M</div>
          <div className="kpi-sub">Across 3 portfolios</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Open flags</div>
          <div className="kpi-value">{(c.flags || []).length}</div>
          <div className="kpi-sub">{(c.flags || [])[0] || "—"}</div>
        </div>
      </div>

      <div className="tabs tabs-priority">
        <button className="tab-primary" aria-current={tab === "reconcile"} onClick={() => setTab("reconcile")}>
          <Icon name="check"/> Reconcile &amp; status
          <span className="tab-pill">3 to review</span>
        </button>
        <span className="tabs-divider"/>
        <button className="tab-secondary" aria-current={tab === "overview"} onClick={() => setTab("overview")}>Overview</button>
        <button className="tab-secondary" aria-current={tab === "ubo"} onClick={() => setTab("ubo")}>Ownership</button>
        <button className="tab-secondary" aria-current={tab === "documents"} onClick={() => setTab("documents")}>Documents</button>
      </div>

      <div className="detail-grid">
        <div>
          {tab === "overview" && (
            <div className="card">
              <div className="card-h"><h3>KYC dimensions</h3><span className="meta">click to drill in</span></div>
              {dimensions.filter(d => panels[d.key] !== false).map((d, i) => (
                <div className="flag-row" key={d.key} style={{ borderTop: i ? "1px solid var(--line)" : "0" }}>
                  <div className="left">
                    <div className={`ico ${d.tone === "ok" ? "" : d.tone === "warn" ? "warn" : "bad"}`}>
                      <Icon name={d.tone === "ok" ? "check" : "flag"}/>
                    </div>
                    <div>
                      <div className="t">{d.title}</div>
                      <div className="s">{d.sub}</div>
                    </div>
                  </div>
                  <span className={`badge ${d.tone === "ok" ? "b-ok" : "b-warn"}`}>
                    <span className="dot"/>{d.tone === "ok" ? "Pass" : "Attention"}
                  </span>
                </div>
              ))}
            </div>
          )}

          {tab === "ubo" && (
            <>
              <div className="section-h"><h3>Ownership structure</h3><span className="meta">3 layers · click a node</span></div>
              <UBOGraph subject={c.client} ini={c.ini}/>
            </>
          )}

          {tab === "documents" && <DocumentsList/>}
          {tab === "reconcile" && <ReconcilePanel client={c}/>}
        </div>

        {/* Right rail — approval workflow only */}
        <div className="col-flex">
          <div className="approval">
            <div className="row-flex between">
              <h4>Decision</h4>
              <span className="badge b-accent">Dual-approval</span>
            </div>
            <div className="muted" style={{ fontSize: 13 }}>
              UHNW threshold requires sign-off from two officers.
            </div>
            <div className={`approver ${signoffA ? "signed" : ""}`}>
              <div className="avatar" style={{ width: 26, height: 26, fontSize: 10 }}>JM</div>
              <div style={{ flex: 1 }}>
                <b>J. Marlow</b>
                <div className="muted" style={{ fontSize: 11.5 }}>{signoffA ? "Signed · 14:22" : "Awaiting signature"}</div>
              </div>
              {!signoffA && <button className="btn" style={{ height: 28 }} onClick={() => setSignoffA(true)}>Sign</button>}
              {signoffA && <Icon name="check" color="var(--ok)"/>}
            </div>
            <div className={`approver ${signoffB ? "signed" : ""}`}>
              <div className="avatar" style={{ width: 26, height: 26, fontSize: 10, background: "linear-gradient(135deg, oklch(72% 0.10 30), oklch(58% 0.16 50))" }}>KT</div>
              <div style={{ flex: 1 }}>
                <b>K. Tran</b>
                <div className="muted" style={{ fontSize: 11.5 }}>{signoffB ? "Signed · 14:31" : "Pending"}</div>
              </div>
              {!signoffB && <button className="btn" style={{ height: 28 }} onClick={() => setSignoffB(true)} disabled={!signoffA}>Sign</button>}
              {signoffB && <Icon name="check" color="var(--ok)"/>}
            </div>

            <textarea
              placeholder="Decision rationale…"
              value={note} onChange={e => setNote(e.target.value)}/>

            <div className="grid">
              <button className="btn success" onClick={() => setDecision("approve")} disabled={!signoffA || !signoffB}>
                <Icon name="check"/> Approve
              </button>
              <button className="btn danger" onClick={() => setDecision("reject")}>
                <Icon name="x"/> Reject
              </button>
            </div>
            <button className="btn full" onClick={() => setDecision("escalate")}>
              <Icon name="escalate"/> Escalate
            </button>
            {decision && (
              <div className="muted" style={{ fontSize: 12, textAlign: "center" }}>
                Recorded: <b style={{ color: "var(--ink)" }}>{decision}</b>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

/* ============================================================
   UBO Graph
   ============================================================ */
function UBOGraph({ subject, ini }) {
  const nodes = [
    { id: "subject", x: 50, y: 14, t: "subject", b: subject,                s: "Settlor & UBO · GB",       pct: "" },
    { id: "trust",   x: 50, y: 42, t: "",        b: "Family Trust (JE)",    s: "Discretionary · 2014",     pct: "" },
    { id: "spv1",    x: 25, y: 72, t: "",        b: "Holding SPV (KY)",     s: "100% owned by Trust",      pct: "100%" },
    { id: "spv2",    x: 75, y: 72, t: "flag",    b: "Investment SPV (CH)",  s: "PSC confirmation pending", pct: "100%" },
  ];
  const edges = [["subject", "trust"], ["trust", "spv1"], ["trust", "spv2"]];
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  return (
    <div className="ubo">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none">
        {edges.map(([a, b], i) => {
          const A = byId[a], B = byId[b];
          return (
            <line key={i} x1={A.x} y1={A.y + 3} x2={B.x} y2={B.y - 3}
                  stroke="var(--line-strong)" strokeWidth="0.2"
                  vectorEffect="non-scaling-stroke"/>
          );
        })}
      </svg>
      {nodes.map(n => (
        <div key={n.id} className={`node ${n.t}`} style={{ left: `${n.x}%`, top: `${n.y}%`, transform: "translate(-50%, -50%)" }}>
          <b>{n.b} {n.pct && <span className="pct">{n.pct}</span>}</b>
          <small>{n.s}</small>
        </div>
      ))}
    </div>
  );
}

function DocumentsList() {
  const docs = [
    { n: "Passport — primary holder",        s: "Verified",      d: "01 Mar 2026", tone: "ok" },
    { n: "Proof of address",                 s: "Verified",      d: "12 Apr 2026", tone: "ok" },
    { n: "SPA — 2019 founder exit",          s: "Reviewed",      d: "22 Apr 2026", tone: "ok" },
    { n: "Trust deed (Jersey)",              s: "Reviewed",      d: "11 Mar 2026", tone: "warn" },
    { n: "PSC confirmation — Investment SPV", s: "Outstanding",   d: "—",           tone: "bad" },
    { n: "CRS self-certification",           s: "Valid",         d: "12 Apr 2026", tone: "ok" },
  ];
  return (
    <div className="card">
      <div className="card-h"><h3>Documents</h3><span className="meta">6 on file · 1 outstanding</span></div>
      {docs.map((d, i) => (
        <div className="flag-row" key={i} style={{ borderTop: i ? "1px solid var(--line)" : "0" }}>
          <div className="left">
            <div className="ico"><Icon name="file"/></div>
            <div>
              <div className="t">{d.n}</div>
              <div className="s">Updated {d.d}</div>
            </div>
          </div>
          <span className={`badge ${d.tone === "ok" ? "b-ok" : d.tone === "warn" ? "b-warn" : "b-bad"}`}><span className="dot"/>{d.s}</span>
        </div>
      ))}
    </div>
  );
}

/* ============================================================
   Reconciliation — upload docs, match fields, change status
   ============================================================ */
function ReconcilePanel({ client }) {
  const { useState, useRef } = React;
  const [files, setFiles] = useState([
    { n: "passport_2026.pdf",       k: "Identity",        s: "matched",   conf: 99 },
    { n: "utility_bill_apr.pdf",    k: "Address",         s: "matched",   conf: 96 },
    { n: "trust_deed_redacted.pdf", k: "Structure",       s: "review",    conf: 78 },
  ]);
  const [status, setStatus] = useState(client.status);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);

  const reconciliations = [
    { field: "Full legal name",  source: "Passport OCR",        ours: client.client,                  theirs: client.client,                match: true  },
    { field: "Date of birth",    source: "Passport OCR",        ours: "1968-04-12",                   theirs: "1968-04-12",                 match: true  },
    { field: "Domicile",         source: "Self-declared",       ours: client.jurisdiction,            theirs: client.jurisdiction,          match: true  },
    { field: "Tax residences",   source: "CRS self-cert",       ours: (client.jurisdictions || [client.jurisdiction]).join(", "), theirs: client.jurisdiction || "—", match: true  },
    { field: "Source of Wealth", source: "SPA + financials",    ours: "Founder exit (2019)",          theirs: "Founder exit (2019)",        match: true  },
    { field: "UBO ≥ 25%",        source: "Trust deed + PSC",    ours: "2 verified",                   theirs: "PSC pending",                match: false },
  ];

  const onDrop = (e) => {
    e.preventDefault(); setDrag(false);
    const dropped = Array.from(e.dataTransfer.files).map(f => ({
      n: f.name, k: "Unclassified", s: "processing", conf: 0,
    }));
    setFiles(f => [...dropped, ...f]);
    setTimeout(() => setFiles(f => f.map(x => x.s === "processing" ? { ...x, s: "matched", conf: 92, k: "Identity" } : x)), 1400);
  };
  const onPick = (e) => {
    const dropped = Array.from(e.target.files).map(f => ({ n: f.name, k: "Unclassified", s: "processing", conf: 0 }));
    setFiles(f => [...dropped, ...f]);
    setTimeout(() => setFiles(f => f.map(x => x.s === "processing" ? { ...x, s: "matched", conf: 92, k: "Identity" } : x)), 1400);
  };

  const allMatched = files.every(f => f.s === "matched") && reconciliations.every(r => r.match);

  return (
    <>
      <div className="card" style={{ marginBottom: "var(--d-gap)" }}>
        <div className="card-h"><h3>Upload supporting documents</h3><span className="meta">PDF, JPG, PNG · OCR runs automatically</span></div>
        <div className="card-pad">
          <div
            onDragOver={e => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            style={{
              border: `1.5px dashed ${drag ? "var(--accent)" : "var(--line-strong)"}`,
              background: drag ? "var(--accent-soft)" : "var(--bg-sunken)",
              borderRadius: "var(--radius-lg)",
              padding: "32px 20px",
              textAlign: "center",
              cursor: "pointer",
              transition: "all .15s",
            }}>
            <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>Drop files here, or click to browse</div>
            <div className="muted" style={{ fontSize: 12.5 }}>Files are OCR'd, classified, and reconciled against on-record fields</div>
            <input ref={inputRef} type="file" multiple style={{ display: "none" }} onChange={onPick}/>
          </div>

          {files.length > 0 && (
            <div style={{ marginTop: 16 }}>
              {files.map((f, i) => (
                <div key={i} className="row-flex between" style={{ padding: "10px 4px", borderTop: i ? "1px dashed var(--line)" : "0" }}>
                  <div className="row-flex">
                    <div className="ico" style={{ width: 28, height: 28, borderRadius: 7, background: "var(--bg-sunken)", display: "grid", placeItems: "center" }}><Icon name="file"/></div>
                    <div>
                      <div style={{ fontSize: 13.5, fontWeight: 500 }}>{f.n}</div>
                      <div className="muted" style={{ fontSize: 12 }}>{f.k} · {f.s === "processing" ? "OCR running…" : `OCR ${f.conf}% confidence`}</div>
                    </div>
                  </div>
                  <span className={`badge ${f.s === "matched" ? "b-ok" : f.s === "review" ? "b-warn" : "b-mute"}`}>
                    <span className="dot"/>{f.s === "matched" ? "Matched" : f.s === "review" ? "Needs review" : "Processing"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card" style={{ marginBottom: "var(--d-gap)" }}>
        <div className="card-h"><h3>Field reconciliation</h3><span className="meta">on-record vs. extracted from docs</span></div>
        <table className="tbl">
          <thead>
            <tr>
              <th>Field</th>
              <th>On record</th>
              <th>Extracted</th>
              <th style={{ width: 130 }}>Source</th>
              <th style={{ width: 110 }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {reconciliations.map((r, i) => (
              <tr key={i} style={{ cursor: "default" }}>
                <td><b style={{ fontWeight: 500 }}>{r.field}</b></td>
                <td className="muted">{r.ours}</td>
                <td>{r.theirs}</td>
                <td className="muted" style={{ fontSize: 12.5 }}>{r.source}</td>
                <td>
                  <span className={`badge ${r.match ? "b-ok" : "b-warn"}`}>
                    <span className="dot"/>{r.match ? "Match" : "Mismatch"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div className="card-h"><h3>Update client status</h3><span className="meta">applies to case {client.id}</span></div>
        <div className="card-pad">
          <div className="muted" style={{ fontSize: 13, marginBottom: 14 }}>
            Current status: <span className="badge b-mute"><span className="dot"/>{client.status}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10, marginBottom: 14 }}>
            {[
              { v: "Awaiting docs",   l: "Awaiting docs",      tone: "warn" },
              { v: "In remediation",  l: "In remediation",     tone: "info" },
              { v: "Dual-approval",   l: "Ready for approval", tone: "accent", disabled: !allMatched },
              { v: "Escalated",       l: "Escalate",           tone: "bad" },
            ].map(s => (
              <button
                key={s.v}
                onClick={() => !s.disabled && setStatus(s.v)}
                disabled={s.disabled}
                className="btn"
                style={{
                  height: 44,
                  justifyContent: "flex-start",
                  borderColor: status === s.v ? "var(--ink)" : "var(--line)",
                  background: status === s.v ? "var(--bg-hover)" : "var(--bg)",
                  opacity: s.disabled ? 0.45 : 1,
                  cursor: s.disabled ? "not-allowed" : "pointer",
                }}>
                <span className={`badge ${s.tone === "bad" ? "b-bad" : s.tone === "warn" ? "b-warn" : s.tone === "info" ? "b-info" : "b-accent"}`}>
                  <span className="dot"/>{s.l}
                </span>
                {status === s.v && <Icon name="check" color="var(--ok)"/>}
              </button>
            ))}
          </div>
          {!allMatched && (
            <div className="muted" style={{ fontSize: 12.5, padding: "10px 12px", background: "var(--warn-soft)", borderRadius: 8, color: "oklch(48% 0.13 75)" }}>
              Resolve outstanding mismatches before marking ready for approval.
            </div>
          )}
          <div className="row-flex" style={{ marginTop: 14, justifyContent: "flex-end" }}>
            <button className="btn">Cancel</button>
            <button className="btn primary" disabled={status === client.status}>
              <Icon name="check"/> Save status change
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

window.CaseDetail = CaseDetail;
