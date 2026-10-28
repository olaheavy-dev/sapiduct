# 0010. Performance budget

Status: Proposed (the owner accepts by merging the pull request)

## Context

"Fast" needs numbers that a check can fail on. Facts as of 2026-10-28:

- Core Web Vitals call a page good when its Largest Contentful Paint is within 2.5 seconds, its Interaction to Next Paint is 200 milliseconds or less and its Cumulative Layout Shift is 0.1 or less, measured at the 75th percentile of page loads across mobile and desktop ([web.dev, Web Vitals](https://web.dev/articles/vitals)).
- The owner's personal website already fails its build when a prerendered page's first-visit transfer (gzipped HTML plus the scripts, styles and fonts it references) exceeds a budget, 600 KB for its main pages, with a script that runs after `next build` ([`scripts/check-budget.mjs`](https://github.com/olaheavy-dev/personal-website/blob/main/scripts/check-budget.mjs), read 2026-10-28).
- The frontend template runs Playwright tests, axe checks and screenshot comparisons in CI but has no size budget (house-template-nextjs v0.3.0).
- The backend's search work is one embedding call for the query plus database work (record 0008); the model call is a network round trip whose time is not under our control.

## Decision

1. **Web, field targets** (what real visitors should see, at the 75th percentile): LCP at most 2.5 s, INP at most 200 ms, CLS at most 0.1, for the public pages and the app. These are the published thresholds; they are checked against real-user data once there is any, and are not asserted before.
2. **Web, lab budget in CI.** A check adapted from the website's `check-budget.mjs` fails the build when a prerendered public page's first-visit transfer exceeds 600 KB gzipped, the website's current ceiling, and for the signed-in pages a per-route ceiling written down after the first build and only ever tightened. The public pages (landing, guides, sign-in, 404) stay prerendered. The script is a template candidate for house-template-nextjs.
3. **Backend targets** (proposals, measured in the spikes and changed to what is achievable, with the measurement recorded here when they are): on the 1,284-document sample, at the 95th percentile,
   - MCP `list_sources` and `get_document`: 200 ms;
   - MCP `search` (query embedding included): 1 s;
   - a documents-list request: 300 ms;
   - the first passages of a 5 MB PDF searchable within 30 s of upload (a time to first result, recorded per document).
4. **Where they are checked.** Backend budgets run as a `make perf` target against a seeded database, run by hand and in the spikes' pull request descriptions, not as a required CI check, because timing checks on shared CI runners are noisy. Each one is also a test with a ceiling three times the budget, so a large regression fails CI without flaking.
5. **When HNSW is added** (record 0008): when `search` on the largest allowed collection (2,000 documents, record 0009) exceeds its budget at the 95th percentile with exact search.
6. **Page weight is a design input.** The prototype's fonts (Fraunces, Geist, Geist Mono) are loaded with `next/font`, subset to the characters in use, and counted in the budget; if they push a page over the ceiling, the fonts change, not the ceiling.

## Consequences

- The first frontend pull request that applies the design must pass the budget, which may force decisions about font weights and the demo's code.
- Backend numbers are provisional until measured; the records say so, and the issue that measures them updates this record rather than silently changing a check.
- Real-user measurement needs a collection method (an analytics or Web Vitals endpoint) that is not decided here; until it exists the field targets are targets only.

## Alternatives considered

- **Lighthouse scores as the gate:** they vary run to run and across machines. Rejected as a required check; useful for investigation.
- **No numbers until after launch:** nothing would fail when pages grow. Rejected.
- **A stricter transfer budget than the website's:** possible once the first build shows what the app needs; budgets only tighten.

## Sources

- web.dev, Web Vitals (thresholds and percentile), read 2026-10-28: https://web.dev/articles/vitals
- The personal website's budget script, read 2026-10-28: https://github.com/olaheavy-dev/personal-website/blob/main/scripts/check-budget.mjs
- house-template-nextjs v0.3.0 README (checks it runs), read 2026-10-28: https://github.com/olaheavy-dev/house-template-nextjs
- Records 0008 and 0009 in this folder.
