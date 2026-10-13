---
target: marketplace.html (design lens W45971, as David Velasco)
total_score: 39
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 1
target_identity: "file:C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\marketplace.html"
target_fingerprint: "sha256:e50a015cbfb6c33cd18502726ff25f113882cd7de44364b2883b9751c48763b0"
target_path: "C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\marketplace.html"
timestamp: 2026-10-12T16-58-05Z
slug: marketplace-html
---
⚠️ DEGRADED: single-context (Ian, this session: "only you for now, no other coding agents" - Assessment A recorded
before Assessment B's detector and live evidence was read, then this synthesis)

# Critique: marketplace.html as David Velasco - 2026-10-13, design lens W45971

Mode: Operate (a plant worker browsing parts, training and jobs, and selling his own). Walked through the Playwright MCP
at phone-390 and desktop-1280, signed in through the wall; every finding below was verified live before it counted.

## Design Health Score (before -> after)

| # | Heuristic | Before | After | Key issue |
|---|-----------|--------|-------|-----------|
| 1 | Visibility of System Status | 4 | 4 | "Showing 9 listings - newest first. Sellers cannot pay for placement."; "9 listings - 3 of them yours" |
| 2 | Match System / Real World | 4 | 4 | parts by category (bearings, seals, VFDs), condition, town, credits back |
| 3 | User Control and Freedom | 4 | 4 | filters, price, compare, watchlist, saved searches, My Listings |
| 4 | Consistency and Standards | 3 | 4 | off-token deep navy, amber-400 and dark-teal colours - now the tokens |
| 5 | Error Prevention | 4 | 4 | contact-only, no payment on platform, stated up front |
| 6 | Recognition Rather Than Recall | 2 | 4 | every seller's name was cut to three or four letters on the cards at 1280 ("Rom...") - now whole |
| 7 | Flexibility and Efficiency | 4 | 4 | search, category chips, section tabs with counts |
| 8 | Aesthetic and Minimalist Design | 3 | 3 | dense cards; every listing in the seed has no photo, so each carries a camera placeholder |
| 9 | Error Recovery | 4 | 4 | read failures said as such across the page |
| 10 | Help and Documentation | 4 | 4 | "How this page works", the trust strip (ID-verified badges, secure inquiries, no fees) |
| **Total** | | **36/40** | **39/40** | Good -> Excellent |

## Design Specificity Verdict
Authored for an industrial marketplace that does not take money: the trust strip states ID-verified sellers, secure
inquiries and no platform fees; the ranking is disclosed ("newest first. Sellers cannot pay for placement"); each card
carries condition, town and the credits back the buyer earns.

Deterministic scan (Assessment B): broken-image 1, design-system-font 1 - the claim reads true today and is carried.
Walk: 0 overlap, 0 controls under 44 px, 0 low-contrast readings, smallest text 12 px, 0 heading skips, no spill, at both
widths; off-token colour reads 76 -> 45, all of them the bronze tier, a categorical scale like community's medals.

## What's Working
- The ranking rule is on the page, and it is a promise: placement cannot be bought.
- Trust is visible per card: tier, verified, trusted, rating.
- A worker's own listings are counted and routed to the seller inbox.

## Priority Issues (all fixed in this walk, verified live)
- [P1] **The seller was "Rom...".** At 1280 the four-column cards are 220 px wide, and the footer gave five star glyphs
  (letter-spacing -1px), the number and View 127 px - the seller's name got 39 of the 80 px it needs, and the name's own
  80 px cap cut longer names even on a phone ("Leandro Marquez" at 390). Who is selling is the first thing a buyer checks.
  One star beside the number now says what five did; the cap is gone and the footer wraps instead, the rating and View
  keeping the right edge. Measured: 0 of 9 names cut at both widths (was 9 at 1280, 3 at 390); every View button still
  44 px. (/impeccable layout)
- [P3] **Off-token colours**: the heart buttons' and badges' deep navy rgba(15,25,35) -> --wh-navy's channels, the
  refurbished chip's amber-400 tint -> --wh-orange's, the Trusted pill's #04212b text -> --wh-navy.

## Persona Red Flags
- **Buyer at a desk**: could not tell sellers apart on the grid - "Rom...", "Pabl...", "Lean...", "Leon...". Fixed.

## Minor Observations
- The "Listings in view" tile tags a filtered view "NARROW" in success green - a word that reads as neither good nor bad.
- The page-guide chip sits over the left edge of the next-step card for its first 8 s at 1280, then folds to an icon.
- The Services tab shows "-" for its count.

## Questions to Consider
- Should the section tabs say why Services has no count ("coming soon" or "0")?
- Should "NARROW" become a plain description ("filtered") in a neutral tone?

Questions skipped: 3 Priority Issues would require them, but this is a roadmap row - Ian's standing direction is to fix and
verify what the lens finds, so the fixes are made and the two open questions travel in the report to Ian instead.
