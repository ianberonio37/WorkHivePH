# Vibration Analysis on a Phone Budget (Philippine PdM)

> Learn how to run a phone-based vibration trend route in a Philippine plant: what a phone accelerometer can and cannot see, how to log readings with Voice Journal, and how to judge them against the ISO 10816-1 severity zone for the machine's class.

Source: https://workhiveph.com/learn/vibration-analysis-on-a-phone-budget/

WorkHive Learn · Philippines

By WorkHive Editorial Team
·
18 May 2026
·
8 min read

**Short answer:** You can start vibration checks with the phone in your pocket. Use a free accelerometer app to take the reading. Then dictate it into WorkHive's Voice Journal, so the trend builds week by week. Judge each reading against ISO 10816-1 for the machine's class. Class II covers 15 to 75 kW, or up to 300 kW on a special foundation. Above 2.8 mm/s RMS it is no longer satisfactory. Above 7.1 mm/s it is severe. On a Class I machine, 15 kW or less, those lines are 1.8 and 4.5. WorkHive's [Vibration Analysis calculator](https://workhiveph.com/engineering-design.html) finds the zone for you. Just pick the class.

Who this is for

- Field workers responsible for daily equipment checks
- Technicians performing routine maintenance tasks
- Supervisors overseeing plant operations
- Engineers designing and implementing maintenance programs
- Planners scheduling maintenance activities
- Managers responsible for plant budgets and resources
- Suppliers and contractors providing maintenance services
- Auditors and officers ensuring compliance with regulations

## What is Phone-Based Vibration Analysis?

Phone-based vibration analysis is predictive maintenance on a small budget. You do not buy an analyser first. You start with two things you already have. One is an accelerometer app on your phone, to take the reading. The other is WorkHive, to record and judge it.

Be clear about which does what. Voice Journal does not measure vibration. It turns your voice into a text entry, so you capture the number and its context on the spot. The app does the measuring, using the phone's built-in accelerometer.

That accelerometer is the limit. Many phones sample it about 100 times a second, and some Android phones go higher. At 100 samples a second, a phone sees vibration up to about 50 Hz. So it sees a machine's running speed up to about 3,000 RPM. It sees twice the running speed only below about 1,500 RPM. Anything faster is invisible to it.

Keep the route steady. Read the same point, with the machine in the same state, on the same day each week. Dictate each number into Voice Journal. It records the time and keeps the entry searchable.

## Logging Readings with Voice Journal

On the route, read each machine with the app and dictate the number into Voice Journal on the spot. People skip this step, and it decides whether the route is worth running. A reading left on the app's screen is gone by the next machine.

Then compare each number with the ISO 10816-1 zone for that machine's class. Take the class from the motor rating, not from how big the machine looks. A 55 kW pump is Class II. Judge it by Class I's severe line of 4.5, and you chase readings its own limits call fine.

Voice Journal has no threshold or alert of its own. So if a reading lands in Zone C or D, say so in words in the entry. The judgement has to be in the entry for anyone reading it later.

The cost is low. Many plants cannot get an analyser for a first route. It is a capital request. You must justify it before you have any data to justify it with. The phones and the app are already there.

## What Can and Can't Phone Vibration Detect?

A phone is a trending tool for low-frequency faults. It tells you which machine is changing and which is just loud. It does not diagnose.

- **Can catch, as a rising trend:** unbalance, misalignment and looseness. Also late bearing wear, once it raises the overall level.
- **Cannot catch:** early bearing damage, gear mesh or cavitation. Nor electrical rotor faults. These live at frequencies the phone cannot reach.

A rising trend on the phone is a reason to bring in a real analyser, not a diagnosis. Use the phone to choose which machine gets the expert's time.

A phone route does not replace full vibration analysis. It adds to it, on a budget that is already spent.

## A Weekly Walkdown Route for Vibration Analysis

Here is a sample weekly route for a plant in Cabuyao, Laguna. Run it at the same point in the shift each week.

1. **Pump house:** read Pump P-204B at its bearing housings.
2. **Boiler area:** read Boiler B-1's feed pump and draft fan. The boiler itself does not rotate, so read the machines that serve it.
3. **Conveyor line:** read the Conveyor #2 drive motor and gearbox.
4. **Air handling:** read the AHU-3 fan and motor.

At each stop, dictate the reading and anything you notice: noise, heat, a loose guard. The phones are already in the crew's pockets, and Voice Journal is free at the worker tier. So the route needs no budget line.

## Failure Modes Detected by Phone Vibration

Here is what each fault looks like on a weekly trend:

- **Unbalance:** a steady rise at running speed, common on fans and pumps. Balance the rotor or clean off the build-up.
- **Misalignment:** a rise after a coupling change or base work. It is often strongest along the shaft. Check the alignment.
- **Looseness:** readings that jump around and get worse over weeks. Check bolts, mounts and the base.
- **Late bearing wear:** a slow climb in the overall level, often with heat and noise. Plan the bearing change.

Each of these is a trend, not a diagnosis. When one appears, bring in a real analyser. Confirm the cause before you open the machine.

**Open the tools:** two surfaces do the work here. **Voice Journal** captures each reading by voice on the round. **Engineering Design → Vibration Analysis** then judges the number. Pick the machine class, and it returns the ISO 10816-1 severity zone. If you are chasing a resonance, it also gives natural frequency. It gives transmissibility too.

## Frequently asked questions

### What is the cost of a vibration analyzer?

A dedicated analyser is a capital purchase, typically in the hundreds of thousands of pesos once the sensor, software and training are counted, and it usually has to be justified before any data exists to justify it. A phone accelerometer app plus a logged route costs nothing beyond the phones the technicians already carry, and the trend it produces is what makes the case for the analyser later.

### Can phone vibration analysis detect all types of equipment failures?

No. A phone sees low-frequency faults as a trend: unbalance, misalignment, looseness and late bearing wear. It misses early bearing damage, gear mesh, cavitation and electrical rotor faults.

### What is ISO 10816 and how does it relate to vibration analysis?

ISO 10816 evaluates machine vibration measured on non-rotating parts. Part 1 sets the general framework, and its annex puts machines into Class I to IV by power and foundation, giving each class its own A/B/C/D velocity zones: Class II (medium machines of 15 to 75 kW, or up to 300 kW on a special foundation) has boundaries at 2.8 and 7.1 mm/s RMS; Class I (15 kW and under) at 1.8 and 4.5. Part 3 works differently: for industrial machines above 15 kW it uses Group 1 (above 300 kW) and Group 2 (15 to 300 kW) on rigid or flexible foundations, with its own limits, and it was replaced in 2022 by ISO 20816-3. Quoting a single threshold without naming the class or group is the commonest way the standard gets misapplied.

### How often should I perform vibration analysis?

The frequency of vibration analysis depends on the equipment and plant conditions. A weekly walkdown route can be a good starting point for many plants.

### Can I use any phone app for vibration analysis?

Use an app that shows velocity in mm/s RMS, so you can compare it with ISO 10816-1. Use the same app and phone each week, so the trend is fair.

### Is phone vibration analysis compliant with Philippine regulations?

DOLE does not require a predictive maintenance program. A phone route is good practice, not a legal duty.

**Keep reading:** [pair it with thermography](https://workhiveph.com/learn/thermography-for-pm-philippine-plants/), or [give each machine one history](https://workhiveph.com/learn/asset-brain-360-one-machine-history-philippine-plant/).

## Sources

- ISO 10816-1, **Mechanical vibration: Evaluation of machine vibration by measurements on non-rotating parts: Part 1: General guidelines** (its annex holds the Class I–IV severity zones quoted above; superseded by ISO 20816-1:2016). ISO 20816-3:2022, which replaced ISO 10816-3, covers industrial machines above 15 kW by Group 1 and Group 2 instead of these classes.

<!-- md-twin source-sha: 781ae04353003562 -->
