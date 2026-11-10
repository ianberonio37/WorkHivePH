# MTBF vs MTTR for supervisors, engineers, and planners

> MTBF and MTTR explained in plain language for supervisors, engineers, planners, and contractors. Formulas, Philippine plant worked examples, and how to track with zero CMMS budget.

Source: https://workhiveph.com/learn/mtbf-vs-mttr-for-supervisors/

Reliability · Plain-English explainer

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 10 Nov 2026
·
9 min read

**Short answer:** MTBF (Mean Time Between Failures) measures how long equipment runs. It counts the time until it breaks down again. MTTR (Mean Time To Repair) measures how long it takes to fix it once it breaks. Higher MTBF and lower MTTR is the goal. Most Philippine plants track neither. That is why the same fault keeps coming back on the same equipment for years. The fix is not a CMMS purchase. It is a logbook entry per fault, recorded honestly, reviewed weekly.
 Our worked example is a cooling-tower pump motor. It sits in a Cabuyao food plant. It ran 24 hours a day, 7 days a week, for 12 months.

Who this is for

- Maintenance supervisors and planners
- Reliability and maintenance engineers
- Plant managers and asset-management teams
- Equipment suppliers tracking failure data
- Service contractors reporting fix metrics
- New reliability-engineering graduates
- Existing workers upskilling on reliability

Part of the [maintenance metrics guide: OEE, MTBF, MTTR and reliability](https://workhiveph.com/learn/maintenance-metrics-reliability-guide/). That hub links every reliability metric. It shows how they chain together.

## The two metrics, side by side

MTBF and MTTR answer two different questions about your plant. Know both numbers for each critical asset. Then you can defend a maintenance budget. Know neither, and you cannot.

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

The pump runs 24 hours a day, 7 days a week. It ran nonstop for the past 12 months, apart from the failures. During that year, it failed 8 times. There were 4 bearing failures and 2 motor winding faults. There was also 1 coupling break and 1 control panel issue.

What it means: on average, this pump runs about 45 days between failures. That is below the benchmark for a critical process pump, usually 8,000+ hours. Maybe the PM strategy is missing the failure modes. Or the asset is past its useful life.

### Counting rules that matter

- **Only count unplanned failures.** Planned PM shutdowns are not failures.
- **Use operating hours, not calendar hours,** if the equipment does not run 24/7.
- **Define "failure" consistently.** A failure is any unplanned event that stops the equipment doing its job. A minor adjustment that took 30 seconds is not a failure unless the asset stopped.
- **Calculate per asset, not per fleet.** Averaging MTBF across 12 pumps hides which one is the problem.

The free [MTBF and MTTR calculator](https://workhiveph.com/tools/mtbf-calculator/) does both figures at once. It takes operating hours, failures and total repair time. It works out Availability too. That helps. The per-asset sums above are where the fleet-average error creeps back.

## How to calculate MTTR (worked example)

The formula:

**Worked example: bottling line conveyor at a Pampanga beverage plant.**

The conveyor had 12 breakdowns in the past year. The supervisor pulled the logbook entries and added up the downtime hours recorded on each:

Drilling into the 38 hours shows the typical Philippine-plant pattern:

- Diagnosis time: 6 hr (16 percent)
- Parts retrieval: 16 hr (42 percent) ← biggest chunk
- Actual repair: 11 hr (29 percent)
- Restart and verification: 5 hr (13 percent)

The biggest MTTR fix here is not faster repair. It is having the right spare parts ready within minutes. That points to a fix in spare parts and reorder points, not in wrench time.

### Counting rules that matter

- **Repair time means total restoration time,** from stop to verified restart. Not just wrench time.
- **Include diagnosis and waiting time** (for parts, for the right skill, for permits). These are usually the biggest chunks.
- **Stop the clock when the equipment is producing again,** not when the technician signs off.
- **Calculate per asset and per fault category.** A fleet-wide MTTR helps less than a split by fault type. Electrical faults take 5 hours on average. Mechanical faults take 90 minutes.

## What MTBF tells you about your plant

MTBF is a reliability metric. A falling MTBF usually means one of three things:

1. **The asset is in its wear-out phase.** Mechanical assets follow a bathtub curve. After useful life, MTBF drops sharply. Time to plan replacement.
2. **The PM strategy is not catching the dominant failure mode.** Were 4 of 8 failures bearings? Then your PM is probably not greasing or replacing them on the right interval.
3. **Operating conditions changed.** A pump that worked fine for 5 years can still drop in MTBF. Maybe upstream pressure changed or the duty cycle rose. Or someone bypassed a protection.

A rising MTBF means your reliability investment is working. Track it monthly for each critical asset. Then you get an honest answer on whether your PM spend pays back.

## What MTTR tells you about your plant

MTTR is a response metric. A high MTTR usually means one of three things:

1. **Parts are not on the shelf.** The most common cause. Run an ABC analysis of your critical spares. Stock the items that fail most often.
2. **The right skill was not on the floor.** Say a pump motor fault waited 3 hours for an electrician to drive in from Manila. That is a gap in the skill matrix and shift cover, not in maintenance.
3. **The procedure was not documented.** Say the technician spent 90 minutes finding out how someone fixed the last failure. That is a knowledge problem, and the logbook solves it directly.

Split MTTR by category, and you usually find a pattern. Waiting takes 40 to 60 percent of total repair time, not the work itself. That is the cheapest 40 percent to cut.

The tool this guide is about

### WorkHive Analytics computes MTBF and MTTR per asset

Every fault you log in WorkHive feeds Analytics. The field that does the work is downtime hours on the entry. There is no separate stop and restart time to fill in. It sits beside the category, root cause and closing time. The first view of each day recomputes MTBF and MTTR and saves them. So the figures are never more than a day old. Nobody waits for a recalculation. One caveat to carry with you. The dashboard labels its own figure “Worst MTBF (partial)”. It divides calendar time, not operating time. That is the shortcut this page warns about, stated openly instead of hidden. For an asset that runs 24/7, the two are the same. For one that does not, treat the dashboard figure as the cautious one. No spreadsheets, no per-user CMMS (computerized maintenance management system) license. Built for Stage 1 of the 4-stage path.

No hive yet? [Join WorkHive](https://workhiveph.com/?signup=1) first (free, takes 30 seconds).

## How MTBF and MTTR combine into Availability

Engineering availability is the cleanest combined metric:

For the Cabuyao pump example: `1,091 / (1,091 + 4) = 99.6%`

That 99.6 percent looks excellent on paper. But the line that depends on this pump may still run at 50 percent OEE. The 4-hour repair always hits at the worst moment. Engineering availability does not capture criticality; it just captures up-time fraction.

This is why MTBF and MTTR alone are not enough. They feed OEE, RCM analysis and PM strategy. RCM means reliability-centered maintenance. Use them as inputs, not as the final scorecard.

## Tracking both with zero CMMS budget

You do not need to buy SAP PM, IBM Maximo, or any paid CMMS to track MTBF and MTTR. You need a digital logbook that captures three things per fault:

1. **How long the asset was down**, in hours. Two times, stopped and producing again, are the strictest way to get this. They cannot drift the way a remembered number does. One downtime-hours field filled in at the close is the practical way. It is what WorkHive’s logbook asks for.
2. **When the job closed**. Then the entries fall into a period without anyone typing dates again.
3. **Fault category** from a controlled list (mechanical, electrical, instrumentation, process, safety).

That is it. Once a month, the supervisor exports the logbook and filters by asset. Then they work out both metrics for the top 10 critical assets. 30 minutes per month. No software bill.

This is what the [digital logbook rollout playbook](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/) teaches at Step 2. That covers weeks 2 to 4: one entry per shift. The discipline that makes the logbook work is the same discipline that makes MTBF and MTTR meaningful.

## Common Philippine plant mistakes

- **Reporting an MTBF without saying which assets it covers.** "Our MTBF is 1,200 hours" is meaningless. "Our 8 critical process pumps had MTBF 1,200 hours last quarter" is useful.
- **Counting only "official" breakdowns.** Say an operator cleared a 15-minute jam without calling maintenance. For MTBF, that still counts as a failure. Hiding small faults inflates MTBF artificially.
- **Including PM downtime in MTTR.** Planned PM is not a repair. Say you took a pump offline for 6 hours to replace a bearing on schedule. That should not count as a 6-hour MTTR event.
- **Calculating MTBF over too short a window.** If an asset failed twice in the past month, your "MTBF" is statistical noise. Use a rolling 12-month window for stable assets. Use a rolling 3-month window for assets that fail often.
- **Treating MTBF and MTTR as the goal.** They are diagnostic, not strategic. Raising MTBF on a minor asset wastes effort if you ignore the bottleneck pump. That pump drives OEE.

**The bigger picture:** MTBF tells you if the asset itself is good. MTTR tells you if your response is good. OEE tells you if the operation is good. All three feed each other. Without the logbook discipline at the bottom of the stack, none of them work.

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

Good MTTR is asset and plant specific, and unlike OEE or PM compliance there is no published cross-industry benchmark to measure yourself against, so the number that matters is your own trend and its composition. The breakdown above is the useful target: when parts retrieval is 42 percent of your repair time, the fix is the store, not the technician. A plant without a disciplined store and a clear procedure typically sits between 3 and 8 hours. The biggest MTTR drivers are spare parts availability (40 percent of MTTR is usually waiting for the part), skill coverage (the right person being on shift), and procedure clarity. Logbook entries with photos cut MTTR faster than any other intervention.

### How are MTBF and MTTR used in availability?

Equipment availability equals MTBF divided by the sum of MTBF and MTTR. Taking the worked example above: a pump with MTBF 1,091 operating hours and MTTR 4 hours has availability of 1,091 divided by 1,095, or 99.6 percent. Use operating hours in that numerator, not calendar hours: subtracting the downtime is what makes it an ISO 14224 MTBF rather than an approximation of one. This is the engineering availability used in reliability calculations and is different from operational availability used in OEE.

### Do I need a CMMS to track MTBF and MTTR?

No. A digital logbook with structured fault entries (asset name, fault time, restart time, fault category) is enough. The supervisor can calculate MTBF and MTTR per asset monthly from the logbook export. CMMS adds value at scale (more than 200 assets) but it does not change the math. The discipline of recording the fault accurately is what matters, not the software.

## Sources

- ISO 14224:2016, **Petroleum, petrochemical and natural gas industries: Collection and exchange of reliability and maintenance data for equipment**. The international standard for MTBF/MTTR data definitions and failure categorization.
- IEC 60050-192, **International Electrotechnical Vocabulary: Dependability**. The formal definitions of reliability, availability, MTBF, and MTTR used across industry.
- Society for Maintenance and Reliability Professionals (SMRP), **Best Practices, 5th Edition**, 2017. North American KPI (key performance indicator) library and benchmark ranges.
- WorkHive platform positioning, "Four Gaps One Hive": Execution, Skills, Intelligence, Marketplace. [workhiveph.com](https://workhiveph.com/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: c76b3ce72160c84f -->
