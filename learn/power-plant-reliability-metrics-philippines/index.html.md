# Power Plant Reliability Metrics in the Philippines

> Learn about key reliability metrics for Philippine power plants, including EAF, EFOR, NCF, heat rate, and RAM benchmarks. Understand ERC reporting requirements and how WorkHive Analytics can help improve power plant performance.

Source: https://workhiveph.com/learn/power-plant-reliability-metrics-philippines/

WorkHive Learn · Philippines

By WorkHive Editorial Team
·
18 May 2026
·
updated 21 September 2026 for ERC Resolution 23 (2026)
·
9 min read

**Short answer:** the ERC judges a power plant on three metrics. They are EAF, EFOR and heat rate, not plain uptime. EAF is the share of the year's 8,760 hours the unit could run at full output, after outages and deratings. So one long forced outage moves it far more than several short ones. All of it comes from one source: an outage log with a cause, a start and an end.

Who this is for

- Field workers monitoring power plant equipment daily
- Technicians performing routine maintenance on plant machinery
- Supervisors overseeing plant operations and maintenance teams
- Engineers designing and optimizing plant systems and processes
- Planners and schedulers coordinating maintenance and repairs
- Managers and directors responsible for plant performance and profitability
- Suppliers and contractors providing goods and services to power plants
- Auditors and officers ensuring compliance with regulations and standards

Part of the [maintenance metrics guide](https://workhiveph.com/learn/maintenance-metrics-reliability-guide/). That hub links every reliability metric and shows how they connect.

## Introduction to Reliability Metrics

Reliability metrics decide what a power plant may dispatch and earn. That is why the Energy Regulatory Commission (ERC) asks for them. It does not ask for a maintenance story.

A forced outage costs the energy the unit could not sell, plus the fuel to start again. So the metrics land on the bottom line through dispatch.

WorkHive does not compute EAF or EFOR for you. Its Analytics page reports four other figures:

- MTBF (mean time between failures)
- MTTR (mean time to repair)
- OEE (overall equipment effectiveness)
- PM compliance

What it does hold is the raw material. That is the outage records your team already writes. Each has a cause, a start and an end. Plants usually lack that half at the deadline. The index arithmetic on top is the reliability engineer's job.

## Key Reliability Metrics for Power Plants

- **Equivalent Availability Factor (EAF).** The share of the period the unit could run at full output. It allows for outages and deratings.
- **Equivalent Forced Outage Rate (EFOR).** The chance a forced outage or derating takes the unit out. It counts only the hours the grid wanted the unit. Lower is better.
- **Net Capacity Factor (NCF).** Actual net output as a share of what the unit could have made.
- **Heat rate.** Fuel per unit of power sent out. Lower is better.

EFOR is the one people get wrong, so mind its denominator. It counts the hours the grid wanted the unit. That means service hours plus forced-out hours. It does not count the energy the unit made. EFOR does not punish a unit left idle with no dispatch. It does punish a unit that fails when the grid wants it.

That makes the demand peak matter most. A forced outage in the late afternoon or evening costs the most. That is when an unavailable megawatt is worth most.

Heat rate in kcal/kWh is 860 divided by the unit's efficiency. A unit at 35 percent net efficiency runs at about 2,460 kcal/kWh. Fuel is the largest cost a plant controls, so every point of efficiency counts.

NCF needs output and capacity figures from your dispatch records. The maintenance log does not hold them. What the log adds is the outage side: why the unit was not running.

## ERC Reporting Requirements

The current rule is ERC Resolution 23, Series of 2026. It is the Revised Rules on the Reliability of Power Plants. The ERC adopted it on 17 July 2026. It covers grid-connected plants of 5 MW or more.

That includes conventional plants and non-variable renewables. Embedded generators count too. It caps how many unplanned outages and deratings a unit may have each year. The cap depends on the technology.

The ERC assesses each unit once a year. It uses the automated Grid Reliability Monitoring System, or GRMS. It is not a quarterly filing the plant assembles by hand. So the figure the regulator sees comes from outage records all year. The records are the filing. Missing the rules carries penalties the regulator sets.

The other dated duty looks forward. By 30 April each year, companies file a planned outage schedule. It covers the next five years. The regulator lines these up across the fleet, so windows do not collide.

It does this through the Grid Operating and Maintenance Program. Put that date in your maintenance calendar. It commits you to outage windows years ahead.

On a plant that never stops, the record is only as good as the handover. So each shift logs its outages before it hands over, not at the end of the month.

## Worked Example: Mindanao Coal-Fired Plant

Take a 300 MW coal-fired plant in Mindanao that runs 24/7. The figures below are an example, not a real plant's data.

On 15 February, at 02:30 on the night shift, a conveyor belt fault stops coal feed for a short time. The crew logs the start, the end and the cause. That one entry is a row of the outage history that EAF and EFOR come from.

At the end of the quarter, the reliability engineer works from that log. Say EAF comes out at 85 percent. Then the unit could run at full output for 85 percent of the quarter. Say EFOR comes out at 5 percent.

Then the unit had about a 5 percent chance of a forced outage. That counts only the hours the grid wanted it. That is a chance over demanded time. It is not the energy the plant failed to sell.

The log also shows which causes dominate. If conveyor faults lead the list, the next planned outage should fix them first.

## Conclusion and Future Directions

The practical next step is narrow. Log every outage with its cause, its start and its end. EAF and EFOR are just arithmetic on that log. A plant that does this monthly stops guessing at its own availability.

Then read NCF against the log. Work out how much of the shortfall came from maintenance and how much from dispatch. That tells you which part of the gap is yours to close.

Prediction comes after the record, never before it. A plant with a full outage log can trend its EAF quarter on quarter. Then it can move maintenance scope where the outages actually come from.

**Open the tool:** this guide leads to WorkHive's Analytics Report. It prints the period's MTBF, failure count and PM compliance from your records. It is free at the worker tier.

## Frequently asked questions

### What is EAF and how is it calculated?

EAF stands for Equivalent Availability Factor. EAF = (available hours - equivalent derated hours) / period hours. Available hours already leave out every outage. Over a full year, the period is 8,760 hours.

### How does WorkHive Analytics compute reliability metrics?

Analytics reports MTBF, MTTR, OEE and PM compliance from your logbook and PM records. It does not compute EAF, EFOR or NCF. It holds the outage log those indices are built from.

### What are the ERC reporting requirements for power plants?

ERC Resolution 23, Series of 2026 covers plants of 5 MW or more. The ERC assesses each unit once a year through the GRMS, and companies file a five-year planned outage schedule by 30 April.

### What is the significance of heat rate in power plant operations?

Heat rate is a measure of a power plant's efficiency. A lower heat rate indicates better efficiency and lower fuel costs. In the Philippines, heat rate is an important metric for optimizing power plant performance.

### How can I improve my power plant's reliability?

Improving power plant reliability requires a combination of effective maintenance, efficient operations, and data-driven decision-making. By tracking key reliability metrics and implementing best practices, power plant operators can improve overall performance.

### What does WorkHive Analytics do for a power plant?

It keeps the outage log complete, with each outage's cause, start and end, and it reports MTBF, MTTR, OEE and PM compliance. Your engineer computes the ERC indices from that log.

**[Keep the outage log behind EAF and EFOR](https://workhiveph.com/analytics.html)**. Analytics reports MTBF, MTTR, OEE and PM compliance from the same records. It is free, and you need no sensors to start. You still compute the ERC indices yourself.

## Sources

- [Energy Regulatory Commission (ERC)](https://www.erc.gov.ph/), **Resolution No. 23, Series of 2026: Revised Rules on the Reliability of Power Plants** (adopted 17 July 2026; annual GRMS assessment, five-year outage schedules due 30 April, applies at 5 MW and above).
- [Energy Regulatory Commission (ERC)](https://www.erc.gov.ph/), **Reliability Performance Indices and Equivalent Unplanned Outage Days Per Year for Generating Units** (the predecessor indices).
- Department of Labor and Employment. (2019). Occupational Safety and Health Standards.
- IIEE. (2017). Code of Practice for Electrical Safety.
- ISO. (2016). ISO 14224:2016 Petroleum, Petrochemical and Natural Gas Industries - Reliability, Availability and Maintainability (RAM) Data Exchange.
- SMRP. (2019). CMRP Body of Knowledge.

<!-- md-twin source-sha: 3480f29ee9e90179 -->
