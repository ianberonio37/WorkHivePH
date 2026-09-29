# Displayed Values Audit (Tier S coverage)

Scans every page for value-display anchors (element ids ending in
`-num`, `-count`, `-pct`, `-score`, `-days`, etc.) and classifies
each as contracted / uncontracted / raw / unknown.

## Summary

- Pages scanned:           **36**
- Display anchors found:   **121**
- Contracted ✅:           **22** (anchor maps to a registered formula)
- **Uncontracted ⚠️:**     **0** (domain-meaningful metric, no formula registered)
- Raw (counts/dates):      **94** (no contract needed)
- Unknown:                 **5** (couldn't classify from id alone)
- Formula registry:        **24** entries

## Per-page breakdown

| Page | Anchors | Contracted | Uncontracted | Raw | Unknown |
|---|---:|---:|---:|---:|---:|
| `hive.html` | 12 | 1 | 0 | 11 | 0 |
| `logbook.html` | 11 | 1 | 0 | 10 | 0 |
| `inventory.html` | 3 | 1 | 0 | 2 | 0 |
| `pm-scheduler.html` | 5 | 0 | 0 | 5 | 0 |
| `analytics.html` | 6 | 1 | 0 | 5 | 0 |
| `analytics-report.html` | 0 | 0 | 0 | 0 | 0 |
| `skillmatrix.html` | 3 | 2 | 0 | 1 | 0 |
| `community.html` | 8 | 0 | 0 | 8 | 0 |
| `public-feed.html` | 0 | 0 | 0 | 0 | 0 |
| `marketplace.html` | 9 | 3 | 0 | 6 | 0 |
| `marketplace-seller.html` | 1 | 1 | 0 | 0 | 0 |
| `dayplanner.html` | 5 | 0 | 0 | 5 | 0 |
| `engineering-design.html` | 1 | 0 | 0 | 1 | 0 |
| `assistant.html` | 2 | 0 | 0 | 2 | 0 |
| `report-sender.html` | 3 | 0 | 0 | 3 | 0 |
| `project-manager.html` | 6 | 0 | 0 | 6 | 0 |
| `integrations.html` | 4 | 0 | 0 | 4 | 0 |
| `ph-intelligence.html` | 1 | 0 | 0 | 1 | 0 |
| `project-report.html` | 0 | 0 | 0 | 0 | 0 |
| `ai-quality.html` | 0 | 0 | 0 | 0 | 0 |
| `plant-connections.html` | 0 | 0 | 0 | 0 | 0 |
| `achievements.html` | 4 | 3 | 0 | 1 | 0 |
| `asset-hub.html` | 7 | 5 | 0 | 2 | 0 |
| `shift-brain.html` | 5 | 0 | 0 | 5 | 0 |
| `alert-hub.html` | 7 | 1 | 0 | 5 | 1 |
| `audit-log.html` | 0 | 0 | 0 | 0 | 0 |
| `voice-journal.html` | 3 | 0 | 0 | 3 | 0 |
| `founder-console.html` | 6 | 2 | 0 | 4 | 0 |
| `index.html` | 1 | 0 | 0 | 1 | 0 |
| `validator-catalog.html` | 3 | 0 | 0 | 1 | 2 |
| `symbol-gallery.html` | 1 | 0 | 0 | 1 | 0 |
| `design-system.html` | 0 | 0 | 0 | 0 | 0 |
| `llm-observability.html` | 2 | 1 | 0 | 0 | 1 |
| `offline-fallback.html` | 0 | 0 | 0 | 0 | 0 |
| `architecture.html` | 1 | 0 | 0 | 0 | 1 |
| `learn/index.html` | 1 | 0 | 0 | 1 | 0 |

## Per-page punch list — uncontracted displays
