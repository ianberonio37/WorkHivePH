# §14.3 sub-discipline COVERAGE — MEASURED (A7.4)

_Tool-pulled by `tools/measure_layer_depth.py`; denominator = each layer's full sub-discipline checklist (rubric-fixed). COVERED=validator/tool evidence exists · PARTIAL=local/sampled · ABSENT=gap (mostly external prod ceiling)._


> ★**COVERAGE ≠ DEPTH.** This measures whether a MECHANISM EXISTS per sub-discipline (presence/breadth) — an **upper bound on** true-scope depth, NOT depth itself. It tracks the §14.3 *Gate* axis (30–80%), not the true-scope estimate (15–45%). The honest, un-fudgeable signal is the **ABSENT set** = the measured depth backlog.


**Overall measured sub-discipline coverage: 84.3%** (83.5/99 sub-disciplines have ≥1 mechanism)


| Layer | coverage% | covered | partial | absent |
|---|---|---|---|---|
| Frontend | 94.4% | 8 | 1 | 0 |
| APIs & Backend Logic | 100.0% | 9 | 0 | 0 |
| Database & Storage | 94.4% | 8 | 1 | 0 |
| Auth & Permissions | 93.8% | 7 | 1 | 0 |
| Hosting & Deployment | 75.0% | 6 | 0 | 2 |
| Cloud & Compute | 64.3% | 4 | 1 | 2 |
| CI/CD & Version Control | 92.9% | 6 | 1 | 0 |
| Security & RLS | 100.0% | 9 | 0 | 0 |
| Rate Limiting | 83.3% | 4 | 2 | 0 |
| Caching & CDN | 78.6% | 5 | 1 | 1 |
| Load Balancing & Scaling | 58.3% | 3 | 1 | 2 |
| Error Tracking & Logs | 78.6% | 5 | 1 | 1 |
| Availability & Recovery | 64.3% | 4 | 1 | 2 |

## Per-layer sub-discipline detail (the denominator + evidence)


### Frontend — 94.4% covered
- ✅ Render-value truth (rendered number == source) · `displayed-values`, `source-chip-truth`, `diagram_value_alignment`
- ✅ XSS-safe rendering (escHtml coverage) · `xss`, `innerhtml-eschtml`
- ✅ Accessibility (aria / labels / headings / contrast) · `accessibility`, `aria-label-coverage`, `heading-hierarchy`
- ✅ Responsive / mobile (touch, safe-area, viewport) · `mobile`, `viewport-user-scalable`
- ✅ Empty / loading / error states · `loading-state`, `feedback-widget`
- 🟡 Render budget / Core Web Vitals · `render-budget`, `bundle-bloat` — _CWV is L2-spec only; live-boot capture unreliable_
- ✅ State management discipline (module scope, listener cleanup) · `module-scope-state`, `event-listener-cleanup`, `timer-cleanup`
- ✅ Design-system tokens / brand consistency · `design-tokens`
- ✅ Capture round-trip (input value -> DB faithfully) · `capture-contracts`, `tool:verify_capture_roundtrip.py`

### APIs & Backend Logic — 100.0% covered
- ✅ Request/response envelope contract · `edge-contracts`, `envelope-conformance`, `envelope-return-shape`
- ✅ Input validation / guards · `input-guards`, `json-parse-safety`, `response_format_validation`
- ✅ Idempotency (safe retries) · `idempotency`, `optimistic-concurrency`
- ✅ Error status + body contract · `edge-status-body`, `edge-response-content-type`, `edge-body-size-guard`
- ✅ Gateway pipeline (one front door) · `gateway-routing`, `gateway-coverage`, `gateway-audit`
- ✅ Routing coverage (no bypass) · `gateway-coverage`, `edge-caller-contract`, `edge-function-invoke`
- ✅ OpenAPI / contract sync · `openapi-sync`
- ✅ CORS / preflight correctness · `cors-wildcard`, `edge-options-preflight`
- ✅ Dependency pinning (reproducible imports) · `edge-unpinned-imports`, `reproducible-build-pin`

### Database & Storage — 94.4% covered
- ✅ Canonical truth layer (one definition per value) · `truth-view-contract`, `truth-view-consumer-columns`, `kpi-source-registry`
- ✅ Migration immutability + ordering · `migration-immutability`, `migration-order`, `migration-immutability-strict`
- ✅ Schema drift / coverage · `schema-drift`, `schema-coverage`, `phantom-columns`
- ✅ Referential integrity (FK / on-delete) · `fk-on-delete`, `soft-delete`
- ✅ Data lineage (input -> consumer graph) · `tool:mine_lineage_map.py`, `tool:journey_trace.py`
- ✅ Retention / archival · `data-retention`, `cold-archive`, `cold-archive-wiring`
- ✅ Indexing / query performance · `index-coverage`, `jsonb-index`, `unbounded-query`
- ✅ JSONB / semi-structured integrity · `jsonb-drift`, `vector-schema`, `pgvector-consistency`
- 🟡 Backup / restore verification · `tool:verify_backups.py` — _verify_backups is a local structural check; prod PITR is external_

### Auth & Permissions — 93.8% covered
- ✅ Identity resolution (server-derived, not client) · `gateway-tenancy`, `auth-boundary`
- ✅ Tenancy resolution (hive scoping) · `gateway-tenancy`, `tenant-boundary`
- ✅ RBAC roles consistency · `role-string-consistency`, `admin-gates`
- ✅ RLS policies (strict + symmetric) · `rls-strict`, `rls-symmetry`, `rls-open-policy`
- ✅ IDOR / policy binding (per-tenant key) · `policy-hive-binding`, `definer-membership-gate`
- ✅ Auth migration readiness · `auth-migration-readiness`
- 🟡 SSO / SAML (enterprise) · `sso-readiness` — _readiness check only; live SSO is enterprise-gated_
- ✅ Service-role exposure guard · `service-role-exposure`, `security-definer-search-path`

### Hosting & Deployment — 75.0% covered
- ✅ Deploy safety gate · `deploy-safety`, `ci-gate-sentinel`
- ✅ Migration immutability at deploy · `migration-immutability-strict`
- ✅ Env / config completeness · `env-variable-existence`, `env-secret-coverage`, `edge-config`
- ✅ Secrets management (no hardcode) · `hardcoded-secrets`
- ✅ Reproducible build (pinned) · `reproducible-build-pin`
- ✅ Deploy-signal mining · `mine-deploy-signals`
- 🔴 Blue-green / rollback — _prod rollout strategy is external (Ian's prod gate)_
- 🔴 CDN / static hosting config — _prod CDN/hosting config is external_

### Cloud & Compute — 64.3% covered
- ✅ Runtime health endpoints · `health-endpoint`, `health-surface-discovery`
- ✅ Cold-start / warm-path optimisation · `cold-start-memoization`
- ✅ Capacity signal mining · `mine-capacity-signals`
- ✅ Edge runtime config · `edge-config`
- 🔴 Autoscaling policy — _autoscale is prod-infra, external_
- 🔴 Provisioning / IaC — _provisioning/IaC is external_
- 🟡 Compute cost observability · `ai-cost-observability` — _AI compute cost tracked; general compute cost is prod-billing_

### CI/CD & Version Control — 92.9% covered
- ✅ Change chokepoint (every change gated) · `auto-discovery`, `gate-observability`
- ✅ Validator self-coverage · `validator-self-coverage`, `validator-freshness`, `tester-coverage`
- ✅ Immutability of shipped artifacts · `migration-immutability-strict`
- ✅ Pattern-mining (new code auto-classified) · `edge-pattern-mining`, `html-pattern-mining`, `seeder-pattern-mining`
- ✅ Baseline / regression ratchets · `sentinel-baseline`, `tool:platform_baseline.json`
- 🟡 CI gate runner · `ci-gate-sentinel`, `tool:ci_gate.py` — _ci_gate runs locally; GitHub Actions runner is external_
- ✅ Reproducible build pin · `reproducible-build-pin`

### Security & RLS — 100.0% covered
- ✅ XSS / output encoding · `xss`, `innerhtml-eschtml`
- ✅ Injection (SQL/LIKE/JSON) · `like-escape`, `json-parse-safety`, `kpi-count-query-safety`
- ✅ Secrets hygiene · `hardcoded-secrets`, `env-secret-coverage`
- ✅ PII egress control · `pii-egress`
- ✅ SAST scanning · `sast-scan`
- ✅ CORS / origin policy · `cors-wildcard`
- ✅ Service-role / privilege escalation · `service-role-exposure`, `security-definer-search-path`, `provider-bypass`
- ✅ Audit trail / tamper evidence · `audit-trail-coverage`, `audit-log-coverage`, `audit-scanner-scope`
- ✅ Auth boundary (cross-ref Auth layer) · `auth-boundary`, `policy-hive-binding`

### Rate Limiting — 83.3% covered
- ✅ Per-tenant rate-limit binding · `policy-hive-binding`
- ✅ Fairness (no cross-tenant drain) · `rate-limit-fairness`
- ✅ Adoption across endpoints · `rate-limit-adoption`
- ✅ Rate-limit signal mining · `mine-rate-limit-signals`
- 🟡 429 + Retry-After contract · `edge-status-body` — _429 contract asserted statically; live burst is V-strict/local_
- 🟡 Per-route quota · `rate-limit-adoption` — _per-route quota in ai-gateway only; not all routes_

### Caching & CDN — 78.6% covered
- ✅ Application cache (LLM / compute) · `llm-cache-adoption`, `cache-hit-rate`
- ✅ Cache invalidation correctness · `cache-invalidation`
- ✅ Hit-rate observability · `cache-hit-rate`
- ✅ Cache-signal mining · `mine-cache-signals`, `mine-cache-name-drift`
- ✅ Offline / service-worker cache · `offline-resilience`, `sw-offline`, `service-worker-shell`
- 🔴 CDN edge caching — _prod CDN edge config is external_
- 🟡 Cache adoption breadth · `llm-cache-adoption` — _cache adoption ratchet < target (documented residual)_

### Load Balancing & Scaling — 58.3% covered
- ✅ Connection-pool saturation guard · `connection-pool-saturation`, `connection-surface-discovery`
- ✅ Capacity planning · `mine-capacity-signals`
- ✅ Load resilience (degraded-mode) · `load-resilience`
- 🟡 Load test (concurrent burst) · `tool:load_test.k6.js` — _k6 harness points at local edge; prod load tier needs k6 install/prod_
- 🔴 Horizontal scaling policy — _horizontal scale is prod-infra, external_
- 🔴 Load balancer config — _LB config is prod-infra, external_

### Error Tracking & Logs — 78.6% covered
- ✅ Structured logging adoption · `structured-log-adoption`
- ✅ Log correlation (trace id) · `log-correlation`
- ✅ Trace store / SLI rollup · `tool:trace-store.ts`, `observability`, `adoption-observability`
- ✅ Log-surface discovery · `log-surface-discovery`
- ✅ Console-log drift guard · `console-log-drift`
- 🔴 Prod aggregation (Loki/Sentry) — _prod log aggregation backend is external_
- 🟡 Error budget / alerting · `pattern-alerts`, `proactive-alerts` — _alerting present; formal error-budget burn is prod-SLO_

### Availability & Recovery — 64.3% covered
- ✅ Health endpoints · `health-endpoint`, `health-surface-discovery`
- ✅ SLO definition · `art:GATEWAY_SLO.md`
- ✅ Game-day readiness · `game-day-readiness`, `tool:game_day.py`
- 🟡 Backup verification · `tool:verify_backups.py` — _structural backup check local; prod PITR external_
- ✅ Degraded-mode / offline resilience · `offline-resilience`, `load-resilience`
- 🔴 Failover / multi-region — _failover/multi-region is prod-infra, external_
- 🔴 PITR / restore drill — _point-in-time-restore drill is external_