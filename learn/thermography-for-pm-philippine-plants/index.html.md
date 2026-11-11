# Thermography for Preventive Maintenance in Philippine Plants

> Learn how to apply thermography for preventive maintenance in Philippine plants, including handheld IR camera selection, critical scan targets, and integration into the PM Scheduler route.

Source: https://workhiveph.com/learn/thermography-for-pm-philippine-plants/

WorkHive Learn · Philippines

By WorkHive Editorial Team
·
18 May 2026
·
10 min read

**Short answer:** a thermal camera finds hot joints and bearings before they fail. Judge each reading by the NETA MTS thresholds. Compare similar parts under similar load. A difference of more than 15°C calls for action now. Against the air around it, more than 40°C calls for action now. Put the scan on a fixed route in your PM schedule.

Who this is for

- Field workers responsible for daily plant operations
- Technicians performing routine maintenance tasks
- Supervisors overseeing maintenance teams
- Engineers designing and implementing maintenance strategies
- Planners scheduling maintenance activities
- Managers responsible for plant operations and maintenance budgets
- Suppliers and contractors providing maintenance services
- Auditors and officers ensuring compliance with safety regulations

## Introduction to Thermography

A thermal camera shows heat you cannot see. That is what thermography does. It works without touching the equipment. A loose joint or a dry bearing runs hot before it fails. An overloaded breaker does too. So the camera sees trouble early.

ISO 18434-1 sets out the general procedure for thermography as condition monitoring. Behind the panel, the wiring must meet the electrical code.

A handheld camera pays for itself the first time it finds a hot joint before the joint finds the plant.

## Handheld IR Camera Selection

Two names come up most. The FLIR ONE Pro clips onto a phone, and its MSX feature adds visible detail to the thermal image. That helps you tell which joint is hot. Seek Thermal sells cheap clip-on cameras. Their images are less sharp. Many plants start with one.

Whatever you buy, check what decides if a reading means anything:

- **Resolution** at the distance you can safely stand
- **Thermal sensitivity**, to see small differences
- **Temperature range**, to cover your hottest target
- **Emissivity setting**, to match the surface you aim at

Pick a camera that is easy to use in poor light on a night round. A tired technician will skip a fiddly one.

## Critical Scan Targets

- **Panel joints:** breaker ends and busbar joints run hot when loose.
- **Motor windings:** overheating that comes before a motor failure.
- **Bearings:** heat that signals poor lubrication or misalignment.
- **Steam traps:** a failed trap wastes steam and energy.

An MCCB is a moulded-case circuit breaker. Start with them, and the busbar joints that feed them. That is where most hot spots hide.

Read a bearing against its own history and its neighbours on the same duty. No single limit fits every bearing. That is why the survey is worth repeating on a cadence.

A failed winding stops the line, and the line standing still costs more than the new motor.

## Reading Thresholds and Interpretation

NETA MTS looks at how much hotter a part is. Compare a part with a similar part under similar load:

- 4 to 15°C hotter: a probable fault. Repair when time allows.
- More than 15°C hotter: repair now.

If the part has no twin, compare it with the air around it:

- 1 to 10°C above: a possible fault. Look into it.
- 11 to 20°C above: a probable fault. Repair when time allows.
- 21 to 40°C above: repair as soon as you can.
- More than 40°C above: repair now.

The words "under similar load" do the work. Two breakers at different loads are not comparable. That is the commonest way a route raises a false alarm.

The baseline matters more than the number. A winding at 60°C on a cool night may be fine. The same winding at 80°C in the afternoon heat may not be. So compare each survey with the last one.

## Integration into PM Scheduler

Put thermography on your PM route like any other task. You do not have to write it yourself. Two thermography tasks ship in the template list. "Check bearing temperature (infrared or thermometer)" runs monthly. "Full thermographic scan of all panels" runs yearly.

Know what the PM Scheduler holds. It schedules the scan and records who completed it. Each completion takes a findings note of up to 2,000 characters. But there is no temperature field, no alert on a reading and no photo field.

So write the numbers into the note. Note the air temperature, the load, the part and the difference. Keep the thermal images in your own numbered folder, under the same date. Then a supervisor can see the same joint climbing across three surveys.

A PM task has no assignee field, so the owner is whoever your shift plan names. The scheduler records who did the task, not who owed it.

Put the route in the PM Scheduler, and you stop finding hot joints by luck. You find them on a date instead.

## Best Practices and Safety Precautions

Do not shut the equipment down for the scan. The survey measures the heat that load current makes. De-energised gear is cold, so a scan of it finds nothing. Take the reading with the equipment running under normal load.

Lockout and tagout apply to the repair you schedule afterwards. The scan itself needs live-work discipline:

- arc-flash rated PPE (personal protective equipment). Your plant's arc-flash study sets the rating.
- a qualified person to open the panel
- the greatest working distance your camera's resolution allows

Opening a live panel is the riskiest part of the survey. ISO 18434-1 covers the procedure. Your own plant's arc-flash and PPE rules cover the safety.

Scan on the shift that runs the equipment hardest. A lightly loaded panel hides the fault you are looking for. Plan for access too: some targets sit high up or in tight spaces.

Train the people who read the images. An untrained eye reads a reflection as heat. Training is usually the first thing cut, and it should be the last.

**Open the tool:** PM Scheduler is the WorkHive surface this guide funnels into. It is free at the worker tier, works offline, and is built for Philippine plants.

## Frequently asked questions

### Which standards govern a thermography survey in a Philippine plant?

Three, and they do different jobs. ISO 18434-1 covers how the survey itself is planned, performed and reported. The NETA acceptance-testing criteria give the temperature differences that decide what counts as a finding. And the electrical work behind the panel door follows the Philippine Electrical Code, published by IIEE. Your client or insurer may also ask for a certified thermographer, which is a training question rather than a standards one. It outlines the requirements for equipment, personnel, and procedures.

### What are the benefits of using thermography for preventive maintenance?

Thermography can help detect potential issues before they become major problems, reducing downtime and increasing plant efficiency. It can also help extend equipment lifespan and reduce maintenance costs.

### What are some common applications of thermography in Philippine plants?

Thermography is commonly used in Philippine plants for inspecting electrical equipment, such as MCCB connections and motor windings, as well as mechanical equipment, such as bearings and steam traps.

### How do I choose a thermal camera?

When selecting a handheld IR camera, consider factors such as resolution, accuracy, and ease of use. Popular options for thermography inspections include the FLIR ONE Pro and Seek Thermal cameras.

### What are some safety precautions to take during thermography inspections?

An electrical thermographic survey is taken with the equipment ENERGISED and under normal load - that is what produces the heat you are looking for - so lockout/tagout belongs to the repair that follows a finding, never to the scan itself. The precautions that do apply are the ones for working near live equipment: arc-flash rated PPE to your plant's incident-energy assessment, a qualified person opening the panel, and reading from the greatest distance your camera's resolution allows.

### How can I integrate thermography into my plant's PM Scheduler?

To integrate thermography into your plant's PM Scheduler, identify critical equipment and inspection points, and schedule regular thermography inspections. Make sure to also track and analyze results to identify trends and areas for improvement.

**Keep reading:** [add vibration checks](https://workhiveph.com/learn/vibration-analysis-on-a-phone-budget/), or [build your asset register first](https://workhiveph.com/learn/building-asset-register-zero-budget/).

## Sources

- [NETA](https://www.netaworld.org/), **Maintenance Testing Specifications (MTS)**: thermographic ΔT action criteria; and [NFPA 70B](https://www.nfpa.org/codes-and-standards), **Electrical Equipment Maintenance**.
- ISO 18434-1:2008, **Condition monitoring and diagnostics of machines - Thermography - Part 1: General procedures** (how the survey is planned, performed and reported).
- DOLE OSHS Guidelines for Preventive Maintenance
- ISO 14224:2016, **Collection and exchange of reliability and maintenance data for equipment** (the failure taxonomy the scan results are recorded against).
- SMRP, **Body of Knowledge**: predictive-maintenance practice.

<!-- md-twin source-sha: fcd0a1d5c14b8d6f -->
