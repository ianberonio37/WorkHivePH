# Full-Stack SaaS Gate — the fourth sibling of the Unified Mega Gate

**Created:** 2026-06-11
**Owner:** Ian Beronio
**Status:** BUILT (front door live). The **spec** is [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md) §4 (the 13×6 matrix). This doc is the **operational** companion — how you run it.

---

## Why this exists

The platform's full-stack concerns (Frontend, APIs, Database, Auth, …) were **absorbed wholly inside the Unified Mega Gate's G0** (`run_platform_checks.py`, one undifferentiated phase). You could not run "just the Auth layer through every gate layer," or see the full-stack health organized the way the Mega Gate itself is organized.

The Full-Stack SaaS Gate **defuses** that — without moving any working code. It is a front door (`tools/fullstack_dev.py`) that reads the matrix that **already exists** (`COMPREHENSIVE_STUDY_FULLSTACK_GATE.md` §4) and runs it **organized under the Unified Mega Gate's own gate-layer names**, so all four gates wear one identical scaffold and you never get lost moving between them.

| Sibling | Front door | Tests |
|---|---|---|
| Unified Mega Gate | `release_gate.py` | platform CODE |
| AI Companion Dev Tool | `tools/companion_dev.py` | AI BEHAVIOR |
| Content Grounding Gate | `tools/content_dev.py` | OUTWARD CONTENT |
| **Full-Stack SaaS Gate** | **`tools/fullstack_dev.py`** | **the 13 production layers × 6 gate layers** |

**Design principle: INVENT NOTHING.** Every artefact the front door routes to already existed (validators, specs, miners, the coverage audit). The work was *organization*, not new machinery.

---

## The two grids (from the study)

- **13 production layers** (matrix ROWS): `F` Frontend · `A` APIs/Backend · `D` Database · `AU` Auth · `H` Hosting · `C` Cloud/LLM · `CI` CI-CD · `S` Security · `RL` Rate-limiting · `CA` Caching/CDN · `LB` Load-balancing · `L` Logs/Errors · `AV` Availability.
- **6 gate layers** (matrix COLUMNS) — **the Unified Mega Gate's own names**: `G-1.5` Substrate · `G-1` Auto-discovery · `G0` Fast Guardian · `GH` Hardening · `GS` Sentinel · `G2` Layer-2 E2E.

The front door's commands **are** the gate-layer names — that is the whole point:

| Command | Gate layer | What it runs / shows | Routes to (existing) |
|---|---|---|---|
| `substrate` | **G-1.5** | pattern-miner SHAPE layer (per matrix column) | `*_pattern_mining_report`, `substrate_manifest.json` |
| `discover` | **G-1** | matrix-integrity meta-gate (real run) + the gap cells | `tools/audit_fullstack_gate_coverage.py` |
| `gate` | **G0** | the 339-validator fast guardian | `run_platform_checks.py` |
| `harden` | **GH** | the L2→L0 hardening-bridge state | `/harden`, `tools/hardening_auto_trigger.py` |
| `sentinel` | **GS** | the L0→L2 sentinel coverage | `sentinels/`, `sentinel_coverage_report.json` |
| `e2e` | **G2** | journey-spec coverage | `tests/journey-*.spec.ts` |
| `mega` | conductor | every layer at once + scorecard + marker | all of the above |

Any command scopes to one production layer with `--layer` (e.g. `--layer AU` for Auth).

---

## How to run

```bash
python tools/fullstack_dev.py status            # the 4-axis matrix scorecard, one glance
python tools/fullstack_dev.py matrix            # the full 13×6 grid (✓ / — gap / X missing)
python tools/fullstack_dev.py matrix --layer AU # one production layer's row across all 6 gate layers
python tools/fullstack_dev.py discover          # G-1 meta-gate: are all matrix artefacts still present?
python tools/fullstack_dev.py gate --fast       # G0 fast guardian (the 339-validator ratchet)
python tools/fullstack_dev.py mega              # run every layer at once (G0 opt-in via --with-guardian)
python tools/fullstack_dev.py --self-test       # prove the wiring (offline, $0)
```

### The 4-axis scorecard

- **coverage** — filled matrix cells / 78 (how complete the gate is)
- **integrity** — named artefacts that actually exist / referenced (no silent gaps; this is the meta-gate)
- **protection** — production layers with ≥1 gate cell / 13 (every layer has *some* protection)
- **guardian** — last `gate`/`mega --with-guardian` G0 result (— until first run)

---

## What it surfaces (the "so we won't be lost" payoff)

Running `matrix` shows, at a glance, **which Mega-Gate columns are thin for which production layers**. As of build (2026-06-11): coverage 76.9% (60/78), integrity 100% (0 missing), protection 100% (all 13 layers have ≥1 gate). The blank cells *are* the gap list (study §7) — the punch-list for the flywheel. The empty `G-1.5` / `GS` columns for the infra layers (Hosting, CI, Rate-limiting, Caching, Load-balancing, Availability) are visible immediately.

---

## Integration with the Unified Mega Gate

`release_gate.py` gains `phase_fullstack` (gated behind `--with-fullstack`, mirroring `phase_content` behind `--with-content`), so the conductor treats Full-Stack as a **peer** of Companion and Content instead of inlining the checks. The heavy G0 ratchet stays opt-in (`--with-guardian`) so the default sibling run is fast and offline.

---

## Standing rules inherited from the study (§8)

- **Rule A** — every production change lands with a gate change.
- **Rule B** — baselines only move down.
- **Rule C** — every fix updates ≥3 skills.

The Full-Stack SaaS Gate does not replace the study; it **operationalizes** it. The study is the law; this front door is how you enforce and navigate it.
