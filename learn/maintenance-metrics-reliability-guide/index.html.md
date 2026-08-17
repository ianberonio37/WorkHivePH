# Maintenance metrics: OEE, MTBF, MTTR & reliability, explained for Philippine plants

> The five maintenance metrics every Philippine plant should track — OEE, MTBF, MTTR, availability, and PM compliance — with formulas, worked examples, and free calculators.

Source: https://workhiveph.com/learn/maintenance-metrics-reliability-guide/

By WorkHive Editorial Team · Updated 2026-08-05 · 9 min read

The five metrics every Philippine plant should track are **OEE** (Overall Equipment Effectiveness = Availability × Performance × Quality; world-class is 85%), **MTBF** (Mean Time Between Failures = operating hours ÷ number of failures), **MTTR** (Mean Time To Repair = total repair time ÷ number of repairs), **Availability** (MTBF ÷ (MTBF + MTTR)), and **PM compliance** (PMs completed on time ÷ PMs scheduled; the SMRP benchmark is ≥90%). Together they turn “the line keeps breaking” into a number you can act on.

## Why maintenance metrics matter

Most Philippine plants run maintenance on memory and firefighting: the senior mechanic knows which pump is “always a problem,” and everyone reacts when a line stops. The trouble is that memory does not scale, does not transfer when the senior mechanic retires, and cannot be put in a budget request. Metrics fix that. A plant that measures reliability can say “this filler cost us 62 hours of downtime last quarter, and 80% of it was the same bearing” — a sentence that unlocks a purchase order.

Reliability metrics also standardise language across shifts and disciplines. When maintenance, production, and management all agree that availability means `MTBF ÷ (MTBF + MTTR)`, the morning meeting stops being an argument about whose fault the downtime was and starts being a decision about where to spend the next peso.

## OEE — Overall Equipment Effectiveness

**OEE = Availability × Performance × Quality.** It is the single number that captures how much saleable output a line actually produced versus its theoretical maximum. Worked example for a bottling line: available 90% of planned time, running at 95% of rated speed, producing 98% good bottles → OEE = 0.90 × 0.95 × 0.98 = **83.8%**. World-class is 85%; a typical plant sits at 40–60%, so the gap is usually enormous and cheap to close.

The trap is measuring only one factor. A line that looks 90% “available” but runs slow and scraps 5% of output is really at ~80% OEE. See the full method in [What is OEE and how to calculate it](https://workhiveph.com/learn/what-is-oee-how-to-calculate/), and read the four maturity stages in [the four phases of maintenance analytics](https://workhiveph.com/learn/four-phases-maintenance-analytics-philippine-plants/).

## MTBF and MTTR — the reliability pair

**MTBF** measures how *reliable* an asset is; **MTTR** measures how *maintainable* it is. A pump that runs 4,000 hours and fails 5 times has MTBF = 4,000 ÷ 5 = **800 hours**. If those five repairs took 40 hours total, MTTR = 40 ÷ 5 = **8 hours**. Push MTBF up with better PM and root-cause fixes; push MTTR down with spares availability, standard work, and good documentation.

The two are often confused, which leads to the wrong fix (buying spares when the real problem is repeat failures). The plain-language breakdown is in [MTBF vs MTTR for supervisors](https://workhiveph.com/learn/mtbf-vs-mttr-for-supervisors/).

## Availability and how the metrics chain together

**Availability = MTBF ÷ (MTBF + MTTR).** Using the pump above: 800 ÷ (800 + 8) = **99.0%**. Notice that availability is what OEE’s first factor comes from — the metrics are not separate scoreboards, they are one chain: reduce failures (MTBF ↑) and speed repairs (MTTR ↓), and availability, then OEE, then output all rise together.

| Metric | Formula | Good target |
| --- | --- | --- |
| OEE | Availability × Performance × Quality | ≥85% (world-class) |
| MTBF | Operating hours ÷ failures | Rising trend |
| MTTR | Repair time ÷ repairs | Falling trend |
| Availability | MTBF ÷ (MTBF + MTTR) | ≥95% |
| PM compliance | PMs on time ÷ PMs scheduled | ≥90% (SMRP) |

## PM compliance — the leading indicator

OEE, MTBF, and MTTR are *lagging* indicators: they tell you what already broke. **PM compliance** — the percentage of preventive tasks done on schedule — is the *leading* indicator that predicts them. The SMRP benchmark is ≥90% schedule compliance; plants that hold that line see MTBF climb within a quarter. Start with a real checklist, not a spreadsheet that nobody updates: [free PM checklist templates](https://workhiveph.com/learn/free-pm-checklist-templates/).

## Climbing the reliability ladder: RCM, FMEA, and predictive alerts

Once the basics are measured, the next rungs are analytical. **FMEA** (Failure Mode and Effects Analysis) ranks what to fix first by risk — see a full [FMEA worked example on a Philippine bottling line](https://workhiveph.com/learn/fmea-worked-example-philippine-bottling-line/). **RCM** (Reliability-Centered Maintenance) then decides the right strategy per failure mode: [RCM for Philippine plants](https://workhiveph.com/learn/reliability-centered-maintenance-philippine-plants/). Finally, **condition-based alert thresholds** catch failures before they happen — the ISO 10816 vibration bands and how to set them are in [predictive alert thresholds](https://workhiveph.com/learn/predictive-alert-thresholds-plants/).

## Free calculators and next steps

Turn the formulas into numbers with the free WorkHive calculators — each shows a worked example and works offline: [Bearing Life (L10)](https://workhiveph.com/tools/bearing-life-calculator/), [Vibration Isolation](https://workhiveph.com/tools/vibration-isolation-calculator/), and the full [engineering calculator suite](https://workhiveph.com/learn/free-engineering-calculators-philippine-plants/). To start recording the raw data these metrics need, begin with a [digital logbook](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/) — undocumented downtime cannot be measured, and unmeasured downtime never gets fixed.

## Frequently asked questions

### What is a good OEE for a Philippine plant?

85% is considered world-class OEE. Most plants start at 40 to 60%, so there is usually a large, low-cost gap to close by attacking availability losses first (unplanned downtime and changeovers), then speed losses, then quality losses.

### What is the difference between MTBF and MTTR?

MTBF (Mean Time Between Failures) measures reliability — how long an asset runs before it fails, calculated as operating hours divided by the number of failures. MTTR (Mean Time To Repair) measures maintainability — how long a repair takes, calculated as total repair time divided by the number of repairs. You raise MTBF with better PM; you lower MTTR with spares and standard work.

### How do I calculate availability?

Availability = MTBF divided by (MTBF + MTTR). For a pump with MTBF 800 hours and MTTR 8 hours, availability is 800 / 808 = 99.0%. This is the same availability figure that feeds the first factor of OEE.

### What PM compliance should I target?

The <a href="https://smrp.org/">Society for Maintenance and Reliability Professionals (SMRP)</a> benchmark is at least 90% schedule compliance — the percentage of preventive maintenance tasks completed on or before their due date. It is the leading indicator that drives MTBF and OEE upward.

### Do I need software to track these metrics?

No. You can start with a disciplined logbook and a checklist. The value is in consistent recording, not the tool. WorkHive is a free, offline-first platform that captures the downtime, repair, and PM data these metrics need without any subscription.

**[Track these metrics free in WorkHive Analytics](https://workhiveph.com/analytics.html)** — OEE, MTBF, MTTR and PM compliance from your own logbook data.

## Sources

- [Society for Maintenance and Reliability Professionals (SMRP)](https://smrp.org/), **Best Practices Metrics (5.4 PM Compliance, 5.1 OEE)**.
- [ISO 14224](https://www.iso.org/standard/64076.html), **Collection and exchange of reliability and maintenance data for equipment**.
- ISO 10816-3, **Mechanical vibration — evaluation of machine vibration**.
- Related WorkHive guides: [OEE](https://workhiveph.com/learn/what-is-oee-how-to-calculate/) · [MTBF vs MTTR](https://workhiveph.com/learn/mtbf-vs-mttr-for-supervisors/) · [RCM](https://workhiveph.com/learn/reliability-centered-maintenance-philippine-plants/).

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: ec6b5108169991e6 -->
