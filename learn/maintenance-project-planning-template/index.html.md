# Maintenance project planning (free template for Philippine plants)

> A free maintenance project planning template for Philippine plants: scope, schedule, resources, risk, cost, and the 6 reasons turnarounds blow over budget. Built for engineers, supervisors, and contractors.

Source: https://workhiveph.com/learn/maintenance-project-planning-template/

Project Manager · Template + 6-step playbook

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 24 Aug 2026
·
9 min read

**Short answer:** A maintenance project (turnaround, shutdown, capex install) needs 6 things: a frozen scope 90 days out, a schedule with critical path, resources matched to skill matrix, identified risks with named owners, costs allocated to the asset (not just to the project code), and disciplined daily standups plus handback. The 6 reasons Philippine plant projects blow over budget are scope creep, discovery work, contractor delays, late parts, safety stand-downs, and weather. Each has a documented mitigation in this template.

Who this is for

- Maintenance project engineers
- Plant and reliability managers
- Shutdown and turnaround leads
- Planners and schedulers
- Project contractors and sub-contractors
- Equipment and parts suppliers
- New engineering graduates joining projects

Part of the [guide to starting digital maintenance in a Philippine factory](https://workhiveph.com/learn/start-digital-maintenance-guide/): the four-step, zero-budget rollout this article is one step of.

## Maintenance project versus routine PM

|  | Routine PM | Maintenance project |
| --- | --- | --- |
| Scope | One job, one asset | Many jobs, often many assets |
| Duration | Under a shift | Days to weeks |
| People | 1 to 2 technicians | Multiple in-house teams + contractors |
| Tool | PM Scheduler + checklist | Project Manager + Gantt + standups |
| Coordination need | Low | High |
| Risk | Bounded | Cascading: one job delay shifts the rest |

The most common Philippine plant mistake is treating a 2-week turnaround as a long list of PMs. PMs do not have critical-path dependencies, do not need contractor coordination, and do not need handback. Projects have all three. Use the right tool for the work.

## The 6 reasons projects blow over budget

Across Philippine plants we have benchmarked, these 6 causes account for 80 percent of budget overruns on maintenance projects:

1. **Scope creep after freeze.** Production adds a "while you have it open" job 2 weeks before the project. The 30-minute add takes 6 hours and shifts the critical path. Hard freeze at 90 days is the rule; only true emergencies add after that, and every emergency add gets a documented justification.
2. **Discovery work.** The team opens an asset and finds worse damage than expected (corrosion under insulation, cracked housing, contaminated oil, undocumented modifications). Plan 15 to 20 percent contingency time and budget for discovery. Plants that plan zero contingency are surprised every time.
3. **Contractor delays.** The third-party crew arrives 2 days late, or arrives with fewer people than contracted, or arrives without the right tools. Mitigation: contractual penalties, pre-arrival kit verification, backup contractor on call.
4. **Late parts.** Imported parts have 60 to 120-day lead times. A single late delivery on a critical-path job extends the whole project. Order long-lead-time parts 120 days out; have backup suppliers identified for everything Tier 1 critical.
5. **Safety incidents triggering stand-down.** A near-miss or actual incident triggers DOLE-required investigation and a plant-wide safety pause. Plan that this will happen approximately once per major project; build a 1-day stand-down into the contingency budget.
6. **Weather.** The Philippine rainy season (June to October) affects outdoor work, scaffolding, hot work, and crane lifts. Schedule weather-sensitive work for early shifts; have indoor-only fallback jobs ready for rain days.

## The 6-step project planning workflow

### Step 1: Freeze the scope 90 days out

One workshop with production, maintenance, engineering, and plant manager. Every proposed job goes on the wall. Each job gets a written justification, an asset reference (from Asset Hub), and an estimated duration. Plant manager signs the frozen scope. After the freeze, only documented emergencies add.

### Step 2: Build the schedule with critical path

Sequence every job. Identify dependencies (you cannot reassemble before alignment; you cannot align before bearing install; you cannot bearing install before bearing arrival). The longest dependency chain is the critical path. Total project duration equals critical path duration; non-critical jobs have slack.

Compression options:

- Parallelise non-dependent work (two crews on different assets simultaneously)
- Pre-fabricate off-line (assemble the spare pump skid before the outage starts)
- Add shifts (24-hour coverage on the longest critical-path jobs)
- Add resources (split a 3-day crew of 2 into 2 days of 3 if the work is parallelisable)

### Step 3: Allocate resources by skill matrix

Match every job to the people and equipment needed. Cross-check against the Skill Matrix to confirm Level 3+ coverage on every critical-path job on every shift. Surface single-point-of-failure people (only one technician can do X) and pre-arrange backup or train a second.

### Step 4: Identify risks and assign mitigations

Top-10 risk workshop with the project team. Each risk gets:

- Probability (Low / Medium / High)
- Impact (cost or schedule)
- Named owner
- Documented mitigation
- Trigger condition for activating the mitigation

### Step 5: Cost the project to the asset, not the project code

Every peso spent gets allocated to the asset that benefited (rebuild cost on Pump P-101A, not "Turnaround 2026 Q3"). This feeds total cost of ownership per asset in Asset Hub. Three years later when you decide replace versus refurbish, you have the data. Plants that lump everything under one project code lose this forever.

### Step 6: Execute with daily standups and handback discipline

15-minute daily standup at start of shift. Standing agenda: yesterday completed, today planned, blockers, risk status. Contractors attend alongside in-house leads.

Per-asset handback: PM schedule updated, Logbook entry of the work, parts consumed, photos in Asset Hub, supervisor and operations sign-off. No asset returns to operations until handback complete.

The tool this guide is about

#### WorkHive Project Manager runs the 6 steps end to end

Project Manager has scope freeze tracking, critical-path Gantt, skill-matrix resource matching, risk register with named owners, per-asset cost allocation that feeds Asset Hub, daily standup template, and per-asset handback checklist. Contractors get scoped access to their assigned jobs. Suppliers see only their consumed parts. Free at the worker tier; SAP PS / Maximo Projects financial integration unlocks at Stage 2.

No hive yet? [Join WorkHive](https://workhiveph.com/?signup=1) first (free, takes 30 seconds).

## Critical path explained for plant projects

Critical path is the longest dependency chain through your schedule. Its duration sets the minimum total project duration. Example for a pump overhaul:

The leverage: if Jobs D, E, or F slip 4 hours, the project finishes 4 hours late. If Job H slips, nobody cares. Knowing this directs the supervisor's attention. Plants without explicit critical path treat every job equally and miss the leverage.

## Coordinating multiple contractors

Most major projects in Philippine plants involve 3 to 8 contractor crews working in parallel: mechanical, electrical, instrumentation, scaffolding, insulation, painting, lifting, civil. Without explicit coordination, they trip over each other: scaffolding crew leaves before electrical needs to access, insulation goes back before instrumentation has had time to check.

Three rules that work:

1. **Single coordinator owns the master schedule.** Contractors do not negotiate schedule with each other; they negotiate through the coordinator. The coordinator is usually a senior planner or project engineer, not a contractor.
2. **Scoped WorkHive access per contractor.** Each contractor sees only their assigned jobs and the assets they touch. No broad plant access. Status updates are logged in WorkHive Project Manager, not in WhatsApp groups.
3. **Daily standup includes contractor leads.** Same 15-minute meeting, same agenda. Blockers surface immediately. Email handoffs and side-chat coordination kill projects.

## Coexistence with SAP PS and Maximo Projects

WorkHive Project Manager does not replace SAP PS (Project System) or Maximo Project Management. Those handle the financial side:

- WBS structure for finance reporting
- Cost allocation to project codes and assets
- Vendor PO tracking and invoice matching
- Capitalisation rules and depreciation triggers

WorkHive Project Manager handles the operations side:

- Who does what when (Gantt + standups)
- Parts staged at the asset by the supervisor
- Contractor check-in and time on site
- Handback checklist per asset
- Logbook entries linked to the project

The two integrate via the [WorkHive CMMS Integration connector](https://workhiveph.com/learn/connecting-workhive-to-sap-maximo-cmms/): financial milestones flow to SAP, operational completion flows to WorkHive. Plants that use both well treat them as complementary; plants that try to make either do both end up with one half-used system.

## Handback discipline: where most projects end badly

The pattern that ruins post-project credibility: the project hits its deadline, the assets restart, production celebrates, and 3 weeks later operations is still asking maintenance for the updated drawings, the new PM schedules, the as-built photos. The work happened; the documentation did not.

Handback discipline closes this gap. For every asset touched by the project, before it returns to operations:

- Asset Hub record updated with any spec changes
- PM schedule reviewed and any frequency changes captured
- Logbook entry of the work done with technician name
- Parts consumed entered in Inventory
- As-built photos attached
- Supervisor signs the handback; operations signs receipt

No signature, no handback. No handback, the asset stays project-owned and the project does not close.

**The bigger picture:** A maintenance project is not a longer PM; it is a different discipline. Scope freeze, critical path, risk register, contractor coordination, per-asset costing, and handback are the differences between a project that lands on time and budget and one that becomes a cautionary tale. WorkHive Project Manager makes the discipline cheap to apply; the discipline itself is on you.

## Frequently asked questions

### What is a maintenance project versus a routine PM?

A routine PM is a single recurring job (lubricate this motor, change this filter) done on schedule by one or two technicians in under a shift. A maintenance project is a multi-job initiative with a defined start and end (a plant turnaround, a line shutdown for overhaul, a capex install) involving multiple teams, often including contractors and suppliers, with coordination across days or weeks. Projects need formal planning; PMs need checklists. Mixing them up is a common Philippine plant mistake that leaves projects under-planned and PMs over-planned.

### Why do most plant turnarounds blow over budget?

Six reasons in order of frequency: (1) scope creep after the planned freeze date adds work without adding time or budget; (2) discovery work when the team opens an asset and finds worse damage than expected; (3) contractor delays from undermanaged subcontractors; (4) parts arriving late from international suppliers; (5) safety incidents triggering stand-downs; (6) weather affecting outdoor work in the Philippine rainy season. Plants that plan with explicit contingency for all six come closer to budget; plants that hope for the best blow through 30 to 60 percent over.

### How far in advance should I start planning a turnaround?

Minimum 90 days for a 1-week turnaround on a typical Philippine production line; 180 days for a 2 to 3-week major turnaround with significant capex work. The longer lead time is needed because: imported parts have 60 to 120-day lead times, contractor crews need to be booked, your own skill matrix gaps need training time to close, and permit-to-work paperwork with DOLE for high-risk work needs filing. Plants that try to plan a major turnaround in 30 days usually have to compress scope mid-project.

### How do I coordinate multiple contractors during a project?

Three rules: (1) Single coordinator owns the master schedule; contractors do not negotiate schedule with each other directly. (2) Every contractor gets scoped WorkHive access showing only their assigned jobs and the assets they touch; no broad plant access. (3) Daily standup includes contractor leads alongside in-house supervisors so blockers surface in the same forum. Plants that try to coordinate contractors by email or WhatsApp lose the audit trail and get blame games when something slips.

### What is critical path and why does it matter?

The critical path is the longest dependency chain through your project schedule; its total duration sets the minimum project duration. A delay on any critical-path job delays the whole project. A delay on a non-critical-path job has slack and may not affect the end date. Identifying the critical path tells you where to focus your best people, your morning standup attention, and your contingency parts. Most Philippine plants do not formally compute critical path; they plan as a list and miss the leverage.

### How does WorkHive Project Manager fit with SAP or Maximo project modules?

SAP PS (Project System) and Maximo Project Management handle the financial side: WBS structure, cost allocation, vendor PO tracking, capitalisation. WorkHive Project Manager handles the operations side: who does what when, daily standups, parts staged at the asset, contractor check-in, handback per asset. The two integrate via the CMMS Integration connector so financial milestones flow to SAP and operational completion flows to WorkHive. Most plants use both; few use both well.

## Sources

- Project Management Institute (PMI), **PMBOK Guide, 7th Edition**. Source for the project planning workflow adapted here for plant maintenance.
- Society for Maintenance and Reliability Professionals (SMRP), **Best Practices, 5th Edition**, 2017. Source for turnaround / shutdown planning benchmarks.
- Department of Labor and Employment (DOLE), **Occupational Safety and Health Standards (OSHS) Rules 1010 and 1040** on hazardous workplace requirements and OSH committee. Source for safety planning in projects.
- WorkHive platform positioning, "Four Gaps One Hive" with Project Manager as the Execution accelerator. [workhiveph.com](https://workhiveph.com/)
- Related WorkHive guides: [CMMS Integration](https://workhiveph.com/learn/connecting-workhive-to-sap-maximo-cmms/) · [Skill matrix](https://workhiveph.com/learn/skill-matrix-for-maintenance-technicians/) · [Asset register](https://workhiveph.com/learn/building-asset-register-zero-budget/) · [Spare parts inventory](https://workhiveph.com/learn/spare-parts-inventory-philippine-plants/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: 6ab031bd5258c698 -->
