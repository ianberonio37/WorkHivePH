# Component Consistency Report — ① Component battery (Phase 1)

> **The altitude below the page.** Is each design-system PRIMITIVE rendered the same way everywhere? Static spine (windowed shape scan); the DOM-accurate confirm is `__UFAI.component('.simple-card')` live. SURFACES drift — fixes nothing.

- Pages: **28**  ·  pinned primitives: **2**  ·  census primitives: **6**  ·  capability tags: **3**

## 1. Pinned primitives — shape consistency

### `.simple-card` — KPI tile (.simple-card)

- **52** instances · modal shape ['.sc-hero', '.sc-label', '.sc-sub', '.sc-tag'] (52 instances) · **1** distinct shape(s).
- ✅ one consistent shape on every page.

### `.sum-card` — Count-chip summary (.sum-card → .sn/.sl)

- **8** instances · modal shape ['.sl', '.sn'] (8 instances) · **1** distinct shape(s).
- ✅ one consistent shape on every page.

## 2. Capability registry (declared visual primitives)

_`<!-- capability: NAME -->` tags = the repo's own canonical primitive list. Cross-referenced with `capability_dedup_report.json`._

| Capability | Declared on |
|---|---|
| `alert_dashboard` | alert-hub |
| `audio_tts_browser` | voice-journal |
| `display_count_chip` | predictive |

## 3. Census — light primitives (consistency = live component() check)

| Primitive | Pages | Total instances |
|---|---|---|
| `.filter-chip` | 4 | 23 |
| `.pill` | 1 | 8 |
| `.view-tab` | 1 | 4 |
| `.phase-tab` | 1 | 4 |
| `.shift-pill` | 1 | 3 |
| `.stepper` | 1 | 1 |

---
### Queue
`python ufai_ingest.py component_consistency_candidates.json` → 0 candidate(s) into `sweep_critiques.json`. Live confirm any shape drift with `__UFAI.component('.<primitive>')` (DOM-accurate).
