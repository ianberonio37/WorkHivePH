---
target: project-report.html
total_score: 39
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 1
target_identity: "file:C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\project-report"
timestamp: 2026-10-12T17-57-22Z
slug: project-report
---
⚠️ DEGRADED: single-context (Ian, this session: "only you for now, no other coding agents" - Assessment A recorded
before Assessment B's detector and live evidence was read, then this synthesis)

# Critique: project-report.html as David Velasco (a worker at Lucena Pharmaceutical Mfg., not a supervisor) - 2026-10-13, design lens W46013

Mode: Read (a printable project report a worker opens to see where a job stands, or to hand to someone). Walked through
the Playwright MCP at phone-390 and desktop-1280, signed in through the wall: the chooser state (no project named) and
SHD-2026-001's report. Every finding below was verified live.

## Design Health Score (before -> after)

| # | Heuristic | Before | After | Key issue |
|---|-----------|--------|-------|-----------|
| 1 | Visibility of System Status | 2 | 4 | a project twelve weeks past its planned finish read "52% complete with 4 scope items remaining" - the schedule was only computed inside the budget block a worker never sees; and the chooser's four disabled buttons were drawn as live |
| 2 | Match System / Real World | 3 | 4 | "No project specified" (an error's words for a choice); "% complete" on six log rows (0, 40, 20, 60, 100, 80) beside a computed 52% |
| 3 | User Control and Freedom | 4 | 4 | recent projects one tap away; Back, the breadcrumb and "Project Manager" all lead out |
| 4 | Consistency and Standards | 2 | 4 | two gold primaries side by side (Print with an inline gradient, Save as PDF flat); toolbar one unit off the navy tokens; the hero card's 4px side stripe over a gradient |
| 5 | Error Prevention | 4 | 4 | with nothing loaded, Print / PDF / CSV / AI are disabled rather than producing an empty document |
| 6 | Recognition Rather Than Recall | 4 | 4 | each recent project shows its code, name and status |
| 7 | Flexibility and Efficiency | 3 | 3 | the chooser offers the eight most recent projects only; anything older means a trip to Project Manager |
| 8 | Aesthetic and Minimalist Design | 3 | 4 | at 390 the chooser's statuses broke into their own column ("·" over "active", beside the wrong half of the name) |
| 9 | Error Recovery | 4 | 4 | a failed read says the list is not loaded, never that the hive has no projects |
| 10 | Help and Documentation | 4 | 4 | "How to read this report" and a standards appendix (PMBOK, AACE 17R-97 / 80R-13, IDCON, ISO 21500) |
| **Total** | | **33/40** | **39/40** | Excellent |

## Design Specificity Verdict
A real engineering document: WBS by phase with owners and hours, linked work orders, logbook entries, PM completions and
parts, a daily progress timeline with blockers, a sign-off block, and a CPI it refuses to print because a labour-only
cost would overstate it twenty-fold. The defects were in what it said to a reader without the budget, and in its empty
state.

Deterministic scan (Assessment B): detector clean - no claim needed (a direct run flags the cover's 3px title rule as a
"side-tab"; it is a document heading's underline, and the bank's reading counts it 0). Walk on the loaded report: 0
overlap, 0 controls under 44 px, 0 low-contrast readings (213 sampled), smallest text 12 px, 0 heading skips, 0 nested
cards, no spill, at both widths; off-grid spacings 30 -> 12 (what remains is 1px tag padding and the screen-reader clip);
big numerals 3 -> 0 non-tabular. The theme's 16 "off" reads are the sheet's paper inks (ink #1F2A37, rule #D7DDE5, accent
#0E5E8A) - a printed document on white, deliberately not the screen's navy tokens.

## What's Working
- The report is honest about what it cannot know: no CPI, and the reason printed beside the absence.
- A failed project read and an empty hive are different sentences.
- Done scope items are struck through in the sheet's muted ink (~5.7:1), still readable.

## Priority Issues (fixed in this walk, verified live)
- [P1] **The budget gate hid the schedule.** SPI and "Behind schedule" were computed only inside the budget block, and the
  budget is shown to supervisors only - so David's report on SHD-2026-001 (planned Jul 17-22, four items still open on
  13 October) never mentioned the date. Schedule performance needs no money (SPI = EV/PV, and the budget cancels), so it
  is now computed for every reader: the hero reads "SHD-2026-001 is 52% complete and past its planned finish of Jul 22,
  2026: 4 scope items still open", and a schedule strip shows SPI 0.52, "Behind schedule - from the dates and progress,
  no budget used". Before a project's start date there is no SPI (the old block printed 0.00 "Behind schedule" for a
  project starting next week); the supervisor's block follows the same rule. The past-finish test uses Manila's calendar.
- [P2] **Disabled, but drawn as live.** In the chooser state AI: Narrative, Print, Save as PDF and CSV were disabled and
  rendered at full opacity, full gold, pointer cursor. Now 0.45 opacity and a not-allowed cursor; hover does not light
  them.
- [P2] **The chooser broke at 390.** Each link was inline-flex, so the name and the status span were two flex items: the
  space collapsed ("Overhaul· active") and at 390 the status became its own column. One inner span keeps each link a
  single run of text; the list reads upright and left-aligned under "Or choose one of your hive's recent projects"; the
  status is the sheet's muted ink (at opacity .7 the link blue measured ~3.6:1) and in words ("on hold", not "on_hold").
- [P2] **"% complete" twice, disagreeing.** The timeline column is now "% reported", with one line above the table: each
  row's percentage is that reporter's own estimate; the project's progress in §1 is computed from its scope items.
- [P3] **Two primaries.** Print carried an inline gradient-gold style beside Save as PDF's flat gold; both open the print
  dialog. Save as PDF (which also names the file) keeps the one amber; Print is the secondary.
- [P3] **The hero card's 4px side stripe over a gradient** - now a 1px border on a flat warm fill, as analytics-report's
  insight cards already are.
- [P3] **Off-token toolbar**: #1d2e44 -> --wh-navy-mid, #1a1208 -> --wh-navy, the bar on --wh-navy's channel. Title "No
  project specified" -> "Choose a project". KPI figures in tabular numerals; KPI, table and sign-off spacing on the 4px
  rhythm. The source line now sits under the sheet instead of at the viewport's left edge.
- [P3] **The PDF's date was UTC's.** Save as PDF named the file with toISOString(), so a report saved before 08:00 PHT
  was dated the day before; it now uses Manila's date, and the tab gets its own title back after the print dialog.

## Persona Red Flags
- **Worker without the budget**: until now, the only schedule judgement on the page sat behind the supervisor-only
  figures; a worker could not see that the job was late without reading every due date.

## Minor Observations
- The chooser shows eight recent projects; older ones need Project Manager.
- "How this page works" sits inside the white sheet, between the title and the cover facts.

## Questions to Consider
- Should the chooser search all of the hive's projects (by code or name) instead of listing the eight most recent?
- Should a project past its planned finish change its status pill ("active" -> "overdue") on every surface, not only in
  this report's sentence?

Questions skipped: 3 Priority Issues would require them, but this is a roadmap row - Ian's standing direction is to fix and
verify what the lens finds, so the fixes are made and the two open questions travel in the report to Ian instead.
