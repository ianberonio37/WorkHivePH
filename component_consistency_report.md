# Component Consistency Report — ① Component battery (Phase 1)

> **The altitude below the page.** Is each design-system PRIMITIVE rendered the same way everywhere? Static spine (windowed shape scan); the DOM-accurate confirm is `__UFAI.component('.simple-card')` live. SURFACES drift — fixes nothing.

- Pages: **146**  ·  pinned primitives: **4**  ·  census primitives: **6**  ·  capability tags: **3**

## 1. Pinned primitives — shape consistency

### `.simple-card` — KPI tile (.simple-card)

- **63** instances · modal shape ['.sc-hero', '.sc-label', '.sc-sub', '.sc-tag'] (41 instances) · **5** distinct shape(s).
- ⚠️ **19 instance(s) MISSING a required sub-part:** achievements missing .sc-hero; achievements missing .sc-label, .sc-hero; hive missing .sc-label; hive missing .sc-label; hive missing .sc-label; marketplace-seller missing .sc-label, .sc-hero; marketplace-seller missing .sc-label, .sc-hero; marketplace-seller missing .sc-label, .sc-hero.
- Minority shapes (converge or justify):
    - [] ×15 (achievements, marketplace, marketplace-seller, skillmatrix) — Δ vs modal ['.sc-hero', '.sc-label', '.sc-sub', '.sc-tag']
    - ['.sc-hero', '.sc-label', '.sc-sub'] ×3 (analytics, marketplace, pm-scheduler) — Δ vs modal ['.sc-tag']
    - ['.sc-hero'] ×3 (hive) — Δ vs modal ['.sc-label', '.sc-sub', '.sc-tag']
    - ['.sc-label'] ×1 (achievements) — Δ vs modal ['.sc-hero', '.sc-sub', '.sc-tag']

### `.sum-card` — Count-chip summary (.sum-card → .sn/.sl)

- **4** instances · modal shape ['.sl', '.sn'] (4 instances) · **1** distinct shape(s).
- ✅ one consistent shape on every page.

### `.article-card` — Learn library card (.article-card → .pill/.card-title)

- **54** instances · modal shape ['.card-title', '.pill'] (54 instances) · **1** distinct shape(s).
- ✅ one consistent shape on every page.

### `.author-card` — Guide byline card (.author-card → .avatar/.meta)

- **35** instances · modal shape ['.avatar', '.meta'] (35 instances) · **1** distinct shape(s).
- ✅ one consistent shape on every page.

## 2. Capability registry (declared visual primitives)

_`<!-- capability: NAME -->` tags = the repo's own canonical primitive list. Cross-referenced with `capability_dedup_report.json`._

| Capability | Declared on |
|---|---|
| `alert_dashboard` | alert-hub |
| `audio_tts_browser` | voice-journal |
| `display_count_chip` | asset-hub |

## 3. Census — light primitives (consistency = live component() check)

| Primitive | Pages | Total instances |
|---|---|---|
| `.pill` | 41 | 102 |
| `.filter-chip` | 7 | 42 |
| `.view-tab` | 1 | 4 |
| `.phase-tab` | 1 | 4 |
| `.shift-pill` | 1 | 3 |
| `.stepper` | 1 | 1 |

---
### Queue
`python ufai_ingest.py component_consistency_candidates.json` → 20 candidate(s) into `sweep_critiques.json`. Live confirm any shape drift with `__UFAI.component('.<primitive>')` (DOM-accurate).
