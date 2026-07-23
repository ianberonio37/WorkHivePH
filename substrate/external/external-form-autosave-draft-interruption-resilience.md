---
name: external-form-autosave-draft-interruption-resilience
type: reference
source: https://design.gitlab.com/patterns/saving-and-feedback/ + https://ui-patterns.com/patterns/autosave
source_sha: gitlab-pajamas-saving + ui-patterns-autosave
fetched_at: 2026-07-22
last_verified: 2026-07-22
ttl_days: 180
distilled_by: night-crawler-v1
supersedes: null
topic: form autosave / draft / interruption resilience — debounced save, restore-on-return, Saving/Saved status, unsaved-changes guard (beforeunload/sendBeacon on unload), multi-step progress — the EXPANDED sub-dimensions of rubric dim X2 (Ian 2026-07-22: expand the low-% dims into more sub-dims, night-crawl)
---

## reference · Form autosave / draft / interruption resilience — the EXPANDED X2

Ian (2026-07-22): _"expand the low-% dims into more sub-dimensions, night-crawl."_ X2 measured **11.1%**
(only 1/9 compose-forms autosave a draft) — the platform's biggest experience-in-motion gap after G5. GitLab
Pajamas "Saving & feedback" + ui-patterns "Autosave" widen X2 from "autosave a draft" into the full
**interruption-resilience** dimension — every lever protects a field-tech's in-progress work from a
connectivity blip / phone call / accidental close:

- **X2a · Draft autosave** — a substantial entry/compose form autosaves to localStorage on a **debounced
  input** (0.5-2s after the user stops typing — not every keystroke) so a refresh/interruption doesn't lose
  the work. *(the current 11.1% signal — the floor to lift.)*
- **X2b · Restore on return** — the saved draft is RESTORED into the form when the user comes back (into
  empty fields; an explicit non-empty value wins), and **cleared on a successful submit** so the next entry
  starts fresh (a stale draft re-showing submitted content is a bug).
- **X2c · Save-status feedback** — reassure the user their progress is kept: a **"Saving…"** (spinner) then
  **"Saved just now / Saved 1 min ago"** (timestamp) indicator; without it the user re-checks or re-types.
- **X2d · Unsaved-changes guard** — a `beforeunload` warning on a dirty form OR a last-chance save via
  `navigator.sendBeacon()` on unload, so an accidental tab-close / back-nav / navigate-away doesn't lose work.
- **X2e · Multi-step progress** — a multi-step flow saves progress PER STEP so an interruption resumes at the
  right step, not the start (pairs G5d resume-where-left-off).

**Storage:** localStorage fits same-device return (WorkHive's field-tech re-opening the app); server-side
drafts fit cross-device resume or when losing a draft would really hurt. **Central fix (centralize-first):
ONE shared `whAutoSaveDraft(key, ids)` helper** (debounced save + restore-into-empty + clear-on-submit) pages
adopt, not N hand-rolled drafts. **Testable X2:** per compose/entry-form page, score X2a (autosaves), X2b
(restores + clears on submit), X2c (save status), X2d (unsaved-changes guard), X2e (multi-step progress).

Sources: https://design.gitlab.com/patterns/saving-and-feedback/ · https://ui-patterns.com/patterns/autosave
