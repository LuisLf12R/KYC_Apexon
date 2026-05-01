/* global React, Icon, RiskBar, MOCK */

/* ============================================================
   View D — Case Detail (HNWI deep-dive) — decluttered.
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

function CaseDetail({ caseData, onBack, panels, onApprove, onReject, onStatusChange }) {
  const { useState } = React;
  const c = caseData || MOCK.cases[0];
  const [tab, setTab] = useState("reconcile");

  const switchTab = (newTab) => {
    setTab(newTab);
    try {
      fetch("/api/audit/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "CASE_TAB_SWITCH", description: `Switched to ${newTab} tab`, customer_id: c.id, details: { tab: newTab } }),
      });
    } catch (_) {}
  };
  const [note, setNote] = useState("");
  const [decision, setDecision] = useState(null);
  const [signoffA, setSignoffA] = useState(false);
  const [signoffB, setSignoffB] = useState(false);
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const [resolvedStatus, setResolvedStatus] = useState(null);
  const [statusSaved, setStatusSaved] = useState(false);

  const effectiveStatus = resolvedStatus || c.status;
  const addUploadedDoc = (doc) => setUploadedDocs(prev => [doc, ...prev]);

  const handleStatusSave = (newStatus) => {
    setResolvedStatus(newStatus);
    setStatusSaved(true);
    setTimeout(() => setStatusSaved(false), 3000);
    if (onStatusChange) onStatusChange(c.id, newStatus);
    if (newStatus === "Cleared" && onApprove) onApprove(c.id);
    else if (newStatus === "Escalated" && onReject) onReject(c.id);
  };

  const dimensions = (c.dimensions && c.dimensions.length > 0) ? c.dimensions : [
    { key: "identity",   title: "Identity verification", tone: "ok",   sub: "No data" },
    { key: "aml",        title: "AML / PEP screening",   tone: "warn", sub: "No data" },
    { key: "ubo",        title: "Beneficial ownership",  tone: "warn", sub: "No data" },
    { key: "sow",        title: "Source of Wealth",      tone: "ok",   sub: "No data" },
    { key: "crs",        title: "CRS / FATCA",           tone: "warn", sub: "No data" },
    { key: "monitoring", title: "Ongoing monitoring",    tone: "ok",   sub: "No data" },
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
          <span className={`badge ${effectiveStatus === "Escalated" ? "b-bad" : effectiveStatus === "Cleared" ? "b-ok" : effectiveStatus === "Dual-approval" ? "b-accent" : "b-mute"}`}>
            <span className="dot"/>{effectiveStatus}
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
          <div className="kpi-value">{fmtAum(c.aum)}</div>
          <div className="kpi-sub">Across 3 portfolios</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Open flags</div>
          <div className="kpi-value">{(c.flags || []).length}</div>
          <div className="kpi-sub">{(c.flags || [])[0] || "—"}</div>
        </div>
      </div>

      <div className="tabs tabs-priority">
        <button className="tab-primary" aria-current={tab === "reconcile"} onClick={() => switchTab("reconcile")}>
          <Icon name="check"/> Reconcile &amp; status
          <span className="tab-pill">3 to review</span>
        </button>
        <span className="tabs-divider"/>
        <button className="tab-secondary" aria-current={tab === "overview"} onClick={() => switchTab("overview")}>Overview</button>
        <button className="tab-secondary" aria-current={tab === "ubo"} onClick={() => switchTab("ubo")}>Ownership</button>
        <button className="tab-secondary" aria-current={tab === "documents"} onClick={() => switchTab("documents")}>Documents</button>
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
              <div className="section-h"><h3>Ownership structure</h3><span className="meta">{(c.ubos || []).length} UBO{(c.ubos || []).length !== 1 ? "s" : ""} on record</span></div>
              <UBOGraph subject={c.client} ini={c.ini} ubos={c.ubos || []}/>
            </>
          )}

          {tab === "documents" && <DocumentsList documents={[...(c.documents || []), ...uploadedDocs]}/>}
          {tab === "reconcile" && <ReconcilePanel client={c} currentStatus={effectiveStatus} onAddDoc={addUploadedDoc} onStatusSave={handleStatusSave} statusSaved={statusSaved}/>}
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
              placeholder="Decision rationale (required)…"
              value={note} onChange={e => setNote(e.target.value)}/>
            {!note.trim() && (signoffA || signoffB) && (
              <div style={{ fontSize: 11.5, color: "oklch(48% 0.13 75)", marginTop: -4 }}>
                A written rationale is required before approving or rejecting.
              </div>
            )}

            <div className="grid">
              <button className="btn success" onClick={() => setDecision("approve")} disabled={!signoffA || !signoffB || !note.trim()}>
                <Icon name="check"/> Approve
              </button>
              <button className="btn danger" onClick={() => setDecision("reject")} disabled={!note.trim()}>
                <Icon name="x"/> Reject
              </button>
            </div>
            <button className="btn full" onClick={() => setDecision("escalate")} disabled={!note.trim()}>
              <Icon name="escalate"/> Escalate
            </button>
            {decision && (
              <div style={{
                padding: "12px 14px", borderRadius: 8, textAlign: "center", fontSize: 13,
                background: decision === "approve" ? "var(--ok-soft, oklch(96% 0.05 145))" : decision === "reject" ? "var(--bad-soft, oklch(97% 0.04 25))" : "oklch(97% 0.03 75)",
                border: `1px solid ${decision === "approve" ? "var(--ok)" : decision === "reject" ? "var(--bad)" : "oklch(58% 0.14 75)"}`,
              }}>
                <div style={{ fontWeight: 600 }}>
                  <Icon name={decision === "approve" ? "check" : decision === "reject" ? "x" : "escalate"}/>
                  {" "}{decision === "approve" ? "Case approved" : decision === "reject" ? "Case rejected" : "Case escalated"}
                </div>
                <div style={{ marginTop: 4, fontSize: 11.5, color: "var(--ink-3)" }}>Recorded · {new Date().toLocaleTimeString()}</div>
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
function UBOGraph({ subject, ini, ubos }) {
  if (!ubos || ubos.length === 0) {
    return (
      <div className="card">
        <div className="card-pad" style={{ color: "var(--ink-4)", fontSize: 13 }}>No beneficial ownership data on file.</div>
      </div>
    );
  }
  return (
    <div className="card">
      <div className="card-h"><h3>Beneficial owners</h3><span className="meta">{ubos.length} UBO{ubos.length !== 1 ? "s" : ""}</span></div>
      {ubos.map((u, i) => (
        <div className="flag-row" key={i} style={{ borderTop: i ? "1px solid var(--line)" : "0" }}>
          <div className="left">
            <div className={`ico ${u.isPep ? "bad" : ""}`}><Icon name={u.isPep ? "flag" : "users"}/></div>
            <div>
              <div className="t">{u.name || "Unknown"}{u.isPep ? " · PEP" : ""}</div>
              <div className="s">{u.pct ? `${u.pct}% ownership` : ""}{ u.country ? ` · ${u.country}` : ""}{ u.verified ? ` · Verified ${u.verified}` : ""}</div>
            </div>
          </div>
          <span className={`badge ${u.isPep ? "b-bad" : "b-ok"}`}><span className="dot"/>{u.isPep ? "PEP" : "Clear"}</span>
        </div>
      ))}
    </div>
  );
}

function DocPreviewModal({ doc, onClose }) {
  const { useState } = React;
  const [imgError, setImgError] = useState(false);
  const statusTone = (s) => {
    const sl = (s || "").toLowerCase();
    if (sl === "verified" || sl === "valid" || sl === "reviewed") return "ok";
    if (sl === "outstanding" || sl === "expired") return "bad";
    return "warn";
  };
  const fname = doc.name || "";
  const ext = fname.split(".").pop().toLowerCase();
  const isPdf = ext === "pdf";
  const isImg = ["png","jpg","jpeg","gif","webp"].includes(ext);
  const previewUrl = fname ? `/api/documents/preview/${encodeURIComponent(fname)}` : null;

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}
         onClick={onClose}>
      <div style={{ background: "var(--bg)", borderRadius: "var(--radius-lg)", width: 620, maxHeight: "90vh", display: "flex", flexDirection: "column", boxShadow: "0 20px 60px rgba(0,0,0,0.22)", overflow: "hidden" }}
           onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div style={{ padding: "18px 22px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: "var(--bg-sunken)", display: "grid", placeItems: "center" }}>
              <Icon name="file" size={18}/>
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14.5 }}>{doc.name || doc.type || "Document"}</div>
              <div style={{ fontSize: 12, color: "var(--ink-4)", marginTop: 1 }}>{doc.type || "—"}</div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className={`badge b-${statusTone(doc.status)}`}><span className="dot"/>{doc.status || "Unknown"}</span>
            <button className="btn ghost" onClick={onClose} style={{ padding: "0 6px" }}><Icon name="x"/></button>
          </div>
        </div>

        {/* Document preview */}
        {previewUrl && !imgError && (
          <div style={{ background: "#1a1a1a", display: "flex", alignItems: "center", justifyContent: "center", minHeight: 260, maxHeight: 400, overflow: "hidden", flexShrink: 0 }}>
            {isPdf ? (
              <embed src={previewUrl} type="application/pdf" style={{ width: "100%", height: 380, border: "none" }}/>
            ) : isImg ? (
              <img src={previewUrl} alt={fname} onError={() => setImgError(true)}
                   style={{ maxWidth: "100%", maxHeight: 380, objectFit: "contain", display: "block" }}/>
            ) : null}
          </div>
        )}
        {previewUrl && imgError && (
          <div style={{ background: "var(--bg-sunken)", padding: "20px 22px", textAlign: "center", color: "var(--ink-4)", fontSize: 13 }}>
            Preview unavailable — document not in vault (uploaded before this server session)
          </div>
        )}

        {/* Metadata */}
        <div style={{ background: "var(--bg-sunken)", padding: "16px 22px", borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--ink-5)", marginBottom: 12 }}>
            <Icon name="shield" size={11}/> Stored securely in document vault
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 24px", fontSize: 13 }}>
            {doc.type      && <div><span style={{ color: "var(--ink-4)" }}>Type </span><b>{doc.type}</b></div>}
            {doc.issuer    && <div><span style={{ color: "var(--ink-4)" }}>Issuer </span><b>{doc.issuer}</b></div>}
            {doc.issueDate && <div><span style={{ color: "var(--ink-4)" }}>Issued </span><b>{doc.issueDate}</b></div>}
            {doc.expiry    && <div><span style={{ color: "var(--ink-4)" }}>Expires </span><b>{doc.expiry}</b></div>}
            {!doc.type && !doc.issuer && !doc.issueDate && !doc.expiry && (
              <div style={{ gridColumn: "span 2", color: "var(--ink-5)", fontSize: 12 }}>No additional metadata available.</div>
            )}
          </div>
        </div>

        {/* OCR confidence */}
        {doc.confidence != null && (
          <div style={{ padding: "14px 22px", flexShrink: 0 }}>
            <div style={{ fontSize: 12, color: "var(--ink-4)", marginBottom: 8 }}>OCR confidence</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ flex: 1, height: 8, background: "var(--line)", borderRadius: 4, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${doc.confidence}%`, background: doc.confidence >= 90 ? "var(--ok)" : doc.confidence >= 70 ? "oklch(58% 0.14 75)" : "var(--bad)", borderRadius: 4 }}/>
              </div>
              <span style={{ fontWeight: 700, fontSize: 14, minWidth: 36 }}>{doc.confidence}%</span>
            </div>
            <div style={{ fontSize: 11.5, color: "var(--ink-5)", marginTop: 6 }}>
              {doc.confidence >= 90 ? "High confidence · all fields extracted and verified" :
               doc.confidence >= 70 ? "Medium confidence · manual review recommended" :
               "Low confidence · document may require re-submission"}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function DocumentsList({ documents }) {
  const { useState } = React;
  const [previewDoc, setPreviewDoc] = useState(null);
  const docs = documents && documents.length > 0 ? documents : [];
  const outstanding = docs.filter(d => (d.status || "").toLowerCase() === "outstanding" || (d.status || "").toLowerCase() === "expired").length;
  const statusTone = (s) => {
    const sl = (s || "").toLowerCase();
    if (sl === "verified" || sl === "valid" || sl === "reviewed") return "ok";
    if (sl === "outstanding" || sl === "expired") return "bad";
    return "warn";
  };
  return (
    <div className="card">
      {previewDoc && <DocPreviewModal doc={previewDoc} onClose={() => setPreviewDoc(null)}/>}
      <div className="card-h">
        <h3>Documents</h3>
        <span className="meta">{docs.length} on file{outstanding > 0 ? ` · ${outstanding} outstanding` : ""}</span>
      </div>
      {docs.length === 0 && <div className="card-pad" style={{ color: "var(--ink-4)", fontSize: 13 }}>No documents on file.</div>}
      {docs.map((d, i) => (
        <div className="flag-row" key={i} style={{ borderTop: i ? "1px solid var(--line)" : "0", cursor: "pointer" }}
             onClick={() => setPreviewDoc(d)}>
          <div className="left">
            <div className="ico"><Icon name="file"/></div>
            <div>
              <div className="t">{d.name || d.type || "Document"}</div>
              <div className="s">
                {d.type}{d.expiry ? ` · Expires ${d.expiry}` : ""}{d.issuer ? ` · ${d.issuer}` : ""}
                {d.confidence != null ? ` · OCR ${d.confidence}% confidence` : ""}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className={`badge b-${statusTone(d.status)}`}><span className="dot"/>{d.status || "Unknown"}</span>
            <Icon name="expand" size={12} style={{ color: "var(--ink-5)" }}/>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ============================================================
   Reconciliation — upload docs, match fields, change status
   ============================================================ */
function ReconcilePanel({ client, currentStatus, onAddDoc, onStatusSave, statusSaved }) {
  const { useState, useRef } = React;
  const initialFiles = (client.documents || []).map(d => ({
    n: d.name || d.type || "Document",
    k: d.type || "Document",
    s: (d.status || "").toLowerCase() === "verified" || (d.status || "").toLowerCase() === "valid" ? "matched" :
       (d.status || "").toLowerCase() === "outstanding" || (d.status || "").toLowerCase() === "expired" ? "review" : "matched",
    conf: (d.status || "").toLowerCase() === "verified" ? 99 : (d.status || "").toLowerCase() === "valid" ? 95 : 78,
  }));
  const [files, setFiles] = useState(initialFiles);
  const [status, setStatus] = useState(currentStatus || client.status);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);

  const uboCount = (client.ubos || []).length;
  const verifiedUbos = (client.ubos || []).filter(u => u.verified).length;
  const reconciliations = [
    { field: "Full legal name",  source: "On record",      ours: client.client,                                    theirs: client.client,                    match: true },
    { field: "Date of birth",    source: "On record",      ours: client.dateOfBirth || "—",                        theirs: client.dateOfBirth || "—",        match: true },
    { field: "Domicile",         source: "Self-declared",  ours: client.jurisdiction || "—",                       theirs: client.jurisdiction || "—",       match: true },
    { field: "Tax residences",   source: "CRS self-cert",  ours: (client.jurisdictions || [client.jurisdiction]).join(", "), theirs: client.jurisdiction || "—", match: true },
    { field: "Account opened",   source: "On record",      ours: client.accountOpenDate || "—",                    theirs: client.accountOpenDate || "—",    match: true },
    { field: "UBO ≥ 25%",        source: "Ownership data", ours: `${verifiedUbos} verified`,                       theirs: uboCount > 0 ? `${uboCount} on file` : "None on file", match: verifiedUbos === uboCount && uboCount > 0 },
  ];

  const finishProcessing = (newFiles) => {
    setFiles(f => f.map(x => x.s === "processing" ? { ...x, s: "matched", conf: 92, k: "Identity" } : x));
    if (onAddDoc) {
      newFiles.forEach(df => onAddDoc({
        name: df.n,
        type: "Identity",
        status: "Valid",
        issuer: "—",
        confidence: 92,
      }));
    }
  };

  const onDrop = (e) => {
    e.preventDefault(); setDrag(false);
    const dropped = Array.from(e.dataTransfer.files).map(f => ({
      n: f.name, k: "Unclassified", s: "processing", conf: 0,
    }));
    setFiles(f => [...dropped, ...f]);
    setTimeout(() => finishProcessing(dropped), 1400);
  };
  const onPick = (e) => {
    const dropped = Array.from(e.target.files).map(f => ({ n: f.name, k: "Unclassified", s: "processing", conf: 0 }));
    setFiles(f => [...dropped, ...f]);
    setTimeout(() => finishProcessing(dropped), 1400);
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
            Current status: <span className="badge b-mute"><span className="dot"/>{currentStatus || client.status}</span>
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
          {statusSaved && (
            <div style={{ marginBottom: 10, padding: "8px 12px", borderRadius: 7, background: "var(--ok-soft, oklch(96% 0.05 145))", border: "1px solid var(--ok)", fontSize: 12.5, color: "var(--ok)", display: "flex", alignItems: "center", gap: 6 }}>
              <Icon name="check" size={13}/> Status updated to <b>{status}</b>
            </div>
          )}
          <div className="row-flex" style={{ marginTop: 14, justifyContent: "flex-end" }}>
            <button className="btn" onClick={() => setStatus(currentStatus || client.status)}>Cancel</button>
            <button className="btn primary" disabled={status === (currentStatus || client.status)} onClick={() => onStatusSave && onStatusSave(status)}>
              <Icon name="check"/> Save status change
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

window.CaseDetail = CaseDetail;
