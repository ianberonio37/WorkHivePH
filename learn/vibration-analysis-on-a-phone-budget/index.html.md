# Vibration Analysis on a Phone Budget (Philippine PdM)

> Learn how to run a phone-based vibration trend route in a Philippine plant: what a phone accelerometer can and cannot see, how to log readings with Voice Journal, and how to judge them against the ISO 10816-3 severity zone for the machine's class.

Source: https://workhiveph.com/learn/vibration-analysis-on-a-phone-budget/

WorkHive Learn · Philippines

By WorkHive Editorial Team
·
18 May 2026
·
8 min read

**Short answer:** Predictive maintenance (PdM) is crucial for Philippine plants to reduce downtime and increase efficiency. However, not all plants have the budget for expensive vibration analyzers. Fortunately, phone-based vibration analysis apps can provide a cost-effective solution. Judge every reading against **ISO 10816-3**, and against the right machine class: on a medium machine (Class II, 15–300 kW on a rigid foundation) **2.8 mm/s** RMS is where it stops being satisfactory and **7.1 mm/s** is where it becomes severe. On a small machine (Class I, ≤15 kW) those boundaries are 1.8 and 4.5. WorkHive’s Vibration Analysis calculator works the zone out for you once you pick the class.

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

Phone-based vibration analysis is a practical approach to Predictive Maintenance (PdM) for Philippine plants with limited budgets. Instead of investing in an analyser first, a plant supervisor at a PEZA industrial site in Batangas can start with two things they already have: a third-party accelerometer app to take the reading, and WorkHive to record and judge it. Be clear about which does what — **Voice Journal does not measure vibration**; it is a voice-to-text journal, and its job here is to capture the number and the context the moment you read it. The measuring is done by any of the accelerometer apps on the store, which use the phone's built-in accelerometer. That accelerometer is the whole constraint: it typically samples up to about 100 Hz, which covers a machine turning below roughly 30 Hz: most pumps, fans and motors under 1,800 RPM, and the first few harmonics above it. Everything faster than that is invisible to it, which is what the can-and-cannot list below is really describing.

A maintenance planner at a Pampanga manufacturing plant runs this on the phone already in their pocket, where a traditional analyser is a capital purchase with a lead time. The discipline is the same whichever app takes the reading: a fixed schedule: the same point, the same machine state, the same day each week: with each number dictated into Voice Journal, which timestamps it and keeps the entry searchable.

Phone-based vibration analysis can detect certain types of equipment problems, such as bearing wear. For example, a shift in-charge at a Bulacan power plant can use an app to identify imbalance or misalignment in Pump P-204B. However, it may not be able to detect more complex issues like gear-mesh frequencies. Understanding these limitations is crucial for effective PdM.

A weekly walkdown route using Voice Journal can be an effective way to integrate phone-based vibration analysis into a plant's PdM routine. By taking readings at regular intervals, maintenance teams can track changes in vibration levels over time and identify potential issues before they become major problems. This approach has been successfully implemented at a Cabuyao industrial site in Calabarzon.

Phone-based vibration analysis can detect three key failure modes: imbalance, misalignment, and bearing wear. By monitoring these issues, plants can prevent unexpected downtime and extend equipment lifespan. For instance, monitoring vibration levels on Boiler B-1 can help prevent costly repairs and ensure smooth operation.

## Logging Readings with Voice Journal

During a weekly walkdown route at a PEZA plant in Cabuyao, Laguna, a maintenance planner reads each machine with the accelerometer app and dictates the number into Voice Journal on the spot. That is the part people skip and the part that decides whether the route is worth running: a reading that stays on the measuring app's screen is gone by the next machine. Voice Journal timestamps the entry and keeps it searchable, so the trend exists.

A typical walkdown route might include critical equipment like Pump P-204B at a Bulacan manufacturing plant. On the walkdown, the shift in-charge dictates each reading into Voice Journal as it is taken. The numbers are then compared against the ISO 10816-3 zone for that machine's class: on a Class II medium machine, above 2.8 mm/s is unsatisfactory and above 7.1 mm/s is severe. Take the class from the motor rating, not from how big the machine looks: 4.5 is the severe threshold for a Class I machine of 15 kW or less, and using it on a 55 kW pump will have you chasing readings ISO 10816-3 calls acceptable.

Voice Journal is particularly useful for detecting certain failure modes, such as bearing wear. However, it's not suitable for detecting gear-mesh frequencies, which typically require more specialized equipment. A plant supervisor at a Davao plant might use Voice Journal to track vibration readings on a weekly basis, focusing on equipment with a history of bearing issues.

When using Voice Journal for vibration analysis, it's essential to establish a consistent routine. For example, a maintenance planner at a Pampanga plant might take readings at the same point in the week, on the same shift, with the machine in the same state. By doing so, you can ensure that you're capturing accurate, comparable data that helps you identify potential issues before they lead to equipment failure.

A weekly walkdown route using Voice Journal can be done at a fraction of the cost of traditional vibration analysis equipment. For many Philippine plants a dedicated analyser is out of reach for a first route - not because of what it costs on the day, but because it is a capital request that has to be justified before any data exists to justify it. In contrast, many maintenance teams already have access to a smartphone and Voice Journal, making it a cost-effective solution for vibration analysis.

## What Can and Can't Phone Vibration Detect?

When conducting vibration analysis using a phone-based app like Voice Journal, it's essential to understand what it can and cannot detect. In a Philippine plant like the one in Cabuyao, Laguna, maintenance teams can use these apps to monitor equipment health. For instance, at the PEZA-designated zone in Calabarzon, plant supervisors can utilize Voice Journal to log readings and track changes in vibration severity over time. However, it's crucial to recognize the limitations of these apps, particularly when it comes to detecting specific types of failures or frequency ranges.

A phone accelerometer reliably catches some failure modes and misses others, whatever app reads it:

- **Can detect:** unbalance, misalignment, looseness, and bearing wear.
- **Cannot detect:** gear-mesh frequencies and other high-frequency phenomena, which need more specialized equipment.

For example, at a plant in Pampanga running around the clock, a shift in-charge takes a reading at the same point on each shift and logs it to Voice Journal, building the per-shift history for critical equipment like Pump P-204B.

In terms of detectable failure modes, phone vibration analysis is a TRENDING tool for the low-frequency faults above: unbalance, misalignment, looseness, and advanced bearing wear once it has raised the overall level. It will not characterise cavitation or an electrical rotor fault: those live at frequencies the phone cannot reach, and a rising trend on the phone is a reason to bring a real analyser, not a diagnosis. For instance, at a plant in Batangas, maintenance planners can use Voice Journal to track changes in vibration severity over time, allowing them to schedule maintenance activities during planned outages. The app can help identify potential issues before they become major problems, reducing downtime and increasing overall equipment effectiveness. By using Voice Journal to log readings and track trends, maintenance teams can prioritize maintenance activities and reduce the risk of unexpected failures.

It's also important to note that phone-based vibration analysis should not replace more comprehensive vibration analysis techniques, but rather complement them. A dedicated analyser is a capital purchase; phone-based apps like Voice Journal cost the plant nothing beyond the phones the technicians already carry. What a phone route buys is a TREND per machine - the same point, the same week, the same hand - which is what tells a team which machine is changing and which is merely loud, and so which to prioritise for maintenance activities, even on a limited budget. For example, a plant in Bulacan can use Voice Journal to monitor equipment vibration levels and identify potential issues before they become major problems, helping to reduce maintenance costs and increase overall plant efficiency.

## A Weekly Walkdown Route for Vibration Analysis

For a typical Philippine plant, such as those in Calabarzon or Batangas, implementing a weekly walkdown route for vibration analysis can be a practical approach to Predictive Maintenance (PdM). With an accelerometer app to read and Voice Journal to log, maintenance personnel can capture readings and notes during their rounds without stopping to type. For example, at a plant in Cabuyao, Laguna, a weekly route could include checking critical equipment like Pump P-204B, Boiler B-1, and Conveyor #2, always at the same point in the shift.

A sample weekly walkdown route might start at the Pump House, where readings are taken on Pump P-204B using Voice Journal. The maintenance planner would then proceed to the Boiler area to check Boiler B-1, followed by the Conveyor belt system. At each stop, the vibration readings are logged, and any anomalies or concerns are noted. This systematic approach helps ensure that critical equipment is monitored regularly, reducing the risk of unexpected failures.

During the walkdown, Voice Journal can be used to record voice notes or dictate observations, making it easier to document findings. For instance, if the reading on Pump P-204B lands in Zone C or D for its class, the voice note is where you say so in words: Voice Journal has no threshold or alert of its own, so the judgement has to be in the entry for anyone reading it later. This facilitates prompt action and helps prevent equipment damage.

A basic phone-based toolkit needs no budget line at all: the technicians have the phones, and the app is free at the worker tier. This affordable solution enables more frequent monitoring and faster response to potential issues, ultimately reducing downtime and increasing overall equipment effectiveness.

By incorporating a weekly walkdown route for vibration analysis into their maintenance routine, Philippine plants can proactively identify potential problems. For example, at a plant in Bulacan, a maintenance team using Voice Journal detected bearing wear on a critical fan, allowing them to schedule a replacement before a failure occurred. This approach helps extend equipment lifespan and improves plant reliability.

## Failure Modes Detected by Phone Vibration

Phone vibration analysis using Voice Journal can detect various failure modes in equipment. One such failure mode is imbalance, which can occur in rotating equipment like pumps and fans. For instance, at the Calabarzon industrial zone, a plant supervisor used Voice Journal to monitor the vibration levels of Pump P-204B. By regularly taking readings, they were able to identify an imbalance issue before it caused a major breakdown. This proactive approach helped prevent costly repairs and reduced downtime.

Another failure mode that phone vibration analysis can detect is misalignment. This occurs when two or more rotating components are not properly aligned, causing excessive vibration. A maintenance planner at a PEZA industrial estate in Bulacan used Voice Journal to track the vibration levels of Conveyor #2. By analyzing the data, they identified a misalignment issue and were able to correct it before it led to equipment failure. It caught the fault while it was still a bearing change rather than a shaft.

Looseness is a third failure mode that phone vibration analysis can detect. This occurs when equipment components become loose, causing vibration levels to increase. At a 24-hour plant in Pampanga, a shift in-charge used Voice Journal to monitor the vibration levels of AHU-3 at each shift change. By regularly taking readings, they were able to identify a looseness issue and tighten the loose components before it caused a major problem. This proactive approach helped ensure equipment reliability and reduced the risk of unexpected downtime.

By using Voice Journal for phone vibration analysis, maintenance teams can detect these failure modes and take proactive steps to prevent equipment failures. Regular walkdown routes and readings can help identify potential issues before they become major problems. For example, a plant in Davao used Voice Journal to establish a weekly walkdown route, which helped them identify and address potential issues before they caused downtime. This approach can be particularly effective in Philippine plants, where budget constraints may limit the use of more expensive vibration analysis tools.

Effective use of phone vibration analysis requires a thorough understanding of the equipment being monitored and the failure modes that can occur. By combining Voice Journal with knowledge of equipment operation and maintenance, teams can identify potential issues and take proactive steps to prevent failures. For instance, a plant in Batangas used Voice Journal to monitor the vibration levels of Boiler B-1 and was able to identify a potential issue before it caused a major breakdown. This approach can help Philippine plants reduce downtime and improve overall equipment reliability.

**Open the tools:** two surfaces do the work here. **Voice Journal** captures each reading by voice on the round, offline. **Engineering Design → Vibration Analysis** then judges the number: pick the machine class and it returns the ISO 10816-3 severity zone, along with natural frequency and transmissibility if you are chasing a resonance.

## Frequently asked questions

### What is the cost of a vibration analyzer?

A dedicated analyser is a capital purchase, typically in the hundreds of thousands of pesos once the sensor, software and training are counted, and it usually has to be justified before any data exists to justify it. A phone accelerometer app plus a logged route costs nothing beyond the phones the technicians already carry, and the trend it produces is what makes the case for the analyser later.

### Can phone vibration analysis detect all types of equipment failures?

No, phone vibration analysis has its limitations. It can detect certain types of failures, such as bearing wear, but may not detect others, such as gear-mesh frequencies.

### What is ISO 10816 and how does it relate to vibration analysis?

ISO 10816 evaluates machine vibration measured on non-rotating parts. Part 1 sets the general framework; Part 3 is the one you use on plant, because it puts machines into Class I to IV by power and foundation and gives each class its own A/B/C/D velocity zones. Class II covers 15-300 kW on a rigid foundation, with boundaries at 2.8 and 7.1 mm/s RMS; Class I covers 15 kW and under, at 1.8 and 4.5. Quoting a single threshold without naming the class is the commonest way the standard gets misapplied.

### How often should I perform vibration analysis?

The frequency of vibration analysis depends on the equipment and plant conditions. A weekly walkdown route can be a good starting point for many plants.

### Can I use any phone app for vibration analysis?

No, not all phone apps are suitable for vibration analysis. Look for apps that are specifically designed for vibration analysis and have good reviews from users.

### Is phone vibration analysis compliant with Philippine regulations?

The Department of Labor and Employment (DOLE) requires plants to implement a predictive maintenance program. Phone vibration analysis can be a part of this program, but ensure that it meets the requirements of DOLE and other relevant regulations.

**Keep reading:** [pair it with thermography](https://workhiveph.com/learn/thermography-for-pm-philippine-plants/), or [give each machine one history](https://workhiveph.com/learn/asset-brain-360-one-machine-history-philippine-plant/).

## Sources

- ISO 10816-3, **Mechanical vibration: Evaluation of machine vibration by measurements on non-rotating parts: Part 3: Industrial machines** (the Class I–IV severity zones quoted above). Part 1:2009 gives the general framework.

<!-- md-twin source-sha: 83d6088ec9b255fd -->
