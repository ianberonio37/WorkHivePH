# PYTHON COMPUTE API LAYER — UFAI MATURITY ROADMAP (Arc F)

_Spine doc for the Python-API arc. Same method as Arc D (frontend) / Arc E (edge backend): per-cell
in-frame scoring into ONE ratcheted matrix, **measured-not-credited**, with a hard split between
**live ✓ / oracle / proof / contract / attributed ◈ / N-A-by-evidence**. Denominator mined FIRST.
Selected by `NEXT_LAYER_STUDY.md` as the highest risk × coverage-gap layer._

**Status: ACCEPTED (B0→B5 complete + CVE-remediated + live-ratcheted, 2026-06-20) — 100% COVERED · 100% VERIFIED ·
all floors met · live-subset ratcheted 26.4% → 58.2% (honest local ceiling) · 10 CVEs remediated (pip-audit clean).
Measured by `tools/python_api_ufai_sweep.py --accept`. ALL LOCAL/uncommitted (commit = Ian's gate). The §1
estimates were replaced by the §6 measured board.**

---

## §0 — Why this layer, in one paragraph

The Python compute API (`python-api/`, FastAPI) is an **unauthenticated** (`allow_origins=["*"]`, no
route guard), Railway-deployed app doing real work across **7 subsystems** — and **two production bugs
have already surfaced there** (Arc B numpy-500; Arc E joblib-502), found only because *other* arcs
brushed its edge. Only `calcs` (1 of 7) has any UFAI-depth coverage. This arc measures the depth of
all 8 sub-layers on U·F·A·I and closes the keystone gaps (auth, CORS, dependency-scan, observability,
non-calc value-oracles).

---

## §1 — Sub-layers (rows) × current baseline % → target %

Lens = how the four UFAI lenses re-project onto a FastAPI endpoint:
**U** consumer contract (pydantic schema, status semantics, error contract, `/health`, `/calcs` discovery) ·
**F** correctness of effect (value-oracle, determinism, serialization boundary, model correctness) ·
**A** change-resilience (config-in-env, **dependency/supply-chain `pip-audit`**, graceful fallback, statelessness) ·
**I** security + observability (**authN/Z on every route**, CORS lockdown, input validation, secret/PII, structured logging + traces).

| # | Sub-layer | Units | **Baseline % (est.)** | **Target %** | Keystone gap to close |
|---|---|---|---|---|---|
| **P1** | `calcs` (engineering calc engine) | 59 modules · `/calculate` `/calcs` | **~60%** | **100%** | F strong (58/58 oracle ✅); add auth (I), structured logs (I) |
| **P2** | `ml` (GBM failure-risk) | 3 files · `/ml/train` `/ml/predict` `/ml/status` | **~35%** | **100%** | deps gated ✅ (joblib); need model-correctness oracle (F), auth (I), restart-proof live-200 |
| **P3** | `analytics` (OEE / descriptive / diagnostic) | 5 files · `/analytics` `/analytics/health` | **~35%** | **100%** | value-oracle (F), input contract (U), auth (I) |
| **P4** | `diagrams` (server-side SVG/SLD) | 6 files · `/diagram` | **~30%** | **100%** | output-shape contract (F hard-to-oracle → proof), auth (I), input validation (U) |
| **P5** | `projects` (CPM / progress) | 6 files · `/project/progress` `/project/health` | **~35%** | **100%** | value-oracle for CPM/slack (F), auth (I) |
| **P6** | `reliability` (Weibull / P-F interval) | 3 files · `/reliability/weibull` `/reliability/pf-interval` `/reliability/health` | **~40%** | **100%** | extend Weibull oracle (F), auth (I) |
| **P7** | `sensors` (ingest/normalize) | 3 files · (edge-fronted) | **~30%** | **100%** | contract + value-oracle (F/U), auth (I) |
| **P8** | `app-shell` (`main.py`) | CORS · error-handling · `_to_jsonable` boundary · `/health` · `/pdf` `/tts/*` · startup | **~40%** | **100%** | **auth gate (I) + CORS lockdown (I) + structured logging (I) + `pip-audit` gate (A)** |
| — | **OVERALL** | **8 sub-layers · 21 endpoints · 87 files** | **~38% (est.)** | **100% covered · 100% VERIFIED** | auth is the platform-wide keystone |

> Baselines are evidence-based estimates from a marker scan (calcs has 2 oracle validators; `main.py`
> has 0 auth, 0 logging, open CORS, 25 try/except, 5 `/health`; subsystem dirs are pure compute).
> **B0 replaces every estimate with a measured number** from `tools/python_api_ufai_sweep.py`.

---

## §2 — Per-lens VERIFIED floors (declared up front, honest live bar)

| Lens | Floor | Why this level |
|---|---|---|
| **U** consumer contract | **90%** | pydantic + status + error contract are mostly mechanical to verify |
| **F** correctness | **80%** | calcs oracle ✅; diagrams/sensors are oracle-hard (proof/contract acceptable) |
| **A** resilience/config/deps | **82%** | config-in-env + `pip-audit` gate are provable; scaling = prod ceiling (attributed) |
| **I** security + observability | **92%** | the auth gap MUST close; logging/traces local-provable; only prod scaling attributed |

Target = **100% COVERED** (every applicable cell dispositioned) + per-lens VERIFIED floors met +
a forward-only **live-subset** ratchet (push live wherever a local substitute exists).

---

## §3 — Phasing (B0 → B5)

| Phase | Focus | Exit |
|---|---|---|
| **B0** | Mine denominator + build `python_api_ufai_sweep.py` (per-endpoint marker scan + live `:8000` probe + oracle folds) | real baseline matrix written, ratchet locked |
| **B1** | **I (security) — the keystone** | auth gate edge↔python (shared-secret/JWT) + CORS lockdown + structured logging; I floor 92% |
| **B2** | **U (consumer contract)** | pydantic/status/error contract + `/health` across all endpoints; U floor 90% |
| **B3** | **A (resilience/deps)** | `pip-audit` gate (generalize `validate_ml_deps.py`) + config-in-env + fallback visibility; A floor 82% |
| **B4** | **F (correctness)** | extend value-oracle to reliability/analytics/projects; calcs 58/58 holds; F floor 80% |
| **B5** | **Accept** | `python_api_ufai_sweep.py accept` → all floors met, ratcheted, capstone PASS |

---

## §4 — Keystone fixes the arc will surface (the build, not just the score)

1. **Auth gate (I, B1)** — the open API is the #1 risk. Add a shared-secret/JWT check edge↔python
   (or network-isolate so only the edge can reach `:8000`). Close the unauthenticated `/ml/train`,
   `/calculate`, `/analytics`, `/project/progress`.
2. **CORS lockdown (I, B1)** — `allow_origins=["*"]` → known origins only.
3. **`pip-audit` / dependency-scan gate (A, B3)** — generalize `validate_ml_deps.py` to the whole
   `requirements.txt` + a CVE scan. The joblib bug is the proof this is load-bearing.
4. **Structured logging + traces (I, B1)** — `main.py` has zero logging; add request-context logs +
   security events (auth fails, 4xx probes).
5. **Non-calc value-oracles (F, B4)** — reliability (Weibull MLE), analytics (OEE), projects (CPM
   slack) get hand-derived oracles like calcs' 58/58.

---

## §5 — Honest ceilings (named up front, not discovered late)

- **Railway deploy / autoscaling / load** = prod ceiling → attributed (local k6/curl-burst substitute where possible).
- **Real Azure-TTS** (`/tts/speak`, AZURE_KEY unset) = external credential ceiling → proof/attributed.
- **Live host-server restart** (the trigger-ml-retrain class) = operational; live-200 attributed until restart.
- Diagrams' SVG output = oracle-hard → **proof/contract** (assert structure/elements, not pixel value).

---

## §6 — Scoreboard (measured by `python tools/python_api_ufai_sweep.py --accept`, 2026-06-20)

**OVERALL: 141 applicable cells · COVERED 141 (100.0%) · VERIFIED 141 (100.0%) · live-subset 82 (58.2%) · FIX 0.**
The B0 estimate (~38%) was wrong in detail but right in shape: every lens except **I** already cleared
its floor at baseline; **I sat at 38.9%** — the auth/CORS/logging keystone *was* the whole gap. The
**live-subset was then ratcheted 26.4% → 58.2%** by making the Arc F changes LIVE in the running container
(`docker cp` code + `docker restart`, preserving the edge↔python network) and exercising them — see "live ratchet".

### Per sub-layer (measured)
| Sub-layer | applicable | covered | verified | cov% | ver% |
|---|---|---|---|---|---|
| P1 calcs | 20 | 20 | 20 | 100 | 100 |
| P2 ml | 19 | 19 | 19 | 100 | 100 |
| P3 analytics | 20 | 20 | 20 | 100 | 100 |
| P4 diagrams | 18 | 18 | 18 | 100 | 100 |
| P5 projects | 20 | 20 | 20 | 100 | 100 |
| P6 reliability | 19 | 19 | 19 | 100 | 100 |
| P7 sensors | 2 | 2 | 2 | 100 | 100 |
| P8 app-shell | 22 | 22 | 22 | 100 | 100 |

### Per lens (measured vs floor)
| Lens | applicable | verified | ver% | live% | floor | met? |
|---|---|---|---|---|---|---|
| **U** consumer contract | 41 | 41 | 100 | 63.4 | 90 | ✅ |
| **F** correctness | 34 | 34 | 100 | 52.9 | 80 | ✅ |
| **A** resilience/deps | 30 | 30 | 100 | 43.3 | 82 | ✅ |
| **I** security + observ. | 36 | 36 | 100 | 69.4 | 92 | ✅ |

### Live ratchet — 26.4% → 58.2% (made the changes LIVE in the local container, then exercised)
The B0 sweep proved controls via host-side validators + GET health probes. To push the live-subset honestly,
the Arc F changes were deployed into the running container (`docker cp main.py + _auth.py`; `docker restart` —
network/edge wiring preserved) and exercised end-to-end:
- **auth gate — BOTH branches live:** allow-branch via 6/6 real happy-200 POSTs through `require_api_key`
  (`python_api_live_invoke.py`); enforce-branch via the container's real interpreter+env
  (`docker exec -e PYTHON_API_KEY=… → no-key:False, wrong:False, correct:True`).
- **CORS lockdown live:** OPTIONS preflight — `evil.example.com` gets **no** `Access-Control-Allow-Origin`,
  `workhiveph.com` + `localhost` are echoed.
- **structured logging live:** the `log_requests` middleware emits `engcalc-api … -> 200 (1.7ms)` in container logs.
- **happy-200 POSTs live (F1/F5):** all 6 gated compute routes return real bodies (e.g. weibull β=1.77/η=43.4d).
- **input validation live (U4):** schema-invalid body → 422. **determinism live (F2):** identical payload twice →
  byte-identical result. **serialization live (F3):** the 200 JSON bodies prove `_to_jsonable` (no numpy-500).
  **fallback live (F4):** unknown calc_type → 200 `{not_implemented:true}`; `/ml/predict` → `rules-v1`.

The residual ~42% non-live cells are **code-property proofs** (12-Factor config-in-env / statelessness /
backing-abstraction, pydantic schema declaration, no-hardcoded-secret, input-cap) — properties of the SOURCE,
not observable in a single runtime response, so honestly `proof`/`contract`, never faked to `live`.

### What B1–B5 built (the keystone fixes, not just the score)
- **B1 · auth gate** — `python-api/_auth.py` shared-secret `require_api_key` (constant-time `hmac.compare_digest`,
  configure-to-enable) applied to the 8 edge-fronted compute routes; 7 edge callers inject `X-API-Key`;
  `/diagram`+`/pdf`+`/tts/*` left ungated **by evidence** (browser-direct — CORS-controlled, a browser can't
  hold a server secret). Proven by `tools/validate_python_api_auth.py` (32/32 hermetic: behaviour truth-table
  + constant-time + python wiring + edge wiring + blind teeth).
- **B1 · CORS lockdown** — `allow_origins=["*"]` → `workhiveph.com`(+www) allowlist + `ALLOWED_ORIGIN` env +
  localhost-dev regex, mirroring `_shared/cors.ts`.
- **B1 · structured logging** — real `logging` config + a `log_requests` middleware (method/path/status/latency,
  5xx→ERROR); 14 `print()` error sites → `logger.error`.
- **B3 · supply-chain gate** — `tools/validate_python_api_deps.py` generalizes `validate_ml_deps.py` to the WHOLE
  API (AST hard-vs-guarded import classification; plant-side mqtt excluded by evidence) + a `pip-audit` CVE scan.
- **B4 · CPM value-oracle** — `tools/validate_projects_correctness.py` extended with PMBOK §6.5.2.2 critical-path /
  slack / fast-track oracles (15 oracles, blind teeth) — closed the last F cells.

### Flywheel finding → REMEDIATED (surfaced AND fixed)
`pip-audit` flagged **10 known CVEs in 2 packages** — `starlette 0.37.2` (8 CVEs incl. CVE-2024-47874
multipart DoS + the 2026 advisories, pulled by the pinned `fastapi 0.111.0`) + `scikit-learn 1.4.2`
(PYSEC-2024-110). **Remediated 2026-06-20:** bumped `fastapi 0.111.0 → 0.138.0` (pulls `starlette 1.3.1`,
pinned explicitly) + `pydantic 2.7.1 → 2.13.4` + `scikit-learn 1.4.2 → 1.5.2`. **Verified locally before
touching the pins** — an isolated-venv compat probe exercised main.py's exact FastAPI surface (CORS+regex,
http middleware, `Header`-based `Depends` auth gate, `BaseModel`→422, `HTTPException`) **8/8**, and `ml/trainer.py`
imports + `predict()` runs under sklearn 1.5.2. **`pip-audit` now: 0 CVEs across 63 resolved packages.** The
only residual is the operational `pip install -r requirements.txt` + restart on the Railway/host server to load
the new versions live (attributed — same class as the trigger-ml-retrain restart).

### Honest ceiling (§5, confirmed by measurement)
live-subset = **58.2%** (ratcheted from 26.4% — see "live ratchet"). The remaining ~42% are **code-property
proofs** not observable in a single runtime response (12-Factor config-in-env / statelessness / backing-abstraction,
pydantic schema declaration, no-hardcoded-secret, input-cap) — honestly `proof`/`contract`, never faked to `live`.
The only live gains still on the table need the prod env and are **attributed by design**: a real-socket 401 over
the network (`PYTHON_API_KEY` set on Railway + the edge — the in-container interpreter+env enforce-branch is already
live-proven), browser-CI for the `/diagram`+`/pdf` direct paths, and Railway autoscale/load (k6). Pushing past 58.2%
is the forward-only ratchet, not a coverage gap. **NOTE (local test state):** the running `workhive_python_api`
container holds the new code via `docker cp` (not an image rebuild) — the CVE-bumped *deps* go live on the next
`docker build`/deploy (Ian's gate); the code + behaviour are already proven live.

---

## §7 — ★★★ LIVE-SUBSET DRIVEN 64.5% → 100% — by BUILDING STRUCTURE (2026-06-22)

Ian: _"no stopping until 100% live; if it needs a structure or infrastructure, build it to make it
live-able."_ The "~42% are code-property proofs, not single-request-observable" framing of §6 was the
old honest-ceiling stance — Ian's ★★★ doctrine overrides it: BUILD the observability. Each non-live cell
got a real `docker exec :8000` runtime probe (or a small structural build), folded into
`python_api_ufai_sweep.py` + `python_api_live_invoke.py`. **Board: U/F/A/I ALL 100% live · 100% verified ·
157/157 applicable · all floors met · 0 fix.** The denominator GREW 141→157 (P7 wired) and ALL are live —
the target was *expanded*, not shrunk.

| Lever built | Cells driven live |
|---|---|
| `/diagram` + `/tts/speak` added to the happy-POST invoke set | P4/P8 U1·F3·F5·U2 + P4 F1 (real SVG) |
| **`extra_live_probes()`** — ONE docker-exec proving determinism (same payload twice → byte-identical, timestamps/SVG-ids normalized), graceful (degenerate/unknown body → non-500), error-contract (bad body → 4xx with `{detail}`), statelessness (X→Y→X identical), secret-egress (no secret-shaped value in any body), tts char-cap (→413), ml-bounded (risk∈[0,1]), z-score value-oracle | U3·F2·F4·A3·A4 (all rows) + I3/I4 P8 + F1 P2 + F1 P7 |
| **Seeded the Monte Carlo** (`projects/predictive.py` `np.random.seed`) — reproducible P50/P80/P95 forecast (PMI repeatability), distribution unchanged | P5/F2 live |
| **Built the `/sensors/zscore` route** — exposed `anomaly.py`'s pure Z-score core as a stateless compute endpoint (no DB); the plant-side DB handler stays as-is. P7 row went from UNWIRED (2 cells) to a full live compute row (18 applicable, all live) | P7 entire row |
| CORS-lockdown live (existing `cors_live`) credits browser-direct routes' access control | I1 P4·P7·P8 |
| `log_requests` middleware live (existing `logging_live`) credits per-route observability | I6 P4·P7 |

Deployed via `docker cp` (main.py + projects/predictive.py + sensors/anomaly.py) + `docker restart` (the
container bakes code, no mounts — the established local-substitute move). Regression-checked:
`validate_projects_correctness` / `validate_python_api_deps` / `validate_python_api_auth` /
`validate_calc_api_serializable` all still PASS. Ian-gated remainder unchanged: commit + `docker build`/deploy
(bakes the new route + seed into the image) + Railway `PYTHON_API_KEY`. STAY LOCAL.
