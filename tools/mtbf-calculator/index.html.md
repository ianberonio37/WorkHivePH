# MTBF & MTTR Calculator

> The MTBF & MTTR Calculator computes Mean Time Between Failures, Mean Time To Repair, and the availability they produce together. Free online, with a worked example. Built for Philippine plants by WorkHive.

Source: https://workhiveph.com/tools/mtbf-calculator/

**The MTBF & MTTR Calculator computes Mean Time Between Failures, Mean Time To Repair, and the availability they produce together. Example: for a pump that ran 4,000 hours, failed 5 times, and took 40 hours of repair in total, MTBF = 800 h, MTTR = 8 h, Availability = 99 %, Failures = 5 (per ISO 14224 | IEC 60050-192 | SMRP).**

## How it works

MTBF = operating hours / number of failures. MTTR = total repair time / number of repairs. Availability = MTBF / (MTBF + MTTR). For the example: MTBF = 4000/5 = 800 h, MTTR = 40/5 = 8 h, Availability = 800/808 = 99.0%.

## Worked example (Reliability & Metrics)

Inputs: a pump that ran 4,000 hours, failed 5 times, and took 40 hours of repair in total.

| Result | Value |
| --- | --- |
| MTBF | 800 h |
| MTTR | 8 h |
| Availability | 99 % |
| Failures | 5 |

Computed live by WorkHive's calculation engine; standard: ISO 14224 | IEC 60050-192 | SMRP.

## How to use this calculator

1. Enter the figures for the duty you are sizing — the worked example below uses a pump that ran 4,000 hours, failed 5 times, and took 40 hours of repair in total.
2. The calculator returns MTBF, MTTR, Availability, Failures, computed per ISO 14224 | IEC 60050-192 | SMRP.
3. Check the worked example to confirm the method matches how you would do it by hand, then run your own numbers in the interactive tool.

## FAQ

### How do you calculate MTBF?

Divide total operating hours by the number of failures in that period. A pump that ran 4,000 hours and failed 5 times has an MTBF of 800 hours.

### How do you calculate MTTR?

Divide total repair time by the number of repairs. Five repairs totalling 40 hours gives an MTTR of 8 hours.

### What is the difference between MTBF and MTTR?

MTBF measures reliability — how long the asset runs before failing. MTTR measures maintainability — how long it takes to restore. You raise MTBF with better preventive maintenance and root-cause fixes; you lower MTTR with spares availability and standard work.

### How do MTBF and MTTR give availability?

Availability = MTBF / (MTBF + MTTR). With MTBF 800 h and MTTR 8 h, availability is 99.0%. That figure is also what feeds the availability factor inside OEE.

## Run it on your own numbers

[Open the interactive MTBF & MTTR Calculator in WorkHive](https://workhiveph.com/engineering-design.html) — free, no sign-up needed for the calculators.

## Related calculators

- [Free Engineering Calculators for Philippine Plants](https://workhiveph.com/learn/free-engineering-calculators-philippine-plants/) (pillar)
- [OEE Calculator](https://workhiveph.com/tools/oee-calculator/)
- [MTBF vs MTTR for supervisors](https://workhiveph.com/learn/mtbf-vs-mttr-for-supervisors/)

<!-- md-twin source-sha: 82e4be6e4a6b8678 -->
