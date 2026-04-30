/* global React, Icon */

const _BATCH_API = ((window.__CONFIG__ || {}).apiUrl != null) ? (window.__CONFIG__ || {}).apiUrl : "";

function BatchView({ onBatchComplete }) {
  const { useState, useRef, useMemo, useCallback } = React;

  const [files, setFiles]               = useState([]);
  const [dragOver, setDragOver]         = useState(false);
  const [running, setRunning]           = useState(false);
  const [runMsg, setRunMsg]             = useState("");
  const [institutions, setInstitutions] = useState([]);
  const [institutionId, setInstitutionId] = useState("");
  const inputRef = useRef(null);

  const token = useCallback(() => localStorage.getItem("auth_token"), []);

  // Fetch institutions once on mount
  React.useEffect(() => {
    fetch(_BATCH_API + "/api/institutions", {
      headers: { Authorization: `Bearer ${token()}` },
    })
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        const list = Array.isArray(data) ? data : [];
        setInstitutions(list);
        if (list.length > 0) setInstitutionId(list[0].id);
      })
      .catch(() => {});
  }, [token]);

  const uploadFile = useCallback(async (file) => {
    const id = `f_${Date.now()}_${Math.random()}`;
    setFiles(prev => [...prev, { id, name: file.name, size: file.size, status: "uploading", rows: 0, datasetType: null, message: "" }]);

    const form = new FormData();
    form.append("files", file);
    try {
      const res = await fetch(_BATCH_API + "/api/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${token()}` },
        body: form,
      });
      let json;
      try { json = await res.json(); } catch { json = {}; }
      const r = json.results?.[0];
      if (!res.ok || !r) throw new Error(json.detail || `HTTP ${res.status}`);
      setFiles(prev => prev.map(f => f.id === id ? {
        ...f, status: r.status, rows: r.rows,
        datasetType: r.dataset_type, message: r.message,
      } : f));
    } catch (err) {
      setFiles(prev => prev.map(f => f.id === id ? { ...f, status: "error", message: err.message } : f));
    }
  }, [token]);

  const addFiles = useCallback((list) => {
    [...list].forEach(f => uploadFile(f));
  }, [uploadFile]);

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragOver(false);
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
  }, [addFiles]);

  const runBatch = useCallback(async () => {
    const okFiles = files.filter(f => f.status === "ok");
    if (!okFiles.length) return;
    setRunning(true); setRunMsg("Running KYC evaluation…");
    try {
      const res = await fetch(_BATCH_API + "/api/kyc/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token()}` },
        body: JSON.stringify({ institution_id: institutionId }),
      });
      let json;
      try { json = await res.json(); } catch { json = {}; }
      if (!res.ok) throw new Error(json.detail || `HTTP ${res.status}`);
      setRunMsg(`Done — ${json.summary?.total ?? 0} cases evaluated`);
      if (onBatchComplete) onBatchComplete(json.results || [], json.summary || {});
    } catch (err) {
      setRunMsg(`Error: ${err.message}`);
    }
    setRunning(false);
  }, [files, token, institutionId, onBatchComplete]);

  const totals = useMemo(() => {
    const ok = files.filter(f => f.status === "ok");
    return { files: files.length, ok: ok.length, rows: ok.reduce((a, b) => a + b.rows, 0) };
  }, [files]);

  const canRun = !running && totals.ok > 0;

  return (
    <div className="batch-page">
      <div className="page-h">
        <div>
          <div className="eyebrow">Operations</div>
          <h1 className="page-title">Batch upload</h1>
          <div className="page-sub">Drop KYC data files — CSV, Excel, JSON, or documents (PDF/images). Each file is processed immediately on drop. Press <b>Run batch</b> to evaluate all loaded customers.</div>
        </div>
      </div>

      {institutions.length > 0 && (
        <div className="row-flex" style={{ marginBottom: 16, gap: 10 }}>
          <label style={{ fontSize: 13, fontWeight: 500, color: "var(--ink-2)" }}>Institution</label>
          <select
            value={institutionId}
            onChange={e => setInstitutionId(e.target.value)}
            style={{
              height: 34, padding: "0 10px", border: "1px solid var(--line)",
              borderRadius: 8, background: "var(--bg)", fontSize: 13,
              color: "var(--ink)", cursor: "pointer", minWidth: 200,
            }}
          >
            {institutions.map(inst => (
              <option key={inst.id} value={inst.id}>{inst.label || inst.id}</option>
            ))}
          </select>
          <span style={{ fontSize: 12, color: "var(--ink-4)" }}>
            {institutions.length} institution{institutions.length !== 1 ? "s" : ""} available
          </span>
        </div>
      )}

      <div
        className={`dropzone ${dragOver ? "is-over" : ""} ${files.length ? "has-files" : ""}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button" tabIndex={0}
        onKeyDown={e => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        aria-label="Upload batch files"
      >
        <input ref={inputRef} type="file" multiple
          accept=".csv,.xlsx,.xls,.json,.jsonl,.pdf,.png,.jpg,.jpeg,.tif,.tiff"
          style={{ display: "none" }}
          onChange={e => e.target.files && addFiles(e.target.files)} />
        <div className="dz-ico"><Icon name="upload" size={28}/></div>
        <div className="dz-title">Drop files here</div>
        <div className="dz-sub">or <span className="lnk">browse from your computer</span></div>
        <div className="dz-meta">
          <span>CSV · XLSX · JSON · PDF · PNG · JPG</span>
        </div>
      </div>

      {files.length > 0 && (
        <div className="batch-summary card" style={{ marginTop: "var(--d-gap)" }}>
          <div className="bs-stats">
            <div><span className="eyebrow">Files</span><b>{totals.files}</b></div>
            <div><span className="eyebrow">Processed</span><b style={{ color: "var(--ok)" }}>{totals.ok}</b></div>
            <div><span className="eyebrow">Rows</span><b className="tnum">{totals.rows.toLocaleString()}</b></div>
          </div>
          <div className="row-flex" style={{ gap: 8 }}>
            {runMsg && <span style={{ fontSize: 12.5, color: "var(--ink-3)" }}>{runMsg}</span>}
            <button className="btn ghost" onClick={() => setFiles([])} disabled={running}>Clear all</button>
            <button className="btn primary" onClick={runBatch} disabled={!canRun}>
              {running ? <>Running…</> : <><Icon name="check"/> Run batch ({totals.ok})</>}
            </button>
          </div>
        </div>
      )}

      {files.length > 0 && (
        <div className="card" style={{ marginTop: "var(--d-gap)" }}>
          <div className="card-h">
            <h3>Files in this batch</h3>
            <span style={{ fontSize: 12, color: "var(--ink-4)" }}>{files.length} file{files.length !== 1 ? "s" : ""}</span>
          </div>
          <table className="tbl">
            <thead>
              <tr>
                <th>Filename</th>
                <th style={{ width: 110 }}>Size</th>
                <th style={{ width: 120 }}>Dataset type</th>
                <th style={{ width: 90 }}>Rows</th>
                <th style={{ width: 130 }}>Status</th>
                <th style={{ width: 60 }}></th>
              </tr>
            </thead>
            <tbody>
              {files.map(f => (
                <tr key={f.id}>
                  <td>
                    <div className="row-flex" style={{ gap: 10 }}>
                      <div className="file-ico"><Icon name="file"/></div>
                      <div>
                        <div style={{ fontSize: 13.5, fontWeight: 500 }}>{f.name}</div>
                        {f.message && f.status !== "ok" && (
                          <div style={{ fontSize: 11.5, color: f.status === "error" ? "var(--bad)" : "var(--ink-4)" }}>{f.message}</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>{prettySize(f.size)}</td>
                  <td style={{ fontSize: 12 }}>{f.datasetType || "—"}</td>
                  <td className="mono tnum">{f.rows > 0 ? f.rows.toLocaleString() : "—"}</td>
                  <td>
                    {f.status === "uploading" && <span className="badge b-accent"><span className="dot pulse"/>uploading</span>}
                    {f.status === "ok"        && <span className="badge b-ok"><span className="dot"/>ready</span>}
                    {f.status === "error"     && <span className="badge b-bad">error</span>}
                    {f.status === "rejected"  && <span className="badge b-bad">rejected</span>}
                  </td>
                  <td>
                    <button className="btn ghost" style={{ height: 26, padding: "0 8px" }}
                      onClick={() => setFiles(prev => prev.filter(x => x.id !== f.id))}
                      aria-label="Remove">
                      <Icon name="x" size={14}/>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function prettySize(b) {
  if (!b) return "—";
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1048576).toFixed(1)} MB`;
}

window.BatchView = BatchView;
