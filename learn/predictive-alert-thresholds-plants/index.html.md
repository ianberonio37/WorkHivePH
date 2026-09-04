# Predictive alert thresholds (practical guide for industrial plants)

> How to set predictive alert thresholds that actually get acted on, not silenced. Covers escalation rules, alert-fatigue prevention, vibration and temperature thresholds, and the 3-tier alert architecture that works in Philippine plants.

Source: https://workhiveph.com/learn/predictive-alert-thresholds-plants/

Alert Hub · Thresholds + escalation

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 24 Aug 2026
·
7 min read

**Short answer:** A predictive alert that gets silenced after 3 weeks is worse than no alert. The pattern that works in Philippine plants: 3 alert tiers (Notice, Warning, Action) with explicit escalation rules, ISO 10816-compliant vibration thresholds adjusted for asset class, named owners per tier, and a weekly alert-fatigue review that retires or retunes any alert silenced more than 3 times. Plants that follow this discipline catch 30 to 40 percent of developing failures before they hit; plants that buy a sensor and never tune the thresholds get expensive shelf decoration.

Who this is for

- Reliability and maintenance engineers
- Shift supervisors managing alerts
- Operators on PdM routes
- Plant managers reviewing alert ROI
- Sensor vendors and integrators
- Contractors on condition monitoring
- New engineering graduates learning PdM

Part of the [maintenance metrics guide: OEE, MTBF, MTTR and reliability](https://workhiveph.com/learn/maintenance-metrics-reliability-guide/): the hub that connects every reliability metric and shows how they chain together.

## Why threshold design matters more than sensor count

Most predictive maintenance programs in Philippine plants fail at the threshold layer, not the sensor layer. The plant buys good sensors, the sensors generate accurate data, and the alerts get silenced because every alert is treated as critical or because the alerts cry wolf and the team learns to ignore them.

Threshold design is the difference. A well-tuned threshold fires once a quarter, gets acted on, and prevents a real failure. A poorly-tuned threshold fires daily, gets dismissed, and trains the team to ignore the sensor. The sensor is the easy part; the threshold tuning is the discipline.

## The 3-tier alert architecture

| Tier | Meaning | Response | Owner |
| --- | --- | --- | --- |
| **Notice** | Reading is rising above baseline but still within normal | Log in WorkHive Logbook for trend tracking; no action this shift | Operator |
| **Warning** | Reading crossed first action threshold; degradation in progress | Schedule investigation within 7 days; trend daily | Maintenance supervisor |
| **Action** | Reading crossed second action threshold; failure imminent | Stop or de-rate asset; investigate this shift | Reliability engineer + supervisor on call |

Three tiers, not seven. Many sensor vendor dashboards ship with 5 to 7 alert levels which look sophisticated and fail in practice. Three tiers map to three distinct human responses: keep watching, plan a check, act now.

## ISO 10816 vibration thresholds by asset class

ISO 10816 defines vibration severity zones for industrial machinery. The standard is the right starting point; tune from there based on your plant's history.

| Asset class | Zone A (Good) | Zone B (Acceptable) | Zone C (Unsatisfactory) | Zone D (Unacceptable) |
| --- | --- | --- | --- | --- |
| Class I (small motors below 15 kW) | < 0.71 mm/s | 0.71 to 1.8 | 1.8 to 4.5 | > 4.5 |
| Class II (medium motors 15 to 75 kW) | < 1.12 | 1.12 to 2.8 | 2.8 to 7.1 | > 7.1 |
| Class III (large rigid foundation) | < 1.8 | 1.8 to 4.5 | 4.5 to 11.2 | > 11.2 |
| Class IV (large flexible foundation) | < 2.8 | 2.8 to 7.1 | 7.1 to 18.0 | > 18.0 |

Map to the 3-tier system: Notice fires at the Zone A to B transition, Warning at the B to C transition, Action at the C to D transition.

## Temperature alert design

Bearing temperature is the cleanest predictive signal for rotating equipment after vibration. Indicative thresholds for an ambient 30 deg C Philippine plant:

- Notice: bearing temperature 5 to 10 deg C above the running baseline (which itself is measured during commissioning, not assumed)
- Warning: 10 to 20 deg C above baseline, or absolute above 75 deg C
- Action: more than 20 deg C above baseline, or absolute above 85 deg C, or rate of rise more than 5 deg C in 1 hour

Always tune the absolute thresholds to your asset's OEM specification; the rate-of-rise threshold is the one that catches sudden failures the OEM did not anticipate.

## Escalation rules and named owners

Every alert tier must have a named owner. Unowned alerts get silenced. The pattern that works:

- **Notice alerts** go to the operator on duty for the asset. Logged in WorkHive Logbook automatically. If no action recorded in 24 hours, escalates to Warning.
- **Warning alerts** go to the maintenance supervisor in addition to the operator. If no action recorded in 72 hours, escalates to Action.
- **Action alerts** go to the reliability engineer and the supervisor on call simultaneously. Phone call (not just notification) within 15 minutes is the SLA.

## Preventing alert fatigue with weekly review

The single most important discipline: weekly review of any alert silenced more than 3 times. If a Notice alert keeps firing without action, one of three things is true:

- The threshold is too tight (false alarms); retune to a higher value
- The asset is genuinely degraded; promote the alert to Warning
- The asset is being run outside design conditions; root-cause that, not the alert

15 minutes per week with the reliability engineer and the operator. Acknowledge and resolve the alert in WorkHive Alert Hub, then document the retuning reasoning in a logbook entry. This single discipline is the difference between a PdM program that compounds and one that dies in year 1.

The tool this guide is about

#### WorkHive Alert Hub manages the threshold + escalation discipline

Define 3-tier thresholds per asset, name owners per tier, configure escalation timing, get the weekly silenced-alert report. Integrates with Predictive Maintenance, Logbook, and Asset Hub. Free at the worker tier; phone-call escalation via SMS/voice gateway unlocks at Stage 3.

No hive yet? [Join WorkHive](https://workhiveph.com/?signup=1) first (free, takes 30 seconds).

## Frequently asked questions

### What are the right number of alert tiers?

Three: Notice (log it, keep watching), Warning (plan an investigation within a week), Action (stop or de-rate this shift). Five to seven tiers, which some sensor vendor dashboards ship with, look sophisticated but fail in practice because humans cannot reliably distinguish more than three response modes.

### Where do ISO 10816 vibration thresholds fit in?

ISO 10816 defines vibration severity zones (A Good, B Acceptable, C Unsatisfactory, D Unacceptable) by asset class. Map them to your tiers: Notice fires at A to B transition, Warning at B to C, Action at C to D. Always use the asset-class-specific thresholds (Class I to IV) rather than a single plant-wide value.

### How do I prevent alert fatigue?

Weekly review of any alert silenced more than 3 times. Retune the threshold (too tight), promote it (asset really is degraded), or root-cause why the asset runs outside design (operating-condition problem, not alert problem). 15 minutes per week with the reliability engineer and operator. Plants that skip this discipline have their PdM programs die within 12 months.

### What is a reasonable alert volume per asset per month?

Tier 1 critical assets: 1 to 3 Notice alerts per month, 0 to 1 Warning, almost zero Action. Tier 2 high assets: 0 to 1 Notice per month. Tier 3 medium: should not be alerting routinely; investigate any pattern. Tier 4 low: usually no alerts (run to failure). If you are seeing 10+ alerts per month per Tier 1 asset, your thresholds are too tight.

### Who should own each alert tier?

Notice alerts: operator on duty for the asset (logged automatically, no immediate response required). Warning: maintenance supervisor in addition to operator. Action: reliability engineer plus supervisor on call. The owner is named in WorkHive Alert Hub for accountability; unowned alerts get silenced because nobody owns the response.

### Should I use vendor-default thresholds or set my own?

Start with vendor defaults (or ISO 10816 for vibration), but tune within 90 days based on your plant's actual baseline. Vendor defaults assume a generic plant; your assets have specific running conditions (Philippine ambient temperature, your power quality, your duty cycle) that shift the thresholds. Plants that never tune from defaults get either too many alerts or too few.

## Sources

- ISO 10816, **Mechanical vibration: Evaluation of machine vibration by measurements on non-rotating parts**, all parts.
- ISO 20816, **Mechanical vibration: Measurement and evaluation of machine vibration** (successor to ISO 10816).
- API 670, **Machinery Protection Systems**. Source for absolute vibration shutdown thresholds on rotating equipment.
- WorkHive platform positioning, "Four Gaps One Hive" with Alert Hub as the Intelligence-gap accelerator. [workhiveph.com](https://workhiveph.com/)
- Related WorkHive guides: [Predictive maintenance on a budget](https://workhiveph.com/learn/predictive-maintenance-on-a-budget-philippines/) · [MTBF vs MTTR](https://workhiveph.com/learn/mtbf-vs-mttr-for-supervisors/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: bfb662019a4da3fb -->
