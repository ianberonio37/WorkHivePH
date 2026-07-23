---
name: external-css-reflow-320px-no-two-dimensional-scroll
type: reference
source: https://www.w3.org/WAI/WCAG22/Understanding/reflow.html
source_sha: wcag22-1.4.10-reflow
fetched_at: 2026-07-22
last_verified: 2026-07-22
ttl_days: 90
distilled_by: night-crawler-v1
supersedes: null
topic: WCAG 2.2 SC 1.4.10 Reflow — content must reflow to 320 CSS px wide (vertical) / 256 CSS px tall (horizontal) with NO two-dimensional scrolling; the 2D-layout exception (tables/maps/toolbars) is scoped only to that section — the measurable core of rubric dim Z2 (responsive reflow)
---

## reference · WCAG 2.2 SC 1.4.10 Reflow (responsive reflow, no 2D scroll)

The measurable core of UFAI **Z2 · Responsive reflow & content parity**. WCAG 1.4.10 (Level AA):

* **320 CSS px width — no horizontal scroll for vertical content.** Content must present without loss of
  info/functionality AND without two-dimensional scrolling at a width equivalent to **320 CSS px**. This is
  exactly a **1280px viewport at 400% zoom** — so a page that has NO horizontal scrollbar at a 320px-wide
  layout viewport passes; one that does (a fixed-width table, an unwrapped row, a `width:600px` card) fails.
* **256 CSS px height — no vertical scroll for horizontal content** (= 1024px viewport at 400%). The mirror
  rule for content whose reading direction is horizontal.
* **One-direction scroll only, along the reading direction.** LTR/RTL text: vertical scroll OK, horizontal
  scroll is the FAIL. You must never have to scroll BOTH axes to read a line of text.
* **The 2D-layout EXCEPTION is narrow + section-scoped.** Parts that genuinely require two-dimensional layout
  for usage/meaning are excepted: **data tables/grids, maps, diagrams, video, games, presentations at fixed
  dimensions, persistent toolbars**. BUT "the exception only applies to that section" — it does NOT extend to
  surrounding content. So a wide data table may 2D-scroll INSIDE its own `overflow:auto` box, but the PAGE
  around it must still reflow to 320 with no page-level horizontal scroll. (This is why a responsive design
  turns a wide table into stacked cards on phone, or wraps it in a horizontally-scrollable container — the
  page body never scrolls sideways.)
* **Reflow ≠ loss.** Repositioning / single-column stacking is NOT a "loss of information or functionality"
  as long as: all content stays reachable, nothing is hidden/removed, and text inside any excepted section
  still reflows to the 320/256 thresholds. **Corollary for Z2 content-parity:** hiding a critical ACTION on
  the small viewport (a button present at 1280 but `display:none` at 390 with no equivalent) IS a loss.

**Testable summary:** at a **320px** layout viewport → `document.documentElement.scrollWidth` must be
≤ viewport width (no page horizontal scroll); any element wider than the viewport is a reflow violation
UNLESS it is inside an `overflow-x:auto|scroll` container OR is an excepted 2D type (table/map/diagram/
video/toolbar). Action-parity: the set of primary/interactive affordances at 390px == the set at 1280px
(none silently dropped).

Sources: https://www.w3.org/WAI/WCAG22/Understanding/reflow.html
