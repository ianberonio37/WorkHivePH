# Condition monitoring and the P-F interval (technical reference)

*Paraphrased reference notes (license-clean). See ISO 17359 (condition monitoring general
guidelines), ISO 13379 (data interpretation/diagnostics), ISO 13381 (prognostics).*

## The P-F curve

Most failures give warning. The **P-F interval** is the time between the point where a
potential failure first becomes detectable (**P**) and the point of functional failure
(**F**). Condition-based maintenance works by detecting **P** early enough to act before
**F**. Two rules follow:

- **Inspection interval must be shorter than the P-F interval** — typically half of it,
  so at least one inspection falls inside the warning window.
- **A longer P-F interval is more useful**: a technique that warns months ahead (oil
  analysis of gear wear) gives more planning room than one that warns hours ahead.

The earliest, longest-warning techniques sit at the top of the P-F curve: oil/wear-debris
analysis and vibration trending warn earliest; audible noise, heat, and smoke are
late-stage indicators where little planning time remains.

## The main condition-monitoring techniques

- **Vibration analysis** — the workhorse for rotating equipment. Detects imbalance,
  misalignment, looseness, bearing defects (with characteristic defect frequencies:
  BPFO, BPFI, BSF, FTF), and gear wear. Broadband velocity (mm/s RMS) trends overall
  health; spectrum and envelope/demodulation diagnose the specific fault.
- **Oil analysis** — viscosity, contamination (water, fuel, dirt), additive depletion,
  and wear-metal spectrometry (Fe, Cu, Cr, Pb...) reveal lubricant condition and which
  component is wearing. Often the earliest warning for gearboxes and engines.
- **Thermography** — infrared imaging finds electrical hot-spots (loose/corroded
  connections, load imbalance) and mechanical heat (bearing friction, steam-trap
  failure). Compare phase-to-phase and against a similar healthy asset.
- **Ultrasound** — high-frequency airborne/structure-borne sound finds early bearing
  friction/lack of lubrication, valve passing, steam-trap and compressed-air leaks.
- **Motor current signature analysis (MCSA)** — current spectrum reveals broken rotor
  bars, eccentricity, and load anomalies without intruding on the machine.

## How to apply it

Pick the technique by failure mode and P-F interval, set the inspection interval below
P-F, **establish a baseline** on a known-good machine, trend against alarm bands, and
confirm a single indicator with a second technique before a teardown. Condition
monitoring replaces calendar overhaul with evidence: maintain on the curve, not the clock.
