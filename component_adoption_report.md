# Component Adoption Report — Layer F (FULLSTACK_COMPONENT_LIBRARY_ROADMAP §2.2)

> MEASURED 2026-10-26 over **39** family pages. % = adopters / pages-that-need-it (need rule named per row; ∪ adopters). census-only rows have no denominator by design; delegated rows are owned by another gate.

| ID | Class | Canonical primitive | Satisfies | Adoption | % | Gap (first 6) |
|---|---|---|---|---|---|---|
| FT1 | FT Tokens | brand color + contrast tints | C2 | → `validate_design_tokens.py (rawhex census)` | — | — |
| FT2 | FT Tokens | spacing scale | R1 | → `validate_design_tokens.py` | — | — |
| FT3 | FT Tokens | radii + type scale (S1 fingerprint) | S1 | → `validate_design_tokens.py L4 (32/32 locked)` | — | — |
| FT4 | FT Tokens | .wh-tap / .wh-tap-h | F1 | 1 page(s) | n/a | — |
| FT5 | FT Tokens | .wh-text-muted / .wh-text-faint | C2 | 1 page(s) | n/a | — |
| FT6 | FT Tokens | .wh-num | C4 | 1 page(s) | n/a | — |
| FC1 | FC Containers | .simple-card / .action-card / .tile | R3 | **19/39** (family) | **49%** | agentic-rag-observability, analytics-report, assistant, audit-log, community, engineering-design … |
| FC2 | FC Containers | .sum-card | R3 | 3 page(s) | n/a | — |
| FC3 | FC Containers | .wh-scroll-x | R2 | **11/16** (wide-table) | **69%** | analytics-report, assistant, engineering-design, founder-console, llm-observability |
| FC4 | FC Containers | .card (dashboard panel) | R3 | 17 page(s) | n/a | — |
| FI1 | FI Interactive | canonical disclosure (.wh-disclose / .wh-help / wireDetailToggle) | A3 | **37/38** (family) | **97%** | offline-fallback |
| FI2 | FI Interactive | whConfirm / whPrompt | J2 | **20/22** (destructive) | **91%** | assistant, resume |
| FI3 | FI Interactive | chips / pills / tabs vocabulary | R3 | 12 page(s) | n/a | — |
| FF1 | FF Feedback | canonical skeletons (whListSkeleton / whCardSkeleton) | G1 | **31/36** (async-data) | **86%** | analytics-report, engineering-design, founder-console, llm-observability, platform-actions |
| FF2 | FF Feedback | whOhBadge / whProgressStrip | G1/C1 | 5 page(s) | n/a | — |
| FD1a | FD Data display | whFmtDate | N1 | **24/27** (renders-date) | **89%** | engineering-design, llm-observability, platform-actions |
| FD1b | FD Data display | whFmtNum | N1 | **6/25** (renders-number) | **24%** | achievements, alert-hub, analytics, asset-hub, assistant, audit-log … |
| FD1c | FD Data display | whFmtPeso | N1 | **11/13** (peso) | **85%** | engineering-design, platform-actions |
| FD1d | FD Data display | whFmtDuration | N1 | 1 page(s) | n/a | — |
| FD1e | FD Data display | whFmtAgo | S1/N1 | **15/18** (relative-time) | **83%** | founder-console, platform-actions, resume |
| FD2 | FD Data display | renderKpiTile | C1 | 2 page(s) | n/a | — |
| FD3 | FD Data display | renderSourceChip | E3 | **33/35** (async-data) | **94%** | llm-observability, resume |
| FD4 | FD Data display | canonical strips (risk/pmDue/parts/actionBrief) | cross-page reuse | 3 page(s) | n/a | — |
| FCh1 | FCh Chrome | nav-hub.js (+ learn-link, freshness chips) | S1/G1 | **31/36** (family) | **86%** | design-system, founder-console, llm-observability, offline-fallback, platform-actions |
| FCh2 | FCh Chrome | companion-launcher.js | S1 | **29/34** (family) | **85%** | design-system, founder-console, llm-observability, offline-fallback, platform-actions |
| FCh3 | FCh Chrome | i18n floor (whI18nApply + WH_FIL_PAGE / _t) | N1 | **33/36** (family) | **92%** | design-system, llm-observability, offline-fallback |

---
Live confirm any row: `__UFAI.component('.<class>')` (DOM-accurate) or a Playwright walk of the WORKED state. Ratchet: `python tools/validate_component_adoption.py`.
