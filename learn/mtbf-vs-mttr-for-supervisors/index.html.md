# MTBF vs MTTR for supervisors, engineers, and planners

> MTBF and MTTR explained in plain language for supervisors, engineers, planners, and contractors. Formulas, Philippine plant worked examples, and how to track with zero CMMS budget.

Source: https://workhiveph.com/learn/mtbf-vs-mttr-for-supervisors/

Reliability · Plain-English explainer

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 17 May 2026
·
9 min read

**Short answer:** MTBF (Mean Time Between Failures) measures how long equipment runs before the next breakdown. MTTR (Mean Time To Repair) measures how long it takes to fix it once it breaks. Higher MTBF and lower MTTR is the goal. Most Philippine plants do not track either, which is why the same fault keeps recurring on the same equipment for years. The fix is not a CMMS purchase. It is a logbook entry per fault, recorded honestly, reviewed weekly.
 The worked example below uses a cooling-tower pump motor at a Cabuyao food plant running **24 hours a day, 7 days a week** over **12 months**.

Who this is for

- Maintenance supervisors and planners
- Reliability and maintenance engineers
- Plant managers and asset-management teams
- Equipment suppliers tracking failure data
- Service contractors reporting fix metrics
- New reliability-engineering graduates
- Existing workers upskilling on reliability

Part of the [maintenance metrics guide: OEE, MTBF, MTTR and reliability](https://workhiveph.com/learn/maintenance-metrics-reliability-guide/) — the hub that connects every reliability metric and shows how they chain together.

## The two metrics, side by side

MTBF and MTTR answer two different questions about your plant. A supervisor who knows both numbers per critical asset can defend a maintenance budget; one who knows neither cannot.

|  | MTBF | MTTR |
| --- | --- | --- |
| **Question it answers** | How reliable is the equipment? | How fast do we recover when it fails? |
| **Driven by** | Design quality, PM discipline, operating conditions | Spare parts availability, skill coverage, procedure clarity |
| **Goal direction** | Higher is better | Lower is better |
| **Who improves it** | Reliability engineer + PM planner | Maintenance supervisor + storeroom + skill matrix |
| **Unit** | Hours (or operating hours) | Hours (per repair) |

Both come from the same source: the fault entries in your logbook. If you have no logbook, you have no MTBF and no MTTR.

## How to calculate MTBF (worked example)

The formula:

**Worked example: cooling tower pump motor at a Cabuyao food plant.**

The pump runs 24 hours a day, 7 days a week. It ran continuously for the past 12 months except during failure events. During that year, it failed 8 times: 4 bearing failures, 2 motor winding faults, 1 coupling break, and 1 control panel issue.

Interpretation: on average, this pump runs about 45 days before the next failure. That is below the benchmark for a critical process pump (usually 8,000+ hours), which means either the PM strategy is not catching the failure modes or the asset is past its useful life.

### Counting rules that matter

- **Only count unplanned failures.** Planned PM shutdowns are not failures.
- **Use operating hours, not calendar hours,** if the equipment does not run 24/7.
- **Define "failure" consistently.** A failure is any unplanned event that stops the equipment from performing its intended function. A minor adjustment that took 30 seconds is not a failure unless the asset stopped.
- **Calculate per asset, not per fleet.** Averaging MTBF across 12 pumps hides which one is the problem.

## How to calculate MTTR (worked example)

The formula:

**Worked example: bottling line conveyor at a Pampanga beverage plant.**

The conveyor had 12 breakdowns in the past year. The supervisor pulled the logbook entries with start and restart timestamps:

Drilling into the 38 hours shows the typical Philippine-plant pattern:

- Diagnosis time: 6 hr (16 percent)
- Parts retrieval: 16 hr (42 percent) ← biggest chunk
- Actual repair: 11 hr (29 percent)
- Restart and verification: 5 hr (13 percent)

The biggest MTTR fix here is not faster repair; it is making the right spare parts available within minutes. That points to a spare-parts inventory and reorder-point fix, not a wrench-time fix.

### Counting rules that matter

- **Repair time means total restoration time,** from stop to verified restart. Not just wrench time.
- **Include diagnosis and waiting time** (for parts, for the right skill, for permits). These are usually the biggest chunks.
- **Stop the clock when the equipment is producing again,** not when the technician signs off.
- **Calculate per asset and per fault category.** "Electrical faults take 5 hours on average; mechanical faults take 90 minutes" is more useful than a fleet-wide MTTR.

## What MTBF tells you about your plant

MTBF is a reliability metric. A falling MTBF usually means one of three things:

1. **The asset is in its wear-out phase.** Mechanical assets follow a bathtub curve. After useful life, MTBF drops sharply. Time to plan replacement.
2. **The PM strategy is not catching the dominant failure mode.** If 4 of 8 failures were bearing failures, your PM is probably not lubricating or replacing bearings on the right interval.
3. **Operating conditions changed.** A pump that worked fine for 5 years can drop MTBF if upstream pressure changed, the duty cycle increased, or someone bypassed a protection.

A rising MTBF means your reliability investment is working. Track it monthly per critical asset and you get an honest answer to "is what I am spending on PM actually paying back?"

## What MTTR tells you about your plant

MTTR is a response metric. A high MTTR usually means one of three things:

1. **Parts are not on the shelf.** The most common cause. Run an ABC analysis of your critical-asset spares and stock the items with high failure frequency.
2. **The right skill was not on the floor.** A pump motor electrical fault that waited 3 hours for an electrician to drive in from Manila is a skill matrix and shift-coverage gap, not a maintenance gap.
3. **The procedure was not documented.** If the technician spent 90 minutes finding out how the previous failure was fixed, that is a knowledge management problem the logbook directly solves.

MTTR breakdowns by category usually reveal that 40 to 60 percent of total repair time is waiting time, not work time. That is the cheapest 40 percent to cut.

The tool this guide is about

#### WorkHive Analytics computes MTBF and MTTR per asset

Every fault entry in the WorkHive Logbook (stop timestamp, restart timestamp, fault category, resolution notes) flows into the Analytics reliability dashboard. MTBF and MTTR are recomputed monthly per critical asset. No spreadsheets, no per-user CMMS license. Built for Stage 1 of the 4-stage path.

No hive yet? [Join WorkHive](https://workhiveph.com/#join) first (free, takes 30 seconds).

## How MTBF and MTTR combine into Availability

Engineering availability is the cleanest combined metric:

For the Cabuyao pump example: `1,091 / (1,091 + 4) = 99.6%`

That 99.6 percent looks excellent on paper, but the OEE on the production line that depends on this pump may still be 50 percent because the 4-hour repair always hits at the worst possible moment. Engineering availability does not capture criticality; it just captures up-time fraction.

This is why MTBF and MTTR alone are not enough. They feed into OEE, RCM analysis, and PM strategy decisions. Use them as inputs, not as the final scorecard.

## Tracking both with zero CMMS budget

You do not need to buy SAP PM, IBM Maximo, or any paid CMMS to track MTBF and MTTR. You need a digital logbook with three structured fields per fault:

1. **Fault start timestamp** (server-side, not editable).
2. **Restart timestamp** when the asset was producing again.
3. **Fault category** from a controlled list (mechanical, electrical, instrumentation, process, safety).

That is it. Once a month, the supervisor exports the logbook, filters by asset, and calculates both metrics for the top 10 critical assets. 30 minutes per month. No software bill.

This is exactly what the [digital logbook rollout playbook](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/) teaches at Step 2 (Weeks 2 to 4: one entry per shift). The discipline that makes the logbook work is the same discipline that makes MTBF and MTTR meaningful.

## Common Philippine plant mistakes

- **Reporting an MTBF without saying which assets were included.** "Our MTBF is 1,200 hours" is meaningless. "Our 8 critical process pumps had MTBF 1,200 hours last quarter" is useful.
- **Counting only "official" breakdowns.** A 15-minute jam that the operator cleared without calling maintenance is still a failure for MTBF purposes. Hiding small faults inflates MTBF artificially.
- **Including PM downtime in MTTR.** Planned PM is not a repair. A pump that was taken offline for 6 hours of scheduled bearing replacement should not show up as a 6-hour MTTR event.
- **Calculating MTBF over too short a window.** If an asset failed twice in the past month, your "MTBF" is statistical noise. Use rolling 12-month windows for stable assets and rolling 3-month windows for assets that fail often.
- **Treating MTBF and MTTR as the goal.** They are diagnostic, not strategic. Improving MTBF on a non-critical asset while ignoring the bottleneck pump that drives OEE is wasted effort.

**The bigger picture:** MTBF tells you "is the asset itself good?" MTTR tells you "is the response system good?" OEE tells you "is the operation good?" All three feed each other. Without the logbook discipline at the bottom of the stack, none of them work.

## Frequently asked questions

### What is the difference between MTBF and MTTR?

MTBF (Mean Time Between Failures) measures how long equipment runs before the next breakdown. MTTR (Mean Time To Repair) measures how long it takes to fix the equipment once it breaks. MTBF is a reliability metric driven by design quality and PM discipline. MTTR is a response metric driven by spare parts availability, skill coverage, and procedure clarity. Higher MTBF and lower MTTR is the goal.

### How do I calculate MTBF?

MTBF equals total operating time divided by number of failures during that period. Example: a motor that ran 8,760 hours in a year and failed 8 times has an MTBF of 8,760 divided by 8 equals 1,095 hours. Only count unplanned failures, not planned PM shutdowns. Only count operating hours, not calendar hours.

### How do I calculate MTTR?

MTTR equals total repair time divided by number of repairs. Repair time means from the moment the equipment stopped to the moment it was producing again, including diagnosis, parts retrieval, repair, and restart. Example: a conveyor that had 12 breakdowns last year with a combined 38 hours of downtime has an MTTR of 38 divided by 12 equals 3.17 hours.

### What is a good MTBF value?

MTBF benchmarks depend heavily on equipment type. A critical pump motor in a process plant should show MTBF above 8,000 hours (roughly one failure per year). A bottling conveyor might be 2,000 to 4,000 hours. The number matters less than the trend. If your MTBF is dropping month over month, the asset is degrading or your PM is slipping. If it is rising, your reliability investment is working.

### What is a good MTTR value?

Good MTTR is asset and plant specific but world-class is generally under 2 hours for critical line equipment. Most Philippine plants we benchmark sit between 3 and 8 hours. The biggest MTTR drivers are spare parts availability (40 percent of MTTR is usually waiting for the part), skill coverage (the right person being on shift), and procedure clarity. Logbook entries with photos cut MTTR faster than any other intervention.

### How are MTBF and MTTR used in availability?

Equipment availability equals MTBF divided by the sum of MTBF and MTTR. A pump with MTBF 1,095 hours and MTTR 4 hours has availability of 1,095 divided by 1,099 equals 99.6 percent. This is the engineering availability used in reliability calculations and is different from operational availability used in OEE.

### Do I need a CMMS to track MTBF and MTTR?

No. A digital logbook with structured fault entries (asset name, fault time, restart time, fault category) is enough. The supervisor can calculate MTBF and MTTR per asset monthly from the logbook export. CMMS adds value at scale (more than 200 assets) but it does not change the math. The discipline of recording the fault accurately is what matters, not the software.

## Sources

- ISO 14224:2016, **Petroleum, petrochemical and natural gas industries: Collection and exchange of reliability and maintenance data for equipment**. The international standard for MTBF/MTTR data definitions and failure categorization.
- IEC 60050-192, **International Electrotechnical Vocabulary: Dependability**. The formal definitions of reliability, availability, MTBF, and MTTR used across industry.
- Society for Maintenance and Reliability Professionals (SMRP), **Best Practices, 5th Edition**, 2017. North American KPI library and benchmark ranges.
- WorkHive platform positioning, "Four Gaps One Hive": Execution, Skills, Intelligence, Marketplace. [workhiveph.com](https://workhiveph.com/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: 1f6b96e774f2773f -->
