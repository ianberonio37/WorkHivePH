# Lineage Map — §13 P0 Denominator (E2E Nerve-Sweep)

_Generated 2026-06-17T19:31:31.923882+00:00 by `tools/mine_lineage_map.py`._

> Mapped% = the P0 exit (denominator discovered). P% / H% = the LIVE differential nerve-probe (P1+). Everything starts verified=0 — honest by design.

## Measured scoreboard

| Number | Meaning | Value |
|---|---|---|
| **mapped %** | input fields with a discovered consumer graph / total (**P0 exit**) | 461/461 = **100.0%** |
| **P · page % (strict)** | feature pages FULLY input-nerve-verified / 27 (§13.5) | 12/27 = **50.0%** |
| P · engine-proven | pages with ≥1 nerve LIVE-proven / applicable (27 − 3 N/A) | 24/24 = **100.0%** |
| **H · nerve %** | verified (field→consumer) paths / total | 71/562 = **12.6%** |
| live-proven nerves | nerves verified by `journey_trace.py` (paths) | 17 (46 paths) |
| **input pages mapped** | input surfaces statically mapped / 15 (the honest fraction) | 13/15 = **86.7%** |
| H breakdown | capture reverse-lineage + curated chains | 477 + 85 |
| **V · strict** | journey×layer cells PROVEN-LIVE / applicable (P4/P5, `journey_vaxis.py`) | 56/67 = **83.6%** |
| V · covered | proven + disk-backed attribution / applicable (77 − 10 n/a) | 67/67 = **100.0%** |

### ⚠ Live-discovery-pending — 2 input surface(s) the static map CANNOT see

> These write canonical tables but expose no static capture markup (JS-rendered grid / action / edge-fn). The 100% mapped figure above is over *static-visible* fields; these surfaces are honestly NOT yet mapped and await the live probe (P1/P2).

| Page | Writes tables | Why invisible |
|---|---|---|
| skillmatrix | skill_badges, skill_exam_attempts, skill_profiles | JS-rendered / action / edge-fn driven |
| alert-hub | amc_briefings, anomaly_signals, hive_audit_log | JS-rendered / action / edge-fn driven |

### Provenance (the reused oracles)

- captures alive / phantom: **504 / 0** (Phantom Capture Auditor); 43 on excluded pages
- KPI metrics (transform layer): **5**
- curated lineage edges: **17**
- calm terminus pages (dashboard→view): **15**

## Per-page input nerves (the P axis)

| Page | Role | Input fields | Writes tables | Engine-proven |
|---|---|---:|---:|:---:|
| logbook | input | 42 | 8 | ✅ |
| pm-scheduler | input | 18 | 6 | ✅ |
| inventory | input | 16 | 4 | ✅ |
| dayplanner | input | 6 | 2 | — |
| skillmatrix | input | 0 | 3 | ✅ |
| engineering-design | input | 265 | 1 | — |
| report-sender | input | 3 | 1 | ✅ |
| community | input | 7 | 4 | ✅ |
| marketplace | input | 31 | 8 | ✅ |
| project-manager | input | 46 | 6 | ✅ |
| integrations | input | 7 | 10 | ✅ |
| asset-hub | input | 22 | 9 | ✅ |
| voice-journal | input | 1 | 1 | ✅ |
| resume | input | 6 | 2 | — |
| alert-hub | input | 0 | 3 | ✅ |
| analytics | terminus | 0 | 0 | ✅ |
| analytics-report | terminus | 0 | 0 | ✅ |
| project-report | terminus | 0 | 0 | ✅ |
| ph-intelligence | terminus | 0 | 0 | ✅ |
| predictive | terminus | 0 | 0 | ✅ |
| ai-quality | terminus | 0 | 0 | ✅ |
| shift-brain | terminus | 0 | 1 | ✅ |
| achievements | terminus | 0 | 0 | ✅ |
| audit-log | terminus | 0 | 0 | ✅ |
| hive | terminus | 0 | 4 | ✅ |
| plant-connections | terminus | 0 | 0 | ✅ |
| assistant | terminus | 0 | 1 | ✅ |
