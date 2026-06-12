# Reliability economics — cost of downtime and life-cycle cost (strategic reference)

*Paraphrased reference notes (license-clean). See ISO 55000 (asset management) and
IEC 60300-3-3 (life-cycle costing).*

## Make the business case in money, not metrics

A maintenance strategy wins budget when it is framed as economics. Two numbers do most
of the work: the **cost of downtime** and the **life-cycle cost** of the asset.

## Cost of downtime

The true cost of an unplanned stoppage is almost always larger than the repair bill.
Account for all of it:

- **Lost production / lost throughput** — units not made × contribution margin per unit
  (the dominant term in most plants).
- **Idle labour** — operators and crew paid while the line is down.
- **Restart and scrap** — startup waste, off-spec product, quality giveaways.
- **Expediting** — premium freight and overtime to recover the schedule.
- **Knock-on costs** — missed shipments, penalties, lost orders, reputation.

Expressed as a **rate (cost per hour of downtime)**, this number sizes the prize. If a
line loses ₱50,000 per hour and a failure causes 8 hours down, that single event costs
₱400,000 — which is the budget you are protecting with reliability work. Reactive plants
suffer this repeatedly and invisibly; the strategist's job is to make it visible.

## Life-cycle cost (LCC)

LCC totals the cost of owning an asset across its life, not just its purchase price:

```
  LCC = Acquisition + Operation (energy) + Maintenance + Downtime + Disposal
```

The purchase price is usually a small fraction of LCC; **energy and maintenance/downtime
dominate** over a 15–20 year life. This reframes decisions: a cheaper pump that is
inefficient and unreliable can cost far more than a premium one. Use LCC to justify
reliability investments (better components, precision installation, condition monitoring)
by the downtime and energy they avoid over the life, not the up-front spend.

## The strategist's rule

Spend on reliability up to the point where the marginal cost of more prevention equals
the marginal downtime+failure cost it avoids. Below that point, prevention is pure
profit; reactive maintenance is the most expensive strategy because it pays the full
cost-of-downtime every time. Sequence investment to the failures with the highest
(consequence × likelihood), i.e. by criticality.
