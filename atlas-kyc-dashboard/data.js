/* ============================================================
   Mock data — generic placeholders (Client A / $XX.X M)
   ============================================================ */

window.MOCK = (function () {
  const jurisdictions = ["GB", "CH", "AE", "SG", "US", "MC", "KY", "JE", "LU"];
  const rmList = ["RM-01 — A. Mercer", "RM-02 — B. Tanaka", "RM-03 — C. Okafor", "RM-04 — D. Lindqvist", "RM-05 — E. Patel"];
  const tiers = ["Wealth", "UHNW", "Family Office"];

  function letter(i) { return String.fromCharCode(65 + (i % 26)); }
  function ini(name) {
    return name.split(" ").filter(Boolean).slice(0, 2).map(s => s[0]).join("").toUpperCase();
  }

  const cases = [];
  const flags = [
    "PEP exposure",
    "Adverse media match",
    "Sanctions secondary list",
    "UBO chain incomplete",
    "Source of Wealth narrative weak",
    "CRS self-cert expired",
    "FATCA W-8 missing",
    "High-risk jurisdiction",
    "Trust structure undisclosed",
    "Cash deposits irregular",
  ];
  const statuses = ["Pending review", "Awaiting docs", "Dual-approval", "Escalated", "In remediation"];
  const slas = [
    { tone: "ok",   label: "4d 12h", pct: 35 },
    { tone: "ok",   label: "3d 06h", pct: 48 },
    { tone: "warn", label: "1d 04h", pct: 78 },
    { tone: "warn", label: "0d 22h", pct: 84 },
    { tone: "bad",  label: "Overdue 1d", pct: 100 },
    { tone: "bad",  label: "Overdue 3d", pct: 100 },
    { tone: "ok",   label: "5d 02h", pct: 22 },
  ];

  for (let i = 0; i < 24; i++) {
    const tier = tiers[i % tiers.length];
    const name = `Client ${letter(i)}${i >= 26 ? letter(Math.floor(i / 26) - 1) : ""}`;
    const aum = (5 + (i * 17.3) % 240).toFixed(1);
    const risk = (i % 7 === 0) ? "high" : (i % 3 === 0 ? "medium" : "low");
    const flagCount = (i % 5 === 0) ? 3 : (i % 3 === 0 ? 2 : 1);
    const caseFlags = [];
    for (let f = 0; f < flagCount; f++) caseFlags.push(flags[(i * 3 + f) % flags.length]);
    cases.push({
      id: `KYC-${(2487 + i).toString().padStart(5, "0")}`,
      client: name,
      ini: ini(name),
      tier,
      aum,
      jurisdiction: jurisdictions[i % jurisdictions.length],
      jurisdictions: [jurisdictions[i % jurisdictions.length], jurisdictions[(i + 3) % jurisdictions.length]],
      risk,
      riskScore: risk === "high" ? 78 + (i % 15) : risk === "medium" ? 48 + (i % 20) : 18 + (i % 25),
      status: statuses[i % statuses.length],
      sla: slas[i % slas.length],
      flags: caseFlags,
      rm: rmList[i % rmList.length],
      lastReview: `2025-${String(((i * 2) % 12) + 1).padStart(2, "0")}-${String(((i * 5) % 27) + 1).padStart(2, "0")}`,
      nextReview: `2026-${String(((i * 3) % 12) + 1).padStart(2, "0")}-${String(((i * 7) % 27) + 1).padStart(2, "0")}`,
      type: (i % 4 === 0) ? "Trust" : (i % 5 === 0 ? "SPV" : "Individual"),
    });
  }

  /* ============================================================
     Audit trail entries
     ============================================================ */
  const audit = [];
  const auditTemplates = [
    { actionGroup: "auth",    action: "LOGIN",                 desc: "User authenticated and session started", who: ["admin","Admin"], hasCust: false },
    { actionGroup: "system",  action: "AUDIT_VIEWER_OPENED",   desc: "User opened the Audit Trail tab",        who: ["admin","Admin"], hasCust: false },
    { actionGroup: "ruleset", action: "RULESET_LOADED",        desc: "Active ruleset loaded into memory",       who: ["system","System"], hasCust: false },
    { actionGroup: "case",    action: "CASE_OPENED",           desc: "Case detail opened for review",           who: ["jmarlow","Analyst"], hasCust: true },
    { actionGroup: "case",    action: "CASE_FLAG_RAISED",      desc: "Adverse media match raised on subject",   who: ["system","System"], hasCust: true, hasBatch: true, hasPrompt: true },
    { actionGroup: "case",    action: "DOCUMENT_REQUESTED",    desc: "Outreach: passport copy requested via RM", who: ["jmarlow","Analyst"], hasCust: true },
    { actionGroup: "case",    action: "CASE_DUAL_APPROVE",     desc: "Case promoted to dual-approval queue",     who: ["jmarlow","Analyst"], hasCust: true },
    { actionGroup: "case",    action: "CASE_APPROVED",         desc: "Case approved · 2 of 2 signatures",        who: ["srahimi","Admin"], hasCust: true },
    { actionGroup: "ruleset", action: "RULESET_PROPOSED",      desc: "Override proposed: SGP velocity 30→14d",   who: ["mlyons","Admin"], hasCust: false },
    { actionGroup: "ruleset", action: "RULESET_APPROVED",      desc: "Override approved by Head of Compliance",  who: ["srahimi","Admin"], hasCust: false },
    { actionGroup: "export",  action: "EXPORT_CSV",            desc: "Worklist exported to CSV (47 rows)",       who: ["jmarlow","Analyst"], hasCust: false, hasBatch: true },
    { actionGroup: "system",  action: "PROMPT_INVOKED",        desc: "kyc-analysis prompt invoked",              who: ["system","System"], hasCust: true, hasBatch: true, hasPrompt: true },
    { actionGroup: "auth",    action: "MFA_CHALLENGE",         desc: "MFA challenge issued and satisfied",       who: ["btanaka","RM"], hasCust: false },
    { actionGroup: "auth",    action: "LOGOUT",                desc: "Session ended · idle timeout (15m)",       who: ["jmarlow","Analyst"], hasCust: false },
    { actionGroup: "case",    action: "RM_NOTE_ADDED",         desc: "RM note appended to case timeline",        who: ["btanaka","RM"], hasCust: true },
  ];
  function pad(n, w=2) { return String(n).padStart(w, "0"); }
  function fakeHash(seed) {
    let h = "";
    let x = seed * 9301 + 49297;
    for (let i = 0; i < 12; i++) {
      x = (x * 16807) % 2147483647;
      h += "0123456789abcdef"[x % 16];
    }
    return h;
  }
  for (let i = 0; i < 64; i++) {
    const t = auditTemplates[i % auditTemplates.length];
    const min = 38 - Math.floor(i * 0.7);
    const sec = (45 - i * 1.3) % 60;
    const ts = `2026-04-29T12:${pad((37 - Math.floor(i/3)) % 60)}:${pad(Math.floor((sec+60)%60))}.${pad(682009 + i*47, 6)}+00:00`;
    audit.push({
      id: `evt_${pad(i,4)}`,
      timestamp: ts,
      user: t.who[0],
      role: t.who[1],
      action: t.action,
      actionGroup: t.actionGroup,
      description: t.desc,
      customerId: t.hasCust ? `KYC-${pad(2487 + (i % 24), 5)}` : "",
      batchId: t.hasBatch ? `b_${pad(840 + i, 4)}` : "",
      promptVersion: t.hasPrompt ? ["kyc-analysis-v1.0","autodetect-v1.0","kyc-structuring-v1.0"][i % 3] : "",
      ruleset: "kyc-rules-v2.1",
      eventHash: fakeHash(i + 1),
      prevHash: fakeHash(i),
      nextHash: fakeHash(i + 2),
      ip: "10.42.18." + (100 + (i % 50)),
      session: `sess_${fakeHash(i+99).slice(0,10)}`,
      trace: `tr_${fakeHash(i+50).slice(0,8)}`,
      source: t.actionGroup === "system" ? "scheduler" : "ui-app",
      payload: t.hasCust ? { customer_id: `KYC-${pad(2487 + (i % 24), 5)}`, jurisdiction: jurisdictions[i % jurisdictions.length] } : null,
    });
  }

  /* ============================================================
     Active ruleset JSON (sample for editor)
     ============================================================ */
  const ruleset = {
    activeJson: `{
  "version": "kyc-rules-v2.1",
  "effective_date": "2026-01-01",
  "created_by": "hand-authored",
  "description": "PWM jurisdiction-aware KYC ruleset v2.0. Baseline: FATF Recommendations and Wolfsberg Private Banking Principles. Jurisdiction overlays for USA, GBR, EU, CHE, SGP, HKG, AUS. China deferred post-v1.",
  "changelog": [
    {
      "version": "kyc-rules-v2.0",
      "date": "2026-04-19",
      "change": "Phase 3: jurisdiction-aware ruleset. Baseline lifted from v1.1. Eight jurisdiction overlays added: USA, GBR, EU, CHE, SGP, HKG, AUS. HKG SFC 10% UBO threshold, SGP MAS 30-day velocity window, EU/CHE 180-day rescreening interval, GBR 60-day doc expiry warning. China deferred post-v1.",
      "author": "hand-authored",
      "reviewed_by": "NYU RegTech Team"
    },
    {
      "version": "kyc-rules-v1.1",
      "date": "2026-01-15",
      "change": "Added adverse media weighting; PEP exposure decay 12-month half-life; UBO 25% disclosure threshold per FATF R10.",
      "author": "Compliance WG",
      "reviewed_by": "S. Rahimi"
    }
  ],
  "thresholds": {
    "ubo_pct_default": 25,
    "ubo_pct_overrides": { "HKG": 10 },
    "velocity_window_days": { "default": 90, "SGP": 30 },
    "doc_expiry_warning_days": { "default": 90, "GBR": 60 },
    "pep_decay_months": 12
  }
}`,
  };

  const integrations = [
    { name: "Anthropic API",        purpose: "Claude haiku-4-5 inference",   endpoint: "api.anthropic.com/v1",     lastCall: "8s ago",  status: "ok",   category: "AI" },
    { name: "Okta",                  purpose: "SSO / MFA",                    endpoint: "atlas.okta.com",            lastCall: "44s ago", status: "ok",   category: "Identity" },
    { name: "Postgres (RDS)",        purpose: "Primary · cases / audit",      endpoint: "rds.eu-west-1.atlas",       lastCall: "1s ago",  status: "ok",   category: "Storage" },
    { name: "S3 (eu-west-1)",        purpose: "Document store · WORM",        endpoint: "s3://atlas-kyc-docs",       lastCall: "12s ago", status: "ok",   category: "Storage" },
    { name: "AWS KMS",               purpose: "Audit Merkle anchoring",       endpoint: "kms.eu-west-1",             lastCall: "6m ago",  status: "ok",   category: "Security" },
    { name: "OFAC / EU / UK feeds",  purpose: "Sanctions feeds",              endpoint: "treasury.gov · esma · ofsi", lastCall: "5h ago", status: "ok",   category: "Data" },
    { name: "Refinitiv World-Check", purpose: "PEP & adverse media",          endpoint: "api.world-check.refinitiv.com", lastCall: "2h ago", status: "ok", category: "Data" },
    { name: "Dow Jones RC",          purpose: "PEP / adverse (secondary)",    endpoint: "rc.dowjones.com",           lastCall: "8h ago",  status: "warn", category: "Data" },
    { name: "Datadog",               purpose: "Logs · APM · alerting",        endpoint: "app.datadoghq.eu",          lastCall: "now",     status: "ok",   category: "Observability" },
  ];

  const datasets = [
    { name: "OFAC SDN",            kind: "Sanctions list · US Treasury", n: "12,847", refreshed: "2026-04-29 06:00", status: "ok" },
    { name: "EU Consolidated",     kind: "Sanctions list · ESMA",        n: "4,213",  refreshed: "2026-04-29 06:00", status: "ok" },
    { name: "UK HMT",              kind: "Sanctions list · OFSI",        n: "3,907",  refreshed: "2026-04-29 06:00", status: "ok" },
    { name: "World-Check",         kind: "PEP / adverse media",          n: "5.4 M",  refreshed: "2026-04-29 02:00", status: "ok" },
    { name: "Dow Jones RiskCenter",kind: "PEP / adverse media",          n: "3.1 M",  refreshed: "2026-04-28 22:00", status: "warn" },
    { name: "Companies House",     kind: "Corporate registry · UK",      n: "5.2 M",  refreshed: "2026-04-28 18:00", status: "ok" },
    { name: "OpenSanctions",       kind: "Aggregator (fallback)",        n: "—",      refreshed: "Disabled",          status: "off" },
  ];

  const prompts = [
    { id: "kyc-structuring-v1.0", v: "v1.0", date: "2026-04-13", desc: "Risk-tier structuring of KYC payload — extracts entities, jurisdictions, beneficial owners.", calls: "8,412",  lat: "1.6s" },
    { id: "autodetect-v1.0",      v: "v1.0", date: "2026-04-13", desc: "Adverse-media auto-detection. Classifies source quality, recency, jurisdictional relevance.", calls: "12,038", lat: "0.9s" },
    { id: "kyc-analysis-v1.0",    v: "v1.0", date: "2026-04-13", desc: "Final analyst-grade summary. Cites every claim, surfaces unresolved flags.",                  calls: "3,217",  lat: "2.4s" },
  ];

  return { cases, jurisdictions, rmList, tiers, audit, ruleset, integrations, datasets, prompts };
})();
