# The 4 Phases of Maintenance Analytics: From What Happened to What To Do Next

> Learn about the 4 phases of maintenance analytics and how WorkHive's Analytics Engine can help Philippine plants improve equipment performance and reduce downtime.

Source: https://workhiveph.com/learn/four-phases-maintenance-analytics-philippine-plants/

WorkHive Learn · Philippines

By WorkHive Editorial Team
·
3 July 2026
·
6 min read

**Short answer:** Maintenance analytics comes in four phases, and a plant can only stand on one at a time: descriptive (what happened), diagnostic (why), predictive (what will), prescriptive (what to do about it). WorkHive's Analytics Engine computes all four from the logbook entries and PM completions a team already writes, which is what decides how far up the four a plant can actually get. The metrics underneath are the standard ones: **ISO 14224** for how failure data is collected, and the **SMRP** benchmark of **90 percent** PM compliance as the leading indicator that moves the rest.

Who this is for

- Reliability engineers who want to know which phase their data can actually support
- Supervisors reading KPI tiles that have to mean something at the morning huddle
- Planners who need a Pareto of causes before they re-cut the PM schedule
- Plant managers deciding whether to buy prediction or fix the record first
- Technicians whose logbook entries are the only input every number here is built from
- Anyone who has been sold a dashboard before the plant had data to put in it

Part of the [maintenance metrics guide: OEE, MTBF, MTTR and reliability](https://workhiveph.com/learn/maintenance-metrics-reliability-guide/): the hub that connects every reliability metric and shows how they chain together.

## What is maintenance analytics?

Maintenance analytics is what a plant can say about its own equipment from the records it keeps - and how far it can say it depends entirely on how good those records are. WorkHive's Analytics Engine takes logbook entries and PM completions as its only inputs and computes MTBF, MTTR, Availability, OEE, PM compliance and a Pareto of failure causes from them. Nothing else is typed; if the entries are thin, so is every number below.

The Analytics Engine is designed to guide maintenance teams through four phases of analytics maturity: descriptive, diagnostic, predictive, and prescriptive analytics. The **Descriptive** phase provides a snapshot of what has happened, through live KPI tiles. The **Diagnostic** phase delves into why things happened, using Pareto and root-cause analysis. The **Predictive** phase forecasts what might happen, through failure risk and forecast tools. Finally, the **Prescriptive** phase recommends what to do next, via an AI-driven action plan. This structured approach ensures that maintenance teams can systematically improve their operations.

WorkHive's Analytics Engine is built with industry standards in mind, including ISO 14224 and ISA-101. It offers a zero-budget, no-CMMS rollout solution that gets richer as your logbook grows. By starting with logbook entries, plants can begin their analytics journey without significant upfront investment. The engine's outputs, such as Predictive Analytics, Asset Hub, and print-ready Analytics Reports, are all interconnected, providing a comprehensive view of maintenance performance. This holistic approach enables Philippine plants, such as those in Cabuyao or Batangas, to benchmark their performance against PH Industry Intelligence standards.

## Descriptive Analytics: What Happened

As a plant supervisor in the Philippines, you need to know what happened in your facility. WorkHive's Analytics Engine provides descriptive analytics to help you understand past events. The engine computes key performance indicators (KPIs) such as Mean Time Between Failures (MTBF) and Mean Time To Repair (MTTR) from logbook entries and preventive maintenance (PM) completions. Live KPI tiles display these metrics, giving you a clear picture of your plant's performance.

The Analytics Engine also calculates other important metrics, including Availability, Overall Equipment Effectiveness (OEE), and PM Compliance. A Pareto analysis helps identify the most common causes of equipment failures. You can view these metrics for different time periods by selecting '30 days', '90 days', '180 days', or '1 year' and clicking the '🔄 Refresh' button. This allows you to track changes in your plant's performance over time.

**Worked example:** A maintenance planner at a Philippine manufacturing plant used WorkHive's Analytics Engine to analyze equipment failures over the past 90 days. The planner selected the '90 days' option and clicked '🔄 Refresh' to view the live KPI tiles. The engine showed a low MTBF for a specific equipment, indicating a high failure rate. The planner then used this information to schedule a root-cause analysis.

## Diagnostic Analytics: Why It Happened

In the **Diagnostic** phase of WorkHive Analytics, we analyze **what happened** and **why** it happened. This phase provides insights into the root causes of equipment failures and maintenance issues. For example, a round-the-clock schedule with changing personnel at 06:00, 14:00, and 22:00 can lead to variations in maintenance quality. The Analytics Engine helps identify these patterns.

The engine provides **Pareto analysis** to highlight the most common causes of failures. This information is crucial for maintenance teams to prioritize tasks and allocate resources effectively. By analyzing data from logbook entries and PM completions, the engine computes key metrics such as **MTBF**, **MTTR**, and **Availability**. These metrics help teams understand the impact of maintenance activities on equipment performance.

| Diagnostic Analytics | WorkHive Capability |
| --- | --- |
| Pareto Analysis | Identifies common causes of failures |
| Root-Cause Identification | Analyzes logbook entries and PM completions |
| Failure Mode Analysis | Computes MTBF, MTTR, and Availability metrics |

## Predictive Analytics: What Will Happen

The WorkHive Analytics Engine takes maintenance analytics to the next level with predictive analytics, enabling your team to anticipate and prepare for potential equipment failures. For instance, consider Pump P-204B in a Philippine plant. By analyzing historical data, the engine provides failure risk scores and forecasts, giving maintenance teams a proactive edge.

With the engine's predictive capabilities, you can assess the likelihood of equipment failure and prioritize maintenance activities accordingly. Risk scores are computed by a batch run at **13:00 PHT each day**, which is worth knowing before you distrust a figure: a score you read at nine in the morning reflects yesterday's evidence, not this morning's breakdown. A supervisor can skip the wait with the **Recompute risk** button, which re-runs the scoring for the hive on demand. It is supervisor-only, so if you are a technician and the numbers look stale, that is the person to ask. The engine's predictions are based on industry-recognized standards, such as ISO 14224, ensuring that your plant's maintenance practices are aligned with global best practices.

1. Navigate to the **Predictive** tab to access failure risk scores and forecasts for your equipment.
2. Filter by risk band with the traffic-light chips — **🔴 Critical**, **🟠 High**, **🟡 Medium**, **🟢 Low** — or **All** to drop the filter. There are discipline chips beside them too (Mechanical, Electrical, Instrumentation, Hydraulic, Pneumatic, Lubrication), which is how you get from “everything at risk” to “everything at risk that my team owns”.
3. Click **Show details** to view more information on the predicted failures and plan maintenance activities.

## Prescriptive Analytics: What to Do Next

Prescriptive Analytics in WorkHive's Analytics Engine takes maintenance strategy to the next level. By analyzing data from logbook entries and PM completions, the engine provides AI-driven action plans. These plans help prioritize and schedule maintenance tasks effectively. For example, a plant in Calabarzon can use prescriptive analytics to identify the most critical assets that require immediate attention.

The engine's prescriptive analytics capability is built on industry-recognized standards such as ISO 14224 and ISA-101. This ensures that the recommended actions are aligned with best practices in reliability and maintenance. By using these standards, the engine can provide actionable insights that maintenance teams can trust. The **Prescriptive** tab in the Analytics Engine provides a clear and concise view of the recommended actions.

**How to read a prescriptive recommendation:** each one names the analysis it came from and the standard behind it: a PM interval suggestion cites SAE JA1011 §7, a reorder recommendation comes from an inventory × PM cross-reference, a training-gap recommendation from MTTR × skill. Read the basis before you act on the advice, because the recommendation is only as good as the history underneath it, and on a thin logbook it will say so rather than guess. Be wary of any tool, this one included, that tells you it prevented a failure: the downtime that did not happen leaves no record, so that claim can never be checked.

## Implementation and Integration

To implement and integrate WorkHive's Analytics Engine into existing plant operations, start by ensuring that your logbook entries and PM completions are up-to-date. This raw data is fed into the engine, which then computes key performance indicators such as MTBF, MTTR, Availability, OEE, PM Compliance, and Pareto. For instance, a Filipino **Plant Supervisor** can use the engine's **Descriptive** analytics to view live KPI tiles and quickly identify areas for improvement.

The Analytics Engine is designed to be interconnected, feeding predictive analytics, asset hub, and print-ready analytics reports. Click the **'🔄 Refresh'** button to update the data and ensure that your analytics are current. The engine also connects to **PH Industry Intelligence** benchmarks, providing a broader context for your plant's performance. By using these features, maintenance planners and reliability engineers can make evidence-backed choices to optimize plant operations.

With the Analytics Engine, you can move through the four phases of maintenance analytics - descriptive, diagnostic, predictive, and prescriptive - to gain a deeper understanding of your plant's performance. For example, click **'Predictive'** to view risk scores and forecast potential failures. The engine's **'Prescriptive'** analytics even provides an AI action plan, recommending specific actions to take next. By following these steps and utilizing the engine's features, you can improve maintenance outcomes and achieve industry-recognized standards such as ISO 14224 and SMRP.

**Open the tool:** Analytics is the WorkHive surface this guide funnels into. It is free at the worker tier, works offline, and is built for Philippine plants.

## Frequently asked questions

### What is the difference between descriptive and predictive analytics?

Descriptive analytics looks at what happened, while predictive analytics forecasts what will happen. In the context of Philippine plants, predictive analytics can help identify potential equipment failures before they occur.

### How does WorkHive's Analytics Engine integrate with existing systems?

The engine reads the logbook entries and PM completions your team already writes, so there is no second system to keep fed - the analysis is built from the record, not from a separate data entry step.

### What is the role of ISO 14224 in maintenance analytics?

ISO 14224 provides guidelines for reliability and maintenance data collection and analysis. It is an important standard for ensuring data accuracy and consistency in Philippine plants.

### Can WorkHive's Analytics Engine be used for small-scale plants?

Yes, the engine can be used for small-scale plants. It is designed to be flexible and adaptable to different plant sizes and operations.

### How does the engine handle data from different equipment types?

The engine can handle data from various equipment types, including rotating equipment, electrical systems, and mechanical systems. It provides a comprehensive view of plant operations and performance.

### What kind of support does WorkHive offer for Analytics Engine users?

WorkHive provides technical support and training for Analytics Engine users. This ensures that users can maximize the engine's capabilities and get the most out of their data.

## Sources

- ISO 14224:2016 - Reliability and maintenance data collection and analysis
- SMRP CMRP BoK - Maintenance and Reliability Body of Knowledge
- DOLE OSHS - Occupational Safety and Health Standards
- Related WorkHive guides: [The print-ready analytics report](https://workhiveph.com/learn/print-ready-maintenance-analytics-report/) · [What is OEE](https://workhiveph.com/learn/what-is-oee-how-to-calculate/) · [Predictive maintenance on a budget](https://workhiveph.com/learn/predictive-maintenance-on-a-budget-philippines/)

<!-- md-twin source-sha: eaadd50607d7f742 -->
