# Triage — rerun3

- stats: {'startTime': '2026-05-24T16:49:51.584Z', 'duration': 3701996.22, 'expected': 571, 'skipped': 23, 'unexpected': 56, 'flaky': 0}
- total failures: **56**
  - A. Network / flake:        **3**
  - F. Fixture sign-in:        **0**
  - B. Sentinel content drift: **0**
  - C. Real regressions:       **53**

## Top failing files
| Count | File |
|---|---|
| 21 | `journey-canonical-signal-parity.spec.ts` |
| 5 | `journey-predictive.spec.ts` |
| 3 | `journey-hive.spec.ts` |
| 2 | `journey-agentic-rag-observability.spec.ts` |
| 2 | `journey-agentic-rag.spec.ts` |
| 2 | `journey-calm-dashboard-behaviour.spec.ts` |
| 2 | `journey-logbook.spec.ts` |
| 1 | `dayplanner.spec.ts` |
| 1 | `founder-console.spec.ts` |
| 1 | `integrations.spec.ts` |
| 1 | `journey-agentic.spec.ts` |
| 1 | `journey-ai-quality.spec.ts` |
| 1 | `journey-alerts.spec.ts` |
| 1 | `journey-asset-hub.spec.ts` |
| 1 | `journey-community.spec.ts` |
| 1 | `journey-engineering-design.spec.ts` |
| 1 | `journey-inventory.spec.ts` |
| 1 | `journey-l0-surface-coverage.spec.ts` |
| 1 | `journey-megagate-marketplace.spec.ts` |
| 1 | `journey-mobile-a11y.spec.ts` |
| 1 | `journey-regression-pins.spec.ts` |
| 1 | `journey-skillmatrix.spec.ts` |
| 1 | `journey-voice-journal.spec.ts` |
| 1 | `ph-intelligence.spec.ts` |
| 1 | `platform-validators.spec.ts` |
| 1 | `pm-scheduler.spec.ts` |

## A. Network / flake  (3)

### `integrations.spec.ts`  (1)
- L11 — loads and renders without page errors
  - err: `Error: page errors on /workhive/integrations.html: [console.error] TypeError: Failed to fetch at https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2:7:105903 at https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2:7:110`

### `journey-agentic-rag-observability.spec.ts`  (1)
- L16 — page loads without console errors
  - err: `Error: expect(received).toEqual(expected) // deep equality - Expected - 1 + Received + 3 - Array [] + Array [ + "supabaseKey is required.", + ] 22 | const serious = errors.filter(e => 23 | !e.includes('net::ERR_') && !e.`

### `ph-intelligence.spec.ts`  (1)
- L11 — loads and renders without page errors
  - err: `Error: page errors on /workhive/ph-intelligence.html: Cannot read properties of null (reading 'classList') expect(received).toEqual(expected) // deep equality - Expected - 1 + Received + 3 - Array [] + Array [ + "Cannot `

## F. Fixture sign-in  (0)

## B. Sentinel content drift  (0)

## C. Real regressions  (53)

### `journey-canonical-signal-parity.spec.ts`  (21)
- L309 — check_pm_overdue_scope_items_count: hive Team Pulse #pulse-pm-overdue == COUNT(v_pm_scope_items_truth WHERE is_overdue)
  - err: `Error: /workhive/hive.html #pulse-pm-overdue shows 0 but v_pm_scope_items_truth.is_overdue directly counts 5 (mode=rows). Page is re-deriving instead of trusting the canonical signal. expect(received).toBe(expected) // O`
- L309 — check_pm_overdue_assets_count: pm-scheduler #stat-overdue == COUNT(DISTINCT asset_id WHERE is_overdue)
  - err: `Error: /workhive/pm-scheduler.html #stat-overdue shows 0 but v_pm_scope_items_truth.is_overdue directly counts 5 (mode=assets). Page is re-deriving instead of trusting the canonical signal. expect(received).toBe(expected`
- L309 — check_low_stock_count: home tile == COUNT(v_inventory_items_truth WHERE is_low_stock)
  - err: `Error: /workhive/index.html [data-kpi="low-stock"] .oh-tile-num shows 3 but v_inventory_items_truth.is_low_stock directly counts 9 (mode=rows). Page is re-deriving instead of trusting the canonical signal. expect(receive`
- L309 — check_open_jobs_count: home tile == COUNT(v_logbook_truth WHERE status=Open)
  - err: `Error: /workhive/index.html [data-kpi="open-jobs"] .oh-tile-num shows 18 but v_logbook_truth.undefined directly counts 53 (mode=rows). Page is re-deriving instead of trusting the canonical signal. expect(received).toBe(e`
- L309 — check_risk_alerts_count: home tile == COUNT(v_risk_truth WHERE risk_level IN critical/high)
  - err: `Error: /workhive/index.html [data-kpi="risk-alerts"] .oh-tile-num shows 2 but v_risk_truth.undefined directly counts 6 (mode=rows). Page is re-deriving instead of trusting the canonical signal. expect(received).toBe(expe`
- L309 — check_pm_overdue_home_tile: home tile == hive Team Pulse count (both v_pm_scope_items_truth.is_overdue / v_pm_compliance_truth.is_due rollup)
  - err: `Error: /workhive/index.html [data-kpi="pm-overdue"] .oh-tile-num shows 22 but v_pm_compliance_truth.is_due directly counts 63 (mode=rows). Page is re-deriving instead of trusting the canonical signal. expect(received).to`
- L309 — check_total_assets_count: asset-hub #ah-total-hero == COUNT(v_asset_truth)
  - err: `Error: /workhive/asset-hub.html #ah-total-hero shows 30 but v_asset_truth.undefined directly counts 90 (mode=all). Page is re-deriving instead of trusting the canonical signal. expect(received).toBe(expected) // Object.i`
- L309 — check_critical_assets_count: asset-hub #ah-critical-hero == COUNT(asset_nodes WHERE criticality=critical, case-insensitive)
  - err: `Error: /workhive/asset-hub.html #ah-critical-hero shows 6 but v_asset_truth.undefined directly counts 16 (mode=rows). Page is re-deriving instead of trusting the canonical signal. expect(received).toBe(expected) // Objec`
- L309 — check_pm_duesoon_assets_count: pm-scheduler #stat-duesoon == DISTINCT(asset_id) WHERE is_due_soon
  - err: `Error: /workhive/pm-scheduler.html #stat-duesoon shows 0 but v_pm_scope_items_truth.is_due_soon directly counts 59 (mode=assets). Page is re-deriving instead of trusting the canonical signal. expect(received).toBe(expect`
- L309 — check_inventory_low_count: inventory #stat-low == COUNT(v_inventory_items_truth WHERE is_low_stock)
  - err: `Error: /workhive/inventory.html #stat-low shows 0 but v_inventory_items_truth.is_low_stock directly counts 9 (mode=rows). Page is re-deriving instead of trusting the canonical signal. expect(received).toBe(expected) // O`
  - ... +11 more

### `journey-predictive.spec.ts`  (5)
- L40 — source chip declares v_risk_truth and 365d window
  - err: `Error: chip should mention v_risk_truth expect(received).toContain(expected) // indexOf Expected substring: "v_risk_truth" Received string: "" 44 | const chip = whPage.locator('.wh-source-chip').first(); 45 | const text `
- L49 — Plain-Read verdict settles with meaningful content
  - err: `Error: expect(received).toBeGreaterThan(expected) Expected: > 3 Received: 0 53 | const label = await whPage.locator('[id$="verdict-label"]').first().textContent().catch(() => ''); 54 | expect(label?.trim()).not.toMatch(/`
- L58 — 3 plain-read cards populated with real numbers
  - err: `Error: expect(received).toBeGreaterThanOrEqual(expected) Expected: >= 3 Received: 0 62 | const heroes = whPage.locator('.sc-hero'); 63 | const count = await heroes.count(); > 64 | expect(count).toBeGreaterThanOrEqual(3);`
- L72 — RULES ENGINE V1 badge is visible
  - err: `Error: expect(locator).toBeVisible() failed Locator: locator('text=RULES ENGINE V1').first() Expected: visible Timeout: 5000ms Error: element(s) not found Call log: - Expect "toBeVisible" with timeout 5000ms - waiting fo`
- L163 — downtime_cap: downtime computation caps outliers
  - err: `Error: downtime computation should be capped against outliers expect(received).toBeTruthy() Received: false 166 | const __sentSrc_4 = await pageSrcWithExternals(whPage); 167 | const has = /downtime[_-]?cap|cap[_-]?downti`

### `journey-hive.spec.ts`  (3)
- L49 — page loads without console errors
  - err: `Error: serious console errors on hive.html: Failed to load resource: the server responded with a status of 400 (Bad Request) expect(received).toEqual(expected) // deep equality - Expected - 1 + Received + 3 - Array [] + `
- L107 — 3 plain-read cards all have non-placeholder heroes
  - err: `Error: stair hero should be populated expect(received).not.toBe(expected) // Object.is equality Expected: not "—" 112 | // Stair card 113 | const stairHero = await whPage.locator('#ss-stair-hero').textContent(); > 114 | `
- L375 — flow_logbook_inventory_transactions: logbook->inventory_transactions linkage referenced
  - err: `Error: inventory_transactions queryable expect(received).toBeTruthy() Received: false 377 | const { data } = await db.from('inventory_transactions') 378 | .select('source').eq('source', 'logbook').limit(1); > 379 | expec`

### `journey-agentic-rag.spec.ts`  (2)
- L155 — citation markers present in answer when chunks were graded successfully
  - err: `Error: answer must either cite a chunk [c#] or admit no records expect(received).toBe(expected) // Object.is equality Expected: true Received: false 171 | const hasCitation = /\[c[a-z0-9#_-]+\]/i.test(result.body.answer `
- L176 — hallucination guard: never invents asset tags not in chunks
  - err: `Error: answer mentions fictional asset but neither cites a chunk nor admits no records expect(received).toBe(expected) // Object.is equality Expected: true Received: false 195 | const hasCitation = /\[c[a-z0-9#_-]+\]/i.t`

### `journey-calm-dashboard-behaviour.spec.ts`  (2)
- L84 — agentic-rag-observability.html: calm-dashboard meta + verdict + <details> + hide-zero helper
  - err: `Error: agentic-rag-observability.html: verdict region must be either pre-rendered in DOM or declared in a template literal / renderVerdict function expect(received).toBe(expected) // Object.is equality Expected: true Rec`
- L133 — every calm-dashboard page exposes a source chip OR a documented dashboard-allow comment
  - err: `Error: Pages with neither a source chip nor a dashboard-allow comment: agentic-rag-observability.html expect(received).toBe(expected) // Object.is equality Expected: 0 Received: 1 140 | } 141 | expect(gaps.length, > 142 `

### `journey-logbook.spec.ts`  (2)
- L384 — new_fields_in_save_edit: saveEdit includes canonical new fields
  - err: `Error: saveEdit should include canonical new fields expect(received).toBeTruthy() Received: false 387 | const __sentSrc_6 = await pageSrcWithExternals(whPage); 388 | const has = /saveEdit[\s\S]{0,500}(asset_ref_id|mainte`
- L455 — parts_txn_parity: every parts_used entry has an inventory_transactions row
  - err: `Error: every parts_used entry must have a matching inv txn expect(received).toBe(expected) // Object.is equality Expected: 0 Received: 10 463 | const seen = new Set((txns ?? []).map(t => t.logbook_id)); 464 | const missi`

### `dayplanner.spec.ts`  (1)
- L14 — page loads and lists today's schedule items
  - err: `Error: expect(locator).toBeVisible() failed Locator: locator('text=/Open|Schedule|Planner|Today/i').first() Expected: visible Received: hidden Timeout: 5000ms Call log: - Expect "toBeVisible" with timeout 5000ms - waitin`

### `founder-console.spec.ts`  (1)
- L49 — admin_gate_not_commented: no commented-out gate redirect logic
  - err: `Error: no commented-out redirect on the admin gate path expect(received).toBe(expected) // Object.is equality Expected: false Received: true 52 | const __sentSrc_4 = await pageSrcWithExternals(whPage); 53 | const strippe`

### `journey-agentic-rag-observability.spec.ts`  (1)
- L27 — renders filter bar + 3 tables + summary container
  - err: `Error: expect(locator).toBeVisible() failed Locator: locator('#summary-cards') Expected: visible Received: hidden Timeout: 8000ms Call log: - Expect "toBeVisible" with timeout 8000ms - waiting for locator('#summary-cards`

### `journey-agentic.spec.ts`  (1)
- L49 — bounded_fetch: trace query carries a .limit(N) clause in source
  - err: `Error: agentic_rag_traces must be referenced expect(received).toContain(expected) // indexOf Expected substring: "agentic_rag_traces" Received string: "<html lang=\"en\" style=\"overflow-x: hidden;\"><head> <meta charset`

### `journey-ai-quality.spec.ts`  (1)
- L86 — three plain-read cards render with non-placeholder heroes
  - err: `Error: expect(received).not.toBe(expected) // Object.is equality Expected: not "—" 94 | const text = await heroes.nth(i).textContent(); 95 | expect(text?.trim(), `card ${i} hero should not be empty`).not.toBe(''); > 96 |`

### `journey-alerts.spec.ts`  (1)
- L63 — 3 plain-read cards populated (HIGH-SEVERITY, ANOMALY SIGNALS, AMC BRIEF)
  - err: `Error: card 0 hero should be populated expect(received).not.toBe(expected) // Object.is equality Expected: not "—" 71 | for (let i = 0; i < Math.min(count, 3); i++) { 72 | const text = await heroes.nth(i).textContent(); `

### `journey-asset-hub.spec.ts`  (1)
- L99 — clicking an asset card opens 360 detail view
  - err: `Error: asset list should have at least 1 card — run test-data-seeder if empty expect(received).toBeGreaterThan(expected) Expected: > 0 Received: 0 105 | // A zero count means the seeder hasn't run or asset data was wiped`

### `journey-community.spec.ts`  (1)
- L96 — happy path: create post — appears in feed and DB
  - err: `Error: Post "Test post from Playwright [WH-PW-34-mpk1emke]" should appear in community_posts or feed expect(received).toBe(expected) // Object.is equality Expected: true Received: false 127 | // Accept either DB confirma`

### `journey-engineering-design.spec.ts`  (1)
- L237 — all_builders_covered: page declares a diagram builder reference
  - err: `Error: engineering-design should declare diagram builders expect(received).toBeTruthy() Received: false 240 | const __sentSrc = await pageSrcWithExternals(whPage); 241 | const has = /buildDiagram|drawDiagram|renderDiagra`

### `journey-inventory.spec.ts`  (1)
- L463 — txn_type_valid: every txn uses a canonical type value
  - err: `Error: every txn type must be canonical expect(received).toBe(expected) // Object.is equality Expected: 0 Received: 7 468 | if (!data) { test.skip(true, 'no rows'); return; } 469 | const bad = data.filter(r => r.type && `

### `journey-l0-surface-coverage.spec.ts`  (1)
- L53 — heading_hierarchy: single h1 + no skip on /workhive/inventory.html
  - err: `Error: heading skip 2->4 on /workhive/inventory.html expect(received).toBeLessThanOrEqual(expected) Expected: <= 3 Received: 4 66 | for (const lvl of levels) { 67 | if (prev > 0) { > 68 | expect(lvl, `heading skip ${prev`

### `journey-megagate-marketplace.spec.ts`  (1)
- L62 — F5_seller_inquiries_visible_on_profile: marketplace-seller-profile reads marketplace_inquiries
  - err: `Error: seller profile must query marketplace_inquiries expect(received).toMatch(expected) Expected pattern: /from\s*\(\s*['"]marketplace_inquiries['"]\s*\)/ Received string: "<!DOCTYPE html>· <html lang=\"en\">· <head>· `

### `journey-mobile-a11y.spec.ts`  (1)
- L82 — G5_main_landmark_present_on_every_page: every public page has <main>
  - err: `Error: every public page must include a <main> landmark expect(received).toEqual(expected) // deep equality - Expected - 1 + Received + 3 - Array [] + Array [ + "agentic-rag-observability.html", + ] 88 | if (!/<main\b/i.`

### `journey-regression-pins.spec.ts`  (1)
- L50 — M3_main_landmark_on_every_page: every production HTML has <main>
  - err: `Error: every production page must include <main> expect(received).toEqual(expected) // deep equality - Expected - 1 + Received + 3 - Array [] + Array [ + "agentic-rag-observability.html", + ] 55 | if (!/<main\b/i.test(c)`

### `journey-skillmatrix.spec.ts`  (1)
- L236 — exam_array_count: exam questions array has expected length
  - err: `Error: skillmatrix should declare at least one questions array expect(received).toBeGreaterThan(expected) Expected: > 0 Received: 0 242 | return matches.length; 243 | }); > 244 | expect(counts, 'skillmatrix should declar`

### `journey-voice-journal.spec.ts`  (1)
- L124 — zaniah-default-persona: voice-journal opens with Zaniah selected by default
  - err: `Error: zaniah should be the default persona (Step D) expect(received).toBe(expected) // Object.is equality Expected: true Received: false 141 | || el.getAttribute('aria-checked') === 'true' 142 | ); > 143 | expect(isActi`

### `platform-validators.spec.ts`  (1)
- L74 — documented_column_pair: every near-duplicate column pair is allowlisted
  - err: `Error: every near-duplicate column pair must be documented expect(received).toBe(expected) // Object.is equality Expected: 0 Received: 1 75 | const r = readReport('canonical_overlap_report.json'); 76 | expect(r.census.ne`

### `pm-scheduler.spec.ts`  (1)
- L13 — page loads and renders scope items list
  - err: `Error: expect(locator).toBeVisible() failed Locator: locator('text=/PM|Preventive|Scheduler|Asset|Maintenance/i').first() Expected: visible Received: hidden Timeout: 5000ms Call log: - Expect "toBeVisible" with timeout 5`
