---
target: engineering-design.html (design lens W45915, as Oscar Ramos)
total_score: 37
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\engineering-design.html"
target_fingerprint: "sha256:f8cebcbbb43b62719fb648233a8f1bc2433538094f64c271e7516529d0f78b02"
target_path: "C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\engineering-design.html"
timestamp: 2026-10-12T15-55-09Z
slug: engineering-design-html
---
⚠️ DEGRADED: single-context (Ian, this session: "only you for now, no other coding agents" - Assessment A recorded
before Assessment B's detector and live evidence was read, then this synthesis)

# Critique: engineering-design.html as Oscar Ramos (jeepney operator) - 2026-10-13, design lens W45915

Mode: Operate (a person who picks a calculation, fills its inputs on a phone and takes the report away). Walked through
the Playwright MCP at phone-390 and desktop-1280, signed in through the wall; the core task was run end to end (Machine
Design -> V-Belt Drive Design -> Run, with the calc agent asked for no model call); every finding below was verified live
before it counted, and each fix was re-measured at both widths.

## Design Health Score (before -> after)

| # | Heuristic | Before | After | Key issue |
|---|-----------|--------|-------|-----------|
| 1 | Visibility of System Status | 3 | 4 | after Run on a phone the report scrolled in BEHIND the pinned header - its Download PDF and Save hidden - now lands below it |
| 2 | Match System / Real World | 4 | 4 | PEC 2017, ASHRAE, PSME, NFPA, ISO cited; PRC License No on the report; metric units |
| 3 | User Control and Freedom | 3 | 4 | once scrolled, the Back/breadcrumb band covered the page title and two of the three tabs - now pinned below it |
| 4 | Consistency and Standards | 3 | 4 | the search magnifier floated above its field (on four other pages too); the help disclosure restyled after paint - both fixed |
| 5 | Error Prevention | 3 | 3 | input validation toasts and guarded saves; example values fill every field, so a report can be made on them untouched |
| 6 | Recognition Rather Than Recall | 4 | 4 | every calc card carries its purpose and standard; per-discipline counts; search all 55 |
| 7 | Flexibility and Efficiency | 4 | 4 | search, units toggle, recent calcs, editable report fields, BOM/SOW export |
| 8 | Aesthetic and Minimalist Design | 2 | 3 | a 245 px pinned header at 390 (a 15-line chip in a 139 px column) and a 92 px dead band at 1280 - now 69 px |
| 9 | Error Recovery | 3 | 3 | friendly failure copy and a 45 s timeout on the calc agent |
| 10 | Help and Documentation | 4 | 4 | "How this page works", the Guide tab, the report's AI-drafted note and "Based on" line |
| **Total** | | **33/40** | **37/40** | Good -> Excellent |

## Design Specificity Verdict
Authored for this product and this country: the calculations are anchored to named standards (PEC 2017, PSME, ASHRAE,
NFPA, RMA IP-20 / ASME B17.1 for the belt drive), the report carries a PRC License No and "Prepared by Oscar Ramos", and
the written summary is labelled AI-drafted with what it was based on. Six disciplines, 55 calculations, each card saying
what it sizes.

Deterministic scan (Assessment B): clipped-overflow-container x3 - html and body (the site-wide `overflow-x: clip`
horizontal-scroll guard, which clips no vertical overflow) and the decorative aurora backdrop; the September claim still
reads true today and is carried. Walk: 0 overlap, 0 controls under 44 px, 0 low-contrast readings, smallest text 12 px,
0 heading skips, no spill, at both widths; 11 nested-card readings; the aurora drifts at 1280 (stops under reduced motion).
Load layout shift after the fixes: 0 at both widths (was 0.035 at 1280).

## What's Working
- The core task is short and honest: Machine Design -> V-Belt Drive Design -> Run produced a full report in about 7 s,
  scrolled to it on a phone, and announced it to a screen reader.
- The report owns its provenance: the standard in the title, the AI-drafted note, "Based on: your inputs and this
  calculation's computed results", and a was-this-right row.
- Nothing is written to the hive until Save is pressed, and the page says so in "How this page works".

## Priority Issues (all fixed in this walk, verified live)
- [P1] **The pinned header held 29% of a phone screen.** The header was sticky and carried the source chip with an inline
  161 px reserve beside the 213 px tab group: at 390 the title column was squeezed to 139 px, the chip wrapped to 15 lines
  (182 px - past its own reserve) and the pinned header was 245 px of 844 while Oscar scrolled the calc list and filled
  inputs; with a phone keyboard up about 300 px were left for the form. At 1280 it was 224 px of 800, 92 px of it the
  unused reserve. The markup's own note says the pin was for the TAB BAR, so the title and tabs stay pinned and the
  provenance chip now reads in the flow under them at full width, reserved at what it renders (69 px at both widths).
  Pinned header: 69 px at both widths; load shift 0 at both. (/impeccable layout + adapt)
- [P1] **After Run, the report landed behind the pinned stack.** The header pinned at top 0 beneath the wayfinding band
  (fixed, z-index 9000, always on screen), so once scrolled the Back and breadcrumb pills covered the page title and the
  Calculator and History tabs; and Run scrolled the report to viewport top 0, so its Download PDF and Save sat under the
  header. The header now pins on the band's own reserve line (64 px + safe area + the offline banner's height), and the
  report and the BOM/SOW preview land below whatever is pinned, measured at the moment of scrolling (reduced motion jumps).
  Hit-tested at 390 after Run: Download PDF, Save, the title and all three tabs clear; the report starts 8 px under the
  header. (/impeccable harden)
- [P2] **The search magnifier floated above its field - on five pages.** The emoji migration replaced each search SVG
  (`absolute left-3 top-1/2 -translate-y-1/2`, or a page's `.search-wrap svg` / `.search-icon` rule) with an .ic span and
  the positioning did not come along: measured on engineering-design, inventory, logbook, marketplace and
  marketplace-admin at both widths, every icon sat above its input beside the 36-40 px left padding still reserved for
  it. One rule in the icon library now places an .ic-search that is followed by its input; the three dead page rules are
  gone. Re-measured: inside the field on all five pages at both widths. sw.js v515. (/impeccable polish)
- [P3] **"How this page works" restyled after first paint.** This page does not link components.css, so utils.js
  injected the .wh-help rules late and the summary grew 24 -> 44 px: a 0.035 shift at 1280. The page now links
  wh-help.css, as the three other pages without components.css already do. Shift 0.

## Persona Red Flags
- **Jeepney operator**: the page opens on HVAC & Cooling; his work is Machine Design (belts, bearings, shafts). The
  default is the plant's discipline, not his.
- **First-timer**: picking a calculation jumps the strip to "Step 4 of 4: Calculate" because example values fill every
  field - he can produce "Untitled Belt Drive" on someone else's 7.5 kW motor without touching an input.

## Minor Observations
- The report's tip says "Click any underlined field" on a phone.
- The wayfinding band's own greys (#111827, #cbd5e1, #f3f4f6, #93c5fd) are off-token on every page - shared chrome,
  graded once, not this page's.
- At 1280 the "No Report Yet" card holds the top of the right column while the left column runs 1,800 px.

## Questions to Consider
- Should the discipline open on the one this person used last (History knows), rather than always HVAC?
- Should example values read as examples (placeholder style) until edited, so a report is never made on them by accident?

Questions skipped: 3 Priority Issues would require them, but this is a roadmap row - Ian's standing direction is to fix and
verify what the lens finds, so the fixes are made and the two open questions travel in the report to Ian instead.
