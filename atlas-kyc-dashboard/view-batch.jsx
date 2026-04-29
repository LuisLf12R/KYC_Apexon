/* global React, Icon */

/* ============================================================
   Batch upload — single-purpose tool
   Drop a CSV/XLSX of cases. Validate. Run.
   ============================================================ */
function BatchView() {
  const { useState, useRef, useMemo } = React;
  const [files, setFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [running, setRunning] = useState(false);
  const inputRef = useRef(null);

  function addFiles(list) {
    const next = [...list].map((f, i) => {
      const ok = /\.(csv|xlsx|xls|json|jsonl|pdf|png|jpg|jpeg|tif|tiff|docx)$/i.test(f.name);
      const rows = ok ? Math.floor(20 + Math.random() * 480) : 0;
      const errs = ok ? Math.floor(Math.random() * 4) : 0;
      const warns = ok ? Math.floor(Math.random() * 8) : 0;
      return {
        id: `f_${Date.now()}_${i}`,
        name: f.name,
        size: f.size,
        type: ok ? "ok" : "bad",
        rows,
        errs,
        warns,
        status: "ready", // ready | running | done | failed
      };
    });
    setFiles(prev => [...prev, ...next]);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
  }

  function remove(id) {
    setFiles(prev => prev.filter(f => f.id !== id));
  }

  function clearAll() {
    setFiles([]);
  }

  function runAll() {
    if (running) return;
    setRunning(true);
    setFiles(prev => prev.map(f => f.type === "ok" ? { ...f, status: "running" } : f));
    setTimeout(() => {
      setFiles(prev => prev.map(f => f.type === "ok" ? { ...f, status: "done" } : f));
      setRunning(false);
    }, 1600);
  }

  const totals = useMemo(() => {
    const valid = files.filter(f => f.type === "ok");
    return {
      files: files.length,
      valid: valid.length,
      rows: valid.reduce((a, b) => a + b.rows, 0),
      errs: valid.reduce((a, b) => a + b.errs, 0),
      warns: valid.reduce((a, b) => a + b.warns, 0),
    };
  }, [files]);

  return (
    <div className="batch-page">
      <div className="page-h">
        <div>
          <div className="eyebrow">Operations</div>
          <h1 className="page-title">Batch upload</h1>
          <div className="page-sub">Upload structured data files or documents for analysis and customer linking. Files are validated against <span className="mono" style={{ fontSize: 12.5 }}>kyc-rules-v2.1</span> before any record is queued — nothing runs until you press <b>Run batch</b>.</div>
        </div>
      </div>

      {/* Dropzone */}
      <div
        className={`dropzone ${dragOver ? "is-over" : ""} ${files.length ? "has-files" : ""}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={e => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
        aria-label="Upload batch files"
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".csv,.xlsx,.xls,.json,.jsonl,.pdf,.png,.jpg,.jpeg,.tif,.tiff,.docx"
          style={{ display: "none" }}
          onChange={e => e.target.files && addFiles(e.target.files)}
        />
        <div className="dz-ico"><Icon name="upload" size={28}/></div>
        <div className="dz-title">Drop files here</div>
        <div className="dz-sub">or <span className="lnk">browse from your computer</span></div>
        <div className="dz-meta">
          <span>200 MB per file</span>
          <span className="sep">·</span>
          <span>CSV · XLSX · XLS · JSON · JSONL · PDF · PNG · JPG · TIF · DOCX</span>
        </div>
      </div>

      {/* Summary + actions */}
      {files.length > 0 && (
        <div className="batch-summary card">
          <div className="bs-stats">
            <div><span className="eyebrow">Files</span><b>{totals.files}</b></div>
            <div><span className="eyebrow">Valid</span><b style={{ color: "var(--ok)" }}>{totals.valid}</b></div>
            <div><span className="eyebrow">Rows</span><b className="tnum">{totals.rows.toLocaleString()}</b></div>
            <div><span className="eyebrow">Warnings</span><b style={{ color: "var(--warn)" }}>{totals.warns}</b></div>
            <div><span className="eyebrow">Errors</span><b style={{ color: totals.errs ? "var(--bad)" : "var(--ink-3)" }}>{totals.errs}</b></div>
          </div>
          <div className="row-flex">
            <button className="btn ghost" onClick={clearAll} disabled={running}>Clear all</button>
            <button className="btn primary" onClick={runAll} disabled={running || totals.valid === 0}>
              {running ? <>Running…</> : <><Icon name="check"/> Run batch ({totals.valid})</>}
            </button>
          </div>
        </div>
      )}

      {/* File list */}
      {files.length > 0 && (
        <div className="card" style={{ marginTop: "var(--d-gap)" }}>
          <div className="card-h">
            <h3>Files in this batch</h3>
            <span className="meta">{files.length} {files.length === 1 ? "file" : "files"}</span>
          </div>
          <table className="tbl">
            <thead>
              <tr>
                <th>Filename</th>
                <th style={{ width: 110 }}>Size</th>
                <th style={{ width: 90 }}>Rows</th>
                <th style={{ width: 90 }}>Warnings</th>
                <th style={{ width: 90 }}>Errors</th>
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
                        {f.type === "bad" && <div style={{ fontSize: 11.5, color: "var(--bad)" }}>Unsupported file type — skipped</div>}
                      </div>
                    </div>
                  </td>
                  <td className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>{prettySize(f.size)}</td>
                  <td className="mono tnum">{f.type === "ok" ? f.rows.toLocaleString() : "—"}</td>
                  <td>{f.type === "ok" && f.warns > 0 ? <span className="badge b-warn">{f.warns}</span> : <span style={{ color: "var(--ink-5)" }}>0</span>}</td>
                  <td>{f.type === "ok" && f.errs > 0 ? <span className="badge b-bad">{f.errs}</span> : <span style={{ color: "var(--ink-5)" }}>0</span>}</td>
                  <td>
                    {f.type === "bad"      && <span className="badge b-bad">rejected</span>}
                    {f.type === "ok" && f.status === "ready"   && <span className="badge b-mute">ready</span>}
                    {f.type === "ok" && f.status === "running" && <span className="badge b-accent"><span className="dot pulse"/>running</span>}
                    {f.type === "ok" && f.status === "done"    && <span className="badge b-ok"><span className="dot"/>queued</span>}
                  </td>
                  <td>
                    <button className="btn ghost" style={{ height: 26, padding: "0 8px" }} onClick={() => remove(f.id)} aria-label="Remove file">
                      <Icon name="x" size={14}/>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {files.length === 0 && null}
    </div>
  );
}

function prettySize(b) {
  if (!b) return "—";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

window.BatchView = BatchView;
