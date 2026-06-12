# Reliability and availability — core definitions (shared reference)

*Paraphrased reference notes (license-clean). Vocabulary per ISO 14224 (reliability data),
IEC 60050-192 (dependability), and SMRP/EN 15341 metric definitions.*

## The vocabulary, precisely

- **MTBF — Mean Time Between Failures.** Average operating time between two consecutive
  failures of a *repairable* item: `MTBF = total operating time ÷ number of failures`. A
  measure of **reliability** (how seldom it fails). Note: "between" implies repairable;
  for non-repairable items use **MTTF** (Mean Time To Failure).
- **MTTR — Mean Time To Repair.** Average time to restore a failed item to service,
  including diagnosis, repair, and verification: `MTTR = total repair time ÷ number of
  repairs`. A measure of **maintainability** (how fast you recover). Lower is better.
- **Failure rate (λ).** Failures per unit of operating time; for a constant-rate period,
  `λ = 1 ÷ MTBF`.
- **Availability (inherent).** The fraction of time an asset is able to perform its
  function: `A = MTBF ÷ (MTBF + MTTR)`. Availability rises by failing less often (higher
  MTBF) *or* recovering faster (lower MTTR) — two different levers.

## OEE vs availability — do not confuse them

- **Availability** above is a *reliability* concept (uptime ratio from MTBF/MTTR).
- **OEE — Overall Equipment Effectiveness** is a *productivity* concept:
  `OEE = Availability × Performance × Quality`, where this Availability is the
  loading-time-based uptime used in OEE accounting. World-class OEE is often cited
  around **85%**. OEE measures how effectively equipment runs when scheduled; it is not
  the same as the inherent availability from MTBF/MTTR. Keep the two separate in any
  report.

## The bathtub curve

Failure rate over a population's life often follows a bathtub shape: **infant mortality**
(early failures from defects/installation, falling rate), **useful life** (low, roughly
constant random-failure rate), and **wear-out** (rising rate from fatigue/erosion). The
strategy differs by region: burn-in and precision installation kill infant mortality;
condition monitoring manages the useful-life random failures; scheduled
restoration/replacement addresses wear-out. (Note: many real components do not show a
dominant wear-out region — an RCM insight — so age-based replacement is not always valid.)

## Why definitions matter

These terms drive next-due dates, compliance numbers, and dashboards across the platform.
Getting MTBF (reliability) vs MTTR (maintainability) vs availability vs OEE (productivity)
straight is the difference between a report that informs a decision and one that misleads
it. When in doubt, state the formula you used.
