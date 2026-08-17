# What is OEE and how do I calculate it? (worked Philippine factory example)

> OEE explained in plain language with a worked Philippine factory example. Formula, benchmarks, the 6 big losses, and how to start tracking without expensive sensors.

Source: https://workhiveph.com/learn/what-is-oee-how-to-calculate/

OEE · Worked example

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 17 Aug 2026
·
10 min read

**Short answer:** Overall Equipment Effectiveness (OEE) measures three things in one number: how often equipment runs, how fast it produces, and how much of what it produces is good. The formula is `OEE = Availability × Performance × Quality`. World-class is 85 percent or higher. Most Philippine plants score 40 to 60 percent on first measurement. The number matters less than what you do with it: catch losses you could not see before, prioritize the right fix, and turn maintenance from a cost center into a measurable contribution.

Who this is for

- Production supervisors and line leaders
- Maintenance and reliability engineers
- Plant managers and operations directors
- Continuous improvement and Lean teams
- Equipment suppliers benchmarking performance
- New industrial-engineering graduates
- Workers upskilling on manufacturing KPIs

Part of the [maintenance metrics guide: OEE, MTBF, MTTR and reliability](https://workhiveph.com/learn/maintenance-metrics-reliability-guide/) — the hub that connects every reliability metric and shows how they chain together.

## What OEE actually measures

OEE was developed by Seiichi Nakajima in Japan in the 1960s as the headline metric for Total Productive Maintenance (TPM). It survives 60 years later because it is the only metric that answers all three questions a plant manager actually cares about, in one number:

- **How often did the equipment run when we wanted it to?** (Availability)
- **How fast did it run when it was running?** (Performance)
- **How much of what it made was actually saleable?** (Quality)

Any one of these alone is misleading. A line that ran for 8 hours straight but produced nothing usable has 100 percent availability and 0 percent OEE. A line that ran fast and quality was perfect but only operated 3 hours of an 8-hour shift hides the same problem. OEE multiplies all three together because losing one component cancels out gains in the others.

## The OEE formula in plain language

The formula is:

Where:

- `Availability = Run Time / Planned Production Time`
- `Performance = (Actual Run Rate) / (Ideal Run Rate)` or equivalently `(Total Units Produced × Ideal Cycle Time) / Run Time`
- `Quality = Good Units / Total Units Produced`

Each component is a fraction between 0 and 1. Multiply them together to get OEE as a fraction; multiply by 100 to express as a percentage.

Notice the formula multiplies, it does not average. This matters because OEE is honest: if Availability is 90 percent and Performance is 90 percent and Quality is 90 percent, the OEE is not 90 percent. It is 72.9 percent. Three small losses compound into one big loss.

## Worked example: chocolate bar packaging line in Laguna

Take a real Philippine plant scenario. A confectionery facility in Laguna runs a chocolate bar packaging line. The ideal rate at design speed is 60 bars per minute. They produce one product type, one packaging format, on an 8-hour shift.

### Step 1: Planned Production Time

### Step 2: Run Time and Availability

During the shift, the line stopped 4 times: a wrapper jam (35 min), a sealer adjustment that ran long (20 min), waiting for the next batch of foil (25 min), and a power dip from Meralco (10 min). Total unplanned downtime: 90 minutes.

### Step 3: Performance

During the 360 minutes the line was running, it produced 17,280 bars. At the ideal rate (60 bars/min), it should have produced 360 × 60 = 21,600 bars.

### Step 4: Quality

The quality inspector pulled 1,728 bars with wrapping defects (sealed crooked, label off-center, foil torn). Those went to rework.

### Step 5: OEE

This is roughly the median Philippine plant. Not embarrassing, not impressive. The number itself is the starting line, not the finish line.

To run this on your own line without redoing the arithmetic, use the free [OEE calculator](https://workhiveph.com/tools/oee-calculator/) — enter planned time, downtime, ideal cycle time, and your good and total counts, and it returns Availability, Performance, Quality and OEE separately, which is what tells you *which* of the three is costing you.

## The 6 big losses OEE catches

Nakajima identified six specific losses that an OEE measurement reveals. Each maps to one of the three components:

| # | Loss | Hurts | Example from above |
| --- | --- | --- | --- |
| 1 | Equipment breakdown | Availability | Wrapper jam (35 min) |
| 2 | Setup / changeover | Availability | Sealer adjustment overrun (20 min) |
| 3 | Idling / minor stops | Performance | Waiting for foil batch (25 min) |
| 4 | Reduced speed | Performance | Line ran at 48/min not 60/min |
| 5 | Production defects | Quality | 1,728 wrapping defects (10%) |
| 6 | Startup losses | Quality | First 50 bars after restart (scrap) |

Once you know the breakdown, the question is no longer "is our OEE bad?" but "which loss is the biggest, and what is the cheapest fix?" In the example above, the biggest single loss is the 35-minute wrapper jam. That is a maintenance fix (better PM on the wrapper) and a knowledge fix (a logbook entry so the next shift sees the recurrence pattern).

## How to measure OEE without expensive sensors

Most OEE software vendors will tell you that you need sensors on every machine, a SCADA layer, and a multi-million-peso MES rollout to track OEE properly. This is theatre. Plants that buy that stack before they have the operating habit waste the investment because the data is never reviewed.

The Stage 1 approach used by every Japanese plant that ever got to 85 percent OEE is much simpler:

1. **One clipboard or digital logbook entry per shift** capturing: shift start time, shift end time, total planned downtime, total unplanned downtime (with reason for each stop), total units produced, total units rejected.
2. **The supervisor calculates OEE at end of shift** using the formula above. Takes 3 minutes if the entry is structured properly.
3. **The supervisor posts the OEE number on a whiteboard** at the line entrance the next morning. No software, no dashboards, no SaaS bills.
4. **Once you have 12 weeks of daily numbers**, the trend tells you everything: which shift is most consistent, which day of the week has the worst OEE, which fault category dominates.

Only after this discipline is in place does sensor investment make sense. Sensors automate what already works; they cannot create what does not exist.

The tool this guide is about

#### WorkHive Analytics computes OEE automatically

Every shift entry in the WorkHive Logbook (run time, unplanned downtime reasons, units produced, defects) flows into Analytics as A × P × Q. Track per asset, per shift, per day. No spreadsheets, no SCADA, no per-user license. Free at the worker tier forever.

No hive yet? [Join WorkHive](https://workhiveph.com/#join) first (free, takes 30 seconds).

## World-class versus Philippine plant reality

| OEE Range | Tier | What it usually means |
| --- | --- | --- |
| 85%+ | World-class | Japanese TPM mature plants, top-quartile global automotive. Rare in PH. |
| 75-85% | Excellent | Mature TPM, sensor data, dedicated reliability team. Top-decile PH plants. |
| 60-75% | Good | Disciplined PM, regular OEE reviews, capable workforce. Top-quartile PH. |
| 40-60% | Typical PH | Functional plant, paper-based or first-year digital. Median Philippine reality. |
| <40% | Measurement error | Almost always a calculation or data-collection problem, not actual performance. |

If a plant tells you their OEE is 30 percent and they are still operating, the OEE measurement is wrong. Either they are double-counting downtime, miscounting planned production time, or treating rework as scrap. Real 30 percent OEE means the plant loses money daily.

## Common OEE calculation mistakes

- **Including planned downtime in Availability denominator.** Planned PM is not a loss. The formula uses Planned Production Time, not calendar time. Including breaks and PM tanks Availability artificially.
- **Using nameplate speed instead of demonstrated ideal speed.** If the equipment has never actually achieved nameplate speed under your conditions (Philippine ambient temperature, your power quality, your raw materials), use the best-demonstrated 1-hour rate as ideal, not the OEM's marketing number.
- **Hiding minor stops in "planned" time.** Five 90-second stops do not become "planned" just because they happen every shift. They are minor-stop losses (loss #3) and they need to show up.
- **Counting reworked units as good.** A bar that came off the line defective and got re-wrapped is a Quality loss. Counting it as good hides loss #5.
- **Aggregating OEE across multiple products.** Different products have different ideal cycle times. Mixing them in one OEE number is meaningless. Calculate per product, then weighted-average if you must.
- **Reporting OEE without the three components.** "OEE was 67 percent" is useless. "OEE was 67 percent: A 92, P 81, Q 90" tells you Performance is the loss to fix.

## The path from 50 percent to 75 percent OEE

Most Philippine plants we have benchmarked sit between 40 and 60 percent OEE on first measurement. The path to 75 percent takes 12 to 18 months of disciplined improvement. The pattern is consistent:

- **Months 1 to 3: Just measure.** No improvement projects yet. Get the OEE number to be the same number on the floor whiteboard as the supervisor reports up. Most plants discover their first 5 percentage points of "improvement" here just from measurement honesty.
- **Months 4 to 6: Fix the top loss.** Pick one loss (usually a recurring breakdown or a slow-changeover) and run a focused improvement project. Aim for 5 to 10 OEE points.
- **Months 7 to 9: PM discipline.** Lock the PM schedule. Tie PM completion to logbook evidence. Aim for another 5 OEE points from reduced unplanned downtime.
- **Months 10 to 12: Skill matrix and quality.** Match technician skill to task type. Address top defect causes with root-cause analysis. Aim for the final 5 to 10 OEE points.

This sequence matches WorkHive's 4-stage path: Paper-to-Digital (months 1 to 3), Disciplined (months 4 to 9), then Predictive-Ready (months 10+ when sensor investment finally pays back).

**The honest reality:** OEE improvement is 80 percent operating discipline and 20 percent technology. Plants that invest in MES and sensors before they have the discipline get a 50 percent OEE measurement system instead of a 75 percent operation. Plants that invest in discipline first then add sensors get to 85 percent.

## Frequently asked questions

### What is a good OEE score?

World-class OEE for discrete manufacturing is 85 percent or higher. Industry average is around 60 percent. Most Philippine plants we have benchmarked sit between 40 and 60 percent on first measurement. Anything below 40 percent usually means measurement errors, not actual performance, because real plants do not survive at that level.

### What is the OEE formula?

OEE equals Availability times Performance times Quality. Availability is run time divided by planned production time. Performance is actual run rate divided by ideal rate. Quality is good units divided by total units. All three are multiplied together (not averaged) which is why OEE is harsh: any weak component drags the whole number down.

### Do I need expensive sensors to measure OEE?

No. Stage 1 OEE is measured by the operator with a clipboard or a digital logbook entry per shift. You only need sensors when you reach Stage 3 (Predictive-Ready). Plants that buy sensors before they have the operating habit waste the investment because the data is never reviewed.

### What are the 6 big losses in OEE?

Seiichi Nakajima's 6 big losses are: (1) breakdowns and equipment failures, (2) setup and adjustment delays, (3) idling and minor stops, (4) reduced speed running, (5) defects in production, and (6) startup losses after a stop. Losses 1 and 2 hurt Availability. Losses 3 and 4 hurt Performance. Losses 5 and 6 hurt Quality. Knowing which loss is biggest tells you which fix to do first.

### Is OEE the same as utilization?

No. Utilization only measures how much time the equipment ran versus calendar time. OEE measures whether what was produced during that run time was actually saleable at the ideal rate. A plant can have 95 percent utilization and 40 percent OEE if the line runs slow or produces a lot of defects. OEE is the more honest number.

### How long does it take to improve OEE from 50 to 75 percent?

12 to 18 months for most Philippine plants that commit to the discipline. The first 25 percent improvement usually comes from fixing the loss the team did not realize was happening. The next 25 percent requires structural change such as PM discipline, skill matrix coverage, and quality root-cause analysis. The last 10 percent (from 75 to 85) requires sensor data and is much harder.

## Sources

- Seiichi Nakajima, **Introduction to TPM: Total Productive Maintenance**, Productivity Press, 1988. The original OEE definition and the 6 big losses framework.
- ISO 22400-2:2014, **Automation systems and integration: Key performance indicators (KPIs) for manufacturing operations management**. The international standard definition of OEE used for benchmarking.
- Society for Maintenance and Reliability Professionals (SMRP), **Best Practices, 5th Edition**, 2017. North American maintenance KPI library, includes OEE adoption guidance.
- Jenni Munar, **"Why Many Imported ERP Systems Fail in the Philippines"**, The Daily Chronicle, 7 May 2026. Relevant for the section on why MES/sensor investment before operating discipline fails. [thechronicle.com.ph](https://thechronicle.com.ph/why-many-imported-erp-systems-fail-in-the-philippines/)
- WorkHive platform positioning, "Four Gaps One Hive": Execution, Skills, Intelligence, Marketplace. [workhiveph.com](https://workhiveph.com/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: 9fac813bcce7f763 -->
