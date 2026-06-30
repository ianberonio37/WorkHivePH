# Displayed Values Audit (Tier S coverage)

Scans every page for value-display anchors (element ids ending in
`-num`, `-count`, `-pct`, `-score`, `-days`, etc.) and classifies
each as contracted / uncontracted / raw / unknown.

## Summary

- Pages scanned:           **31**
- Display anchors found:   **106**
- Contracted ✅:           **24** (anchor maps to a registered formula)
- **Uncontracted ⚠️:**     **0** (domain-meaningful metric, no formula registered)
- Raw (counts/dates):      **72** (no contract needed)
- Unknown:                 **10** (couldn't classify from id alone)
- Formula registry:        **22** entries

## Per-page breakdown

| Page | Anchors | Contracted | Uncontracted | Raw | Unknown |
|---|---:|---:|---:|---:|---:|
| `hive.html` | 9 | 1 | 0 | 7 | 1 |
| `logbook.html` | 11 | 1 | 0 | 10 | 0 |
| `inventory.html` | 3 | 1 | 0 | 2 | 0 |
| `pm-scheduler.html` | 5 | 0 | 0 | 5 | 0 |
| `analytics.html` | 5 | 1 | 0 | 4 | 0 |
| `analytics-report.html` | 0 | 0 | 0 | 0 | 0 |
| `skillmatrix.html` | 3 | 2 | 0 | 1 | 0 |
| `community.html` | 7 | 0 | 0 | 7 | 0 |
| `public-feed.html` | 0 | 0 | 0 | 0 | 0 |
| `marketplace.html` | 7 | 3 | 0 | 4 | 0 |
| `marketplace-seller.html` | 2 | 2 | 0 | 0 | 0 |
| `dayplanner.html` | 4 | 0 | 0 | 3 | 1 |
| `engineering-design.html` | 1 | 0 | 0 | 0 | 1 |
| `assistant.html` | 1 | 0 | 0 | 0 | 1 |
| `report-sender.html` | 3 | 0 | 0 | 2 | 1 |
| `platform-health.html` | 6 | 3 | 0 | 1 | 2 |
| `project-manager.html` | 2 | 0 | 0 | 2 | 0 |
| `integrations.html` | 4 | 0 | 0 | 3 | 1 |
| `ph-intelligence.html` | 1 | 0 | 0 | 1 | 0 |
| `project-report.html` | 0 | 0 | 0 | 0 | 0 |
| `predictive.html` | 3 | 0 | 0 | 3 | 0 |
| `ai-quality.html` | 0 | 0 | 0 | 0 | 0 |
| `plant-connections.html` | 0 | 0 | 0 | 0 | 0 |
| `achievements.html` | 3 | 2 | 0 | 1 | 0 |
| `asset-hub.html` | 7 | 5 | 0 | 2 | 0 |
| `shift-brain.html` | 5 | 0 | 0 | 5 | 0 |
| `alert-hub.html` | 5 | 1 | 0 | 4 | 0 |
| `audit-log.html` | 0 | 0 | 0 | 0 | 0 |
| `voice-journal.html` | 2 | 0 | 0 | 1 | 1 |
| `founder-console.html` | 6 | 2 | 0 | 4 | 0 |
| `index.html` | 1 | 0 | 0 | 0 | 1 |

## Per-page punch list — uncontracted displays
