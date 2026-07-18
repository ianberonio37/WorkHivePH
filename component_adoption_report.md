# Component Adoption Report — Layer F (FULLSTACK_COMPONENT_LIBRARY_ROADMAP §2.2)

> MEASURED 2026-07-17 over **32** family pages. % = adopters / pages-that-need-it (need rule named per row; ∪ adopters). census-only rows have no denominator by design; delegated rows are owned by another gate.

| ID | Class | Canonical primitive | Satisfies | Adoption | % | Gap (first 6) |
|---|---|---|---|---|---|---|
| FT1 | FT Tokens | brand color + contrast tints | C2 | → `validate_design_tokens.py (rawhex census)` | — | — |
| FT2 | FT Tokens | spacing scale | R1 | → `validate_design_tokens.py` | — | — |
| FT3 | FT Tokens | radii + type scale (S1 fingerprint) | S1 | → `validate_design_tokens.py L4 (32/32 locked)` | — | — |
| FT4 | FT Tokens | .wh-tap / .wh-tap-h | F1 | 0 page(s) | n/a | — |
| FT5 | FT Tokens | .wh-text-muted / .wh-text-faint | C2 | 0 page(s) | n/a | — |
| FT6 | FT Tokens | .wh-num | C4 | 0 page(s) | n/a | — |
| FC1 | FC Containers | .simple-card / .action-card / .tile | R3 | **18/32** (family) | **56%** | agentic-rag-observability, assistant, audit-log, community, engineering-design, logbook … |
| FC2 | FC Containers | .sum-card | R3 | 2 page(s) | n/a | — |
| FC3 | FC Containers | .wh-scroll-x | R2 | **10/10** (wide-table) | **100%** | — |
| FC4 | FC Containers | .card (dashboard panel) | R3 | 31 page(s) | n/a | — |
| FI1 | FI Interactive | canonical disclosure (.wh-disclose / .wh-help / wireDetailToggle) | A3 | **31/31** (family) | **100%** | — |
| FI2 | FI Interactive | whConfirm / whPrompt | J2 | **16/16** (destructive) | **100%** | — |
| FI3 | FI Interactive | chips / pills / tabs vocabulary | R3 | 23 page(s) | n/a | — |
| FF1 | FF Feedback | canonical skeletons (whListSkeleton / whCardSkeleton) | G1 | **29/29** (async-data) | **100%** | — |
| FF2 | FF Feedback | whOhBadge / whProgressStrip | G1/C1 | 4 page(s) | n/a | — |
| FD1a | FD Data display | whFmtDate | N1 | **19/19** (renders-date) | **100%** | — |
| FD1b | FD Data display | whFmtNum | N1 | **5/5** (renders-number) | **100%** | — |
| FD1c | FD Data display | whFmtPeso | N1 | **9/9** (peso) | **100%** | — |
| FD1d | FD Data display | whFmtDuration | N1 | 0 page(s) | n/a | — |
| FD1e | FD Data display | whFmtAgo | S1/N1 | **14/14** (relative-time) | **100%** | — |
| FD2 | FD Data display | renderKpiTile | C1 | 1 page(s) | n/a | — |
| FD3 | FD Data display | renderSourceChip | E3 | **28/28** (async-data) | **100%** | — |
| FD4 | FD Data display | canonical strips (risk/pmDue/parts/actionBrief) | cross-page reuse | 3 page(s) | n/a | — |
| FCh1 | FCh Chrome | nav-hub.js (+ learn-link, freshness chips) | S1/G1 | **29/29** (family) | **100%** | — |
| FCh2 | FCh Chrome | companion-launcher.js | S1 | **27/27** (family) | **100%** | — |
| FCh3 | FCh Chrome | i18n floor (whI18nApply + WH_FIL_PAGE / _t) | N1 | **29/29** (family) | **100%** | — |

---
Live confirm any row: `__UFAI.component('.<class>')` (DOM-accurate) or a Playwright walk of the WORKED state. Ratchet: `python tools/validate_component_adoption.py`.
