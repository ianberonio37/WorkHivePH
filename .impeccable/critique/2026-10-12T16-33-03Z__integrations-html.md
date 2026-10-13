---
target: integrations.html (design lens W45936, as Christine Dizon)
total_score: 38
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\integrations.html"
target_fingerprint: "sha256:305172d5a363c9c9e1391587f63088c6d6c9a40b82d98d4670c52380f8682114"
target_path: "C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\integrations.html"
timestamp: 2026-10-12T16-33-03Z
slug: integrations-html
---
⚠️ DEGRADED: single-context (Ian, this session: "only you for now, no other coding agents" - Assessment A recorded
before Assessment B's detector and live evidence was read, then this synthesis)

# Critique: integrations.html (Connections - CMMS) as Christine Dizon (supervisor) - 2026-10-13, design lens W45936

Mode: Operate (a supervisor connecting the hive's CMMS and checking that syncs are healthy). Walked through the Playwright
MCP at phone-390 and desktop-1280, signed in through the wall; the worker view was read in a separate context as Bryan
Garcia. Every finding below was verified live before it counted.

## Design Health Score (before -> after)

| # | Heuristic | Before | After | Key issue |
|---|-----------|--------|-------|-----------|
| 1 | Visibility of System Status | 3 | 4 | "No CMMS integrations syncing yet" beside an enabled integration gone stale - now "None has synced in the last 7 days" |
| 2 | Match System / Real World | 2 | 4 | "Phase 2 - Cold Start Solver" and "(Phase 2)" - internal program names on the page - removed |
| 3 | User Control and Freedom | 4 | 4 | a dismissible setup guide, one-way connections stated, nothing syncs until Connect |
| 4 | Consistency and Standards | 2 | 4 | the vehicle wizard's four primary buttons rendered as grey native buttons (a class this page never defines); off-token card and tag colours |
| 5 | Error Prevention | 4 | 4 | a five-step import with a preview before anything lands |
| 6 | Recognition Rather Than Recall | 3 | 4 | the page's title was 1,136 px down inside one tab - the first heading anyone met was "Add a Vehicle" |
| 7 | Flexibility and Efficiency | 4 | 4 | file import, live sync and API keys side by side |
| 8 | Aesthetic and Minimalist Design | 3 | 3 | grouped, but long: a vehicle card, a banner, three tiles, a next step and a guide before the work |
| 9 | Error Recovery | 4 | 4 | the stale banner names the usual cause (an expired key or a changed URL) and where to look |
| 10 | Help and Documentation | 4 | 4 | "How to connect your CMMS" in three steps, "How this page works" |
| **Total** | | **33/40** | **38/40** | Good -> Excellent |

## Design Specificity Verdict
Authored for this product: the source picker speaks the systems' own field names (SAP's AUFNR / ISTAT / EQUNR, Maximo's
WONUM / ASSETNUM), the help states that a connection is one-way unless it says otherwise and that nothing syncs until
Connect, and a stale sync is defined in the page's own words (enabled, not synced for 7 days).

Deterministic scan (Assessment B): nested-cards 8, cramped-padding 1 - the September claim still reads true and is
carried (its all-caps finding has since been fixed and is dropped). Walk: 0 overlap, 0 controls under 44 px, 0
low-contrast readings, smallest text 12 px, 0 heading skips, no spill, at both widths; off-token colour reads 12 -> 6, and
the remaining six are the shared wayfinding band, graded separately.

## What's Working
- The stale banner is specific: which tab, which row, and the two usual causes.
- The import is staged - source, upload, map, preview, import - so nothing lands unseen.
- Workers are told plainly that the console is a supervisor surface, and keep the vehicle wizard.

## Priority Issues (all fixed in this walk, verified live)
- [P1] **The page's title was 1,136 px down, inside one tab.** "Connections" was the h1 of the Import tab's header, so on
  Live Sync and API Keys the page had no h1 at all, and on Import it came after the vehicle card's h2, the summary and the
  tab bar. The title and the CMMS / Plant-IoT switch now head the page; the worker gate keeps the title and removes the
  switch. Measured: supervisor headings h1 Connections -> h2 Add a Vehicle -> h2 Which CMMS..., at both widths; worker
  h1 Connections -> h2 Add a Vehicle -> h2 Supervisor access only.
- [P1] **The vehicle wizard's primary buttons were unstyled.** "Add my vehicle", both "Next" steps and "Create my vehicle"
  used .btn-primary, a class from other pages that this one never defines - so they rendered as Chrome's grey native
  buttons (#6b6b6b), the primary action looking disabled. Now the page's own primary, btn btn-gold.
- [P2] **Internal program names on the page**: a "Phase 2 - Cold Start Solver" pill over the title and "(Phase 2)" in the
  source chip. Removed. (/impeccable clarify)
- [P2] **"No CMMS integrations syncing yet"** read as "none set up" beside an enabled integration gone stale, and the
  stale tile said "1 enabled integration haven't synced". Now "None has synced in the last 7 days" and "hasn't".
- [P3] **Colours and motion.** The source cards' --card was #1d2e44, one unit from --wh-navy-mid; the shared grey tag
  (components.css, also dayplanner's) was Tailwind slate-300; four rules transitioned `all`. Now the token, the
  platform's muted white, and the named properties on --wh-ease-out.

## Persona Red Flags
- **Supervisor using a screen reader**: the first heading was a car; the page's name was not reachable on two of its
  three tabs. Fixed.
- **Solo car owner**: the "Add my vehicle" button looked disabled. Fixed.

## Minor Observations
- The page background is #0f1923, the same near-navy as the signed-in home's - a candidate for a token, not a per-page
  edit.
- Before the import work begins a supervisor passes a vehicle card, a banner, three tiles, a next step and a guide.

## Questions to Consider
- Should "Add a Vehicle" live on Asset Hub (where assets are made) rather than on the CMMS page?
- Should the deep navy #0f1923 that several pages paint their background with become a named token?

Questions skipped: 3 Priority Issues would require them, but this is a roadmap row - Ian's standing direction is to fix and
verify what the lens finds, so the fixes are made and the two open questions travel in the report to Ian instead.
