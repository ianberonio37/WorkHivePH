# HONEST per-layer depth — GATEWAY × GATE × PROD-REAL (2026-06-17)

_The corrected figure Ian asked for: a Gateway (prevention chokepoint / PEP) AND a Gate (detection ratchet) for every layer, graded by REAL depth + whether the proof is PROD-REAL or a local substitute. Deliberately stricter than the 13×6 matrix (100%) and `measure_layer_depth` coverage (84.3%), which both credit detection-presence and local substitutes._


**★ HONEST OVERALL DEPTH = 67.9%**  (axis totals /13 — Gateway 9.0 · Gate 11.0 · Prod-real 6.5)


| Layer | Gateway | Gate | Prod-real | depth% |
|---|---|---|---|---|
| APIs & Backend Logic | 1.0 | 1.0 | 1.0 | **100.0%** |
| Auth & Permissions | 1.0 | 1.0 | 1.0 | **100.0%** |
| Security & RLS | 1.0 | 1.0 | 1.0 | **100.0%** |
| Frontend | 1.0 | 1.0 | 1.0 | **100.0%** |
| Database & Storage | 1.0 | 1.0 | 1.0 | **100.0%** |
| CI/CD & Version Control | 1.0 | 1.0 | 0.5 | **83.3%** |
| Rate Limiting | 1.0 | 1.0 | 0.5 | **83.3%** |
| Availability & Recovery | 1.0 | 1.0 | 0.0 | **66.7%** |
| Caching & CDN | 0.5 | 0.5 | 0.5 | **50.0%** |
| Error Tracking & Logs | 0.5 | 0.5 | 0.0 | **33.3%** |
| Hosting & Deployment | 0.0 | 1.0 | 0.0 | **33.3%** |
| Cloud & Compute | 0.0 | 0.5 | 0.0 | **16.7%** |
| Load Balancing & Scaling | 0.0 | 0.5 | 0.0 | **16.7%** |

## Per-layer basis (m=measured · a=assessed · s=local-substitute · f=factual-external)


### APIs & Backend Logic — 100.0%
- **Gateway 1.0** — m: bypass=0 via gateway_coverage_report.json (measured)
- **Gate 1.0** — m: edge_contracts + envelope ratchets
- **Prod-real 1.0** — f: edge fns ARE the prod backend

### Auth & Permissions — 100.0%
- **Gateway 1.0** — m: bypass=0 via gateway_tenancy_report.json (measured)
- **Gate 1.0** — m: rls-strict/rls-symmetry + tenancy ratchets
- **Prod-real 1.0** — f: RLS + identity run in prod

### Security & RLS — 100.0%
- **Gateway 1.0** — m: bypass=0 via policy_hive_binding_report.json (measured)
- **Gate 1.0** — m: 12 security validators + sast-scan ratchet
- **Prod-real 1.0** — f: RLS/redaction run in prod

### Frontend — 100.0%
- **Gateway 1.0** — m: bypass=0 via user_facing_kpi_canonical_report.json (measured)
- **Gate 1.0** — m: many F ratchets (xss, a11y, displayed-values, capture-roundtrip)
- **Prod-real 1.0** — f: the HTML/JS runs for real users

### Database & Storage — 100.0%
- **Gateway 1.0** — m: bypass=0 via canonical_sources_report.json (measured)
- **Gate 1.0** — m: migration-immutability + truth-view + lineage ratchets
- **Prod-real 1.0** — f: Postgres/Supabase is the prod store

### CI/CD & Version Control — 83.3%
- **Gateway 1.0** — m: bypass=0 via auto_discovery_report.json (measured)
- **Gate 1.0** — m: forward-only baselines + migration-immutability-strict
- **Prod-real 0.5** — s: local runner proven; GitHub Actions runner is external (Ian's gate)

### Rate Limiting — 83.3%
- **Gateway 1.0** — m: bypass=0 via policy_hive_binding_report.json (measured)
- **Gate 1.0** — m: rate-limit-fairness/adoption ratchets
- **Prod-real 0.5** — s: live burst proven LOCAL (60x->429); prod-scale fairness is external

### Availability & Recovery — 66.7%
- **Gateway 1.0** — m: bypass=0 via health_surface_discovery_report.json (measured)
- **Gate 1.0** — m: game-day-readiness ratchet (game_day + verify_backups + RTO/RPO present)
- **Prod-real 0.0** — f: prod failover / multi-AZ / PITR drill are external/unbuilt

### Caching & CDN — 50.0%
- **Gateway 0.5** — a: cached() is a partial chokepoint, adoption < target (documented residual); no CDN-edge convergence
- **Gate 0.5** — a: cache-hit-rate ratchet present but adoption-incomplete
- **Prod-real 0.5** — s: app-cache prod-real; CDN-edge config is external

### Error Tracking & Logs — 33.3%
- **Gateway 0.5** — m: bypass=16 via structured_log_adoption_report.json (measured-partial)
- **Gate 0.5** — a: structured-log-adoption ratchet but sampled
- **Prod-real 0.0** — f: PROD aggregation (Loki/Sentry) is external -- local ndjson only

### Hosting & Deployment — 33.3%
- **Gateway 0.0** — f: no deploy/rollout chokepoint locally enforceable; prod deploy is external
- **Gate 1.0** — m: migration-immutability + deploy-safety ratchet (local)
- **Prod-real 0.0** — f: prod hosting / blue-green / rollback are external (Ian's gate)

### Cloud & Compute — 16.7%
- **Gateway 0.0** — f: no provisioning/autoscale chokepoint (prod-infra)
- **Gate 0.5** — a: health-surface-discovery + cold-start ratchets (partial)
- **Prod-real 0.0** — f: autoscale / provisioning / multi-AZ are external/unbuilt

### Load Balancing & Scaling — 16.7%
- **Gateway 0.0** — f: NO load-balancing chokepoint exists (prod-infra)
- **Gate 0.5** — s: load_probe + connection-pool ratchet are LOCAL SUBSTITUTES (the green tick that most overstated)
- **Prod-real 0.0** — f: real LB / horizontal autoscale are external/unbuilt