# Displayed Values Audit (Tier S coverage)

Scans every page for value-display anchors (element ids ending in
`-num`, `-count`, `-pct`, `-score`, `-days`, etc.) and classifies
each as contracted / uncontracted / raw / unknown.

## Summary

- Pages scanned:           **31**
- Display anchors found:   **112**
- Contracted ✅:           **18** (anchor maps to a registered formula)
- **Uncontracted ⚠️:**     **13** (domain-meaningful metric, no formula registered)
- Raw (counts/dates):      **35** (no contract needed)
- Unknown:                 **46** (couldn't classify from id alone)
- Formula registry:        **22** entries

## Per-page breakdown

| Page | Anchors | Contracted | Uncontracted | Raw | Unknown |
|---|---:|---:|---:|---:|---:|
| `hive.html` | 8 | 1 | 0 | 4 | 3 |
| `logbook.html` | 11 | 1 | 0 | 7 | 3 |
| `inventory.html` | 3 | 1 | 0 | 1 | 1 |
| `pm-scheduler.html` | 5 | 0 | 0 | 2 | 3 |
| `analytics.html` | 4 | 0 | 0 | 0 | 4 |
| `analytics-report.html` | 0 | 0 | 0 | 0 | 0 |
| `skillmatrix.html` | 3 | 1 | 1 | 0 | 1 |
| `community.html` | 7 | 0 | 1 | 3 | 3 |
| `public-feed.html` | 0 | 0 | 0 | 0 | 0 |
| `marketplace.html` | 7 | 3 | 0 | 2 | 2 |
| `marketplace-seller.html` | 2 | 0 | 2 | 0 | 0 |
| `dayplanner.html` | 4 | 0 | 0 | 2 | 2 |
| `engineering-design.html` | 8 | 1 | 4 | 0 | 3 |
| `assistant.html` | 1 | 0 | 0 | 0 | 1 |
| `report-sender.html` | 3 | 0 | 0 | 1 | 2 |
| `platform-health.html` | 6 | 3 | 0 | 1 | 2 |
| `project-manager.html` | 2 | 0 | 0 | 1 | 1 |
| `integrations.html` | 4 | 0 | 1 | 1 | 2 |
| `ph-intelligence.html` | 1 | 0 | 0 | 0 | 1 |
| `project-report.html` | 0 | 0 | 0 | 0 | 0 |
| `predictive.html` | 3 | 0 | 0 | 0 | 3 |
| `ai-quality.html` | 0 | 0 | 0 | 0 | 0 |
| `plant-connections.html` | 0 | 0 | 0 | 0 | 0 |
| `achievements.html` | 3 | 2 | 0 | 0 | 1 |
| `asset-hub.html` | 7 | 4 | 1 | 1 | 1 |
| `shift-brain.html` | 5 | 0 | 0 | 4 | 1 |
| `alert-hub.html` | 6 | 1 | 0 | 4 | 1 |
| `audit-log.html` | 0 | 0 | 0 | 0 | 0 |
| `voice-journal.html` | 2 | 0 | 0 | 1 | 1 |
| `founder-console.html` | 6 | 0 | 3 | 0 | 3 |
| `index.html` | 1 | 0 | 0 | 0 | 1 |

## Top uncontracted metric tokens (build formulas for these next)

| Token | Pages displaying it |
|---|---:|
| `earned` | 2 |
| `ring-pct` | 2 |
| `result-score` | 1 |
| `xp` | 1 |
| `tg-eg` | 1 |
| `tg-lg` | 1 |
| `tg-oa` | 1 |
| `tg-preload` | 1 |
| `progress` | 1 |
| `pf-pf` | 1 |
| `cost` | 1 |

## Per-page punch list — uncontracted displays

### `skillmatrix.html` (1 uncontracted)
- `id="result-score"` · token=`result-score`

### `community.html` (1 uncontracted)
- `id="profile-xp"` · token=`xp`

### `marketplace-seller.html` (2 uncontracted)
- `id="ps-earned"` · token=`earned`
- `id="pstat-earned"` · token=`earned`

### `engineering-design.html` (4 uncontracted)
- `id="tg-eg-num"` · token=`tg-eg`
- `id="tg-lg-ratio"` · token=`tg-lg`
- `id="tg-oa-pct"` · token=`tg-oa`
- `id="tg-preload-pct"` · token=`tg-preload`

### `integrations.html` (1 uncontracted)
- `id="progress-label"` · token=`progress`

### `asset-hub.html` (1 uncontracted)
- `id="pf-pf-days"` · token=`pf-pf`

### `founder-console.html` (3 uncontracted)
- `id="ring-pct-label"` · token=`ring-pct`
- `id="ring-pct-num"` · token=`ring-pct`
- `id="stat-aicost-trend"` · token=`cost`
