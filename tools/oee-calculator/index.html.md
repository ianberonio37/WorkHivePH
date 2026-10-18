# OEE Calculator

> The OEE Calculator computes Overall Equipment Effectiveness as Availability x Performance x Quality, the single number for how much saleable output a line actually produced versus its maximum. Free online, with a worked example. Built for Philippine plants by WorkHive.

Source: https://workhiveph.com/tools/oee-calculator/

OEE Calculator
 G1+E3 
**The OEE Calculator computes Overall Equipment Effectiveness as Availability x Performance x Quality, the single number for how much saleable output a line actually produced versus its maximum. Example: for a bottling line available 90% of planned time, running at 95% of rated speed, producing 98% good bottles, OEE = 83.8 %, Availability = 90 %, Performance = 95 %, Quality = 98 %, TPM benchmark = 85 % (per Nakajima TPM and ISO 22400-2).**
How it works
OEE = Availability x Performance x Quality. Availability = run time / planned production time; Performance = (ideal cycle time x total count) / run time; Quality = good count / total count. For the example: 0.90 x 0.95 x 0.98 = 0.838, i.e. 83.8%. Anything the worked example does not state uses this calculator's standard default. The interactive version shows every input and lets you change it.
I2: reserved block 
Worked example (Reliability & Metrics)
Inputs: a bottling line available 90% of planned time, running at 95% of rated speed, producing 98% good bottles.
ResultValue
OEE83.8 %
Availability90 %
Performance95 %
Quality98 %
TPM benchmark85 %
Computed by WorkHive's calculation engine when this page was built; standard: Nakajima TPM and ISO 22400-2.
How to use this calculator
Read the worked example. It uses a bottling line available 90% of planned time, running at 95% of rated speed, producing 98% good bottles and shows every number in the method.
Follow the formula with your own figures: it returns OEE, Availability, Performance, Quality, TPM benchmark, computed per Nakajima TPM and ISO 22400-2.
To compute interactively, open the OEE Calculator inside WorkHive's free Engineering Design suite (link below). It runs the same method with your inputs.
FAQ
How do you calculate OEE?Multiply the three factors: OEE = Availability x Performance x Quality. For a line available 90% of planned time, running at 95% of rated speed, and producing 98% good units, OEE = 0.90 x 0.95 x 0.98 = 83.8%.
What is a good OEE score?85% is the benchmark Nakajima set for a mature TPM plant. Most plants start between 40% and 60%, so there is usually a large and inexpensive gap to close. Attack availability losses (unplanned downtime, changeovers) first, then speed, then quality.
Why is my OEE lower than my availability?Because availability is only one of three factors. A line that is available 90% of the time but runs slow and scraps 5% of output lands near 80% OEE. Measuring availability alone is the most common OEE mistake.
Do I need sensors to measure OEE?No. You can calculate OEE from shift records: planned time, downtime, counts produced, and rejects. A disciplined logbook is enough to start; sensors improve resolution later.
See it worked out from your own log
[See OEE for every machine in WorkHive Analytics](https://workhiveph.com/analytics.html). Free. Availability comes from the downtime your crew logs and quality from the good and total units they record; add each machine's ideal cycle time and performance joins them for the full OEE. A new account starts empty, so the figure appears once that work is being logged.
Related calculators
[Free Engineering Calculators for Philippine Plants](https://workhiveph.com/learn/free-engineering-calculators-philippine-plants/) (pillar)
[MTBF & MTTR Calculator](https://workhiveph.com/tools/mtbf-calculator/)
[What is OEE and how to calculate it](https://workhiveph.com/learn/what-is-oee-how-to-calculate/)
 wh-sources: written by tools/render_sources_area.py (ENH-R) - lines are filed into the list at runtime 
Where these figures come from
Static · formula-only · worked example computed when this page was built · no live data
 /wh-sources

<!-- md-twin source-sha: 6afd859d17a76c8b -->
