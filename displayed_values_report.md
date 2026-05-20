# Displayed Values Audit (Tier S coverage)

Scans every page for value-display anchors (element ids ending in
`-num`, `-count`, `-pct`, `-score`, `-days`, etc.) and classifies
each as contracted / uncontracted / raw / unknown.

## Summary

- Pages scanned:           **31**
- Display anchors found:   **50**
- Contracted ✅:           **6** (anchor maps to a registered formula)
- **Uncontracted ⚠️:**     **8** (domain-meaningful metric, no formula registered)
- Raw (counts/dates):      **22** (no contract needed)
- Unknown:                 **14** (couldn't classify from id alone)
- Formula registry:        **15** entries

## Per-page breakdown

| Page | Anchors | Contracted | Uncontracted | Raw | Unknown |
|---|---:|---:|---:|---:|---:|
| `hive.html` | 5 | 0 | 1 | 2 | 2 |
| `logbook.html` | 7 | 0 | 1 | 6 | 0 |
| `inventory.html` | 1 | 1 | 0 | 0 | 0 |
| `pm-scheduler.html` | 1 | 0 | 0 | 1 | 0 |
| `analytics.html` | 0 | 0 | 0 | 0 | 0 |
| `analytics-report.html` | 0 | 0 | 0 | 0 | 0 |
| `skillmatrix.html` | 1 | 0 | 0 | 0 | 1 |
| `community.html` | 3 | 0 | 0 | 3 | 0 |
| `public-feed.html` | 0 | 0 | 0 | 0 | 0 |
| `marketplace.html` | 4 | 1 | 1 | 2 | 0 |
| `marketplace-seller.html` | 1 | 0 | 0 | 0 | 1 |
| `dayplanner.html` | 0 | 0 | 0 | 0 | 0 |
| `engineering-design.html` | 4 | 0 | 1 | 0 | 3 |
| `assistant.html` | 0 | 0 | 0 | 0 | 0 |
| `report-sender.html` | 1 | 0 | 0 | 1 | 0 |
| `platform-health.html` | 3 | 0 | 2 | 0 | 1 |
| `project-manager.html` | 1 | 0 | 0 | 1 | 0 |
| `integrations.html` | 0 | 0 | 0 | 0 | 0 |
| `ph-intelligence.html` | 0 | 0 | 0 | 0 | 0 |
| `project-report.html` | 0 | 0 | 0 | 0 | 0 |
| `predictive.html` | 0 | 0 | 0 | 0 | 0 |
| `ai-quality.html` | 0 | 0 | 0 | 0 | 0 |
| `plant-connections.html` | 0 | 0 | 0 | 0 | 0 |
| `achievements.html` | 1 | 0 | 1 | 0 | 0 |
| `asset-hub.html` | 6 | 3 | 1 | 1 | 1 |
| `shift-brain.html` | 4 | 0 | 0 | 4 | 0 |
| `alert-hub.html` | 5 | 1 | 0 | 0 | 4 |
| `audit-log.html` | 0 | 0 | 0 | 0 | 0 |
| `voice-journal.html` | 1 | 0 | 0 | 1 | 0 |
| `founder-console.html` | 1 | 0 | 0 | 0 | 1 |
| `index.html` | 0 | 0 | 0 | 0 | 0 |

## Top uncontracted metric tokens (build formulas for these next)

| Token | Pages displaying it |
|---|---:|
| `quality` | 2 |
| `health` | 2 |
| `level` | 2 |
| `adoption` | 1 |
| `load` | 1 |

## Per-page punch list — uncontracted displays

### `hive.html` (1 uncontracted)
- `id="adoption-risk-score"` · token=`adoption`

### `logbook.html` (1 uncontracted)
- `id="quality-pct-value"` · token=`quality`

### `marketplace.html` (1 uncontracted)
- `id="quality-score-num"` · token=`quality`

### `engineering-design.html` (1 uncontracted)
- `id="tg-preload-pct"` · token=`load`

### `platform-health.html` (2 uncontracted)
- `id="health-num"` · token=`health`
- `id="health-score"` · token=`health`

### `achievements.html` (1 uncontracted)
- `id="ac-card-level"` · token=`level`

### `asset-hub.html` (1 uncontracted)
- `id="detail-level"` · token=`level`
