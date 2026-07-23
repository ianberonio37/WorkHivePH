---
name: external-responsive-patterns-reflow-content-parity-breakpoints
type: reference
source: https://web.dev/articles/responsive-web-design-basics
source_sha: webdev-rwd-basics
fetched_at: 2026-07-22
last_verified: 2026-07-22
ttl_days: 180
distilled_by: night-crawler-v1
supersedes: null
topic: responsive design PATTERNS — viewport meta, content-driven breakpoints, wide-table reflow (stack/scroll/hide-secondary), content parity (don't hide by viewport), fluid grid + flexible images, pointer/hover media adaptation — the EXPANDED sub-dimensions of rubric dim Z2 (Ian 2026-07-22: expand every dim into sub-dims)
---

## reference · Responsive design patterns — the EXPANDED Z2 sub-dimensions

Ian (2026-07-22): expand every dim into sub-dims. Z2 (responsive reflow) widens from "no h-scroll @320"
(WCAG 1.4.10, `external-css-reflow-320px...`) into the full responsive-adaptation dimension:

- **Z2a · Reflow (no 2D scroll @320)** — the WCAG 1.4.10 floor: `<meta viewport width=device-width>`, page
  `scrollWidth ≤ clientWidth` at 320 CSS px (a wide table 2D-scrolls only inside its own `overflow-x:auto`).
- **Z2b · Wide-table → cards** — a wide data table REFLOWS on phone (stack rows into cards, or a scroll
  container, or hide-secondary-columns), not a pinch-zoom grid.
- **Z2c · Content parity** — "don't hide content just because you can't fit it": no INFO or ACTION present at
  1280 is silently dropped at 390 (evaluate user need per breakpoint, don't remove by viewport size).
- **Z2d · Content-driven breakpoints + fluid grid** — breakpoints set where the CONTENT degrades (line length
  ~70-80 chars), NOT by device class; fluid grid (flexbox/grid) + flexible images (`max-width:100%` + explicit
  w/h to reserve space, pairs I1 CLS).
- **Z2e · Pointer/hover adaptation** — use `@media (pointer/hover/any-pointer)` so a touchscreen user isn't
  forced into hover-only behaviour; tap targets meet the touch floor at small widths (pairs Z3/F1).

Sources: https://web.dev/articles/responsive-web-design-basics
