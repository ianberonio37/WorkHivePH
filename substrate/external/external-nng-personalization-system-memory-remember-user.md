---
name: external-nng-personalization-system-memory-remember-user
type: reference
source: https://www.nngroup.com/articles/personalization/
source_sha: nng-personalization
fetched_at: 2026-07-22
last_verified: 2026-07-22
ttl_days: 180
distilled_by: night-crawler-v1
supersedes: null
topic: NN/g personalization / system-memory — what an app should REMEMBER to cut user effort (recent items/searches, sensible defaults/autofill, last filter/view, resume-where-left-off, user override) — the EXPANDED sub-dimensions of rubric dim G5 (Ian 2026-07-22: dig into the lowest-% dim + expand it)
---

## reference · System memory / personalization — the EXPANDED G5 (what an app should remember)

Ian (2026-07-22): _"expand/extend the dimensions with the lowest % — dig from there, night-crawl internally +
externally."_ G5 measured **17.6%** (only 3/17 filterable pages persist the filter) — the platform's biggest
experience-in-motion gap. NN/g personalization + recognition-over-recall widen G5 from "persist the filter"
into the full **system-memory** dimension — every remembered thing is interaction cost the user doesn't re-pay:

- **G5a · Last filter/view/sort** — a filterable/sortable/tabbed surface RESTORES the user's last choice next
  visit (localStorage-keyed), so they don't re-apply it. *(the current 17.6% signal — the floor to lift.)*
- **G5b · Recent items / recent searches** — surface recently-viewed/edited entities + recent search terms
  ("frequent selections from previous activities") for quick re-access, instead of hunt-again.
- **G5c · Sensible defaults / autofill** — pre-fill known values (the user's hive/role, last-used asset,
  last job-ref, `autocomplete` on identity fields) — ALWAYS editable, never a locked assumption.
- **G5d · Resume where left off** — periodically save progress in longer flows so the user picks up where
  they stopped, even across a session/device (pairs X2 interruption; G5d is the cross-SESSION half).
- **G5e · Transparent + controllable** — personalization is user-overridable ("view as", an opt-out); promote
  relevant content, don't REMOVE access; audit the data so a stale value doesn't mislead. Recognition over
  recall applied ACROSS sessions: show the option, don't make the user remember + re-enter it.

**Cautions:** don't over-segment (past behaviour ≠ future); keep it transparent; keep prefilled values
editable. **Testable G5 (expanded):** per surface, score how many memory affordances it wires — restores last
filter/view (G5a), offers recents (G5b), pre-fills sensible defaults (G5c), resumes long flows (G5d) — and
whether they're user-overridable (G5e). The CENTRAL fix (centralize-first): ONE shared
`whRememberView(key, get, set)` helper pages adopt, not 14 hand-rolled persistences that drift.

Sources: https://www.nngroup.com/articles/personalization/
