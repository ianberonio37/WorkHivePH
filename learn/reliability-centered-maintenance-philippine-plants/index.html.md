# Reliability-Centered Maintenance (RCM) for Philippine Plants

> Learn how Reliability-Centered Maintenance (RCM) can optimize plant maintenance in the Philippines, reducing downtime and improving efficiency.

Source: https://workhiveph.com/learn/reliability-centered-maintenance-philippine-plants/

WorkHive Learn · Philippines

By WorkHive Editorial Team
·
18 May 2026
·
9 min read

**Short answer:** Reliability-centered maintenance (RCM) decides what work each asset needs. It starts from what each failure costs. It asks seven questions, set by SAE JA1011. You fix what causes downtime first. You stop servicing everything on a fixed calendar. On a Cabuyao bottling line where a pump stop costs PHP 180,000 an hour, that pump comes first. In WorkHive, you record RCM decisions in the Asset Hub. Then push each task to PM Scheduler.

Who this is for

- Field workers responsible for equipment upkeep
- Technicians performing routine maintenance tasks
- Supervisors overseeing maintenance teams
- Engineers designing and implementing maintenance strategies
- Planners scheduling maintenance activities
- Managers responsible for plant operations and budget
- Suppliers and contractors providing maintenance services
- Auditors and officers ensuring compliance with regulations

Part of the [maintenance metrics guide](https://workhiveph.com/learn/maintenance-metrics-reliability-guide/). That hub links every reliability metric and shows how they connect.

## What is Reliability-Centered Maintenance (RCM)?

RCM ranks maintenance by what each failure would cost. Then you fix what really causes downtime. You stop servicing everything by the calendar.

F. Stanley Nowlan and Howard F. Heap wrote it down in 1978, at United Airlines. The U.S. Department of Defense published their report. Today SAE JA1011 sets the test for what counts as RCM.

In a Philippine plant, the planner's hours are scarcer than the tools. So RCM earns its keep mostly in what it stops the team doing. The analysis is only worth the days it takes if its tasks reach a schedule.

## The 7 RCM Questions

The seven questions come from Nowlan and Heap's report. SAE JA1011 fixes them today:

1. **Functions.** What must the asset do, and to what standard? Not "run", but "deliver 300 litres a minute at 4 bar".
2. **Functional failures.** How can it fail to do that? Partial failure counts. A pump at 200 litres a minute has failed its function.
3. **Failure modes.** What causes each failure? Think bearing wear, a seal leak, impeller erosion or a blocked suction line.
4. **Failure effects.** What happens when it occurs? What does the operator see, what stops, and how long is the fix?
5. **Failure consequences.** How does each failure matter? Is it safety, environment, production, or repair cost alone? This is the triage step, and the reason RCM exists.
6. **Proactive tasks.** What can you do in advance to prevent the failure or catch it early? And how often?
7. **Default actions.** What if no proactive task is worth doing? Choose one: run to failure, or scheduled discard or restoration. Or a failure-finding check, or a redesign. Skip this question and an "RCM" study turns back into a PM list.

Take Pump P-204B, which feeds water to a Cabuyao bottling line. If it fails, the line stops, at PHP 180,000 an hour. The seven questions lead from that cost to the failure modes worth preventing. Worn bearings and a clogged strainer are two.

## P-F Intervals and FMEA Tie-in

The P-F interval is the time from the first sign of a failure (P) to the failure itself (F). Say a pump's vibration starts to rise 30 days before it fails. That 30 days is its P-F interval.

Two intervals live here, and mixing them up is the commonest RCM mistake. The P-F interval belongs to the failure mode. You do not choose it; you measure or estimate it. What you choose is the inspection interval.

SAE JA1011 says to inspect within the P-F interval. The common rule is half of it, so at least two inspections fall inside the window. Then one missed round does not cost you the catch. Tighten it further where the consequence is severe.

So inspect a 30-day P-F interval every 15 days or less. Not every 30. Set them equal, and you will often miss the failure you inspect for.

WorkHive's P-F calculator, in the Asset Hub, works this out from readings in the logbook. It recommends half the P-F interval as the inspection gap. For safety-critical assets, it uses a third.

FMEA ties in here. It lists each failure mode, its effect and its cause, and ranks them. RCM then picks a task, or a default action, for each mode worth acting on.

## 90-Day RCM Rollout for Philippine Plants

A plant with no CMMS can roll out RCM in 90 days. CMMS means computerized maintenance management system. Split it into three blocks of 30 days:

1. **Days 1 to 30: collect and rank.** List the critical assets and gather their history. Run an FMEA on each, and pick the assets to analyze first.
2. **Days 31 to 60: analyze.** Work the seven questions for each chosen asset. Estimate each P-F interval. For Pump P-204B, bearing failure might give a P-F interval of 60 days.
3. **Days 61 to 90: schedule and review.** Put the tasks on the schedule, then check whether they work. Adjust as you learn.

WorkHive is free at the worker tier, so the real cost of RCM is analysis time. Measure the return against that.

## Worked Example: Cabuyao Bottling-Line Pump

Pump P-204B supplies water to a Cabuyao bottling line. It runs 24/7, and a stop costs PHP 180,000 an hour.

One failure mode is a sudden loss of suction. The FMEA rates it at an RPN (risk priority number) of 180, so it ranks high. The P-F interval for suction-line fouling is about 30 days. So the team inspects the suction line every 15 days. That is half the P-F interval. They also replace the suction strainer once a year.

If an inspection falls on a Sunday, move it a day earlier rather than later. One hour of unplanned downtime on this line costs PHP 180,000. Preventing one suction loss pays for a lot of inspections.

## Capturing RCM-Derived Tasks with WorkHive PM Scheduler

RCM programmes usually die at the hand-off to the schedule. WorkHive closes it in two places.

In the Asset Hub, each FMEA failure mode can carry an RCM strategy. The strategy records one of six decisions:

- run to failure
- scheduled on-condition
- scheduled restoration
- scheduled discard
- failure-finding
- redesign

It also holds the task, its interval in days and the reasoning. A supervisor approves it. For a scheduled or failure-finding decision, tap Push to PM. The task then lands in PM Scheduler as a recurring PM with its interval.

Know what PM Scheduler holds. Each task has an item and a frequency. There is no assignee field, so who owes the task lives in your shift plan. The scheduler records who completed each PM.

Nothing chases a single person either. A daily PM-overdue report goes to the supervisor. The supervisor then pushes it out to the crew. There is no approval step, so make reviewing that report a habit.

Plan the suction-line check into a quiet window, such as 02:30. Stage the parts beforehand. Then the window goes to work, not to fetching.

**Open the tool:** this guide leads to WorkHive's PM Scheduler. It is free at the worker tier and works offline.

## Frequently asked questions

### What is the first step in implementing RCM in our Philippine plant?

The first step is to assemble a cross-functional team to identify critical equipment and processes.

### How does RCM relate to Philippine occupational safety and health standards?

DOLE's OSH Standards do not require RCM. RCM's consequence step does put safety first, so it supports a safe plant. It is good practice, not a legal duty.

### Can RCM be applied to small and medium-sized enterprises (SMEs) in the Philippines?

Yes, RCM can be adapted to SMEs, helping them improve equipment reliability and reduce maintenance costs.

### What is the role of FMEA in RCM?

FMEA (Failure Mode and Effects Analysis) is used in RCM to identify potential failure modes and their effects on equipment and plant operations.

### How long does it take to see results from implementing RCM?

It depends on your starting point and your records. Fewer needless PM tasks can show within the 90-day rollout. Fewer failures take longer, because each one has to not happen for a while before it counts.

### Is RCM compatible with existing CMMS systems?

Yes, RCM can be integrated with existing Computerized Maintenance Management Systems (CMMS) to enhance maintenance scheduling and tracking.

## Sources

- Nowlan, F. S., & Heap, H. F. (1978). **Reliability-Centered Maintenance**. Prepared at United Airlines; published by the U.S. Department of Defense.
- SAE **JA1011**, **Evaluation Criteria for Reliability-Centered Maintenance (RCM) Processes**: the seven questions above, and the test of whether a process may be called RCM.
- ISO 14224:2016. Collection and exchange of reliability and maintenance data for equipment.
- SMRP (2015). CMRP BoK (Body of Knowledge). Society for Maintenance and Reliability Professionals.

<!-- md-twin source-sha: 9e4d761c12653cfe -->
