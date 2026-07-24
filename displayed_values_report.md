# Displayed Values Audit (Tier S coverage)

Scans every page for value-display anchors (element ids ending in
`-num`, `-count`, `-pct`, `-score`, `-days`, etc.) and classifies
each as contracted / uncontracted / raw / unknown.

## Summary

- Pages scanned:           **29**
- Display anchors found:   **102**
- Contracted ✅:           **19** (anchor maps to a registered formula)
- **Uncontracted ⚠️:**     **0** (domain-meaningful metric, no formula registered)
- Raw (counts/dates):      **83** (no contract needed)
- Unknown:                 **0** (couldn't classify from id alone)
- Formula registry:        **22** entries

## Per-page breakdown

| Page | Anchors | Contracted | Uncontracted | Raw | Unknown |
|---|---:|---:|---:|---:|---:|
| `hive.html` | 12 | 1 | 0 | 11 | 0 |
| `logbook.html` | 11 | 1 | 0 | 10 | 0 |
| `inventory.html` | 3 | 1 | 0 | 2 | 0 |
| `pm-scheduler.html` | 5 | 0 | 0 | 5 | 0 |
| `analytics.html` | 5 | 1 | 0 | 4 | 0 |
| `analytics-report.html` | 0 | 0 | 0 | 0 | 0 |
| `skillmatrix.html` | 3 | 2 | 0 | 1 | 0 |
| `community.html` | 7 | 0 | 0 | 7 | 0 |
| `public-feed.html` | 0 | 0 | 0 | 0 | 0 |
| `marketplace.html` | 8 | 3 | 0 | 5 | 0 |
| `marketplace-seller.html` | 1 | 0 | 0 | 1 | 0 |
| `dayplanner.html` | 4 | 0 | 0 | 4 | 0 |
| `engineering-design.html` | 1 | 0 | 0 | 1 | 0 |
| `assistant.html` | 1 | 0 | 0 | 1 | 0 |
| `report-sender.html` | 3 | 0 | 0 | 3 | 0 |
| `project-manager.html` | 2 | 0 | 0 | 2 | 0 |
| `integrations.html` | 4 | 0 | 0 | 4 | 0 |
| `ph-intelligence.html` | 1 | 0 | 0 | 1 | 0 |
| `project-report.html` | 0 | 0 | 0 | 0 | 0 |
| `ai-quality.html` | 0 | 0 | 0 | 0 | 0 |
| `plant-connections.html` | 0 | 0 | 0 | 0 | 0 |
| `achievements.html` | 3 | 2 | 0 | 1 | 0 |
| `asset-hub.html` | 7 | 5 | 0 | 2 | 0 |
| `shift-brain.html` | 5 | 0 | 0 | 5 | 0 |
| `alert-hub.html` | 6 | 1 | 0 | 5 | 0 |
| `audit-log.html` | 0 | 0 | 0 | 0 | 0 |
| `voice-journal.html` | 3 | 0 | 0 | 3 | 0 |
| `founder-console.html` | 6 | 2 | 0 | 4 | 0 |
| `index.html` | 1 | 0 | 0 | 1 | 0 |

## Per-page punch list — uncontracted displays
