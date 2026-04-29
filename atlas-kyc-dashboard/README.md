# Atlas KYC Dashboard — design handoff

Static HTML + React (loaded via Babel-in-browser). No build step required to view; serve the folder over any static server.

## Run locally

```bash
cd atlas-kyc-dashboard
python3 -m http.server 8080
# open http://localhost:8080/KYC%20Dashboard.html
```

> Opening the HTML directly via `file://` will fail because of CORS — JSX modules must be fetched over HTTP.

## File map

```
KYC Dashboard.html      Entry point. Loads React/Babel, all scripts, mounts <App>.
styles.css              Design tokens + every component style. Edit tokens at top of file.
data.js                 All mock data (cases, RMs, audit events, ruleset, integrations,
                        datasets, prompts). Replace with real API calls when wiring up.
icons.jsx               Inline SVG icon set. Add a key to `paths` to register a new icon.
tweaks-panel.jsx        In-design tweak panel (font / density / role / etc.).

shell.jsx               <Sidebar>, <Topbar>, <Spark>, <RiskBar>. App-level chrome.

view-worklist.jsx       Workspaces · Worklist
view-rm.jsx             Workspaces · Client book
view-case.jsx           Workspaces · Case detail
view-batch.jsx          Workspaces · Batch upload
view-audit.jsx          Administration · Audit trail
view-ruleset.jsx        Administration · Ruleset & policy
view-system.jsx         Administration · System info
view-portfolio.jsx      (legacy variation — unused by current entry point)
```

## Wiring it to a real backend

All views read from a single global `MOCK` object built in `data.js`. To wire real data:

1. Replace the `data.js` IIFE with `fetch()` calls that resolve to the same shape, e.g.

   ```js
   window.MOCK = await (await fetch("/api/bootstrap")).json();
   ```

   Expected keys: `cases`, `jurisdictions`, `rmList`, `tiers`, `audit`, `ruleset`,
   `integrations`, `datasets`, `prompts`.

2. Each view component is a pure function of `MOCK` + props — no internal data
   fetching. Swap props for fetched data when you split into a real SPA.

3. Roles: the sidebar reads `role` from app state in `KYC Dashboard.html`
   (`useState("admin")`). Replace with your auth context. Admin-gated views are
   listed in `shell.jsx::adminViews`.

## Versioning / cache

Every script tag in `KYC Dashboard.html` has a `?v=N` query string. Bump that
number any time you change a JSX file so browsers don't serve a stale copy.

## What's still mocked

- The Run batch button on `view-batch.jsx` is a `setTimeout` — no upload yet.
- Audit chain verification, ruleset diff/approval, and the model-call latency
  numbers all read from `data.js`.
- "Download template" was intentionally removed per design review.
