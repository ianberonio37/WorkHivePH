# Spare parts inventory for Philippine plants (ABC, FIFO, reorder points)

> A practical spare parts inventory guide for Philippine plants: ABC analysis, FIFO discipline, reorder-point math, and the 4 storeroom failures that cause 40 percent of MTTR.

Source: https://workhiveph.com/learn/spare-parts-inventory-philippine-plants/

Inventory · ABC · FIFO · Reorder

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 10 Nov 2026
·
10 min read

**Short answer:** A working spare parts store needs three things. First, ABC classes, so your time goes to the 20 percent of parts that hold 80 percent of value. Second, first in, first out (FIFO) on every shelf, so parts do not age unseen. Third, reorder points built from real usage, so critical parts arrive in time. Done well, this takes 20 to 25 percent off MTTR. Waiting for the part is 40 to 50 percent of it, and a stocked shelf halves that.

Who this is for

- Storekeepers and inventory clerks
- Maintenance supervisors and planners
- Procurement and purchasing staff
- Reliability engineers
- Plant and operations managers
- Suppliers managing consignment stock
- New graduates rotating through MRO

Run your spare parts store on three habits: ABC classes, FIFO on every shelf, and reorder points from real usage. The ABC and reorder methods follow APICS/ASCM CPIM. It matters most in Philippine plants. There, 40 to 50 percent of MTTR (mean time to repair) is waiting for parts. A well-run storeroom cuts that.

## Why most Philippine storerooms fail

Walk any Philippine plant storeroom and you will see the same four failures:

- **Phantom inventory.** The bin card says 12 bearings; the shelf has 3. Someone used the other 9 and never wrote them off. Or the store issued them without a withdrawal slip. Or they sit in another technician's toolbox. Phantom inventory is the #1 reason a planned repair stops mid-job.
- **Dead inventory.** 30 to 50 percent of SKUs have not moved in 12+ months. Some are obsolete, because the plant retired their asset 4 years ago. Some come from over-ordering. We panic-bought in a 2022 supply crunch and never used the rest.
- **Wrong-shelf inventory.** The part is there, but the label is wrong. Or it sits in the bin for the old SKU code. Or it moved during a storeroom shake-up in 2024. The technician spends 90 minutes looking for it.
- **Expired inventory.** Rubber O-rings, gaskets, greases, sealants, and batteries all have shelf lives of 1 to 3 years. After that they fail on installation. A storeroom that does not track date-received installs degraded parts as if they were new.

None of these failures are about the storeroom keeper being lazy. They come from three missing habits, which the rest of this guide teaches: ABC classes, FIFO and reorder points. With those three, the storeroom becomes a reliability asset. Without them, it becomes a place where ₱8M of capital quietly rots.

## ABC analysis explained with a worked example

ABC analysis is a Pareto sort applied to spare parts. Sort every SKU by its yearly spend. That is the unit cost times how many you use a year. The top 20 percent of SKUs will almost always account for 70 to 85 percent of total spend.

Those are A items. The next 30 percent are B items (about 15 percent of spend). The remaining 50 percent are C items (about 5 percent of spend).

Why this matters: each tier gets its own controls. Equal time on a ₱180,000 motor and a ₱25 cable tie wastes effort.

| Tier | % of SKUs | % of value | Cycle count | Reorder review | Storage |
| --- | --- | --- | --- | --- | --- |
| **A** | ~20% | ~70-85% | Monthly | Daily auto-trigger | Locked or controlled |
| **B** | ~30% | ~10-15% | Quarterly | Weekly review | Open bins, labelled |
| **C** | ~50% | ~5% | Annual | Visual ("bin is half") | Open bins |

Most Philippine plants have never done this sort. The first time they do it, they find 3 to 5 dead SKUs in the A tier. The asset is gone, but the plant still holds its spare.

They also find 30 to 50 dead SKUs in the C tier. Those are write-offs that should not count toward stock value. The first ABC analysis usually finds ₱500K to ₱2M of paper stock you can remove.

## FIFO discipline (it is paint, not software)

FIFO (First In First Out) means the oldest unit on the shelf gets picked first. It is critical for any spare with a shelf life:

- Rubber O-rings, gaskets, seals: 2 to 5 year shelf life
- Greases and lubricants: 2 to 3 years from manufacture
- Batteries: 1 to 3 years depending on chemistry
- Sealants and adhesives: 6 months to 2 years
- Filters with treated media: 1 to 2 years

The mistake most plants make is treating FIFO as a software feature. It is not. You enforce FIFO with paint on the shelf label. Every receipt gets its date received, in permanent marker, on the bag or box. The keeper picks from the oldest date first. Arrange the shelf left to right by date. No app required.

A tool that logs the date can show, each month, what expires in the next 60 days. WorkHive's Inventory does not keep that date. So the marker on the bag is your record.

## The reorder point formula

For A items, the reorder point is the stock level at which you raise a purchase order. The formula:

Average Daily Usage and Lead Time both come from your past records, not guesswork. If your digital logbook lists the parts on each job, you already have the data. If you do not, this is one more reason to start a digital logbook (see [our 12-week rollout guide](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/)).

Safety Stock covers usage variability and supplier delays. A common rule:

For B items, a regular review is enough. Check them each week and order back up to a target level. For C items, visual review at the bin is enough: when the bin looks half-full, order more.

## Worked example: a bearing in a Cabuyao plant

A food plant in Cabuyao uses one 6205-2RS deep-groove bearing on 14 conveyor motors. The supervisor wants to set a reorder point.

From the WorkHive Logbook, the past 12 months show:

- 156 bearings used across 14 motors (average 13 per month, 0.43 per day)
- Maximum monthly usage: 22 (peak month was December packaging push)
- Supplier lead time: 21 days (local supplier in Quezon City)

Plug into the formulas:

When the bin drops to 16, the PO triggers automatically. The 21-day lead time gets covered, plus a safety buffer for the December peak. The plant usually holds 30 to 40 of these at month-end. That is above the safety stock but below the maximum that EOQ sets.

The tool this guide is about

### WorkHive Inventory holds the reorder point and deducts parts as you log the job

Each item carries a reorder point. Low-stock and critical-low flags go from there into Alert Hub. So the trigger this guide describes is the one the product uses. The counting is automatic too. Save a logbook entry with its parts, and it takes them off the shelf count. Each move also gets its own ledger row.

So you keep no second stock book. The Inventory page does not classify for you. It computes no ABC class and keeps no date received for FIFO. So the sort above and the marker-date rotation stay yours. Use the reorder point to hold the A items. Review the rest on this guide's cycle. Free at the worker tier forever.

No hive yet? [Join WorkHive](https://workhiveph.com/?signup=1) first (free, takes 30 seconds).

## Why this is the cheapest MTTR fix you can buy

Our [MTBF vs MTTR guide](https://workhiveph.com/learn/mtbf-vs-mttr-for-supervisors/) showed a conveyor on a Pampanga bottling line. Its MTTR was 3.17 hours, and 42 percent of that was waiting for the part.

That pattern is common. In a plant without a disciplined store, much of the MTTR is waiting for parts, not work. That is why you usually fix the reorder point, not the technician. Measure the split on your own repairs before you size the fix.

So about 25 minutes of every repair hour went to waiting for parts. Compare cost-per-hour saved:

- **Hiring a second electrician for a 24/7 shift** to cut waiting for skills: PHP 600,000 to PHP 900,000 a year.
- **Buying a CMMS (maintenance software)** to cut admin time: PHP 200,000 to PHP 1.2M a year in licenses.
- **Fixing the storeroom** with ABC, FIFO and reorder points: usually free. It takes one supervisor weekend, then 30 minutes a month.

The storeroom fix is almost always the cheapest hour you can take off MTTR. It is also the one most plants put off because nobody owns it. The maintenance supervisor thinks it is the storeroom keeper's job.

The keeper thinks it is procurement's job. Procurement thinks it is the supervisor's job. The fix: make the maintenance supervisor the owner of MRO stock health. Give it 30 minutes a month, tied to the 5S walk you already do.

## Common Philippine plant mistakes

- **Treating MRO inventory as a procurement metric.** Procurement cares about price-per-PO; maintenance cares about availability. The two pull in opposite directions. MRO stock health is a maintenance metric. It goes on the maintenance KPI sheet, not on procurement's.
- **Bulk-buying to get unit discount.** A 15 percent discount on a 6-month supply of an item with 24-month shelf life is real money. The same discount on an item with 6-month shelf life is a guaranteed write-off in month 7.
- **No write-off discipline.** If a technician draws a part and does not use it, they should return it. The keeper re-shelves it with a "previously issued" note. In practice, technicians keep it in their toolbox, and the system shows the part as still on the shelf. Quarterly reconciliation between bin card and shelf catches this.
- **One reorder point set in 2019.** Usage patterns change. Redo the ABC classes once a year. Redo the reorder points on A items every quarter.
- **No supplier diversification on A items.** Say your only supplier for a critical bearing has a 60-day lead time from Manila. If they strike, your plant stops. The rule is two suppliers for every A item, even if one costs more.

**The bigger picture:** Good MRO stock cuts MTTR, since less time goes to waiting for parts. It lifts MTBF, since no aged parts go in. It lifts OEE through less unplanned downtime. And it shows on the bottom line.

It is one of the best returns a supervisor can get. It is also one of the easiest to put off. Start with the storeroom walk-through and the first ABC sort. Most plants find the payback in the first 90 days.

## Frequently asked questions

### What is ABC analysis in spare parts inventory?

ABC analysis classifies parts into three tiers by annual usage value. A items (top 20 percent by value) typically drive 80 percent of inventory spend and get the tightest controls: cycle counts every month, reorder points monitored daily, locked storage. B items get quarterly counts and weekly review. C items get annual counts and reorder-when-you-see-it. The point is to spend management time where it pays back, not equally across 1,000 SKUs.

### What is the reorder point formula?

Reorder Point equals Average Daily Usage times Lead Time in Days, plus Safety Stock. Example: a bearing used 3 per week (0.43 per day) from a supplier with a 21-day lead time, peaking at 22 a month, gives a safety stock of (0.73 minus 0.43) times 21, which rounds up to 7 - so the reorder point is 0.43 times 21 plus 7, which is 16 units. When the bin drops to 16, the PO triggers automatically. Derive the safety stock from your own peak rather than assuming a round number. Get the lead time and usage from the WorkHive Logbook history; do not guess.

### Why is FIFO important for spare parts?

FIFO (First In First Out) matters for any spare with a shelf life: greases, oils, gaskets, O-rings, batteries, sealants, adhesives, and any chemical. A rubber O-ring that has been on the shelf for 4 years often fails on installation because the rubber has cured. The replacement looks identical to the one you bought yesterday but performs differently. FIFO is enforced with paint on the storeroom shelf labels (date received), not with software.

### How much inventory should we hold?

Industry rule of thumb: 1 to 3 percent of asset replacement value for a typical Philippine plant. A plant with PHP 500M of equipment should target PHP 5M to PHP 15M of MRO inventory. Below 1 percent and you starve maintenance of parts; above 3 percent and you are carrying obsolete stock. The split matters more than the total: 60 to 70 percent of inventory value should be in A items even though they are only 20 percent of SKUs.

### Why does spare parts inventory affect MTTR?

Because the clock does not stop when the fault is found. The technician has diagnosed it and knows the fix, and then waits - the part is not on the shelf, or is on the wrong shelf, or has expired. That waiting is counted in MTTR exactly like the repair is, and it is the part of MTTR a storeroom controls: FIFO discipline and an accurate reorder point shorten it without changing the repair at all. Time your own next three breakdowns in two halves - diagnosis to part-in-hand, and part-in-hand to running - and you will know which half your plant should spend on. The cheapest hour of MTTR you can buy is usually good inventory management.

### Do I need a paid inventory system?

No, not for plants with fewer than 1,000 SKUs. A clean spreadsheet or the free WorkHive Inventory tool handles up to about 2,000 SKUs with proper categories, reorder points, and history. Paid systems (SAP MM, IBM Maximo MRO) add value at multi-site scale (5,000+ SKUs across multiple plants) but they do not improve discipline; they enforce a discipline you already have. Most Philippine plants buy the paid system before they have the discipline and end up with an expensive shelf-decoration project.

## Sources

- Society for Maintenance and Reliability Professionals (SMRP), **Best Practices, 5th Edition**, 2017. MRO inventory KPIs and benchmark targets.
- ISO 55001:2014, **Asset management: Management systems requirements**. Includes MRO inventory as a critical asset management input.
- APICS / ASCM, **CPIM Body of Knowledge**. Source for ABC classification methodology and reorder-point formulas.
- WorkHive platform positioning, "Four Gaps One Hive": Execution, Skills, Intelligence, Marketplace. [workhiveph.com](https://workhiveph.com/)
- Related WorkHive guides: [digital logbook rollout](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/) · [MTBF vs MTTR explained](https://workhiveph.com/learn/mtbf-vs-mttr-for-supervisors/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: 0309d18b08d22f32 -->
