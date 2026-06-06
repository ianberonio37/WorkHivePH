# Grounded MCP Sweep - Per-Page Worksheet

> Copy this whole file to `.tmp/sweep/<page>_sweep.md` and fill it in as you go.
> It is the "don't get lost" companion to `workflows/grounded_mcp_sweep.md`.
> One page per session. Score everything against UFAI (Usability · Functionality ·
> Adaptability · Internal Control).

---

## 0. Header
- **Page:** `<page>.html`  ->  served at `http://127.0.0.1:5000/workhive/<page>.html`
- **Date:** `<YYYY-MM-DD>`   **Driver:** Playwright MCP (grounded)
- **Domain skill(s):** `<e.g. logbook-validator, maintenance-expert>`
- **One-line purpose of this page (from the skill / COMPREHENSIVE_STUDY):** ______
- **Identity = role × experience (2-D):**
  - Role: ☐ costumes (1, private page) ☐ **role matrix `solo`/`worker`/`supervisor`**
    (shared/tenant pages; reuse `e2e_roles_runner.py` + `PERMISSION_MATRIX`)
  - Experience: run **NOVICE (first-timer)** AND experienced for EACH role in scope
    (novice = empty state, blank fields, out-of-order steps, fat-fingers, flaky net).
    Fill the Novice Pass block below — it spans ALL FOUR pillars.

## 1. Ground the observer  (read BEFORE driving; tick when read)
- [ ] Domain skill(s): ____________________
- [ ] Always-in-scope skills: QA · Frontend · Performance · Mobile-Maestro · Security
- [ ] `COMPREHENSIVE_STUDY_FULLSTACK_GATE.md` (this page's row) + `PLATFORM_ROADMAP.md`
- [ ] L0 contract: `tools/validate_<page>.py` (exists? Y/N) + page's rows in the 5
      page lists (xss / schema / tenant_boundary / performance / input_guards) +
      `tests/surface-coverage.spec.ts`
- [ ] L2 contract: `tests/journey-<page>.spec.ts` (exists? Y/N - read what it already asserts)
- [ ] Canonical/data truth this page reads: `canonical_sources` / `v_*_truth`: ____________
- **Expectation set derived (what "good" means here, in the page's OWN terms):**
  - ____________________________________________

## 2. Test seam
- [ ] Exposed module on `window`? `window.WH<____>` -> methods: ____________
- [ ] Storage keys: ____________   File inputs: ____________
- [ ] **If NO seam -> FINDING #1:** add `window.WH<Page> = { get, set }` (record below)
- [ ] Pollution-safe plan confirmed: in-memory only, no cloud writes, MCP closed before journey run

## 3. UFAI batteries  (fill result + the NUMBER measured; mark BUG if it fails)

### Usability  (grounds in Frontend / Mobile-Maestro / Designer)
| # | Scenario | Expected (grounded in) | Result + number |
|---|---|---|---|
| U1 | Empty / first-timer state points at EVERY start path | skill empty-state rule | |
| U2 | Mobile TRUE-390 (mind dpr trap): 0 horiz overflow | mobile-maestro | scrollW=___ / 390 |
| U3 | Tap targets >= 44px (icon buttons) | mobile-maestro | min=___px |
| U4 | All text inputs >= 16px (no iOS zoom) | mobile-maestro | under16=___ |
| U5 | a11y: focus trap in dialogs, ESC restores to trigger, heading roles | frontend a11y | |
| U6 | Errors are calm + legible, no dev jargon | designer | |
| U7 | Visual regression: screenshot vs baseline (per template + breakpoint) | L2 `visual.py` | diff=___ |

### Functionality  (grounds in domain skill + validate_<page> + journey-<page>)
| # | Scenario | Expected | Result + number |
|---|---|---|---|
| F0a | **Wired & alive — STATIC:** every `onclick="fn()"` references a defined fn; no dead `href="#"`/`""`/`javascript:void` (EXERCISE clickables, don't just measure them — SOP F0) | no unwired/dead | unwired=___ dead=___ of ___ clickables |
| F0b | **Wired & alive — LIVE + ASSERT OUTCOME:** click/fill every SAFE clickable; skip write/destructive. "Didn't throw" ≠ "worked" | 0 throws · 0 new console errors | clicked=___ throws=___ |
| F0c | **WHERE it landed:** right modal/page/state appeared (correct id/URL/content); filter/sort changed the list in the RIGHT direction; input accepted+reflected (empty⇒guard) | per interaction | wrong-landings=___ |
| F0c2 | **WHAT it shows (VALUE correctness, vs platform contracts):** values are canonical-sourced (right v_*_truth, not raw/re-derived) · calc matches formula/standard · cross-surface parity (==sibling==DB) · written value==DB row · partial/stale carries honesty marker. Flag DEFECT vs CONTENT | canonical_registry · formula contracts · kpi-parity · crud DB-verified | wrong-values=___ |
| F0d | **WHEN it landed:** settled promptly (waitFor effect); no stuck spinner / dead async / land-then-revert | per interaction | slow/stuck=___ |
| F0e | **CORRECT for WHO (role × experience):** same interaction per identity lands right — supervisor=full · worker on supervisor-only=helpful denial (not action, not raw error) · solo=hive-gate guided · novice mis-click recoverable | I4b matrix | role-mismatches=___ |
| F0f | **No PHANTOM capture (lineage down):** every input/select/upload/toggle flows Capture→Source/Fuel(canonical_capture_contracts)→Engine→Brain(v_*_truth)→Dashboard; LIVE: fill→submit→trace value lands in source table + surfaces on dashboard with right value | Phantom Capture Auditor + flows/*_crud.py | phantom-captures=___ |
| F0g | **No PHANTOM display (lineage up):** every tile/number/badge traces to a `v_*_truth` source (has a JS setter + source chip), not hardcoded; select options = canonical enum | Orphan KPI Tiles + Source-Chip Truth | phantom-displays=___ ; DEFECT vs by-design(ephemeral/read-only) |
| F1 | Core job done correctly (define per page) | domain skill | |
| F2 | No duplicates (dedupe on the page's identity key) | domain skill | count=___ |
| F3 | Output/export integrity (round-trip each format, schema-valid, escaped) | skill | |
| F4 | XSS / special chars / overflow tokens escaped + contained | security + frontend | |
| F5 | Section/data order matches editor == export == standard | skill | |
| F6 | **CRUD DB-VERIFIED** (data pages): UI create/update -> QUERY Supabase -> the write LANDED (not just DOM) | L2 `flows/*_crud.py` | row in DB? Y/N |

### Adaptability  (grounds in AI-Engineer / Performance / free-tier+CGNAT)
| # | Scenario | Expected | Result + number |
|---|---|---|---|
| A1 | Offline / timeout / 429 -> calm message + graceful fallback, no stuck spinner | ai-engineer S22 | |
| A2 | Diverse inputs (Taglish, special chars, heavy/multi-page, low-end) | skill | |
| A3 | Partial/fan-out honesty (reports N of M, never silent drop) | ai-engineer | |
| A4 | Recall on a NEW labeled corpus (if model-backed) - re-measure, don't trust prior | qa-tester | _/_ |

### Internal Control  (grounds in Security / Multitenant / "never auto-delete")
| # | Scenario | Expected | Result + number |
|---|---|---|---|
| I1 | Nothing AI/extracted applied without a confirm/checklist | skill | |
| I2 | Undo on EVERY destructive action | skill | |
| I3 | Provenance chips / source labels present | designer | |
| I4 | Owner/RLS gating + rate-limit gate (solo + hive) | multitenant + security | |
| I4b | **ROLE MATRIX** (shared/tenant pages): UI matches `PERMISSION_MATRIX` for solo/worker/supervisor; solo hits hive-gate; worker can't READ another hive's rows nor do supervisor-only actions; owner-only edit/delete DENIES non-owner; no cross-hive leak | `e2e_roles_runner.py` + `journey-hive-isolation-property` | |
| I4c | **CONCURRENT EDIT** (shared records): 2 sessions edit same row -> conflict warning OR clean last-write-wins; simultaneous create -> both succeed, no dup-key | L2 `e2e_concurrent_runner.py` | |
| I5 | No silent data loss (reset/switch auto-saves; worthSaving counts contact) | frontend | |

### 3b. NOVICE PASS — run for EACH role in scope (solo / worker / supervisor)
A first-timer hits friction across ALL FOUR pillars. Tick per role; note any BUG.
| # | Novice check (do this AS a first-timer for the role) | Pillar | solo | worker | supervisor |
|---|---|---|---|---|---|
| N1 | First-run/EMPTY state guides to every start path; no assumed prior data; no dead end | U | | | |
| N2 | Plain labels, obvious "where do I start"; no unexplained jargon | U | | | |
| N3 | Core flow works with blank fields / out-of-order steps; empty/invalid -> friendly GUARD toast, never a crash/silent no-op | F | | | |
| N4 | Offline / old-device / mistake -> calm message + recovery, no stuck spinner | A | | | |
| N5 | EVERY destructive action (remove/New/Switch/Delete) is UNDOABLE and/or auto-saves first (no silent data loss) | IC | | | |
| N6 | Permission DENIAL is explained helpfully ("ask your supervisor"), not a dead-end/raw error; solo not stranded at hive-gate | IC | | | |
| N7 | A first-timer cannot accidentally trigger an irreversible / cross-tenant action without a confirm | IC | | | |

## 4. Findings + root-cause fixes
| Finding | Pillar | Root-cause fix (file:line) | Negative control | Overlap case | Re-verified LIVE? |
|---|---|---|---|---|---|
| | | | | | |

## 4b. Critique — the HARSH CRITIC ("should-be" recs → `promotion_queue.md`, NEVER auto-applied)
Opinionated + prescriptive, but every row CITES what it's measured against. Severity =
Blocker/Major/Minor/Polish; Effort = S/M/L; flag DEFECT vs TASTE vs CONTENT.
| # | Now (evidence) | Should be (prescription) | Where (same / →move to page) | Why (heuristic / pillar / sibling) | Pillar | Sev | Eff | Flag |
|---|---|---|---|---|---|---|---|---|
| C1 | | | | | | | | |
| C2 | | | | | | | | |
- [ ] Top recs appended to `promotion_queue.md` (you DISPOSE via `promotion_dispositions.json`)

## 5. Blast radius  (the web pass - what this fix ripples to)
- Shared seams touched: edge fn ____ · `_shared/` ____ · table/view ____ · nav/identity/escHtml ____
- Connected pages to re-verify: ____________________
- Cross-surface sentinels re-run:
  - [ ] `tests/canonical-lineage.spec.ts`
  - [ ] `tests/journey-cross-surface-kpi-parity.spec.ts`
  - [ ] `tests/journey-cross-page.spec.ts` / `tests/journey-megagate-cross-page.spec.ts`
  - [ ] `tests/journey-mobile-a11y.spec.ts`
  - [ ] `tests/journey-hive-isolation-property.spec.ts`
  - [ ] `codebase-integrity` skill (if nav/identity/escHtml touched)

## 6. Crystallize + prove green
- [ ] `tools/validate_<page>.py` checks added: ____  (run: `python tools/validate_<page>.py`)
- [ ] `tests/journey-<page>.spec.ts` assertions added: ____
      (run: `node node_modules/@playwright/test/cli.js test tests/journey-<page>.spec.ts --reporter=list`)
- [ ] Flake check: failures DECAY on `--last-failed` (flake) vs deterministic (regression)? ____
- [ ] Connected pages + cross-surface sentinels green
- [ ] (optional) full gate: `python run_platform_checks.py --fast`

## 7. Clean up + writeback
- [ ] DB clean (deleted created rows by auth_uid/marker); journey starts clean
- [ ] MCP browser closed
- [ ] Lessons -> skills (list which): ____________________
- [ ] Project memory + `MEMORY.md` index + this page's roadmap row updated

## 8. One-paragraph verdict
`<n>` scenarios run; `<k>` real bugs fixed; blast radius `<status>`; guards
`validate=__/__`, `journey=__/__`; pollution = zero; deploy = PENDING explicit OK
(no migration unless noted).
