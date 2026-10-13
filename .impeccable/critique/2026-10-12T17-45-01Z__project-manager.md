---
target: project-manager.html
total_score: 39
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "file:C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\project-manager"
timestamp: 2026-10-12T17-45-01Z
slug: project-manager
---
⚠️ DEGRADED: single-context (Ian, this session: "only you for now, no other coding agents" - Assessment A recorded
before Assessment B's detector and live evidence was read, then this synthesis)

# Critique: project-manager.html as Gloria Tan (Tan Delivery Vans, no projects yet) - 2026-10-13, design lens W46006

Mode: Operate (a van-fleet supervisor opening Project Manager for the first time, with an empty portfolio). Walked through
the Playwright MCP at phone-390 and desktop-1280, signed in through the wall; every finding below was verified live.

## Design Health Score (before -> after)

| # | Heuristic | Before | After | Key issue |
|---|-----------|--------|-------|-----------|
| 1 | Visibility of System Status | 4 | 4 | the verdict states the empty portfolio plainly |
| 2 | Match System / Real World | 3 | 4 | the only worked example was a plant's ("pump overhaul ... 4 spare seals") on a van fleet's board |
| 3 | User Control and Freedom | 4 | 4 | three ways in: + New project, a template, or AI: from text |
| 4 | Consistency and Standards | 2 | 4 | cards and buttons one unit off the navy tokens, brown text on the gold button, the status chips on an old red/green/amber, `transition: all` x5 |
| 5 | Error Prevention | 4 | 4 | the wizard asks type -> template -> details before creating anything |
| 6 | Recognition Rather Than Recall | 4 | 4 | templates show their scope count and duration before they are chosen |
| 7 | Flexibility and Efficiency | 4 | 4 | AI: from text turns a sentence into a scope list |
| 8 | Aesthetic and Minimalist Design | 3 | 3 | "No projects yet" three times on one screen, each with a different first step; template cards read as cards inside a card |
| 9 | Error Recovery | 4 | 4 | nothing to recover from on an empty portfolio; reads that fail say so |
| 10 | Help and Documentation | 4 | 4 | "How this page works" disclosure |
| **Total** | | **36/40** | **39/40** | Excellent |

## Design Specificity Verdict
Written for maintenance work - work-order bundles, shutdowns, CAPEX, contractor jobs, FEL phase gates, resource
overload by worker and day. The empty state was the generic part: it repeated itself and spoke to a plant.

Deterministic scan (Assessment B): detector clean - no claim needed. Walk: 0 overlap, 0 controls under 44 px, 0
low-contrast readings, smallest text 12 px, 0 heading skips, no spill, at both widths; theme 8 of 9 regions on the tokens
after the fix - the one left is the filter select's well on the page's own deep navy (#0f1923, 3 reads).

## What's Working
- The verdict is honest about an empty portfolio and names what a project can be.
- Every door into a first project is on the first screen: + New project, the templates, AI: from text.
- The vocabulary is the platform's own: a plant supervisor and a fleet supervisor both recognise the four project types.

## Priority Issues (fixed in this walk, verified live)
- [P2] **Three "No projects yet", three different first steps, one plant example.** The verdict said it, the template
  list said it, and the next-step card said it a third time naming yet another start - with "3-day pump overhaul next
  week, 2 mechanics, 4 spare seals" as its only example on a van fleet. The next-step card now only says how to start:
  "Start from a template below ... Or describe the job in AI: from text, like "3-day pump overhaul next week, 2
  mechanics" or "brake service on 4 vans this month"". Two mentions remain: the verdict at the top and the template
  list's headline ~700 px below it, which introduces that section.
- [P2] **Red text on a red tint at ~4.1:1.** The shutdown, reactive, cancelled and phase-gate chips (0.75rem) set
  #f87171 on an 18% red wash over the card navy - under AA. They now use --wh-red-text (#FDC9C9, ~7.3:1), the platform's
  text-on-red token. Latent for Gloria (no projects yet); verified in the live stylesheet.
- [P3] **Off-token colours.** --card #1d2e44 -> --wh-navy-mid (one unit away); the gold button's #1a1208 text ->
  --wh-navy; the overlay's rgba(15,25,35) -> the navy channel; 12 status tints moved from #E15554 / #30D068 / #F4C430 onto
  --wh-red / --wh-green / --wh-amber.
- [P3] **`transition: all` on five rules** (buttons, recent chips, project cards, type tiles, template cards) now name
  the properties each hover actually moves, on the platform's ease-out curve.

## Persona Red Flags
- **Fleet supervisor**: the page cannot tell a fleet from a plant, so every example has to serve both; its templates are
  plant-shaped too (shutdown, CAPEX).

## Minor Observations
- At 1280 the "How this page works" disclosure sits mid-header rather than under the title.
- Template cards sit inside a bordered panel, inside the page card - three borders deep.
- The form fields keep the page's deep navy (#0f1923) as their well; the platform has no token for it yet.

## Questions to Consider
- Should Project Manager read the hive's type (fleet / plant) and offer fleet templates (a vehicle service campaign, a
  tyre programme, an inspection round) to a fleet?
- Should the page's deep navy (#0f1923), used as the ground and the input well on several pages, become a token?

Questions skipped: 3 Priority Issues would require them, but this is a roadmap row - Ian's standing direction is to fix and
verify what the lens finds, so the fixes are made and the two open questions travel in the report to Ian instead.
