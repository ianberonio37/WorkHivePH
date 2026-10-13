---
target: inventory.html (design lens W45943, as Hector Salvador)
total_score: 39
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 1
target_identity: "file:C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\inventory.html"
target_fingerprint: "sha256:a1aae2e1f6ae56d58021c9c221674c88c7766d32758a573e73b21201975f8b4c"
target_path: "C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\inventory.html"
timestamp: 2026-10-12T16-39-00Z
slug: inventory-html
---
⚠️ DEGRADED: single-context (Ian, this session: "only you for now, no other coding agents" - Assessment A recorded
before Assessment B's detector and live evidence was read, then this synthesis)

# Critique: inventory.html as Hector Salvador (supervisor, Manila Electronics Assembly) - 2026-10-13, design lens W45943

Mode: Operate (a supervisor checking what is running low and restocking it). Walked through the Playwright MCP at
phone-390 and desktop-1280, signed in through the wall; every finding below was verified live before it counted.

## Design Health Score (before -> after)

| # | Heuristic | Before | After | Key issue |
|---|-----------|--------|-------|-----------|
| 1 | Visibility of System Status | 2 | 4 | "Parts at healthy stock: 4 of 27" beside tiles saying only 3 were at or below minimum - now 24 of 27 |
| 2 | Match System / Real World | 4 | 4 | reorder point, critical below half the minimum, pending supervisor sign-off - the stores' own terms |
| 3 | User Control and Freedom | 4 | 4 | use / restock / adjust per part, CSV out, add part |
| 4 | Consistency and Standards | 2 | 4 | 125 off-token colour reads - Tailwind green/red buttons and sky/rose stock colours - now 13, all a deliberate hue |
| 5 | Error Prevention | 4 | 4 | a missing quantity reads "Stock unknown", never "In Stock" |
| 6 | Recognition Rather Than Recall | 4 | 4 | stock state as a coloured edge AND a word on every card |
| 7 | Flexibility and Efficiency | 4 | 4 | search part, number or linked asset; one-tap "Find on Marketplace" for low parts |
| 8 | Aesthetic and Minimalist Design | 3 | 3 | dense but ordered; two "back" controls at the top (the band and "Back to Home") |
| 9 | Error Recovery | 4 | 4 | a failed read is said, not shown as an empty store |
| 10 | Help and Documentation | 4 | 4 | "How this page works", "How this is computed", the page guide |
| **Total** | | **35/40** | **39/40** | Good -> Excellent |

## Design Specificity Verdict
Authored for a stores room: critical is defined (below half the minimum), low is at or below the reorder point, a part can
be linked to the assets it serves, a low part opens the marketplace pre-searched, and a part a worker adds waits for the
supervisor's sign-off.

Deterministic scan (Assessment B): nested-cards 3, clipped-overflow-container 1, broken-image 1 (the photo preview's
src-less <img>, filled from JavaScript inside a hidden wrapper) - the September claim reads true today and is carried.
Walk: 0 overlap, 0 controls under 44 px, 0 low-contrast readings, smallest text 12 px, 0 heading skips, no spill, at both
widths. Motion: the part cards' 0.22 s ease-out entrance, stilled under reduced motion.

## What's Working
- "Stock unknown" is its own state: a missing quantity is never painted as "In Stock".
- The critical banner says what critical means and what to do: reorder now, before zero.
- Low parts carry a door to the marketplace, searched for that part.

## Priority Issues (all fixed in this walk, verified live)
- [P1] **The healthy-stock bar told the opposite of the tiles beside it.** It counted only parts whose state is "ok",
  and the page calls a part with three times its minimum or more "surplus" - so the twenty best-stocked parts counted as
  NOT healthy: "Parts at healthy stock: 4 of 27" (15%) directly above "Low stock: 3 of 27" and "Out of stock: 0". A
  supervisor reads a store in trouble that is 89% stocked. Healthy is ok or surplus now: "24 of 27".
- [P2] **125 off-token colour reads.** The use/restock buttons were Tailwind green-500 and red-500 tints (100 reads), the
  surplus state sky-400, and the red badge texts #FCA5A5, the value tokens.css retired for contrast. Now --wh-green /
  --wh-red channels, the brand blue family for surplus, --wh-red-text. Critical keeps its rose, the one step of the scale
  with no token of its own - folding it into red would paint "Critical Low" and "Out of Stock" alike. 125 -> 13.

## Persona Red Flags
- **Supervisor deciding what to order**: the progress bar said 4 of 27 parts were healthy. Fixed.

## Minor Observations
- Two ways back at the top: the shared band's "Back" and the page header's "Back to Home".
- The shared page-guide chip sits over the left edge of the first tile row at 1280 at rest: it avoids controls by design,
  not labels, so "Out of stock" is partly under it until dismissed - shared chrome, recorded for the report.
- One orange-400 text span remains off-token.

## Questions to Consider
- Should the header's "Back to Home" go, now that every page carries the band?
- Should the page-guide chip also avoid headings and tile labels, not only controls?

Questions skipped: 3 Priority Issues would require them, but this is a roadmap row - Ian's standing direction is to fix and
verify what the lens finds, so the fixes are made and the two open questions travel in the report to Ian instead.
