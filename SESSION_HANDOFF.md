# Session Handoff — fresh context window

**Created:** 2026-05-27 (end of turn 7)
**For:** the next Claude session that opens this project cold
**Read time:** ~3 minutes
**Then read:** [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md) → [PLATFORM_ROADMAP.md](PLATFORM_ROADMAP.md)

---

## TL;DR — where the platform is

7 flywheel turns. **Combined coverage 14% → 48%** across both grids (production + gate). Gate grid at 64%. Production at 40%. **68 / 78 matrix cells filled (87%).** 10 gap cells remain.

**Guardian state:** 327 PASS / 1 FAIL / 13 SKIP. The 1 FAIL is `validate_pwa.py` git-commit-time check — fixable only by `git commit`.

**Meta-gate `tools/audit_fullstack_gate_coverage.py`:** 47/47 artefacts in the study's §4 matrix exist on disk.

---

## What's uncommitted (158 working-tree changes)

Significant unstaged work spans 7 turns. **DO NOT `git checkout <file>` on any of these** — see [feedback memory `never-git-checkout-uncommitted-work`](../../../Users/ILBeronio/.claude/projects/.../memory/feedback_never_git_checkout_uncommitted_work.md). Turn 7 lost ~2 hours to that exact mistake.

If a file's syntax breaks mid-session, undo via Edit. If that fails, copy aside first:
```bash
cp <file> <file>.broken
git checkout <file>
# diff and re-apply
```

---

## The 4 docs that anchor the architecture

1. **[COMPREHENSIVE_STUDY_FULLSTACK_GATE.md](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md)** — the architectural source of truth. 13 production × 6 gate matrix, 15 persistence mechanisms, 22→10 gap list, 3 standing rules. Read first.
2. **[PLATFORM_ROADMAP.md](PLATFORM_ROADMAP.md)** — 101-item operational tracker with 7-turn changelog. Read second.
3. **[UNIFIED_MEGA_GATE.md](UNIFIED_MEGA_GATE.md)** v2 — 6-gate-layer definitions (G-1.5 / G-1 / G0 / GH / GS / G2).
4. **[ROLLBACK_RUNBOOK.md](ROLLBACK_RUNBOOK.md)** — fast path / standard rollback / PITR.

---

## The 7 priorities locked for next session

From [PLATFORM_ROADMAP.md](PLATFORM_ROADMAP.md) Part 5 + study §7. In order:

1. **Commit working tree** — fixes the persistent PWA git-commit-time FAIL. `tools/mine_cache_name_drift.py` confirms 8 SHELL_FILEs are stale vs sw.js. **Get user confirmation first** before committing (per project rules).
2. **Per-skill validator tagging** — retry with safer approach. Turn 7 attempt broke dict syntax. New plan: write skill tags to a **sidecar JSON file** (e.g. `VALIDATOR_SKILLS.json`) instead of inline edits to `run_platform_checks.py`. Then the validator catalog page can join the two.
3. **RLS USING(true) cleanup** — 15 policies surfaced by `tools/mine_rls_policies.py`. Each needs a forward migration that supersedes the permissive policy with an explicit role+expression.
4. **Missing TO clause cleanup** — 123 policies default to PUBLIC. Audit + add explicit TO clauses.
5. **Per-fn envelope success-path migration** — `validate_envelope_return_shape.py` floor is 1 (ai-gateway only). 55 fns import the envelope but don't return it. Migrate next 4 high-traffic fns.
6. **Truth-view meta-columns** — baseline still 37. Top-5 views need `_source_count`, `_freshness_ts`, `_canonical_version` added via `CREATE OR REPLACE VIEW`.
7. **Push branch + enable GitHub Actions** — yaml in place at `.github/workflows/ci.yml`. Needs repo enable + `WH_TEST_BASE_URL` secret.

Projected after these 7: combined **48% → ~60%**.

---

## What's deferred (10 remaining gap cells)

Lower priority, mostly need external setup:

- (H, G-1) Staging environment auto-discovery — needs separate Supabase project
- (AV, GH) Game-day automation — quarterly trigger
- 8 other low-priority cells (see study §7)

---

## Important persistence notes

**These 15 mechanisms guarantee nothing is lost across sessions** — see `reference_persistence_doctrine.md` memory entry. Critical ones:

| Mechanism | Where | What it preserves |
|---|---|---|
| Frozen baselines (`*_baseline.json`) | Project root | Locked violation counts per validator |
| Migration hashes | `migration_hashes.json` | sha256 of all 188 migrations; FAIL on edit |
| PLATFORM_ROADMAP.md changelog | Part 6 | 7-turn history with %s |
| Memory entries | `~/.claude/projects/.../memory/` | Cross-session orientation |
| Canonical registry | `canonical_registry.json` | 73 RPCs + tables + views declared |
| Sentinel registry | `SENTINEL_REGISTRY.json` | Every sentinel anchor |

---

## What was almost lost in turn 7

The `git checkout run_platform_checks.py` accident in turn 7 dropped 15 validator registrations + the severity sweep. Recovered by re-appending in one Edit. **Severity sweep is currently at 13/345 (was 273/330 before revert)** — re-run `python tools/add_validator_severity.py` early next session to restore it.

This is the only known "stale" persistence — everything else is intact.

---

## Quick session-start sequence

```bash
# 1. Confirm state (≤30 sec)
python tools/audit_fullstack_gate_coverage.py     # expect 47/47 present
python sentinels/multi_scenario_per_rule.py        # expect PASS (0 gaps)
python tools/build_substrate_manifest.py           # surfaces this-session signal

# 2. Restore severity sweep (turn 7 leftover)
python tools/add_validator_severity.py             # should add ~330 entries

# 3. Read the architecture
cat COMPREHENSIVE_STUDY_FULLSTACK_GATE.md | head -200   # §1-§4

# 4. Pick a priority from above and ship.
```

---

## Cross-links

- [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md)
- [PLATFORM_ROADMAP.md](PLATFORM_ROADMAP.md)
- [UNIFIED_MEGA_GATE.md](UNIFIED_MEGA_GATE.md) v2
- [ROLLBACK_RUNBOOK.md](ROLLBACK_RUNBOOK.md)
- [CAPACITY_PLAN.md](CAPACITY_PLAN.md)
- [RTO_RPO_DECLARATION.md](RTO_RPO_DECLARATION.md)
- `MEMORY.md` — top entries point you to all the above + the feedback memories

---

## The standing rules (re-asserted)

1. **Every production change lands with a gate change.** Helpers without validators don't count as done.
2. **Baselines only move down.** An incrementing baseline is a real regression, not a "rebase."
3. **Every fix updates ≥3 skills.** Lessons compound platform-wide, not just per-file.

If a future turn violates any of these, revert that turn. The flywheel only compounds when the rules hold.
