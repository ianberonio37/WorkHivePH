# How to write a maintenance shift handover (template included)

> A 5-section maintenance shift handover template, a worked example from a Philippine bottling line, and the rules that make handovers actually get read by the next shift.

Source: https://workhiveph.com/learn/maintenance-shift-handover-template/

Handover · Template + worked example

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 17 May 2026
·
9 min read

**Short answer:** A good maintenance shift handover has 5 sections that fit on one screen: equipment status, work in progress, open issues with P1/P2/P3 priority, parts awaiting, and a safety + signature line. It takes 10 to 15 minutes to write at end of shift and 5 minutes to read at start of next. The difference between a good handover and a bad one is usually whether the next shift solves a problem in 5 minutes or rediscovers it in 5 hours.
 The stake is concrete: a good handover is the difference between the next shift solving a problem in **5 minutes** and rediscovering it over **5 hours**.

Who this is for

- Shift supervisors and line leaders
- Field technicians and operators
- Production and maintenance planners
- Plant managers reviewing handover trends
- Safety officers auditing records
- Contracted service team leads
- New supervisors learning the handover habit

Part of the [guide to starting digital maintenance in a Philippine factory](https://workhiveph.com/learn/start-digital-maintenance-guide/) — the four-step, zero-budget rollout this article is one step of.

## Why most shift handovers fail (the 8-minute problem)

Most Philippine plants schedule 30 minutes for shift change. In practice the actual overlap is 8 minutes: the outgoing crew is tired and wants to go home, the incoming crew is signing in and grabbing coffee, and the supervisors meet at the line for a verbal walk-through that nobody writes down.

Eight minutes is enough to say "everything is running, may issue lang sa Conveyor 3." It is not enough to transfer:

- Which assets are at risk and why
- What was tried already (so the next shift does not redo it)
- Which parts are on order and when they will arrive
- What the open safety items are
- What the priority order is for the next 8 hours

The result is the pattern every Filipino maintenance supervisor has lived through: a problem the graveyard shift was solving gets restarted from zero by the morning shift, who waste 2 hours rediscovering what was already known. Multiplied across 365 days, that is 730 hours of waste per year per shift transition.

## The 5-section template

A useful handover fits on one screen, takes 10 to 15 minutes to write, and uses the same 5 sections every time:

### Section 1: Equipment status

One line per critical asset. Two columns: asset name and status (running, stopped with reason, in PM). No long sentences. If you have 60 critical assets, only list the ones whose status changed during the shift or that the next shift needs to watch.

### Section 2: Work in progress

One line per open job. Include what was started, what is left, and which technician started it. If technician Cruz started replacing the Pump 4 bearing and got to the coupling alignment stage, the next shift needs to know that, not start from "remove the cover".

### Section 3: Open issues with priority

Use a 3-tier priority: P1 deal with it in the first hour. P2 deal with it within the shift. P3 deal with it before week-end. If everything is P1, nothing is P1. Most shifts should have 0 to 2 P1 items.

### Section 4: Parts awaiting

List any parts requested, ordered, or in transit. Include the asset waiting, the supplier (Globe Steel, Indrad, etc.), and the expected arrival. This prevents the next supervisor from ordering the same part again or wondering why a job is stalled.

### Section 5: Safety items and signatures

List any safety incidents, near-misses, or permit-to-work items still active. Then both supervisors sign with timestamp. Without signatures the document is not a handover; it is a memo the next shift can ignore.

## Worked example: bottling line, graveyard to morning

A real-world example from a carbonated beverage plant in Cabuyao. Graveyard shift (10 PM to 6 AM) handing over to morning shift (6 AM to 2 PM):

Notice what is NOT in this handover: long narrative paragraphs, troubleshooting theories, blame for who caused what. A handover is a status document, not an essay. Save the analysis for the weekly review.

## The handover that prevented a ₱180,000 loss

In one of the plants we work with, a graveyard handover similar to the one above noted "Conveyor 3 Motor 3B vibration rising, 2.1 to 4.8 mm/s in 7 hours" as a P1 item. The morning supervisor escalated it within the first hour, ordered the standby motor swap during the 10 AM changeover, and prevented a full-line stop during the 1 PM peak production window.

The math:

- Planned 45-minute motor swap during scheduled changeover: cost ≈ ₱0 (already-scheduled downtime).
- Unplanned motor failure mid-production: 4-hour line stop × ₱45,000/hr in lost revenue ≈ **₱180,000**, plus emergency motor purchase markup.

The supervisor who wrote the P1 entry did not know any of this would happen. He just followed the template: a measurement, a trend, a priority. The discipline produced the catch. The catch produced the saving. Without the written handover, the morning supervisor would have walked the line at 7 AM, noticed the noise himself, and started planning at 8 AM. By then the motor would have been dying for 9 hours instead of 7. The window to act would have closed.

## Digital versus paper handover

|  | Paper | Digital |
| --- | --- | --- |
| **Writing time** | 15-20 min | 10-15 min (auto-draft from logbook entries) |
| **Reading time** | 5 min if legible | 2-3 min (search and filter) |
| **Findable 6 months later** | Almost never | Search by asset, date, priority |
| **Multi-audience (plant mgr, reliability, safety)** | No (only the binder) | Yes (shared dashboard) |
| **Survives technician turnover** | No | Yes |
| **DOLE OSHS audit response** | Manual photocopy | PDF export in seconds |
| **Cost** | Notebook + pen | Free (with a free tool) or ₱20-200/user/month for paid CMMS |

The big difference is not the writing experience; it is the read experience three weeks later when something escalates and you need to retrieve "what did the graveyard shift on the 17th say about Conveyor 3?" Paper makes that a 90-minute archaeology project. Digital makes it a 5-second search.

The tool this guide is about

#### WorkHive Shift Brain auto-drafts the handover from your Logbook entries

Every entry your team logs during the shift gets categorised and prioritised. At end of shift, Shift Brain auto-fills the 5-section handover. The supervisor edits in 5 minutes instead of writing from scratch in 15, and submits. The incoming supervisor sees it the moment they log in. Free at the worker tier forever.

No hive yet? [Join WorkHive](https://workhiveph.com/#join) first (free, takes 30 seconds).

## Common mistakes that make handovers useless

- **"Everything OK, no issues."** Almost never true. If literally nothing changed during 8 hours of running plant, the supervisor was not paying attention. Force at least one specific observation per shift.
- **Everything marked P1.** When every item is critical, nothing is. The next shift triages by gut feel instead of by your priority. Limit P1 to 0-2 items per handover.
- **Long narrative paragraphs.** Nobody reads them at 06:05 with coffee in hand. Bullet points or one-line entries always.
- **Blame language.** "Tech Cruz did not finish the bearing job" is a memo. "Bearing job 50 percent complete, resume from coupling alignment" is a handover. The next shift needs to act, not adjudicate.
- **No signature.** Without both supervisors signing, the handover has no accountability. The incoming supervisor can later claim "I was not told." The outgoing supervisor can claim "I told them but they did not write it down." Signatures kill both arguments.
- **Same template for 3 years.** Review the template quarterly. The 5 sections are universal, but the asset list under section 1 should change as the plant changes.

## The supervisor's 60-second review checklist

Before submitting the handover, the outgoing supervisor reads it back and checks:

- Section 1 lists every asset whose status changed today.
- Section 2 includes the technician name for each open job.
- Section 3 has 0 to 2 P1 items (anything more is a triage failure).
- Section 4 lists every parts order with ETA, not just "parts ordered".
- Section 5 has at least one signature line filled.
- The whole thing fits on one screen on a phone.

**The bigger picture:** The shift handover is the most concentrated knowledge transfer in your plant. Done well, it compounds: every shift learns from the last, the AI work assistant has 365 days × 3 shifts = 1,095 handovers to learn your plant's patterns, and a new supervisor can read 30 days of handovers to onboard in a week. Done poorly, it loses 730 hours per shift transition per year.

## Frequently asked questions

### How long should a shift handover take to write?

10 to 15 minutes for the outgoing supervisor, 5 minutes to read for the incoming supervisor. If it takes longer to write, the template is too long. If it takes longer to read, the writing is too vague. Both signal that the handover habit is not yet in place.

### Is a verbal handover enough?

No. Verbal handovers fail two tests: the incoming supervisor cannot retrieve the information mid-shift when they need it, and DOLE OSHS Rule 1063 requires that safety and health observations be recorded in a way an inspector can sample. A 10-minute verbal walk-through plus a written handover is the standard. The walk-through builds context; the written record makes the handover useful 6 hours later when something escalates.

### Should handover use Filipino or English?

Whichever the team actually uses fluently. Forcing English on a team that thinks in Filipino or Taglish produces shorter and less specific entries. A handover that says 'may tagas sa drain valve ng tank 3, may bago na O-ring' is more useful than 'water leak observed; remediation in progress'. The point is the entry exists and the next shift understands it. Train your AI work assistant to parse both.

### What if my plant runs 3 shifts?

The template does not change. Each shift writes its own handover at end of shift. The morning supervisor reads the graveyard handover plus the previous day's afternoon handover to get full 24-hour context. The digital format makes this easy; the paper format makes it nearly impossible, which is the single biggest reason plants move to digital logbooks.

### Who reads the handover other than the next supervisor?

In a mature plant: the plant manager during the morning huddle, the reliability engineer when investigating recurring faults, the safety officer when reviewing near-misses, the planner when scheduling the next PM round, and (in plants using AI) the AI work assistant that surfaces patterns across hundreds of handovers. The handover is a multi-audience document, not just a shift-to-shift memo.

### Can a digital logbook replace the shift handover?

The logbook captures individual events as they happen during the shift. The handover summarises and prioritises what the next shift inherits. They are not the same document. A well-built digital logbook auto-generates the first draft of the handover from the shift's entries, which the supervisor then edits in 5 minutes instead of writing from scratch in 15. This is the WorkHive logbook pattern.

## Sources

- Department of Labor and Employment (DOLE), **Occupational Safety and Health Standards (OSHS) Rule 1063**: Safety and Health Records.
- UK Health and Safety Executive (HSE), **"Effective Shift Handover: A Literature Review"**, Research Report 558. The most widely-cited industrial-safety study on handover failures, drawn on across the global process industry.
- American Petroleum Institute (API) Recommended Practice 754, **"Process Safety Performance Indicators for the Refining and Petrochemical Industries"**. Includes handover quality as a Tier 4 safety indicator.
- WorkHive platform positioning, "Four Gaps One Hive": Execution, Skills, Intelligence, Marketplace. [workhiveph.com](https://workhiveph.com/)
- Related WorkHive guide: [How to start a digital logbook in a Philippine factory](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: 9aed24cfb76ccabc -->
