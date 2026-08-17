# Free engineering design calculators for Philippine plants

> Free, standards-referenced engineering design calculators covering HVAC and cooling, mechanical, electrical, plumbing, fire protection, and machine design. Built for Philippine plants and tropical-climate constants.

Source: https://workhiveph.com/learn/free-engineering-calculators-philippine-plants/

Engineering Design · Standards-referenced

By **WorkHive Editorial Team**
·
Published 17 May 2026
·
Updated 17 May 2026
·
10 min read

**Short answer:** WorkHive Engineering Design is a free set of 53 standards-referenced calculators across six disciplines: HVAC and cooling, mechanical, electrical, plumbing, fire protection, and machine design. Each calculator is built on the relevant standard (PEC 2017, ASHRAE, PSME, NFPA, ISO) and applies Philippine tropical-climate constants where they matter. It replaces 30 minutes of careful spreadsheet work with 30 seconds of structured input, and produces a PDF report a licensed PME or PEE can sign off. Built for the full engineering team: junior engineers, design and project engineers, licensed engineers, consultants, contractors, and engineering students building a portfolio.

Who this is for

- Maintenance and reliability engineers
- Design and project engineers
- Junior engineers verifying senior work
- Licensed PMEs and PEEs (sanity check)
- Consulting engineers and contractors
- Engineering students learning standards
- New graduates building OFW-track portfolio

## Why every Philippine plant engineer needs design calculators

Walk into any Philippine engineering office and you will see the same workflow: open a 5-year-old Excel sheet inherited from a senior engineer, change three numbers, hope the formula still works, manually look up a coefficient in a printed ASHRAE handbook, type it in, get an answer, doubt the answer, redo it differently, get a different answer, pick one, send it off.

This pattern wastes 2 to 4 hours per design and produces inconsistent answers because:

- The spreadsheet was written by someone who left in 2021 and nobody has reviewed the formula since
- The coefficient table is the 2012 edition; ASHRAE 2021 has different values
- The standard temperate constants do not match Philippine 35 degree C ambient
- The licensed PME or PEE doing final sign-off has no time to redo the calculation, so they sign what they get

A standards-referenced calculator fixes all four. It uses the current standard, the right tropical constants, the same formula for every junior engineer in the team, and produces a structured report the senior engineer can verify in 60 seconds. This is the same productivity case that the digital logbook makes for technicians at [Stage 1](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/): replace ad-hoc memory with structured records.

## The 6 disciplines covered

| Discipline | Calculators included |
| --- | --- |
| **HVAC & Cooling** | Cooling load, ventilation and air changes (ACH), chilled-water flow, duct sizing (ASHRAE equal-friction), fan static pressure, FCU and AHU selection |
| **Mechanical** | Pump sizing and NPSH, fan sizing, bearing life, V-belt tension, coupling alignment tolerance, gear ratio |
| **Electrical** | Transformer sizing, cable and conductor sizing (PEC 2017), motor selection, panel and load calculations, voltage drop, power factor correction |
| **Plumbing** | Pipe sizing and velocity, pump head, expansion-tank sizing, pipe slope and drainage, pressure drop (Darcy-Weisbach) |
| **Fire Protection** | Sprinkler hydraulics (NFPA 13), smoke and heat detector counts, manual pull stations (NFPA 72), fire pump selection |
| **Machine Design** | Bolt and metric-thread selection (M10 to M30), fastener torque, gear and shaft design, keyway sizing |

Total: 53 specific calculators across 6 disciplines, each tagged with its applied standard (PEC 2017, ASHRAE, PSME, NFPA, ISO).

## Tropical constants: why the temperate defaults are wrong here

Most engineering design software ships with default constants from temperate climates (20 degree C, sea level). The Philippines runs at 30 to 35 degree C with humidity well above the temperate default. The difference matters for any calculation that depends on air density, viscosity, or saturation pressure.

| Property | Temperate (20 degree C) | Tropical (35 degree C, PH) | Affects |
| --- | --- | --- | --- |
| Air density rho | 1.204 kg/m3 | 1.15 kg/m3 (4% lower) | Fan sizing, duct pressure |
| Air viscosity mu | 1.81e-5 Pa s | 1.90e-5 Pa s (5% higher) | Reynolds number, friction |
| Kinematic viscosity nu | 1.505e-5 m2/s | 1.652e-5 m2/s (10% higher) | Duct sizing K constant |
| Saturation pressure | ~2.3 kPa | ~5.6 kPa | Cooling load, condensate |

The duct-sizing K constant in the equal-friction formula is K = 0.01811 for temperate, K = 0.01740 for tropical. Using the temperate K in a Philippine project gives undersized duct, 5 to 10 percent low fan static, and a fan motor that struggles in real ambient. The WorkHive HVAC calculator uses tropical K by default.

## Worked example: HVAC duct sizing for a 100 kW office cooling load

A real Philippine project: a 1,200 m2 BPO office in BGC needs HVAC duct sizing for a 100 kW total cooling load split across 4 zones.

### Step 1: Calculate volume flow per branch

### Step 2: Pick a design friction rate

Office cooling, low-noise requirement: `fr = 1.0 Pa/m`

### Step 3: Apply the equal-friction formula

### Step 4: Convert to rectangular at 2:1 aspect ratio

Using ASHRAE De equation, target a:b = 2:1:

### Step 5: Recompute D_h for pressure-drop calc

If a junior engineer uses De (541 mm) instead of D_h (467 mm) in the pressure-drop calculation, the result is 15 percent low. The fan gets undersized. The plant runs the fan flat-out and still gets warm zones in Manila humidity. The WorkHive HVAC calculator shows the formula and an input field reference for each calculation, so you can verify which diameter it expects before trusting the result.

The tool this guide is about

#### WorkHive Engineering Design replaces 30 minutes of spreadsheet work with 30 seconds

53 standards-referenced calculators across 6 disciplines (HVAC and cooling, mechanical, electrical, plumbing, fire protection, machine design). Each output is tagged with its applied standard (PEC 2017, ASHRAE, PSME, NFPA, ISO) and Philippine tropical constants where they matter. PDF report ready for licensed PME or PEE sign-off. Saved designs build your engineering portfolio. Free at the worker tier forever.

No hive yet? [Join WorkHive](https://workhiveph.com/#join) first (free, takes 30 seconds).

## All 60 calculators

Every calculator below is free, works offline, and shows the formula plus a worked example with real numbers. Grouped by discipline:

### Reliability & Metrics (2)

- [MTBF & MTTR Calculator](https://workhiveph.com/tools/mtbf-calculator/)
- [OEE Calculator](https://workhiveph.com/tools/oee-calculator/)

### Electrical & Power (15)

- [Cable Tray Sizing Calculator](https://workhiveph.com/tools/cable-tray-sizing-calculator/)
- [Earthing / Grounding Calculator](https://workhiveph.com/tools/earthing-grounding-calculator/)
- [Electrical Load Estimation Calculator](https://workhiveph.com/tools/load-estimation-calculator/)
- [Electrical Load Schedule Calculator](https://workhiveph.com/tools/load-schedule-calculator/)
- [Generator Sizing Calculator](https://workhiveph.com/tools/generator-sizing-calculator/)
- [Harmonic Distortion (THD/TDD) Calculator](https://workhiveph.com/tools/harmonic-distortion-calculator/)
- [Lighting Design Calculator](https://workhiveph.com/tools/lighting-design-calculator/)
- [Lightning Protection Calculator](https://workhiveph.com/tools/lightning-protection-calculator/)
- [Power Factor Correction Calculator](https://workhiveph.com/tools/power-factor-correction-calculator/)
- [Short Circuit Calculator](https://workhiveph.com/tools/short-circuit-calculator/)
- [Solar PV System Calculator](https://workhiveph.com/tools/solar-pv-calculator/)
- [Transformer Sizing Calculator](https://workhiveph.com/tools/transformer-sizing-calculator/)
- [UPS Sizing Calculator](https://workhiveph.com/tools/ups-sizing-calculator/)
- [Voltage Drop Calculator](https://workhiveph.com/tools/voltage-drop-calculator/)
- [Wire Sizing Calculator](https://workhiveph.com/tools/wire-sizing-calculator/)

### HVAC & Cooling (10)

- [AHU Sizing Calculator](https://workhiveph.com/tools/ahu-sizing-calculator/)
- [Chiller Sizing Calculator](https://workhiveph.com/tools/chiller-sizing-calculator/)
- [Compressed Air System Calculator](https://workhiveph.com/tools/compressed-air-calculator/)
- [Cooling Tower Sizing Calculator](https://workhiveph.com/tools/cooling-tower-calculator/)
- [Duct Sizing Calculator](https://workhiveph.com/tools/duct-sizing-calculator/)
- [Expansion Tank Sizing Calculator](https://workhiveph.com/tools/expansion-tank-calculator/)
- [FCU Selection Calculator](https://workhiveph.com/tools/fcu-selection-calculator/)
- [HVAC Cooling Load Calculator](https://workhiveph.com/tools/hvac-cooling-load-calculator/)
- [Refrigerant Pipe Sizing Calculator](https://workhiveph.com/tools/refrigerant-pipe-calculator/)
- [Ventilation / ACH Calculator](https://workhiveph.com/tools/ventilation-ach-calculator/)

### Plumbing & Pumps (14)

- [Domestic Water Demand Calculator](https://workhiveph.com/tools/domestic-water-demand-calculator/)
- [Drainage Pipe Sizing Calculator](https://workhiveph.com/tools/drainage-pipe-sizing-calculator/)
- [Grease Trap Sizing Calculator](https://workhiveph.com/tools/grease-trap-calculator/)
- [Hot Water Demand Calculator](https://workhiveph.com/tools/hot-water-demand-calculator/)
- [Pipe Sizing Calculator](https://workhiveph.com/tools/pipe-sizing-calculator/)
- [Pump TDH Calculator](https://workhiveph.com/tools/pump-tdh-calculator/)
- [Roof Drain Sizing Calculator](https://workhiveph.com/tools/roof-drain-calculator/)
- [Sanitary Drainage Calculator](https://workhiveph.com/tools/sewer-drainage-calculator/)
- [Septic Tank Sizing Calculator](https://workhiveph.com/tools/septic-tank-calculator/)
- [Storm Drain Calculator](https://workhiveph.com/tools/storm-drain-calculator/)
- [Wastewater Treatment (STP) Calculator](https://workhiveph.com/tools/wastewater-stp-calculator/)
- [Water Softener Sizing Calculator](https://workhiveph.com/tools/water-softener-calculator/)
- [Water Supply Pipe Sizing Calculator](https://workhiveph.com/tools/water-supply-pipe-calculator/)
- [Water Treatment Sizing Calculator](https://workhiveph.com/tools/water-treatment-calculator/)

### Mechanical & Machine Design (10)

- [Bearing Life (L10) Calculator](https://workhiveph.com/tools/bearing-life-calculator/)
- [Bolt Torque Calculator](https://workhiveph.com/tools/bolt-torque-calculator/)
- [Heat Exchanger LMTD Calculator](https://workhiveph.com/tools/heat-exchanger-calculator/)
- [Hydraulic Cylinder Calculator](https://workhiveph.com/tools/hydraulic-cylinder-calculator/)
- [Noise / Acoustics Calculator](https://workhiveph.com/tools/noise-acoustics-calculator/)
- [Pressure Vessel Shell Calculator](https://workhiveph.com/tools/pressure-vessel-calculator/)
- [RC Beam Design Calculator](https://workhiveph.com/tools/beam-design-calculator/)
- [Shaft Design Calculator](https://workhiveph.com/tools/shaft-design-calculator/)
- [V-Belt Drive Calculator](https://workhiveph.com/tools/v-belt-drive-calculator/)
- [Vibration Isolation Calculator](https://workhiveph.com/tools/vibration-isolation-calculator/)

### Fire Protection (5)

- [Clean Agent Suppression Calculator](https://workhiveph.com/tools/clean-agent-suppression-calculator/)
- [Fire Alarm Battery Calculator](https://workhiveph.com/tools/fire-alarm-battery-calculator/)
- [Fire Pump Sizing Calculator](https://workhiveph.com/tools/fire-pump-calculator/)
- [Fire Sprinkler Hydraulic Calculator](https://workhiveph.com/tools/fire-sprinkler-calculator/)
- [Stairwell Pressurization Calculator](https://workhiveph.com/tools/stairwell-pressurization-calculator/)

### Boiler & Utilities (2)

- [Boiler / Steam Duty Calculator](https://workhiveph.com/tools/boiler-steam-calculator/)
- [Boiler System Sizing Calculator](https://workhiveph.com/tools/boiler-system-calculator/)

### Vertical Transport (2)

- [Elevator Traffic Calculator](https://workhiveph.com/tools/elevator-traffic-calculator/)
- [Hoist Capacity Calculator](https://workhiveph.com/tools/hoist-capacity-calculator/)

## Standards referenced by each calculator

| Calculator | Primary standard |
| --- | --- |
| HVAC duct sizing | ASHRAE 2021 Fundamentals Ch 21, SMACNA HVAC Duct Construction |
| HVAC fan static | ASHRAE 62.1, AMCA 210 |
| Cooling tower sizing | ASHRAE Handbook HVAC Systems Ch 39 |
| Transformer sizing | IEC 60076, NEMA TR-1 |
| Cable sizing (LV) | IEC 60364-5-52, PEC 2017 |
| Cable sizing (MV) | IEC 60502 |
| Lightning protection | IEC 62305, NFPA 780 |
| Substation grounding | IEEE 80, IEEE 81 |
| Pump sizing | API 610, ANSI HI 1.3 |
| Bearing life | ISO 281, ISO 76 |
| Sprinkler hydraulics | NFPA 13, NFPA 20 |
| Generator sizing | ISO 8528-1, NFPA 110 |
| Lighting design | IESNA Lighting Handbook, PEC 2017 |
| Structural beam | NSCP 2015 (Philippine), AISC 360 |
| Control valve sizing | ISA-75.01, IEC 60534 |

## Calculator versus licensed engineer sign-off

A common question: "If the calculator gives me the answer, do I still need a PME or PEE to sign?"

Yes. The calculator gives you an engineering-grade answer that a junior engineer would produce in 30 minutes of careful work. The licensed engineer is responsible for:

- **Code compliance** (NSCP 2015 for structural, PEC 2017 for electrical, NFPA for fire) and Philippine regulatory submissions
- **Site-specific judgment** (the calculator does not know that this BGC site has limited overhead clearance, or that this plant has 5 percent extra voltage drop on the upstream feeder)
- **Professional liability** for the design under the Philippine Mechanical Engineering Act, Electrical Engineering Law, or Civil Engineering Law
- **Coordination across disciplines** (the electrical engineer's design must respect the HVAC engineer's load and the structural engineer's space)

What changes: the licensed engineer's review time drops from "redo the calculation from scratch" (3 hours per design) to "verify the inputs and sanity-check the output" (15 minutes). That capacity gain is the real value of standards-referenced calculators.

## Your design history as a career portfolio

This is the part most Filipino engineers underuse: the design history saved in WorkHive Engineering Design is a verifiable professional portfolio.

When a Filipino engineer applies for:

- An OFW position in Saudi, UAE, Qatar, or Singapore
- An internal promotion from junior to senior engineer
- A consulting engagement with a new client
- A PRC licensure interview

The hiring manager or reviewer wants to see verifiable work. A folder of saved WorkHive calculations with dates, applied standards, and PDF reports is exactly that. It is the engineering equivalent of the documented logbook history we make the worker-protection case for in the [Skill Matrix guide](https://workhiveph.com/learn/skill-matrix-for-maintenance-technicians/).

In the AI era, engineers whose work is documented get promoted. Engineers whose work lives only in PDFs scattered on local drives get bypassed. Document your designs.

## Common mistakes when using design calculators

- **Skipping the standard check.** If the calculator does not tell you which standard it applied, do not use it. Anonymous calculators on random websites give wrong answers with confidence.
- **Using temperate constants in a Philippine design.** Always verify the calculator is using tropical defaults for air, water, and humidity properties.
- **Treating the output as final without coordination.** A 100 kW HVAC design that ignores the electrical room load and the structural ceiling height will fail in installation regardless of how correct the HVAC math is.
- **Not saving the calculation report.** Six months later when the owner asks "why is this fan 30 kW and not 25 kW?", you need the dated calculation. Save every design.
- **Letting the senior engineer skip review.** The calculator removes the redo burden, not the review burden. The PME or PEE still owns the design.

**The bigger picture:** Standards-referenced calculators do for engineering what the digital logbook does for maintenance. They replace ad-hoc tribal knowledge with structured, verifiable, portable records. Plants and engineers that adopt them compound their work over years. Plants and engineers that resist them stay dependent on the senior engineer's memory.

## Frequently asked questions

### What engineering disciplines do the WorkHive calculators cover?

Six disciplines: HVAC and cooling (cooling load, ventilation and air changes, chilled-water flow, duct sizing per ASHRAE, FCU and AHU selection), mechanical (pump sizing and NPSH, fan sizing, bearing life, belt tension, alignment, gear ratio), electrical (transformer sizing, cable and conductor sizing per PEC 2017, motor selection, panel and load calculations, voltage drop), plumbing (pipe sizing and velocity, pump head, expansion-tank sizing, pipe slope and drainage), fire protection (sprinkler hydraulics per NFPA 13, smoke and heat detector counts, pull stations per NFPA 72, fire pump selection), and machine design (bolt and metric-thread selection, fastener torque, gear and shaft design, keyway sizing). All 53 calculators reference the relevant standard, PEC 2017, ASHRAE, PSME, NFPA, or ISO, and apply Philippine tropical constants where they matter.

### Why use tropical-climate constants instead of standard ASHRAE values?

Standard ASHRAE constants assume 20 degree C ambient at sea level (rho = 1.204 kg/m3). Philippine ambient averages 30 to 35 degree C with high humidity (rho = 1.15 kg/m3). The 4 percent density difference matters for fan sizing, duct pressure-drop, and refrigerant capacity. Using temperate constants in a tropical design gives undersized fans and unmet cooling load. The WorkHive HVAC calculator uses K = 0.01740 (35 degree C tropical) by default, not the temperate 0.01811.

### Are the calculators a substitute for a licensed PME or PEE sign-off?

No. The calculators give you the engineering-grade answer that a junior engineer would produce in 30 minutes of careful work. A licensed Professional Mechanical Engineer (PME) or Professional Electrical Engineer (PEE) still signs the final design for code compliance and professional liability. The calculators reduce the junior engineer's time from 30 minutes to 30 seconds and give the licensed engineer a sanity-check baseline before sign-off.

### What standards do the calculators reference?

The WorkHive Engineering Design tool tags every output with its standard authority. Common references: ASHRAE 2021 Fundamentals (HVAC), IEC 62305 (lightning), IEC 60364 (LV electrical installations), IEEE 80 (substation grounding), NFPA 13 (sprinkler systems), ISO 8528-1 (generator sets), ISO 14224 (reliability data), SMACNA HVAC Duct Construction, ASHRAE 62.1 (ventilation), IESNA Lighting Handbook, API 610 (pumps), DOLE OSHS for Philippine safety, NSCP 2015 (structural). Each output cites the chapter and clause used.

### Can I export the calculation report as a PDF for sign-off?

Yes. Every calculation in the WorkHive Engineering Design tool produces a structured report with input values, intermediate steps, applied standards, and final answer. The PDF export is formatted for licensed engineer review and inclusion in project bid documents or as-built records. The format follows the typical Philippine government and DOLE submission style.

### What happens to my designs if I leave the plant?

Your saved calculations stay in your hive's project history and can be exported with you (subject to your employment IP terms). For Filipino engineers building a portfolio for overseas work or OFW positions, the WorkHive design history is a verifiable record of work done, complete with date stamps and applied standards. This is the Engineering equivalent of the career-protection argument we make for technicians in the Skill Matrix guide: documented work compounds; undocumented work disappears.

## Sources

- ASHRAE, **2021 Fundamentals Handbook, Chapter 21 (Duct Design)**.
- SMACNA, **HVAC Duct Construction Standards, 3rd Edition**.
- IEC 62305, **Protection against lightning**, all parts.
- IEEE 80, **Guide for Safety in AC Substation Grounding**.
- NFPA 13, **Installation of Sprinkler Systems**.
- ISO 8528-1, **Reciprocating internal combustion engine driven alternating current generating sets**.
- NSCP 2015, **National Structural Code of the Philippines**.
- PEC 2017, **Philippine Electrical Code**.
- WorkHive platform positioning, "Four Gaps One Hive": Execution, Skills, Intelligence, Marketplace. [workhiveph.com](https://workhiveph.com/)
- Related WorkHive guides: [Skill matrix](https://workhiveph.com/learn/skill-matrix-for-maintenance-technicians/) · [Digital logbook rollout](https://workhiveph.com/learn/start-digital-logbook-philippine-factory/)

[← Back to all guides](https://workhiveph.com/learn/)

<!-- md-twin source-sha: cbc864b734a3d0ca -->
