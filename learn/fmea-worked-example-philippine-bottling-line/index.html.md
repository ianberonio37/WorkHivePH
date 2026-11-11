# FMEA Worked Example: a Philippine Bottling Line

> Learn how to apply FMEA to a Philippine bottling line filler to identify and mitigate potential failures, minimize downtime, and maximize productivity.

Source: https://workhiveph.com/learn/fmea-worked-example-philippine-bottling-line/

WorkHive Learn · Philippines

By WorkHive Editorial Team
·
18 May 2026
·
9 min read

**Short answer:** FMEA (failure mode and effects analysis) lists how a machine can fail and ranks each way. Rate each failure mode from 1 to 10 on three scales. They are severity, occurrence and detection. Multiply the three to get the RPN, then fix the highest first. On our Cabuyao filler, a fill-level mode scores 192 and a pump failure 96. At PHP 180,000 an hour, a 2-hour stop costs PHP 360,000.

Who this is for

- Field workers looking to improve equipment reliability
- Technicians responsible for maintenance and repairs
- Supervisors overseeing production lines
- Engineers designing and implementing equipment
- Maintenance planners and schedulers
- Managers and directors responsible for asset management
- Suppliers and contractors providing equipment and services
- Auditors and officers ensuring compliance with regulations

Part of the [maintenance metrics guide](https://workhiveph.com/learn/maintenance-metrics-reliability-guide/). That hub links every reliability metric and shows how they connect.

## Introduction to FMEA

FMEA stands for failure mode and effects analysis. It lists the ways a machine can fail and what each failure does. Then it ranks them, so the team fixes the worst first.

This guide works one example. It is the filler on a bottling line in Cabuyao, Laguna. The line runs 24/7. We assume a stop costs PHP 180,000 an hour in lost production. That figure is an assumption for the example, so use your own plant's number.

Do it as a team. Bring the shift in-charge, the maintenance planner and the production supervisor. Each knows failures the others miss.

## FMEA Worksheet Example

A worksheet has one row per failure mode. Each row records:

- the failure mode, such as "the pump stops delivering"
- its effect, such as "bottles go out underfilled or not at all"
- its cause, if you know it
- **Severity** (S): how bad the effect is, from 1 to 10
- **Occurrence** (O): how often it happens, from 1 to 10
- **Detection** (D): how hard it is to catch in time, from 1 to 10, where 10 is hardest
- the controls already in place

Rate occurrence in a unit your team thinks in. Our pump, P-204B, fails about 4 times a year. A 24/7 line runs about 1,095 shifts a year, so that is about 1 shift in 270. "A few times a year" and "once in a hundred shifts" sound alike. Yet the second is almost three times as often.

## Calculating RPN

RPN is the risk priority number. Multiply the three ratings: RPN = S × O × D. It runs from 1 to 1,000. Here is the pump's row:

| Rating | Value | Why |
| --- | --- | --- |
| Severity | 8 of 10 | The filler stops, at about PHP 180,000 an hour |
| Occurrence | 4 of 10 | About 4 failures a year, or 1 shift in 270 |
| Detection | 3 of 10 | A failing pump shows within about 30 minutes |
| RPN | 96 of 1,000 | 8 × 4 × 3 |

The same line has a second mode: the filler puts the wrong amount in each bottle. It rates S 8, O 6 and D 4, so its RPN is 192. Fill errors happen more often than pump stops, and they are harder to catch.

In WorkHive's Asset Hub, you enter S, O and D for each mode. The database computes the RPN for you. It also colors each RPN. 200 or more is critical, and 100 to 199 is high. 40 to 99 is medium, and below 40 is low.

## Prioritizing Failure Modes

Rank the modes by RPN and work from the top. On our line, the order is:

1. Fill level wrong: RPN 192 (high)
2. Pump P-204B fails: RPN 96 (medium)
3. Conveyor belt fails: RPN 80 (medium)
4. Electrical control fails: RPN 72 (medium)

The single number means little alone. What matters is the order. A severity of 9 or 10 usually means a safety risk. Look at those rows even when the RPN is low.

Rank first, then fix in order. When you can, plan the fix into a planned stop, on a bottling line usually the small hours. A fault that strikes at night and waits for the day crew costs the whole gap. So pick the part and set it aside in advance.

## Storing FMEA Output in Asset Hub

Each asset in Asset Hub has its own FMEA list. Tap Add failure mode to enter one by hand. Each mode holds its function, failure mode, effect and cause. It also holds the three ratings, a consequence class and notes. The consequence class is safety, production, environment, cost or quality.

The AI button can also suggest modes. It reads the asset's corrective logbook entries from the last 365 days and groups them by root cause. Each suggestion waits for a supervisor to approve it.

The list keeps the analysis in one place as the asset ages. When a fix lands, update the ratings, and the RPN moves with them. Asset Hub does not track the cost of downtime or the actions themselves. Keep those in the work order or the logbook.

## Cost of Downtime Calculation

The cost of downtime tells you what fixing a failure mode is worth. Work it out by hand:

- Lost production: hours stopped × output value per hour
- Labour: crew hours × your labour rate
- Damage: parts and repair

In our example, the line makes 10,000 bottles an hour, worth PHP 180,000. A 2-hour pump stop at 02:30 costs PHP 360,000 in lost production. Add the crew's hours at your own labour rate, plus any parts.

Set that figure beside the RPN. A mode with a lower RPN but a much higher cost may still go first.

**Open the tool:** this guide leads to WorkHive's Asset Hub. It is free at the worker tier and built for Philippine plants.

## Frequently asked questions

### What is the purpose of FMEA in a Philippine bottling plant?

FMEA finds the ways your equipment can fail and ranks them, so the team fixes the worst first. It cuts downtime by putting effort where the risk is.

### How do I rate severity, occurrence and detection?

Rate them as a team, on 1-to-10 scales your plant writes down once. A severity of 9 or 10 usually means a safety risk. Base occurrence on your logbook history, and detection on how soon the failure shows.

### What is RPN and how is it calculated?

RPN (Risk Priority Number) is calculated by multiplying the severity, occurrence, and detection ratings for each failure mode. For example, if the severity rating is 5, occurrence rating is 3, and detection rating is 2, the RPN would be 5 x 3 x 2 = 30.

### How do I prioritize which failure modes to fix first?

Prioritize failure modes with the highest RPN ratings. On the bottling line worked through above that means the filler's fill-level mode at 192 before the pump-failure mode at 96, then the conveyor at 80 and the electrical control at 72. Rank first, then fix in order.

### Can I use Asset Hub to store and track FMEA outputs?

Yes. Each asset has an FMEA list with the three ratings, and the database computes the RPN. The AI can suggest modes from your logbook, and a supervisor approves each one. Asset Hub does not track downtime cost or actions.

### How do I calculate the cost of downtime for each failure mode?

Use a standard formula to calculate the cost of downtime, taking into account factors such as lost production, labor costs, and equipment damage. For example, if a failure mode causes 2 hours of downtime and costs PHP 10,000 per hour in lost production, the total cost would be PHP 20,000.

## Sources

- IEC 60812:2018, 'Failure modes and effects analysis (FMEA and FMECA)'
- ISO 14224:2016, 'Collection and exchange of reliability and maintenance data for equipment'
- SMRP CMRP BoK, 'Failure Mode and Effects Analysis (FMEA)'

<!-- md-twin source-sha: e1e9fc48ba34a71e -->
