---
name: external-wcag-target-size-minimum-24px-spacing
type: reference
source: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
source_sha: wcag22-2.5.8-target-size
fetched_at: 2026-07-22
last_verified: 2026-07-22
ttl_days: 180
distilled_by: night-crawler-v1
supersedes: null
topic: WCAG 2.2 SC 2.5.8 Target Size (Minimum) 24x24 CSS px + the 24px-circle spacing exception — accidental-activation guard, the measurable core of rubric dim Z3 (gesture ergonomics & accidental-touch)
---

## reference · WCAG 2.2 SC 2.5.8 Target Size (Minimum) — 24px + spacing (accidental-touch)

The measurable core of UFAI **Z3 · Gesture ergonomics & accidental-touch** (the accidental-activation half).
WCAG 2.5.8 (Level AA); note WorkHive's field context (gloves, one-handed, motion) argues for the stronger
44-48px comfort target (F1/K2) as the design goal, with 24px as the hard floor.

* **Minimum target 24×24 CSS px** for pointer inputs.
* **Spacing exception (the accidental-touch rule):** an undersized target still passes IF a **24px-diameter
  circle** centered on it does not intersect another target (or another's circle). Restated for Z3: two
  adjacent tap targets need **≥24px center-to-center clearance**, so a fat finger can't hit the wrong one.
  This is the measurable form of "a destructive control must not sit adjacent to a common one."
* **Exceptions:** inline (in-sentence links), equivalent alternative elsewhere on the page at ≥24px,
  UA-controlled (native `<input type=date>`), essential (maps/data-viz where position carries meaning),
  transient/obscured (dropdowns, modals).
* **Why:** users with tremor/limited dexterity + all touchscreen users mis-activate small/crowded targets.

**Testable rule (Z3):** every interactive target ≥24×24 CSS px OR passes the 24px-circle spacing test; a
DESTRUCTIVE target (delete/reset/cancel-order) adjacent (<24px clearance) to a common one = accidental-touch
FAIL. Gesture-only actions (swipe-to-delete, long-press) must also expose a visible/tappable equivalent
(discoverability) — a hidden gesture is not an affordance.

Sources: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
