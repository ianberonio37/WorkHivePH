# KPI selection and asset criticality (strategic reference)

*Paraphrased reference notes (license-clean). Metric families per SMRP Best Practices;
criticality per ISO 55000 risk-based asset management.*

## Choosing KPIs — measure to decide, not to decorate

A dashboard full of metrics nobody acts on is waste. Pick a small set tied to decisions.
The SMRP body of knowledge groups maintenance-and-reliability metrics into five families:

1. **Business & economics** — maintenance cost as a % of RAV (replacement asset value),
   maintenance cost per unit produced, stocked-spares value.
2. **Reliability** — MTBF, MTTR, availability, failure rate, OEE.
3. **Work management** — PM compliance, planned vs reactive ratio, schedule compliance,
   backlog (in crew-weeks), wrench time.
4. **Equipment reliability** — by criticality class, recurring failures, bad actors.
5. **People / safety** — training/skills coverage, recordable incidents.

**Rules for a good KPI set:** lead with a few *outcome* metrics (availability, OEE,
maintenance cost/RAV) and pair each with a *driver* you can act on (PM compliance,
planned ratio, backlog). A KPI you cannot influence is a thermometer, not a lever.
Benchmark a metric against its own trend first, the industry second.

## Two starter KPIs for most plants

If a plant can track only two things to start: **PM compliance** (are we doing the
planned work?) and **planned-vs-reactive ratio** (are we ahead of failures or behind
them?). These two predict the reliability outcomes before the outcomes show up.

## Asset criticality — where to spend first

You cannot maintain everything equally; criticality decides the order. Rank each asset
by **risk = consequence × likelihood of failure**:

- **Consequence** spans safety, environment, production loss (cost of downtime),
  quality, and repair cost.
- **Likelihood** comes from condition, age, failure history, and duty.

Score each on a scale, plot on a **criticality matrix**, and band assets A/B/C (or
1–4). Then differentiate strategy by band:

- **Critical (A)** — proactive: condition monitoring, RCM-based PM, critical spares held,
  redundancy considered.
- **Essential (B)** — planned PM, moderate spares.
- **Non-critical (C)** — run-to-failure where the consequence is acceptable; don't waste
  PM effort here.

## The strategist's use

Criticality turns a limited budget into a sequence: protect the few assets whose failure
hurts most, run-to-failure the many that don't, and put the KPIs that drive that
behaviour (PM compliance, planned ratio, cost/RAV) on the wall. Spend on the next rung of
maturity, on the most critical assets, measured by a handful of decision-linked KPIs.
