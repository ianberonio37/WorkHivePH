# Vibration severity zones (ISO 10816-3) — quick technical reference

ISO 10816-3 evaluates broadband vibration **velocity (RMS, mm/s)** measured on the
bearing housings of in-situ industrial machines (typically 15 kW–50 MW). Severity is
graded into four evaluation zones:

- **Zone A** — newly commissioned machines; vibration is low.
- **Zone B** — acceptable for unrestricted long-term operation.
- **Zone C** — unsatisfactory; not acceptable for long-term continuous operation.
  Plan corrective action at the next convenient opportunity.
- **Zone D** — severe; vibration is likely to cause damage. Investigate and correct
  before further operation.

## Canonical boundary values (medium machines, 15–300 kW, rigid foundation)

| Zone boundary | Velocity RMS |
|---|---|
| A / B | 2.3 mm/s |
| B / C | 4.5 mm/s |
| C / D | **7.1 mm/s** |

So for a medium machine on a rigid foundation, a broadband velocity reading **above
7.1 mm/s RMS sits in Zone D — the damage zone — and the machine should be taken
offline for investigation** before it runs further. Flexible foundations shift the
boundaries higher (e.g. C/D ≈ 11 mm/s). These are paraphrased reference values; always
confirm against the OEM's acceptance limits for the specific machine class.
