# UFAI UI/UX Improvement Plan — CLOSING STATE (2026-09-02)

_Generated from `critic_registry.json` at walk-coverage completion. The living registry is the SSOT;
this document is the program's synthesis and hand-off record._

## Where the program landed

- **All 480 in-scope trajectories walked and critiqued**: 440 critiqued · 40 improving · 0 pending.
- **63 receipted findings → 1 remaining** (T12's S1 opener-tune, deferred: the local edge runtime is
  down, so a prompt change's OUTPUT cannot be live-verified — deferred rather than banked unverified).
- **Major+ (severity ≥3): ZERO open.** Every S4 and S3 was fixed by judgment, verified live at the
  exact walked hop, and locked by a resurrection-toothed gate.
- **19 new gates registered** on the platform board this program (all grep-verified):
  team-deeplink-survives, one-clock-per-string, journal-transcript-is-raw, critic-registry, kpi-evidence-links, xp-feedback-reaches-worker, skill-privacy-copy-consistent, risk-pm-linkage, assistant-no-orphan-fragment, pm-completion-repaints-truth, hive-name-reconciles, inventory-tx-attribution, staged-stock-guard, modal-back-helper, draft-age-visible, approval-queue-aggregates, report-reason-deliberate, pick-prefills-category, embed-retry-queue.
- **3 migrations** landed+applied: credit-hold audience-neutral voice, inventory server-side
  attribution (JWT-not-body), staged-stock guard (the marketplace-hold mirror).
- **The flywheel proved itself**: journal-transcript-is-raw's DB layer caught a LIVE regression
  same-day (the third scaffold-sender in assistant.html) that the fix-audit had missed.

## The 13 root clusters — final dispositions

1. **Clock discipline** (one clock per string, plant-anchored, labeled) — FIXED+GATED
   (one-clock-per-string; logbook/index/shift-brain/audit-log/alert-hub all verified).
2. **Reserved stock enforcement** — FIXED+GATED (staged-stock-guard REPLAYS the refusal live each run).
3. **Audit attribution** — FIXED+GATED (inventory-tx-attribution; payload-lies-JWT-wins proven).
4. **AI transcript integrity** — FIXED+GATED (journal-transcript-is-raw, 3 sender paths + DB layer).
5. **Dead/broken chain hops** — FIXED+GATED (team-deeplink-survives; the diagnostic chain runs
   alert-hub→asset-hub→logbook end-to-end).
6. **Stale renders after writes** — FIXED+GATED (pm-completion-repaints-truth: write→read→render).
7. **XP/feedback legibility** — FIXED+GATED (xp-feedback-reaches-worker: queue + earn notes).
8. **KPI truthfulness** (caps-as-totals, dead-end figures, unnamed windows) — FIXED+GATED
   (kpi-evidence-links: exact counts, drill-to-evidence, window labels).
9. **Identity/name integrity** (wrong-plant chrome, phantom risks) — FIXED+GATED (hive-name-reconciles).
10. **Honest refusals & walls** (privacy copy, report reasons, quota voice, credit-hold pronoun) —
    FIXED+GATED (skill-privacy-copy-consistent, report-reason-deliberate + migrations).
11. **Interaction costs** (modal-back, category prefill, approval aggregation, dwell/review ages) —
    FIXED+GATED (modal-back-helper, pick-prefills-category, approval-queue-aggregates,
    draft-age-visible).
12. **Resilience surfaces** (offline round-trip, stream fragments, mic dead-taps, embed retry) —
    FIXED+GATED (assistant-no-orphan-fragment, embed-retry-queue, MIC_BOUND; T14's full
    offline→queue→sync→DB round-trip proven live).
13. **Instrument honesty** — 12 findings withdrawn as instrument misreads across the program, each
    with the probe lesson banked (toast TTLs, layout-vs-exposure, partial-listing traps,
    never-settling promises).

## What remains (the endgame, in order)

1. **The residual FULL BOARD** (Ian's ~6h gate): re-earns the ~687 browser-gated bank rows and — via
   `tools/post_board_promote.py --apply` — flips critiqued/improving → locked on gate-PASS. This is
   the 71.2% → 100% lever, and it is deliberately Ian-initiated.
2. **T12's opener-tune** once the edge runtime is up (a `supabase functions serve` attempt is
   in flight; if it serves, tune + verify + clear the last finding).
3. **Ian's standing gates**: the commit manifest (`.tmp/COMMIT_MANIFEST.md`), the skills writeback
   (cross-skill table prepared for one-pass approval).

The platform's UI/UX story after this program: **the strong majority of what the walks tested was
already sound** — conversion, onboarding, re-auth, offline, failure-legibility all took hits and
held — and every place it wasn't sound is now fixed at the root, proven at the broken hop, and
gated so it cannot quietly regress.
