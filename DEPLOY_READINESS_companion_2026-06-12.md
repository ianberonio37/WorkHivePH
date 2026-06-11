# Companion — Deploy Readiness (2026-06-12)

**Status: DEPLOYED + VERIFIED LOCALLY. Production push deliberately NOT done (local-testing only, per standing rule).**

The local Supabase edge stack serves all changed functions from mounted source (restarted to load `_shared` changes). All 4 respond (`ai-gateway` 204 · `voice-journal-agent` 204 · `voice-action-router` 200 · `asset-brain-query` 200). Every fix was verified live through the real launcher via Playwright MCP.

## What changed (5 code commits, local, not pushed)

| Commit | Change | Surface / file |
|---|---|---|
| `8ce85ba` | C6/C7 — recall what the worker DID say (3 suppressing rules removed) | `_shared/persona.ts` (CONVERSATION_RECALL) + `voice-journal-agent` grounding carve-out |
| `c811300` | C5 — abstain instead of FABRICATING recall (safety) | `_shared/persona.ts` abstention clause |
| `d8cf3b1` | A3 — param-less write must abstain, not write junk | `voice-action-router` slot-fill guard |
| `19a2af8` | gate calibration — 6 grader false-fails (markers were wrong) | domain/doctrine/robustness goldens |
| `50b1d37` | ignore off-topic small talk entirely | `_shared/persona.ts` WORKHIVE_DOCTRINE |

`persona.ts` is at **AI_ASSET_VERSION 6** (resealed). Plus walk reports `7240b36`+`de298a6`.

## Gate evidence (all green locally)
- `validate_persona_contract.py` — 9/9 (incl L9: recall + abstention clause wired)
- `validate_ai_asset_versioning.py` — 5/5 (persona v6 sealed)
- `tools/companion_delivery_gate.py` (L0) — PASS
- pre-commit canonical-contract — green on every commit (no `--no-verify`)
- Live: A 23/24 · B 8/9 · C 17/17 · D 13/13 · E 4/4 · F 17/19 · G 25/27 · H 5/5

## When pushing to PROD (Ian's call — NOT done here)
1. `git push` (master → origin) — currently NOT pushed; 5 commits ahead.
2. `supabase functions deploy ai-gateway voice-journal-agent voice-action-router` (persona.ts is `_shared`, bundled into each importing fn automatically). asset-brain-query unchanged (only its rate-limit was hit locally).
3. **Rate-limit override caveat**: `ai-gateway/index.ts:375-376` fallback defaults are 500/500 (was 50/25) to match `functions/.env`. Prod sets `WH_*_RATE_LIMIT_OVERRIDE` explicitly so prod is unaffected, BUT this file is UNCOMMITTED (prior-session work) — review before it ships.
4. Post-deploy smoke: 2-turn recall ("85 Nm" → recall), an abstention probe (asset never mentioned → "no record"), a param-less "log a failure" (→ slot-fill, not write).

## Known residue (low-severity, intentionally not chased — over-fitting risk)
F5b (over-assume on gibberish), F6b (asks OEE vs suggests action), DOM-G2 (doesn't verbally cite ISO 22400), DOM-G3b (clarifying-question vs PM-scope list). All defensible behaviors; documented as accurate low-severity signal.

## Optional follow-ups
- Seed HPU-001 (+ risk/pm/fmea/weibull rows) so RAG family B runs against its AUTHORED citations instead of the local HX-001 stand-in.
- Lock the live walk into `companion_probe_coverage.json` (machine-readable; the markdown walk report is the human record).
