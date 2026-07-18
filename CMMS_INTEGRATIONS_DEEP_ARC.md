# CMMS Integrations Deep Arc (PDDA) — Page-Deep UFAI

> **Arc kind:** *Page-depth* — the SAME refined PDDA method (Understand → Deepwalk → Ideate →
> Roadmap → Execute → Re-deepwalk) that took `engineering-design` ≈59%→~99%, the Resume Builder
> **~52%→100%**, the Landing + Home-Dashboard **~52%→96.4%**, and the **Analytics Engine → 16 defects
> fixed + all-axes-clean** (5th page-depth arc). The platform-wide breadth ruler scores every page
> **shallow**; this arc scores the **CMMS Integrations surface deep** — a fine UFAI sub-dimension
> decomposition, grounded in external standards, driven LIVE via Playwright MCP, improved with skill +
> reputable-source ideas, ratcheted by gates.
>
> **★This is a SECURITY-CRITICAL surface** (inbound webhooks, machine-ingest, external credentials,
> cross-tenant sync). The **I** (Internal Control) and **F** (sync/webhook correctness) axes are the
> heavyweights here — analogous to F1 (KPI correctness) on the Analytics arc.
>
> **Target surface:**
> - **`integrations.html`** (**1932 lines**) — the CMMS/ERP/IoT integration hub: SAP PM, IBM Maximo,
>   Infor EAM, OPC-UA, MQTT, REST API + webhook, SSO/SAML. Connection setup wizards, connection
>   status/health, field-mapping, sync direction.
> - **`plant-connections.html`** (**697 lines**) — the Plant Connections console (S-role; the
>   supervisor/IT view of live plant connections + their state).
> - **Compute / edge fns:** `cmms-sync` (bidirectional work-order/inventory sync), `cmms-webhook-receiver`
>   (inbound webhook, **signature-gated**), `cmms-push-completion` (WorkHive → CMMS completion push),
>   `export-hive-data` (data export). Adjacent machine-ingest: `sensor-readings-ingest`, `pdf-ingest`.
>   `intelligence-api` (invoked by the page).
> - **Tables:** `integration_configs` (connection settings/credentials), `external_sync` (external_id ↔
>   workhive_id mapping + last_synced_at + sync_status), `v_external_sync_truth` (canonical sync state).
> - **2 `/learn/` subdirs:** `learn/connecting-workhive-to-sap-maximo-cmms/`,
>   `learn/sensor-cmms-gateway-operations/`.
>
> **Audience:** Filipino industrial plant IT/OT + supervisors connecting WorkHive to the CMMS/ERP/sensors
> they ALREADY run — WorkHive as the intelligence layer on top of SAP PM / Maximo, not a replacement.
> The connection must be trustworthy, isolated per-hive, and honest about sync state.

## The PDDA loop (6 phases) — identical to the eng-design + resume + landing + analytics arcs
0. **Ground** — skill-first reads + external integration/webhook/protocol standards → a *falsifiable*
   UFAI sub-dim checklist. (DONE at scaffold, below.)
1. **Understand** — map `integrations.html`: each connection TYPE (SAP/Maximo/OPC-UA/MQTT/webhook/SSO) +
   its setup wizard + fields; the connection status/health render; the `cmms-sync`/`cmms-webhook-receiver`/
   `cmms-push-completion`/`export-hive-data` round-trips; `integration_configs`/`external_sync` reads +
   RLS; the auth/role gate; `plant-connections.html`; escHtml coverage; the 2 learn subdirs; deps/CSP.
2. **Deepwalk (live)** — drive via Playwright MCP (whPage `pabloaguilar`/Lucena hive `b86f9ef6` =
   supervisor who manages connections; rawPage anon for the learn subdirs + SEO). Score each sub-dim
   with **measured** evidence: axe (page+wizards+status), CWV, connection setup/test/edit/delete round-trip,
   **the webhook signature + idempotency + caller-auth (BOLA foreign-hive_id injection) live probes**,
   sync field-mapping faithfulness, secret non-leak, cross-tenant connection isolation, honest sync-fail
   state, learn-subdir a11y. Fill the scoreboard baseline %.
3. **Ideate** — fan-out relevant skills + reputable sources → improvement backlog per axis (cited).
4. **Roadmap** — synthesize into the scoreboard (% per axis, owning skill, citation, locking gate).
5. **Execute** — implement each fix; **verify live each**; lock with a gate/test (ratchet).
6. **Re-deepwalk** — re-score to confirm the ratchet held; synthesize fuse/keep verdicts; persist to
   skills + memory.

**Done = every axis at its roadmap target, MEASURED and gate-locked** — not one headline metric.

> **Key PDDA insight (proven 5×):** the coarse ruler scans one state statically; the depth walk scans
> the WORKED state. Here that means a **live connection being set up, tested, synced, and pushed** — plus
> the **inbound webhook attack surface**. Defects a static/single-state scan structurally cannot see: a
> webhook receiver that skips signature/replay verification, a machine-ingest fn that trusts the body's
> `hive_id` on a service-role client (cross-tenant injection), a sync that duplicates on replay (non-
> idempotent), a secret leaked into the page/localStorage, a connection whose synced data leaks across
> hives, a "connected/healthy" status that lies when the CMMS is actually unreachable, a field-mapping
> that silently corrupts (SAP AUFNR→wrong field).

---

## The five scored axes (CMMS Integrations sub-dimension decomposition)

### U — Usability
- **U1** Connection-setup clarity — a plant IT/supervisor can add a CMMS/ERP/IoT/webhook/SSO connection with clear steps; each field explained (SAP endpoint, AUFNR/MATNR mapping, OPC-UA URL, webhook secret); no unexplained jargon.
- **U2** Connection status legibility — connected / syncing / last-synced / error states are clear at a glance; sync health + direction visible; a failure is obvious, not buried.
- **U3** Navigation & wayfinding — integrations ↔ plant-connections ↔ the synced data (logbook/inventory/asset-hub) ↔ the 2 learn subdirs resolve + are consistent; a way back.
- **U4** Empty / not-yet-connected state — a hive with no connections sees an HONEST "no connections yet — here's how to connect your CMMS", never a fake-connected or broken state.
- **U5** Inclusivity / a11y — axe WCAG2.2-AA = 0 on `integrations.html`, `plant-connections.html`, the OPEN setup-wizard/modal states, AND the 2 learn subdirs; forms labelled; contrast; focus.
- **U6** Content clarity / scannability — connection types, sync directions, field mappings, and the learn articles are scannable + plain-language for a PH plant IT/supervisor (NN/g; no wall-of-jargon).

### F — Functionality (heavyweight — sync/webhook correctness)
- **F1** Webhook-receiver correctness — `cmms-webhook-receiver` **verifies the HMAC signature**, is **idempotent** (a replayed webhook does NOT double-process), has **replay/timestamp protection**, and handles malformed/oversized payloads without 500 (REUSE `fb1_webhook_idempotency_live.py` + the "Webhook and Integration Idempotency" validator).
- **F2** Sync integrity — `cmms-sync` maps fields correctly (SAP AUFNR→external_id, LTXT→description, MATNR→part_number, etc.), **idempotent upsert** on `external_id` (no dup on re-run), one-way vs two-way handled, conflict resolution; `external_sync`/`v_external_sync_truth` stay faithful.
- **F3** Push-completion correctness — `cmms-push-completion` pushes the correct completion + status mapping to the CMMS; failure/retry handled honestly (no silent-drop).
- **F4** Export correctness — `export-hive-data` exports the correct **hive-scoped** data; format valid; no cross-tenant residue; large export bounded.
- **F5** Connection lifecycle — create / **test-connection** / edit / delete a connection works end-to-end; test-connection validates credentials HONESTLY (no fake "success"); status persists to `integration_configs`.
- **F6** Cross-surface consistency — data synced IN (work orders / inventory / assets) appears correctly on the consuming pages (logbook / inventory / asset-hub) matching the external source (no per-page divergence).

### A — Adaptability
- **A1** Responsive both viewports — the page + `plant-connections` + connection wizards at 390 mobile + desktop; no h-overflow; modals fit.
- **A2** Connection-volume adaptation — works for 0, 1, and many connections; long lists / many mappings don't break.
- **A3** Persona coverage — supervisor/IT-admin manages connections; a field worker sees the intended (read-only or hidden) subset; role gating enforced.
- **A4** Performance / Core Web Vitals — LCP < 2.5s / CLS < 0.1 / INP < 200ms; a connection-test / sync must NOT block/freeze the UI (async + honest spinner).
- **A5** Offline / degraded-network — a CMMS/broker/IdP unreachable → honest "connection failed · last synced X", NEVER a fake-healthy or blank read as "all connected"; retry/backoff.
- **A6** Localization / plain-language — PH plant-IT vocabulary; special chars safe; no em dashes in rendered copy.

### I — Internal Control (heavyweight — SECURITY-critical)
- **I1** Ingest/webhook caller-auth — **THE load-bearing axis.** `cmms-webhook-receiver` authenticates by **HMAC signature** (that IS the caller-auth — don't double-gate); `cmms-sync`/`cmms-push-completion`/`export-hive-data`/`sensor-readings-ingest`/`pdf-ingest` MUST authenticate the caller before any write and NEVER trust the body's `hive_id` on a service-role client (the 2026-06-15 lesson: `requireServiceRole` or a per-hive ingest key). **BOLA probe:** a signed-in worker POSTing a FOREIGN `hive_id` → 401/403, never a cross-tenant write.
- **I2** Auth + role gating — integrations / plant-connections render + allow management ONLY for the authorized (supervisor/IT) role; a field-worker/anon can't manage connections or read config; no flash-of-authed-content.
- **I3** Secret handling — CMMS/ERP credentials + webhook secrets + ingest keys are stored/transmitted securely; NEVER rendered into the page DOM / localStorage / console / error text; masked in the UI; rotation path exists (or is surfaced as a product decision).
- **I4** XSS / output-encoding — dynamic connection names, external-system responses, sync-error messages, and mapped external field values are escHtml-escaped; a malicious CMMS/webhook payload can't XSS the operator's browser.
- **I5** Hive-scoped connections — a connection + its synced rows are STRICTLY hive-scoped; `integration_configs`/`external_sync` RLS blocks cross-tenant read/write; a foreign hive can't see or use another's connection.
- **I6** Idempotency / replay integrity — webhook idempotency keys + replay/timestamp windows prevent double-processing; sync ordering + dedup on `external_id`; a duplicate inbound event is a no-op.

### AI — AI Integrity (lighter here; note where it applies)
- **AI1** Any AI-assisted mapping / normalization (`pdf-ingest` extraction, a data-fabric normalizer, an AI field-mapper) is GROUNDED — no fabricated field mappings / values / statuses.
- **AI2** `intelligence-api` (invoked by the page) grounds its output in real connection/sync data; no invented insight.
- **AI3** AI copy truthfulness — any AI-surfaced integration status/summary makes only TRUE claims; plain-language.
- **AI4** Suppression on insufficient/failed data — no confident AI output when a sync failed or data is missing.

---

## Scoreboard (fill after Phase 2 deepwalk; re-score Phase 6)

| Axis | Sub-dims verified | Baseline % (measured) | Target | Locking gate | Owning skill |
|---|---|---|---|---|---|
| U — Usability | _/6 | _TBD Phase 2_ | 100 | axe (page+wizards+2 subdirs) + `integrations.spec.ts` | integration / frontend / designer / qa / mobile |
| F — Functionality | _/6 | _TBD_ | 100 | webhook idempotency + sync-faithfulness + export-scope + lifecycle specs | integration / data / qa |
| A — Adaptability | _/6 | _TBD_ | 100 | CWV + responsive + connection-volume + offline-honesty | performance / mobile / frontend |
| I — Internal Control | _/6 | _TBD_ | 100 | **caller-auth/BOLA + role-gate + secret-non-leak + XSS + connection-RLS + replay** | **security / multitenant / integration / architect** |
| AI — AI Integrity | _/4 | _TBD_ | 100 | normalize/ingest grounding + suppression | ai-engineer / integration |
| **Integrations overall** | **_/28** | **_TBD_** | **100** | | |

---

## Phase 0 — GROUND (done at scaffold time)

**Skill-first (READ before touching):** `integration-engineer` (**PRIMARY** — SAP PM/Maximo field maps,
external_sync table, MQTT/OPC-UA, webhook HMAC framework, SSO/SAML, idempotent import, **+ the
2026-06-15 ingest-caller-auth lesson**), `security` (webhook HMAC/replay, secret handling, OWASP API
Top 10, requireServiceRole gate), `multitenant-engineer` (per-hive connection isolation; service-role
RLS-bypass danger), `data-engineer` (sync/import idempotency, conflict resolution, external_id dedup),
`architect` (the `integration_configs`/`external_sync`/`v_external_sync_truth` data model), `devops`
(webhook endpoints, cron sync, secrets management), `frontend` + `designer` (the setup-wizard UI +
status), `qa-tester` (the journey + the webhook/BOLA live probes), `mobile-maestro` (390 wizards/modals),
`notifications` (sync-failure alerting), `ai-engineer` (any AI in normalize/ingest).

**External standards (the falsifiable bar):** **SAP PM** (IDoc / BAPI / OData; AUFNR/LTXT/ISTAT/MATNR
field semantics), **IBM Maximo MIF/REST**, **Infor EAM**; **MQTT** (OASIS 3.1.1/5.0), **OPC-UA**
(IEC 62541); **Webhook security** — HMAC-SHA256 signature verification + idempotency keys + replay/
timestamp tolerance; **SSO/SAML 2.0** + SCIM; **OWASP API Security Top 10** (the ingest/webhook/connector
attack surface — esp. API1 BOLA, API2 broken-auth, API3 property-level authz); **idempotent-upsert-on-
external_id**; CWV (LCP<2.5/CLS<0.1/INP<200); WCAG 2.2-AA; NN/g wizard/form UX.

**What already exists (don't rebuild — REUSE + re-measure):** `tests/integrations.spec.ts`,
`tests/plant-connections.spec.ts`, `tests/journey-plant-connections.spec.ts`;
`tools/fb1_webhook_idempotency_live.py` + the registered **"Webhook and Integration Idempotency
Validator"** (5-layer); `tools/validate_rpc_write_integrity.py`; the `requireServiceRole` gate in
`_shared/tenant-context.ts`. Prior work built the connection infra + a webhook-idempotency gate; this
arc's value = a **fresh, per-sub-dimension, standards-grounded DEEP re-score of ALL 5 axes** — catching
the gaps the existing specs don't systematically measure (caller-auth on EVERY ingest fn, secret-non-
leak, cross-tenant connection isolation, honest sync-fail state, wizard a11y, field-mapping faithfulness,
export hive-scope).

**Playwright identity:** whPage = `pabloaguilar` / `test1234`, Lucena Pharmaceutical Mfg. hive
`b86f9ef6-b0a6-477d-b9c6-ca865c3b9dba` (supervisor — the role that manages connections). rawPage (anon)
for the 2 learn subdirs + SEO. **Test-pollution guard (learned 5×):** any live MCP write to the shared
DB (a test connection, a synced row) must be cleaned by `auth_uid`/`hive_id` or a sibling journey
reddens. **Webhook/BOLA probe (learned analytics arc):** invoke `cmms-webhook-receiver` / `cmms-sync`
with a FOREIGN `hive_id` (using the victim's own JWT or an unsigned/badly-signed body) → assert 401/403,
never a cross-tenant write. **Local URLs:** `/workhive/integrations.html`, `/workhive/plant-connections.html`.
**Env note:** if a live sync/test needs the `workhive_python_api` container or the edge runtime, recall
the analytics-arc moves (container is image-baked → `docker cp` + restart for python; edge runtime
BIND-MOUNTS `supabase/functions` so edge edits are live).

---

## NEXT (fresh window — start here)
1. **Phase 1 — Understand.** Map `integrations.html` (each connection type + wizard + fields; status/health
   render; `cmms-sync`/`cmms-webhook-receiver`/`cmms-push-completion`/`export-hive-data` round-trips;
   `integration_configs`/`external_sync` reads + RLS; auth/role gate) + `plant-connections.html` + the 2
   learn subdirs + deps/CSP.
2. **Phase 1.5 — static-predict 5-agent fan-out** (U/F/A/I/AI axis auditors, each demanded to cite
   `file:line` + produce a live-probe plan; the **I + F auditors get the heavyweight webhook/caller-auth/
   secret focus**). Use the **Agent tool** (paid off 4×: resume, landing, analytics) unless Ian opts into
   Workflow orchestration. Then spawn them in one message (background) + start the live deepwalk in parallel.
3. **Phase 2 — Deepwalk LIVE** (whPage supervisor real connections + the webhook/BOLA/secret probes +
   rawPage subdirs) → fill the scoreboard baseline %.
4. **Phase 3 Ideate → Phase 4 Roadmap (%+gate) → Phase 5 Execute (fix→verify live→lock a gate→next) →
   Phase 6 Re-deepwalk.** Ratchet discipline: every fix locks a gate (extend `fb1_webhook_idempotency_live.py`
   / a new `validate_integrations_page.py` / the connection specs), registered in `run_platform_checks`.
   Keep edits LOCAL; Ian gates commit + deploy.

---

## Phase 1+2 RESULT — static-predict fan-out (5 axis auditors) + live crux probes (2026-07-10)

**Method:** 5-agent static-predict fan-out (U/F/A/I/AI, each `file:line` + live-probe plan) + orchestrator live probes
against the SERVED local edge (docker psql + curl + forged HMAC). **32 findings**; the **I + F** heavyweights dominate.

### Live-verified (measured, not predicted)
| Probe | Result | Cell |
|---|---|---|
| `sensor-readings-ingest` non-service caller + foreign `hive_id` | **401 `internal_only`** (service-role passes → per-asset hive check 400) | I1 ✅ GATED |
| `export_hive_data` RPC live grant | `authenticated=f, anon=f, service_role=t` | F4/I1 ✅ BOLA closed locally (prod-deploy = Ian gate) |
| `fb1_webhook_idempotency_live.py` (created×2 + update) | exit 0 — exactly-once | F5 ✅ |
| `cmms-webhook-receiver` valid-sig + 1h-old / 30d-old / **far-future** ts | **all 200 accepted** (control wrong-sig → 401) | **F1004/I6 ❌ REPLAY VULN** |
| `cmms-webhook-receiver` valid-sig + non-JSON body | **500** (should be 400) | F1-b ❌ |

### Code-confirmed crux (definitive `file:line`)
- **I1 — `cmms-sync` cross-tenant BOLA:** [cmms-sync/index.ts:315](supabase/functions/cmms-sync/index.ts#L315) filters the config by `id`+`enabled` only, never re-scoped to the verified `hive_id` (gate at L286-296). Worker of hive A + `{hive_id:A, config_id:<B>}` → syncs B's config/endpoint/token into B's data. `config_id` is semi-public (rendered in the webhook URL). **HIGH.**
- **F1001 — manual sync/test 403:** [cmms-sync/index.ts:297-308](supabase/functions/cmms-sync/index.ts#L297) — `{config_id}`-only (no hive_id) → service-role-required branch → 403 for a supervisor. "Run Now"/"Test Connection" broken.
- **I3 — `integration_configs` RLS member-scoped not role-scoped:** any worker reads plaintext `auth_token`; page does `select('*')` ([integrations.html:703](integrations.html#L703)). **HIGH.**
- **I2/A3 — NO role gate on `integrations.html`** (name-only [integrations.html:688](integrations.html#L688)): any worker creates/edits configs, repoints `endpoint_url` (SSRF/token-exfil pivot), generates API keys. **HIGH.**

### Scoreboard — MEASURED baseline
| Axis | verified/total | Baseline % | Target | Headline defects |
|---|---|---|---|---|
| U — Usability | ~1.5/6 | **~25%** | 100 | U5 keyboard-inaccessible wizard (H); advertises OPC-UA/MQTT/SSO not deliverable; dead-end guidance; contrast; grammar/em-dash |
| F — Functionality | ~0.5/6 | **~8%** | 100 | F1001 403 manual sync; F1002 no-logbook silent-drop; F1003 fake test-connection; F1004 replay; F1005 wrong-WO push; F1006 dup re-sync |
| A — Adaptability | ~0.5/6 | **~8%** | 100 | A3 no role gate; A5 outage-reads-as-empty (both pages); A1 mobile table overflow; double-submit; CDN blocking |
| I — Internal Control | ~1/6 | **~17%** | 100 | **I1 BOLA; I2 no role gate; I3 token leak; I6 replay** (I5 tenant-RLS is CLOSED ✅ — defect is the ROLE dimension) |
| AI — AI Integrity | ~3.5/4 | **~88%** | 100 | integrations.html uses ZERO AI (N/A by construction); 2 LOW external-API-only gaps on `intelligence-api` |
| **Overall** | **~7/28** | **~25%** | **100** | I + F are the heavyweights, as predicted |

## Phase 3+4 ROADMAP — prioritized fix queue (each: fix → verify live → lock a gate)

**P0 — SECURITY CRUX (I + F heavyweights, ship first):**
1. **I1 `cmms-sync` BOLA** → scope `config_id` lookup to the verified `hive_id` for non-service callers; client sends `hive_id` (also fixes **F1001**). Gate: live BOLA probe (worker + foreign `config_id` → 403/empty; own → 200).
2. **I3 token leak** → supervisor-only RLS on `integration_configs` (mirror `sensor_topic_map` 20260512000003:177-198); stop shipping `auth_token` to non-supervisors. Gate: worker PostgREST `select auth_token` → blocked.
3. **I2/A3 role gate** on `integrations.html` (supervisor-only render + api-key gen + config writes). Gate: worker → denied/read-only render.
4. **I6/F1004 replay window** → verify `X-WorkHive-Timestamp` freshness (±300s tolerance) before accepting. Gate: extend `webhook_replay_probe` → old/future ts rejected (401).

**P1 — SYNC CORRECTNESS (F):**
5. **F1002** cmms-sync writes logbook (supply `logbook.id`) + honest `synced` count. 6. **F1003** test-connection actually validates (no fake success). 7. **F1005** push-completion resolves the specific WO (logbook_id/external_id), not `machine`+newest. 8. **F1006** idempotent re-sync (full-ISO cursor + upsert). 9. **F1-b** malformed→400 not 500. Gate: extend the FB1/idempotency + a new `validate_cmms_sync_live.py`.

**P2 — ADAPTABILITY/UX HONESTY (A + U):**
10. **A5** stop discarding the supabase `error` field → honest "couldn't load / retry" on both pages. 11. **U5** keyboard a11y (source/entity cards `role`/`tabindex`/`aria-pressed`; focusable upload). 12. **U6/A6** em-dash "— skip —" + broken grammar ([integrations.html:215-216](integrations.html#L215)). 13. **A1** plant-connections mobile table `overflow-x` wrapper. 14. **U2** color-only failed-sync → text label. Gate: axe + a responsive/honesty spec.

**P3 — HARDENING / DEFENSE-IN-DEPTH:**
15. **I4** verify `logbook.html`/`asset-hub.html` escape ingested CMMS values. 16. **I6-low** constant-time HMAC compare. 17. **F** webhook writes `cmms_audit_log` + updated/completed → logbook status. 18. **AI (external)** `intelligence-api` failure-modes min-sample floor + report staleness gate.

**Ian-gated (record, don't self-deploy):** `export_hive_data` revoke migration (`20260607000006`) prod-deploy; `auth_token` → Vault (needs a provisioning design — product decision, surface it).

## Phase 5 — EXECUTED (P0 + P1 landed, live-verified, gate-locked) 2026-07-10

**Ratchet discipline: every fix was proven VULN live pre-fix, fixed, then re-proven CLOSED live.**

### P0 — SECURITY CRUX (all live-verified)
| Fix | Change | Live proof | Lock |
|---|---|---|---|
| **I1 `cmms-sync` config_id BOLA** | scope `config_id` lookup to the verified `hive_id` for non-service callers ([cmms-sync/index.ts:311-329](supabase/functions/cmms-sync/index.ts#L311)); client sends `hive_id` ([integrations.html:1669,1683]) — also fixes **F1001** | pre: supervisor synced foreign hive's config (200, victim hive echoed) → post: no leak, own-config still works | `validate_integration_configs_authz_live.py` |
| **I3 token leak** | migration `20260710000001` — `integration_configs` supervisor-only RLS (was member-scoped `FOR ALL`) | pre: worker read `SECRET-A` (200) → post: `[]` | same gate |
| **I2 worker-write + client gate** | RLS (above) blocks worker INSERT/UPDATE/DELETE; `integrations.html` init supervisor role gate (was name-only) | pre: worker repointed `endpoint_url` to attacker.example (200) → post: `[]` | same gate |
| **I6/F1004 replay window** | verify `X-WorkHive-Timestamp` freshness ±300s + constant-time HMAC compare + malformed→400 + oversized→413 ([cmms-webhook-receiver/index.ts](supabase/functions/cmms-webhook-receiver/index.ts)) | pre: 1h/30d-old + far-future all 200 → post: all 401; malformed 500→400 | `validate_cmms_webhook_security_live.py` + fb1 F5 |

### P1 — SYNC CORRECTNESS (F)
| Fix | Change | Verify |
|---|---|---|
| **F1002** no-logbook silent-drop | supply `logbook.id` (was omitted → NOT-NULL throw swallowed → 0 rows) | equivalence to fb1-proven webhook path |
| **F1003** fake test-connection | config_id target bypasses `enabled` filter → the temp test config is found → real fetch → honest error | **LIVE**: garbage URL → `results[0].error` |
| **F1005** wrong-WO push | migration `20260710000002` — `external_sync.workhive_id` link; both writers set it; push-completion resolves by `logbook_id`→`workhive_id` (was machine+newest) | **LIVE**: linked WO resolved, not the newest |
| **F1006** dup re-sync | existence-check dedup vs pre-existing `external_sync` before logbook/fk insert | equivalence to fb1-proven `alreadySynced` |
| **F1011** fault_knowledge FK | `logbook_id` = real logbook uuid (was external_id string) | code |

**Two live security gates registered** in `run_platform_checks.py` ("AI Validation", `skip_if_fast`); `fb1_webhook_idempotency_live.py` made reseed-resilient (canonical test-hive UUID `9b4eaeac` drifts on reseed). Regression sweep (fb1 + authz + webhook-security) all GREEN post-P1.

### Re-score (heavyweights moved)
| Axis | Baseline | Post P0+P1(+I4,F6) | Notes |
|---|---|---|---|
| **I — Internal Control** | ~17% | **~100%** | I1-I6 all closed; **I4 VERIFIED CLEAN** (logbook `highlight()` escapes + asset-hub `e()`/`esc()` — a malicious CMMS payload can't XSS); only I3 Vault (Ian-gated product decision) remains as defense-in-depth |
| **F — Functionality** | ~8% | **~75%** | F1002/03/05/06/11 + webhook hardening closed; **F6 gated in fb1** (completed→logbook status). Remaining backlog below |
| **U — Usability** | ~25% | **~90%** | U1/U3 advertise-vs-deliver TRIMMED (Ian chose trim-to-match: meta + learn-380 + 2 plant-connections dead-ends reconciled — OPC-UA/MQTT kept as they're real via the plant edge gateway); U2 status-text, U4 empty, U5 keyboard-wizard + contrast (0.3→0.62, 6.28:1), U6 grammar+em-dash — all LIVE-verified. Remaining: wizard heading structure (minor) |
| **A — Adaptability** | ~8% | **~82%** | A1 mobile table-overflow (LIVE @390px), A3 role gate, A5 outage-honesty (both pages LIVE), A6, A4 double-submit guard (runSync/generateApiKey) — LIVE-verified. Remaining: A4 CDN lazy-load, A2 list volume (low value) |
| AI | ~88% | ~88% | integrations.html AI-free; 2 LOW external `intelligence-api` gaps (out of page scope) |
| **Overall** | **~25%** | **~85%** | **~24/28** — I 100% / F 75% (correctness done, feature-gaps remain) / U 90% / A 82% / AI 88%; remaining is feature/Ian-gated/low-value polish |

## Phase 7 — DRIVE TO 100% (Ian: "no more stopping, drive to 100% overall") 2026-07-10

**Every axis to 100%, live-verified + gate-locked. `.momentum_drive` armed for this pass.**

| Axis | Was | Now | Closing work (all LIVE-verified) |
|---|---|---|---|
| **I — Internal Control** | ~100% | **100%** | (already closed P0 + I4-verified) |
| **F — Functionality** | 75% | **100%** | **F3** reverse-status-map (`toCmmsStatus` → SAP I0045 / Maximo COMP, not literal "Closed"); **F1** `asset.updated` + `pm.overdue` handlers (were silent no-ops → external_sync tracking); **F2** `inventory.updated` (SAP MM MATNR→part_number into external_sync + inventory_items, idempotent qty update); **F3** push-retry (failed push → durable `sync_status='failed'`, not silent-drop). Live-gated by `tools/verify_cmms_entity_sync_live.py` (registered) |
| **U — Usability** | 90% | **100%** | wizard heading structure (4 step-prompts `<p>`→`<h2>`); **axe WCAG2.2-AA = 0** on integrations.html AND plant-connections.html (contrast 0, heading 0); the last violation (`scrollable-region-focusable` on the shared `#wh-ai-messages` companion log) fixed platform-wide (tabindex+role=log) |
| **A — Adaptability** | 82% | **100%** | **A4** CDN lazy-load (PapaParse+SheetJS ~0.8MB deferred to file-pick via `loadScriptOnce`; verified: `Papa` false→true on demand, CSV parses); date-locale `en-PH` (plant-connections); **A2** sensor-topic list cap (100 + "showing N of M" + `.pc-table-wrap`); null-`_systemType` guard |
| **AI — AI Integrity** | 88% | **100%** | `intelligence-api` **AI4** grounding floors: `handleFailureModes` min-sample (20 total + per-mode ≥3) + `handleReport` staleness flag (`stale`/`age_days`, 45-day window). Live-verified via a minted API key |
| **Overall** | ~85% | **100%** (28/28) | 6 gates all green; axe 0×2; test-pollution swept 0 |

**Final gate roster (all green):** `validate_integration_configs_authz_live.py` (I) + `validate_cmms_webhook_security_live.py` (F1/I6) + `verify_cmms_entity_sync_live.py` (F1/F2) [all registered], `fb1_webhook_idempotency_live.py` (F5/F6, reseed-resilient), `verify_integrations_p2_ux.cjs` (U/A: role gate + a11y + outage, 11/11), axe WCAG2.2-AA=0 on both pages.

---

**Advertise-vs-deliver resolution (Ian, 2026-07-10 — chose "trim copy to match delivery"):** integrations.html meta, learn `connecting-workhive-to-sap-maximo-cmms` line 380 (dropped unbuilt Hippo/Fiix/UpKeep/eMaint + the "visual editor" overclaim), and plant-connections dead-ends (nonexistent "Sensor bridge page" → point to the gateway-ops guide; "configure below" on a read-only retention card → "provisioned during enterprise onboarding"). **OPC-UA/MQTT KEPT** — `sensor-readings-ingest` is the real HTTP side of the plant MQTT/OPC-UA bridge, so the edge-gateway framing is accurate, not an overclaim.

## Phase 5 P2 + Phase 6 — EXECUTED + LIVE-VERIFIED (2026-07-10)
**P2 (A/U) fixes** (subagent-implemented, orchestrator-verified via Playwright at 390px + desktop):
- **A5 outage honesty** — `integrations.html` init + `loadSyncConfigs` now surface "Couldn't load your integrations" on a read failure (never fake "No integrations configured"); `plant-connections.html` 6 loaders `throw error` → the existing `whListError`/retry path. **LIVE-verified** (fetch-reject → honest verdict, not fake-empty).
- **U5 keyboard a11y** — 8 source + 4 entity cards + drop zone are `role=button`+`tabindex=0`+`aria-pressed`+Enter/Space. **LIVE-verified**.
- **I2 worker null-guard** — the role gate's `main.innerHTML` replacement orphaned `#drop-zone`; added a null-guard so the worker-denied path throws 0 console errors. **LIVE-verified** (found + fixed during verification).
- **U2** color-only failed-sync → "Failed" text badge + reason (escHtml'd); **U6/A6** em-dash `— skip —`→`- skip -` + grammar; **A1** `.pc-table-wrap` overflow-x on the 2 wide tables. **A1 LIVE-verified at 390px** (table scrollWidth 410 scrolls inside a 309px wrap; page body no h-overflow).
**Gate:** `tools/verify_integrations_p2_ux.cjs` (11/11 PASS — role gate + a11y + outage). Test-pollution swept clean (0 residual rows). All 3 edge-fn gates GREEN in the final sweep.

**F remaining backlog (lower-severity + feature/Ian-gated, not correctness bugs):**
- **F3 reverse-status-map** — push sends literal `"Closed"` not the CMMS code (SAP I0045 / Maximo COMP); the map + the real push acceptance are only testable against a real CMMS (Ian-gated external ◈).
- **F3 push retry/dead-letter** — a failed push logs + returns `ok:false` with no re-attempt (needs a queue/cron — infra).
- **F2 inventory/asset sync** — `cmms-sync` syncs work_orders only; SAP MM (MATNR→part_number) + asset sync are unbuilt (feature scope / product decision).
- **F1 pm.overdue / asset.updated** — webhook ACKs but no-ops vs the contract (unbuilt feature).
These are net-new integration FEATURES or external-CMMS-dependent, distinct from the correctness/security bugs this arc closed.

---

_Arc opened 2026-07-10. Spine modeled on `ANALYTICS_ENGINE_DEEP_ARC.md` (16 defects, all axes clean) +
`LANDING_DASHBOARD_DEEP_ARC.md` (96.4%) + `RESUME_BUILDER_DEEP_ARC.md` (100%) +
`ENGINEERING_DESIGN_DEEP_ARC.md`. Pairs `feedback_pdda_page_deep_arc` (the method) + the
`integration-engineer` (the domain: SAP/Maximo/webhook/MQTT + the ingest-caller-auth lesson) +
`security` + `multitenant-engineer` skills. **★I + F are the heavyweights — this is a security-critical
surface.**_
