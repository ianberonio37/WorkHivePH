# How to reduce unplanned equipment downtime

> A four-step, evidence-based path to cutting unplanned downtime: measure it by cause, fix the recurring few at root cause, hold PM compliance above 90%, and monitor the critical assets.

Source: https://workhiveph.com/learn/reduce-unplanned-downtime-guide/

By WorkHive Editorial Team · Updated 2026-08-05 · 8 min read

Cut unplanned downtime in four steps, in this order: **(1) measure it by cause** so you know what actually stops the line, **(2) fix the recurring few at root cause** instead of repeatedly restoring them, **(3) hold PM compliance above the SMRP benchmark of 90%**, and **(4) add condition monitoring to the critical assets only**. Most plants find their downtime hours concentrated in a small minority of assets, which is why measurement comes first, and preventive maintenance done on schedule runs **12-18% cheaper** than the reactive repair it replaces. Programmes that follow this order typically report a **15 to 25% reduction in unplanned downtime by month 18**.

## Why downtime persists in most plants

Unplanned downtime rarely persists because nobody is working hard. It persists because the work is aimed by memory rather than by data. The senior mechanic knows which machine is “always a problem,” so attention flows there, but nobody can say how many hours it actually cost last quarter, or whether it was one failure mode or six.

Three patterns keep it in place: failures get restored but never diagnosed, so the same one returns; preventive work slips quietly because nothing chases it; and the plant has no downtime record, so improvement cannot be proven and therefore cannot be funded.

## Step 1: measure downtime by cause

You cannot Pareto what you have not recorded. Capture, for every stoppage: the asset, the start and end time, and the cause. That is enough to rank losses. The discipline that makes it survivable is capturing it *at the asset, when it happens*: see [how to start a digital logbook](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/).

After four weeks you will have a ranked list, and it is almost always lopsided: a small set of assets and failure modes accounts for most of the hours. That list is your work order for the next quarter. Track the result with the metrics in the [maintenance metrics guide](https://workhiveph.com/learn/maintenance-metrics-reliability-guide/).

## Step 2: fix the recurring few at root cause

Restoring a machine is not the same as fixing it. For each top failure mode, ask what condition produced it: lubrication, alignment, contamination, operating outside design, or a deferred PM. [FMEA](https://workhiveph.com/learn/fmea-worked-example-philippine-bottling-line/) gives a structured way to rank by risk, and [RCM](https://workhiveph.com/learn/reliability-centered-maintenance-philippine-plants/) picks the right strategy per mode instead of applying the same PM to everything.

The test of a root-cause fix is simple: the interval to the next identical failure gets longer. If MTBF is flat, the cause was not addressed.

## Step 3: hold PM compliance above 90%

PM compliance is the leading indicator: it moves before MTBF does. The SMRP benchmark is at least **90%** of preventive tasks completed on time, and **95%+** for critical assets. “On time” has a precise definition worth knowing: completed by the due date plus 20% of the task's own frequency, capped at 28 days, so a monthly PM has roughly a six-day window, not a whole month. Below 80% the programme is not functioning; below 90% it is not protective.

Two rules make it stick: schedule work the crew can actually do (an over-ambitious plan produces 40% compliance and cynicism), and make overdue work visible to a named owner. Start from [free PM checklist templates](https://workhiveph.com/learn/free-pm-checklist-templates/) rather than a blank sheet.

## Step 4: monitor the critical assets only

Condition monitoring is where plants overspend first and benefit last. Applied to the critical few from step 1, it catches failures before they stop the line; applied everywhere, it produces alerts nobody reads.

Start at the cheapest tier that answers a real question: phone-based vibration screening and thermography cover a lot of ground before any sensor purchase. See [predictive maintenance on a budget](https://workhiveph.com/learn/predictive-maintenance-on-a-budget-philippines/) and set bands using [ISO 10816 alert thresholds](https://workhiveph.com/learn/predictive-alert-thresholds-plants/).

## What to expect, and in what order

| Horizon | What changes |
| --- | --- |
| Month 1-2 | Downtime recorded by cause; the Pareto is visible for the first time |
| Month 3-6 | Top failure modes addressed at root cause; PM compliance climbing toward 90% |
| Month 6-12 | MTBF rising on treated assets; condition monitoring on the critical few |
| Month 12-18 | Typically 15-25% reduction in unplanned downtime; 35-50% in mature programmes |

The order matters more than the speed. Plants that buy sensors before they have a downtime record almost always end up with data they cannot act on.

## Frequently asked questions

### What causes most unplanned downtime?

In most plants the hours concentrate in a small minority of assets and a handful of repeating failure modes: commonly lubrication, misalignment, contamination, operating outside design conditions, and deferred preventive work. Recording downtime by cause for four weeks usually makes the concentration obvious.

### How much can unplanned downtime realistically be reduced?

Programmes that measure first, fix root causes, and hold PM compliance above 90% commonly report a 15 to 25% reduction in unplanned downtime by month 18, with mature programmes reaching 35 to 50%. Treat those as widely-reported industry ranges rather than a published standard: the figure that IS standardised is the SMRP PM-compliance benchmark of 90%.

### Is preventive maintenance actually cheaper than fixing breakdowns?

Yes, though the honest figure is smaller than the ratios often quoted. The US Department of Energy's O&M Best Practices Guide puts a preventive programme at roughly 12-18% cheaper than running reactive, and a predictive layer adds a further 8-12%. Facilities that lean heavily on reactive work can find savings opportunities above 30-40%. None of that counts lost production, expedited freight, or overtime.

### Do I need sensors to reduce downtime?

Not to start, and buying them first is the most common mistake. Measurement and PM discipline deliver the early gains; condition monitoring pays off once you know which assets are critical and which failure modes you are hunting.

### What is the single first step?

Record every stoppage with asset, duration and cause. Without that record you cannot rank losses, prove improvement, or justify spending, and improvement that cannot be proven does not get funded.

**[Open the PM Scheduler](https://workhiveph.com/pm-scheduler.html)**: the step after recording stoppages, where a due date chases someone instead of sitting in a column. Pair it with the [Logbook](https://workhiveph.com/logbook.html) that captures asset, duration and cause. Free at the worker tier, offline-first. [Join WorkHive](https://workhiveph.com/#join) first if you do not have a hive yet.

## Sources

- [SMRP](https://smrp.org/), **Best Practices Metrics, 6th Edition**: PM schedule compliance benchmark 90% (95%+ for critical assets); a PM counts as on time if completed by the due date + 20% of its frequency, capped at 28 days. Downtime-reduction ranges quoted here are widely-reported industry outcomes, not an SMRP-published figure.
- [US Department of Energy / PNNL](https://www.energy.gov/femp/articles/operations-and-maintenance-best-practices-guide-achieving-operational-efficiency), **Operations & Maintenance Best Practices Guide, Release 3.0** (preventive vs reactive cost savings: 12-18%; predictive adds 8-12%).
- [ISO 14224](https://www.iso.org/standard/64076.html), **Reliability and maintenance data collection**; ISO 10816-3 (vibration severity).
- Related: [Maintenance metrics guide](https://workhiveph.com/learn/maintenance-metrics-reliability-guide/) · [Predictive maintenance on a budget](https://workhiveph.com/learn/predictive-maintenance-on-a-budget-philippines/).

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: d2a22672d723fd03 -->
