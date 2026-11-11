# The 4 Phases of Maintenance Analytics: From What Happened to What To Do Next

> Learn about the 4 phases of maintenance analytics and how WorkHive's Analytics Engine can help Philippine plants improve equipment performance and reduce downtime.

Source: https://workhiveph.com/learn/four-phases-maintenance-analytics-philippine-plants/

WorkHive Learn · Philippines

By WorkHive Editorial Team
·
3 July 2026
·
6 min read

**Short answer:** Maintenance analytics has four phases. Descriptive says what happened. Diagnostic asks why. Predictive looks at what is likely next. Prescriptive says what to do. WorkHive's Analytics page has a tab for each one. Every tab reads the logbook and PM records your team already keeps. Pick a period of 30, 90 or 180 days, or 1 year. The PM compliance tile turns green at 85 percent.

Who this is for

- Reliability engineers who want to know which phase their data supports
- Supervisors who read KPI (key performance indicator) tiles at the huddle
- Planners who need a Pareto of causes before they re-cut the PM schedule
- Plant managers choosing between buying prediction and fixing the record
- Technicians whose logbook entries feed every number here
- Anyone who has been sold a dashboard before the plant had data to put in it

Part of the [maintenance metrics guide](https://workhiveph.com/learn/maintenance-metrics-reliability-guide/). That hub links every reliability metric and shows how they connect.

## What is maintenance analytics?

Maintenance analytics is what a plant learns from its own records. How far it gets depends on how good those records are.

WorkHive's Analytics page takes two inputs: logbook entries and PM completions. Nobody types anything else. So if the entries are thin, every figure is thin too.

The page splits the work into four tabs, one per phase. Each tab names the standards it follows. Read them in order, because each phase needs the one before it.

## Descriptive Analytics: What Happened

The Descriptive tab shows what happened in the period you pick. It follows ISO 14224 and the SMRP metrics. Its main tiles are:

- **MTBF**: mean time between failures
- **MTTR**: mean time to repair
- **OEE**: overall equipment effectiveness
- **Availability**: the share of time the asset could run
- **PM compliance**: the share of due PM tasks done on time

Below them sit failure counts, a downtime Pareto, parts use and repeat failures. Pick 30, 90 or 180 days, or 1 year, then tap Refresh. The PM compliance tile turns green at 85 percent and red below 70.

**Worked example:** A planner picks 90 days and taps Refresh. One pump shows a short MTBF, so it fails often. The planner books a root-cause review for it.

## Diagnostic Analytics: Why It Happened

The Diagnostic tab looks for causes. It follows the ISO 14224 failure taxonomy and SAE JA1011. It measures each link with a Spearman correlation.

It shows which failure modes come up most. It checks whether missed PMs line up with failures. It checks whether repair time tracks a technician's skill level. It also checks whether waiting for parts adds downtime.

It groups repeat failures, so one recurring fault stands out from many one-offs. It also sorts each failure by its RCM consequence. RCM means reliability-centered maintenance.

## Predictive Analytics: What Will Happen

The Predictive tab looks ahead. It follows ISO 13381-1, the standard for forecasting how equipment will wear. It shows a health score per asset, the next likely failure date and a failure trend. It also shows a PM due calendar and parts that may run out.

Risk scores come from a batch run at 13:00 PHT each day. So a score you read at nine in the morning reflects yesterday's evidence. A supervisor can tap Recompute risk to run it now. Only supervisors see that button, so ask yours if a score looks stale.

Two rows of chips filter every tab. One picks asset criticality: Critical, High, Medium or Low. The other picks a discipline, such as Mechanical, Electrical or Instrumentation. Together they take you from everything at risk to what your team owns.

## Prescriptive Analytics: What to Do Next

The Prescriptive tab turns the other three into advice. It follows ISO 55000 and SAE JA1011. It builds an AI action plan and ranks assets by priority. It suggests PM intervals, parts to reorder, who to assign and where training is short.

Each recommendation names its source. A PM interval suggestion cites SAE JA1011 §7. A reorder comes from parts use set against the PM plan. A training gap comes from repair times set against skill levels.

Read the basis before you act. Advice is only as good as the history under it, and on a thin logbook it says so. Be wary of any tool, this one too, that claims it prevented a failure. A failure that never happened leaves no record to check.

## Implementation and Integration

Start with the record. The Analytics page needs no setup and no budget. You do not need a CMMS either. A CMMS is a computerized maintenance management system.

So the first job is a clean logbook. Log every failure, and close every PM when it is done. Then climb the phases in order. A prediction from a thin record is a guess with a chart on it.

| Phase | Question | What the tab shows |
| --- | --- | --- |
| Descriptive | What happened? | MTBF, MTTR, OEE, availability, PM compliance, a downtime Pareto |
| Diagnostic | Why? | Failure modes, PM and failure links, skill and repair time |
| Predictive | What is likely next? | Health scores, next failure dates, a PM due calendar, parts at risk |
| Prescriptive | What should we do? | An AI action plan, a priority list, PM, parts and training advice |

The Asset Hub and the Analytics Report read the same records.

**Open the tool:** this guide leads to WorkHive's Analytics page. It is free at the worker tier and built for Philippine plants.

## Frequently asked questions

### What is the difference between descriptive and predictive analytics?

Descriptive analytics looks at what happened, while predictive analytics forecasts what will happen. In the context of Philippine plants, predictive analytics can help identify potential equipment failures before they occur.

### How does WorkHive's Analytics Engine integrate with existing systems?

The engine reads the logbook entries and PM completions your team already writes, so there is no second system to keep fed - the analysis is built from the record, not from a separate data entry step.

### What is the role of ISO 14224 in maintenance analytics?

ISO 14224 provides guidelines for reliability and maintenance data collection and analysis. It is an important standard for ensuring data accuracy and consistency in Philippine plants.

### Can a small plant use WorkHive's Analytics Engine?

Yes. It needs only logbook entries and PM completions, so a team of three can use it. The figures get sharper as the record grows.

### How does the engine handle data from different equipment types?

It reads every logbook entry and PM completion, whatever the asset. Discipline chips split the results into Mechanical, Electrical, Instrumentation and the rest.

### What kind of support does WorkHive offer for Analytics Engine users?

The guides on this site explain each tab. For anything else, email admin@workhiveph.com.

## Sources

- ISO 14224:2016 - Reliability and maintenance data collection and analysis
- SMRP CMRP BoK - Maintenance and Reliability Body of Knowledge
- DOLE OSHS - Occupational Safety and Health Standards
- Related WorkHive guides: [The print-ready analytics report](https://workhiveph.com/learn/print-ready-maintenance-analytics-report/) · [What is OEE](https://workhiveph.com/learn/what-is-oee-how-to-calculate/) · [Predictive maintenance on a budget](https://workhiveph.com/learn/predictive-maintenance-on-a-budget-philippines/)

<!-- md-twin source-sha: e64dd4faebef241d -->
