---
name: external-offline-ux-state-queue-sync-guidelines
type: reference
source: https://web.dev/articles/offline-ux-design-guidelines
source_sha: webdev-offline-ux-2026
fetched_at: 2026-07-22
last_verified: 2026-07-22
ttl_days: 180
distilled_by: night-crawler-v1
supersedes: null
topic: offline-capable web-app UX — communicate connectivity state, queue offline actions visibly (never silent-fail or false-success), give reconnect sync feedback, map which features work offline — the measurable core of rubric dim Y1 (offline & connectivity resilience)
---

## reference · Offline UX — state, queued actions, sync feedback (web.dev)

The measurable core of UFAI **Y1 · Offline & connectivity resilience**. This is the offline *UX*, distinct
from deepwalk layer **CA** = caching *integrity* (SW shell membership). Critical for WorkHive's spotty-signal
Filipino field workers.

* **Communicate connectivity STATE persistently** — a visible online / offline / reconnecting indicator
  (text + icon + colour, not colour alone). "Tell the user both the app's state and the actions they can
  still take" when the network fails.
* **Queue offline actions VISIBLY — never silent-fail, never false-success.** An action taken offline shows a
  pending status ("will be sent when the network is restored"), never a confirmation it didn't actually
  commit, never a swallowed error. (Pairs J3 optimistic-UI honesty + the deepwalk L error-capture backbone.)
* **Reconnect sync FEEDBACK** — on reconnect, tell the user what synced + surface any conflict needing their
  resolution (don't silently overwrite or drop).
* **Map feature availability** — each control indicates whether it needs connectivity; disable connectivity-
  required actions (purchase, live pricing) while offline, preserve read/browse/compose.
* **No broken/blocking states** — no full-screen loading modal that traps interaction, no gray-out that
  hides whether offline features work; use honest skeletons + reassuring copy.

**Testable rule (Y1):** with the network forced offline (devtools/SW) → a connectivity indicator is present;
a write attempt is queued + labelled pending (not a false toast, not a silent drop); on reconnect the user
gets sync feedback. A page that shows "Saved" while offline without committing = FAIL (also a J3 violation).

Sources: https://web.dev/articles/offline-ux-design-guidelines
