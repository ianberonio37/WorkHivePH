# Spare parts inventory for Philippine plants (ABC, FIFO, reorder points)

> A practical spare parts inventory guide for Philippine plants: ABC analysis, FIFO discipline, reorder-point math, and the 4 storeroom failures that cause 40 percent of MTTR.

Source: https://workhiveph.com/learn/spare-parts-inventory-philippine-plants/

Inventory · ABC · FIFO · Reorder

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 24 Aug 2026
·
10 min read

**Short answer:** A working spare parts inventory in a Philippine plant needs three things: ABC classification so management time goes to the top 20 percent of SKUs that drive 80 percent of value, FIFO discipline on every shelf so shelf-life parts do not silently degrade, and reorder points calculated from real usage history so critical parts arrive before they are needed. Done well, this cuts MTTR by 20 to 40 percent because the part is on the shelf when the technician walks in.

Who this is for

- Storekeepers and inventory clerks
- Maintenance supervisors and planners
- Procurement and purchasing staff
- Reliability engineers
- Plant and operations managers
- Suppliers managing consignment stock
- New graduates rotating through MRO

Run your spare parts inventory on three disciplines: ABC classification, FIFO on every shelf, and reorder points built from real usage history (ABC and reorder points follow APICS/ASCM CPIM methods). It matters because 40 to 50 percent of MTTR in Philippine plants is just waiting for the part to arrive, and a well-run storeroom cuts that.

## Why most Philippine storerooms fail

Walk any Philippine plant storeroom and you will see the same four failures:

- **Phantom inventory.** The bin card says 12 bearings; the shelf has 3. The other 9 were used but never written off, or were issued without a withdrawal slip, or are sitting in another technician's toolbox. Phantom inventory is the #1 reason a planned repair stops mid-job.
- **Dead inventory.** 30 to 50 percent of SKUs have not moved in 12+ months. Some are obsolete (the asset they served was retired 4 years ago). Some are over-ordered (we panic-bought during a supplier crisis in 2022 and never used the rest).
- **Wrong-shelf inventory.** The part is there, but it is labelled wrong, or it is in the bin for the previous SKU code, or it migrated during a storeroom reorganisation in 2024. The technician spends 90 minutes looking for it.
- **Expired inventory.** Rubber O-rings, gaskets, greases, sealants, and batteries all have shelf lives of 1 to 3 years. After that they fail on installation. A storeroom that does not track date-received installs degraded parts as if they were new.

None of these failures are about the storeroom keeper being lazy. They are about the absence of three disciplines that the rest of this guide teaches: ABC classification, FIFO, and reorder points. With those three, the storeroom becomes a reliability asset. Without them, it becomes a place where ₱8M of capital quietly rots.

## ABC analysis explained with a worked example

ABC analysis is a Pareto sort applied to spare parts. Sort every SKU by annual usage value (unit cost times annual quantity used). The top 20 percent of SKUs will almost always account for 70 to 85 percent of total spend. Those are A items. The next 30 percent are B items (about 15 percent of spend). The remaining 50 percent are C items (about 5 percent of spend).

Why this matters: each tier gets a different control regime, because spending equal management time on a ₱180,000 motor and a ₱25 cable tie is wasted effort.

| Tier | % of SKUs | % of value | Cycle count | Reorder review | Storage |
| --- | --- | --- | --- | --- | --- |
| **A** | ~20% | ~70-85% | Monthly | Daily auto-trigger | Locked or controlled |
| **B** | ~30% | ~10-15% | Quarterly | Weekly review | Open bins, labelled |
| **C** | ~50% | ~5% | Annual | Visual ("bin is half") | Open bins |

Most Philippine plants have never done this sort. When they do it for the first time, they discover 3 to 5 obviously dead SKUs in their A tier (an asset retired but the spare still being held), and 30 to 50 dead SKUs in C tier (write-off candidates that should not even count toward inventory value). The first ABC analysis usually surfaces ₱500K to ₱2M of paper inventory that can be removed.

## FIFO discipline (it is paint, not software)

FIFO (First In First Out) means the oldest unit on the shelf gets picked first. It is critical for any spare with a shelf life:

- Rubber O-rings, gaskets, seals: 2 to 5 year shelf life
- Greases and lubricants: 2 to 3 years from manufacture
- Batteries: 1 to 3 years depending on chemistry
- Sealants and adhesives: 6 months to 2 years
- Filters with treated media: 1 to 2 years

The mistake most plants make is treating FIFO as a software feature. It is not. FIFO is enforced with paint on the storeroom shelf label: every receipt gets a date-received written in permanent marker on the bag or box. The keeper picks from the oldest date first. The shelf is organised left-to-right by date. No app required.

A digital inventory tool then records the date-received in the database so the supervisor can run a "expiring in next 60 days" report monthly. The WorkHive Inventory tool does this automatically; any system you use should.

## The reorder point formula

For A items, the reorder point is the inventory level that triggers an automatic PO. The formula:

Average Daily Usage and Lead Time both come from historical data, not from guesswork. If you have a digital logbook with parts-used entries, you already have the data. If you do not, this is one more reason to start a digital logbook (see [our 12-week rollout guide](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/)).

Safety Stock covers usage variability and supplier delays. A common rule:

For B items, periodic review is enough: review weekly, order back up to a target level. For C items, visual review at the bin is enough: when the bin looks half-full, order more.

## Worked example: a bearing in a Cabuyao plant

A food-processing plant in Cabuyao uses a specific 6205-2RS deep-groove bearing across 14 motors in its conveyor system. The supervisor wants to set a reorder point.

From the WorkHive Logbook, the past 12 months show:

- 156 bearings used across 14 motors (average 13 per month, 0.43 per day)
- Maximum monthly usage: 22 (peak month was December packaging push)
- Supplier lead time: 21 days (local supplier in Quezon City)

Plug into the formulas:

When the bin drops to 16, the PO triggers automatically. The 21-day lead time gets covered, plus a safety buffer for the December peak. The plant typically holds 30 to 40 of these on the shelf at month-end (above the safety stock but below the EOQ-derived maximum).

The tool this guide is about

#### WorkHive Inventory does ABC, FIFO, and reorder points out of the box

Every SKU has a date-received field for FIFO, an ABC class auto-computed from usage value, and a reorder-point alert wired to the supervisor's dashboard. The data comes from your WorkHive Logbook entries automatically; no double-entry. Free at the worker tier forever.

No hive yet? [Join WorkHive](https://workhiveph.com/?signup=1) first (free, takes 30 seconds).

## Why this is the cheapest MTTR fix you can buy

In our [MTBF vs MTTR guide](https://workhiveph.com/learn/mtbf-vs-mttr-for-supervisors/) we showed a Pampanga beverage-line conveyor with MTTR of 3.17 hours, of which 42 percent was waiting for the part to arrive. That pattern is consistent across every Philippine plant we have benchmarked: 40 to 50 percent of total MTTR is parts-waiting, not work time.

This means that for every hour you reduce parts-waiting time, you reduce MTTR by roughly 25 minutes. Compare cost-per-hour saved:

- **Hiring a second electrician for a 24/7 shift** to reduce wait-for-skill time: PHP 600,000 to PHP 900,000 per year.
- **Buying a CMMS work-order system** to reduce admin time: PHP 200,000 to PHP 1.2M per year in licenses.
- **Fixing the storeroom** with ABC, FIFO, and reorder points: usually free (one supervisor weekend + ongoing 30 minutes per month).

The storeroom fix is almost always the cheapest hour of MTTR reduction available. It is also the one most plants put off because nobody owns it. The maintenance supervisor thinks it is the storeroom keeper's job; the storeroom keeper thinks it is procurement's job; procurement thinks it is the supervisor's job. The fix is to assign the maintenance supervisor formal ownership of MRO inventory health, with 30 minutes monthly tied to the existing 5S walk.

## Common Philippine plant mistakes

- **Treating MRO inventory as a procurement metric.** Procurement cares about price-per-PO; maintenance cares about availability. The two pull in opposite directions. MRO inventory health is a maintenance metric reported on the maintenance KPI sheet, not procurement.
- **Bulk-buying to get unit discount.** A 15 percent discount on a 6-month supply of an item with 24-month shelf life is real money. The same discount on an item with 6-month shelf life is a guaranteed write-off in month 7.
- **No write-off discipline.** A part withdrawn from inventory but not used is supposed to be returned and re-shelved with a "previously issued" note. In practice, technicians keep it in their toolbox, and the system shows the part as still on the shelf. Quarterly reconciliation between bin card and shelf catches this.
- **One reorder point set in 2019.** Usage patterns change. ABC classification should be recomputed annually; reorder points should be recomputed quarterly on A items.
- **No supplier diversification on A items.** If the only supplier for a critical bearing is on a 60-day lead time from Manila and they have a strike, your plant stops. Two suppliers for every A item is the rule, even if one is more expensive.

**The bigger picture:** Good MRO inventory feeds MTTR (less waiting for parts), feeds MTBF (no installation of degraded parts), feeds OEE (less unplanned downtime), and feeds the plant's bottom line. It is one of the highest-ROI interventions available to a supervisor and one of the easiest to put off. Start with the storeroom walk-through and the first ABC sort. Most plants find the payback in the first 90 days.

## Frequently asked questions

### What is ABC analysis in spare parts inventory?

ABC analysis classifies parts into three tiers by annual usage value. A items (top 20 percent by value) typically drive 80 percent of inventory spend and get the tightest controls: cycle counts every month, reorder points monitored daily, locked storage. B items get quarterly counts and weekly review. C items get annual counts and reorder-when-you-see-it. The point is to spend management time where it pays back, not equally across 1,000 SKUs.

### What is the reorder point formula?

Reorder Point equals Average Daily Usage times Lead Time in Days, plus Safety Stock. Example: a bearing used 3 per week (0.43 per day) from a supplier with a 21-day lead time, with 5-unit safety stock has a reorder point of 0.43 times 21 plus 5 equals 14 units. When the bin drops to 14, the PO triggers automatically. Get the lead time and usage from the WorkHive Logbook history; do not guess.

### Why is FIFO important for spare parts?

FIFO (First In First Out) matters for any spare with a shelf life: greases, oils, gaskets, O-rings, batteries, sealants, adhesives, and any chemical. A rubber O-ring that has been on the shelf for 4 years often fails on installation because the rubber has cured. The replacement looks identical to the one you bought yesterday but performs differently. FIFO is enforced with paint on the storeroom shelf labels (date received), not with software.

### How much inventory should we hold?

Industry rule of thumb: 1 to 3 percent of asset replacement value for a typical Philippine plant. A plant with PHP 500M of equipment should target PHP 5M to PHP 15M of MRO inventory. Below 1 percent and you starve maintenance of parts; above 3 percent and you are carrying obsolete stock. The split matters more than the total: 60 to 70 percent of inventory value should be in A items even though they are only 20 percent of SKUs.

### Why does spare parts inventory affect MTTR?

Studies of Philippine plant breakdowns consistently show that 40 to 50 percent of MTTR (Mean Time To Repair) is waiting for the part to arrive at the asset. The technician has diagnosed the fault, knows the fix, but the part is not on the shelf or is on the wrong shelf or has expired. A well-run storeroom with FIFO discipline and accurate reorder points cuts that 40 percent in half. The cheapest hour of MTTR you can buy is good inventory management.

### Do I need a paid inventory system?

No, not for plants with fewer than 1,000 SKUs. A clean spreadsheet or the free WorkHive Inventory tool handles up to about 2,000 SKUs with proper categories, reorder points, and history. Paid systems (SAP MM, IBM Maximo MRO) add value at multi-site scale (5,000+ SKUs across multiple plants) but they do not improve discipline; they enforce a discipline you already have. Most Philippine plants buy the paid system before they have the discipline and end up with an expensive shelf-decoration project.

## Sources

- Society for Maintenance and Reliability Professionals (SMRP), **Best Practices, 5th Edition**, 2017. MRO inventory KPIs and benchmark targets.
- ISO 55001:2014, **Asset management: Management systems requirements**. Includes MRO inventory as a critical asset management input.
- APICS / ASCM, **CPIM Body of Knowledge**. Source for ABC classification methodology and reorder-point formulas.
- WorkHive platform positioning, "Four Gaps One Hive": Execution, Skills, Intelligence, Marketplace. [workhiveph.com](https://workhiveph.com/)
- Related WorkHive guides: [digital logbook rollout](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/) · [MTBF vs MTTR explained](https://workhiveph.com/learn/mtbf-vs-mttr-for-supervisors/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: 57d43254fec3c19a -->
