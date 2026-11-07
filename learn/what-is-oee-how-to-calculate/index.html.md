# What is OEE and how do I calculate it? (worked Philippine factory example)

> OEE explained in plain language with a worked Philippine factory example. Formula, benchmarks, the 6 big losses, and how to start tracking without expensive sensors.

Source: https://workhiveph.com/learn/what-is-oee-how-to-calculate/

OEE · Worked example

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 24 Aug 2026
·
10 min read

**Short answer:** Overall Equipment Effectiveness (OEE) puts three things in one number. It shows how often a machine runs, how fast it runs, and how much output is good. The formula is `OEE = Availability × Performance × Quality`. The TPM benchmark is 85 percent. An honest first reading often lands at 40 to 60 percent. What you do with the number matters most.

Who this is for

- Production supervisors and line leaders
- Maintenance and reliability engineers
- Plant managers and operations directors
- Continuous improvement and Lean teams
- Equipment suppliers benchmarking performance
- New industrial-engineering graduates
- Workers upskilling on manufacturing KPIs

Part of the [maintenance metrics guide: OEE, MTBF, MTTR and reliability](https://workhiveph.com/learn/maintenance-metrics-reliability-guide/). That guide links each reliability metric to the next.

## What OEE actually measures

Seiichi Nakajima created OEE in Japan in the 1960s. It was the headline metric for Total Productive Maintenance (TPM). It still matters 60 years later. No other metric answers a plant manager's three questions in one number:

- **How often did the equipment run when we wanted it to?** (Availability)
- **How fast did it run when it was running?** (Performance)
- **How much of what it made was actually saleable?** (Quality)

Any one of these alone misleads. Say a line ran 8 hours straight but made nothing usable. It has 100 percent availability and 0 percent OEE.

Now take a line that ran fast with perfect quality, but only for 3 of 8 hours. It hides the same problem. OEE multiplies all three, so a loss in one part cancels gains in the others.

## The OEE formula in plain language

The formula is:

Where:

- `Availability = Run Time / Planned Production Time`
- `Performance = (Actual Run Rate) / (Ideal Run Rate)` or equivalently `(Total Units Produced × Ideal Cycle Time) / Run Time`
- `Quality = Good Units / Total Units Produced`

Each component is a fraction between 0 and 1. Multiply them to get OEE as a fraction. Multiply by 100 to get a percentage.

Notice the formula multiplies, it does not average. This matters because OEE is honest. Say Availability, Performance and Quality are each 90 percent. The OEE is not 90 percent. It is 72.9 percent. Three small losses compound into one big loss.

## Worked example: chocolate bar packaging line in Laguna

Take a real Philippine plant scenario. A confectionery facility in Laguna runs a chocolate bar packaging line. The ideal rate at design speed is 60 bars per minute. They produce one product type, one packaging format, on an 8-hour shift.

### Step 1: Planned Production Time

### Step 2: Run Time and Availability

The line stopped 4 times during the shift. A wrapper jam took 35 min. A sealer adjustment ran 20 min long. Waiting for the next batch of foil took 25 min. A power dip from Meralco took 10 min. Total unplanned downtime: 90 minutes.

### Step 3: Performance

During the 360 minutes the line was running, it produced 17,280 bars. At the ideal rate (60 bars/min), it should have produced 360 × 60 = 21,600 bars.

### Step 4: Quality

The inspector pulled 1,728 bars with bad wrapping: crooked seals, off-center labels and torn foil. Those went to rework.

### Step 5: OEE

That is a normal first reading. Nothing about it says the plant is in bad shape.

Of every 100 bars the line could make in its planned time, 42 never come out good. The three factors say where they went. The line is down for a fifth of the time. When it runs, it runs at 80 percent of rated speed. And one bar in ten is scrap.

To run this on your own line, know where the number comes from. There is no form for these five figures in WorkHive. It *works out* OEE from the shift entries your team already writes. Analytics then shows Availability, Performance and Quality on their own. That split tells you *which* of the three is costing you.

The [OEE calculator page](https://workhiveph.com/tools/oee-calculator/) walks through the formula. It also has a second worked example, so you can check your own math by hand.

## The 6 big losses OEE catches

Nakajima identified six specific losses that an OEE measurement reveals. Each maps to one of the three components:

| # | Loss | Hurts | Example from above |
| --- | --- | --- | --- |
| 1 | Equipment breakdown | Availability | Wrapper jam (35 min) |
| 2 | Setup / changeover | Availability | Sealer adjustment overrun (20 min) |
| 3 | Idling / minor stops | Performance | Brief photo-eye misfeeds and jams cleared in seconds: never logged as downtime |
| 4 | Reduced speed | Performance | Line ran at 48/min not 60/min |
| 5 | Production defects | Quality | 1,728 wrapping defects (10%) |
| 6 | Startup losses | Quality | First 50 bars after restart (scrap) |

Once you know the breakdown, stop asking if your OEE is bad. Ask which loss is the biggest, and what the cheapest fix is. Count it in bars, not minutes. Bars are the unit all three parts share.

In the example above, the wrapper jam is the biggest single *stop*: 35 minutes, or 2,100 bars. It needs two fixes. One is better PM on the wrapper. The other is a logbook entry, so the next shift sees the jam coming back. But it is not the biggest loss.

Running at 48 bars a minute instead of 60, for all 360 minutes, cost **4,320 bars**. That is more than the jam and the sealer overrun put together. And no one ever logged it as a stop.

Loss 4, reduced speed, is the one this line should chase first. A shift report built only from downtime would have hidden it. That is why OEE keeps the three parts apart.

## How to measure OEE without expensive sensors

Most OEE software vendors say you need a lot to track OEE well. They mean sensors on every machine and a SCADA layer. They also mean an MES rollout that costs millions of pesos. This is theatre. Plants that buy that stack before they have the habit waste the money. No one ever reviews the data.

Every Japanese plant that reached 85 percent OEE started with a much simpler Stage 1:

1. **One clipboard or logbook entry per shift. It records the shift's start and end, and its planned downtime. It records unplanned downtime too, with a reason for each stop. It also records units made and units rejected.**
2. **At the end of each shift, the supervisor works out OEE with the formula above. Takes 3 minutes with a well-built entry.**
3. **Next morning, the supervisor posts the OEE number on a board at the line. No software, no dashboards, no SaaS bills.**
4. **After 12 weeks of daily numbers, the trend tells you a lot. You see which shift is steadiest and which weekday has the worst OEE. You also see which kind of fault comes up most.**

Only after this discipline is in place does sensor investment make sense. Sensors automate what already works; they cannot create what does not exist.

The tool this guide is about

### WorkHive Analytics computes OEE automatically

Every shift entry in the WorkHive Logbook flows into Analytics. That covers run time, downtime reasons, units made and defects. Analytics shows it per asset, per shift and per day. Those four give you Availability and Quality.

**Performance needs one more field:** how many seconds the asset takes per unit at its best. That is its ideal cycle time. You set it once on the asset wizard. For a 600-unit-per-hour line, it is 6. Leave it blank and Analytics says so. The tile reads *OEE (avg, partial)*, and the figure is A × Q, not the full number. Fill it in and the same tile becomes real three-factor OEE.

The entry a technician writes at the end of a shift is the OEE record. Nothing gets typed twice, and no one pays per seat. Free at the worker tier forever.

No hive yet? [Join WorkHive](https://workhiveph.com/?signup=1) first (free, takes 30 seconds).

## The TPM benchmark versus Philippine plant reality

| OEE Range | Tier | What it usually means |
| --- | --- | --- |
| 85%+ | TPM benchmark | Japanese TPM mature plants, top-quartile global automotive. Rare in PH. |
| 75-85% | Excellent | Mature TPM, sensor data, dedicated reliability team. Top-decile PH plants. |
| 60-75% | Good | Disciplined PM, regular OEE reviews, capable workforce. Top-quartile PH. |
| 40-60% | Typical PH | Functional plant, paper-based or first-year digital. Median Philippine reality. |
| <40% | Measurement error | Almost always a calculation or data-collection problem, not actual performance. |

Say a plant reports 30 percent OEE and is still running. Then its OEE reading is wrong. They may count downtime twice or miscount planned time. Or they may treat rework as scrap. Real 30 percent OEE means the plant loses money daily.

## Common OEE calculation mistakes

- **Including planned downtime in Availability denominator.** Planned PM is not a loss. The formula uses Planned Production Time, not calendar time. Including breaks and PM tanks Availability artificially.
- **Using nameplate speed instead of demonstrated ideal speed.** Your line may never have reached nameplate speed in your plant. Think of Philippine heat, your power and your raw materials. If so, use your best 1-hour rate as the ideal. Do not use the maker's sales number.
- **Hiding minor stops in "planned" time.** Five 90-second stops do not become "planned" just because they happen every shift. They are minor-stop losses (loss #3) and they need to show up.
- **Counting reworked units as good.** A bar that came off the line defective and got re-wrapped is a Quality loss. Counting it as good hides loss #5.
- **Aggregating OEE across multiple products.** Different products have different ideal cycle times. Mixing them in one OEE number is meaningless. Calculate per product, then weighted-average if you must.
- **Reporting OEE without the three components.** "OEE was 67 percent" is useless. "OEE was 67 percent: A 92, P 81, Q 90" tells you Performance is the loss to fix.

## The path from 50 percent to 75 percent OEE

A first honest OEE reading often lands between 40 and 60 percent. The path to 75 percent takes 12 to 18 months of disciplined improvement. The pattern is consistent:

- **Months 1 to 3: Just measure.** No improvement projects yet. Make the OEE number on the floor board match the one the supervisor reports up. Most plants find their first 5 points of "improvement" here, just by measuring honestly.
- **Months 4 to 6: Fix the top loss.** Pick one loss, often a repeat breakdown or a slow changeover. Then run a focused project to fix it. Aim for 5 to 10 OEE points.
- **Months 7 to 9: PM discipline.** Lock the PM schedule. Tie PM completion to logbook evidence. Aim for another 5 OEE points from reduced unplanned downtime.
- **Months 10 to 12: Skill matrix and quality.** Match technician skill to task type. Address top defect causes with root-cause analysis. Aim for the final 5 to 10 OEE points.

This order matches WorkHive's 4-stage path. First comes Paper-to-Digital, in months 1 to 3. Then Disciplined, in months 4 to 9. Then Predictive-Ready, from month 10, when sensors finally pay back.

**The honest truth: better OEE is mostly habit. Think 80 percent habit, 20 percent technology. Some plants buy MES and sensors before they have the habit. They end up measuring a 50 percent OEE line. They could have run a 75 percent one instead. Plants that invest in discipline first then add sensors get to 85 percent.**

## Frequently asked questions

### What is a good OEE score?

The TPM benchmark for discrete manufacturing (Nakajima's) is an OEE of 85 percent or higher. Industry average is around 60 percent. A plant measuring OEE honestly for the first time typically lands between 40 and 60 percent. Anything below 40 percent usually means measurement errors, not actual performance, because real plants do not survive at that level.

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

<!-- md-twin source-sha: 710b1881a80ff907 -->
