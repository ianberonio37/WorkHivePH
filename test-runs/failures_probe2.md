# Triage — probe2

- stats: {'startTime': '2026-05-24T15:12:18.791Z', 'duration': 605588.066, 'expected': 38, 'skipped': 0, 'unexpected': 34, 'flaky': 0}
- total failures: **34**
  - A. Network / flake:        **1**
  - F. Fixture sign-in:        **0**
  - B. Sentinel content drift: **0**
  - C. Real regressions:       **33**

## Top failing files
| Count | File |
|---|---|
| 19 | `journey-canonical-signal-parity.spec.ts` |
| 13 | `journey-voice-journal.spec.ts` |
| 1 | `founder-console.spec.ts` |
| 1 | `ph-intelligence.spec.ts` |

## A. Network / flake  (1)

### `ph-intelligence.spec.ts`  (1)
- L11 — loads and renders without page errors
  - err: `Error: page errors on /workhive/ph-intelligence.html: Cannot read properties of null (reading 'classList') expect(received).toEqual(expected) // deep equality - Expected - 1 + Received + 3 - Array [] + Array [ + "Cannot `

## F. Fixture sign-in  (0)

## B. Sentinel content drift  (0)

## C. Real regressions  (33)

### `journey-canonical-signal-parity.spec.ts`  (19)
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
  - ... +9 more

### `journey-voice-journal.spec.ts`  (13)
- L124 — zaniah-default-persona: voice-journal opens with Zaniah selected by default
  - err: `Error: zaniah should be the default persona (Step D) expect(received).toBe(expected) // Object.is equality Expected: true Received: false 141 | || el.getAttribute('aria-checked') === 'true' 142 | ); > 143 | expect(isActi`
- L383 — dialog-noise-transcript-guard: empty / 1-2 char / pure-filler transcripts route as noise
  - err: `Error: Noise guard mis-classified: [ { "text": "no", "expected": false, "label": "short negation (handled by negation bypass)", "got": true } ]. Empty / filler-only transcripts that fall through to the LLM waste model co`
- L471 — dialog-prior-topic-handle: voice-handler prompt builder emits a PRIOR TOPIC HANDLE clause with PH + English pronouns
  - err: `Error: PRIOR TOPIC HANDLE must list "that" expect(received).toBe(expected) // Object.is equality Expected: true Received: false 504 | expect(audit.hasHandle, 'PRIOR TOPIC HANDLE clause must exist').toBe(true); 505 | expe`
- L554 — dialog-system-prompt-slot-bullets-live: _buildVoiceSystemPrompt emits "You already know:" + PRIOR TOPIC HANDLE for a real dialogState object
  - err: `Error: page.evaluate: ReferenceError: transcript is not defined at _buildVoiceSystemPrompt (http://127.0.0.1:5000/workhive/voice-handler.js:6380:184) at eval (eval at evaluate (:302:30), <anonymous>:18:22) at UtilityScri`
- L685 — dialog-quality-extended-detectors: turns #5-#10 + #14 helpers behave correctly
  - err: `Error: One or more turn #5-#14 detectors mis-classified: [ { "label": "repeat: \"what does that mean exactly\"", "got": true, "expected": false } ] expect(received).toEqual(expected) // deep equality - Expected - 1 + Rec`
- L759 — ai-companion-workflow-detectors: turns #55-#64 behaviour locked
  - err: `Error: T58 action replay returns new asset expect(received).toBe(expected) // Object.is equality Expected: "P-205" Received: null 826 | expect(verdict.stale).not.toContain('asset_tag'); 827 | expect(verdict.stale).toCont`
- L839 — ai-companion-orchestration-detectors: turns #65-#74 behaviour locked
  - err: `Error: T65 "save as PDF" detected expect(received).toBe(expected) // Object.is equality Expected: true Received: false 933 | expect(verdict.ready).toBe(true); 934 | // T65 PDF export > 935 | expect(verdict.pdf[0], 'T65 "`
- L976 — ai-companion-trust-deployment-detectors: turns #75-#84 behaviour locked
  - err: `Error: T77 "is this fresh" detected expect(received).toBe(expected) // Object.is equality Expected: true Received: false 1064 | expect(verdict.shapes.social).toBe('social'); 1065 | // T77 freshness > 1066 | expect(verdic`
- L1101 — ai-companion-input-normalization-detectors: turns #85-#94 behaviour locked
  - err: `Error: T85 null input → null expect(received).toBeNull() Received: "0.0%" 1176 | expect(verdict.kpi[0], 'T85 92.4823% → "92.5%"').toMatch(/^92\.[45]%/); 1177 | expect(verdict.kpi[1], 'T85 13.7 days, 0 decimals → "14 days`
- L1301 — ai-companion-learning-detectors: turns #105-#114 behaviour locked
  - err: `Error: T109 1-day required + 1 day → persistent expect(received).toBe(expected) // Object.is equality Expected: true Received: false 1392 | expect(verdict.sentiment.pos, 'T109 positive sentiment').toBe('positive'); 1393 `
  - ... +3 more

### `founder-console.spec.ts`  (1)
- L49 — admin_gate_not_commented: no commented-out gate redirect logic
  - err: `Error: no commented-out redirect on the admin gate path expect(received).toBe(expected) // Object.is equality Expected: false Received: true 52 | const __sentSrc_4 = await pageSrcWithExternals(whPage); 53 | const strippe`
