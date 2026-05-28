# Phantom Capture Audit (Layer -1.5 reverse-lineage)

Every HTML form field that no engine, brain, or dashboard reads.
Run by `tools/audit_phantom_captures.py`. Output is a deletion
candidates punch list. To keep a field, add `phantom-allow: <key> <reason>`
as an HTML comment on the capture page.

## Summary

- Capture fields discovered:  **500**
- Framework names skipped:    **2** (submit, search, csrf, ...)
- Alive (≥1 consumer):        **498** ✅
- Phantom (0 consumers):      **0** ❌
- Allowlisted (justified):    **0**

## Deletion candidates (0)

_None — every capture has at least one downstream consumer. Schema discipline is currently good; the gate locks this in against future drift._


## Low-usage candidates — `consumer_count == 1` (219)

Fields read in exactly one place. Likely fine (single-purpose),
but worth a scan for vestigial half-wired fields.

| Capture name | Captured on |
|---|---|
| `a-scan-input` | logbook.html |
| `custom-item-freq` | pm-scheduler.html |
| `edge-target` | asset-hub.html |
| `edge-type` | asset-hub.html |
| `f-C-rating` | engineering-design.html |
| `f-Fa` | engineering-design.html |
| `f-Fr` | engineering-design.html |
| `f-Mu` | engineering-design.html |
| `f-Pu` | engineering-design.html |
| `f-Vu` | engineering-design.html |
| `f-acc-pmax` | engineering-design.html |
| `f-acc-pmin` | engineering-design.html |
| `f-acc-vol` | engineering-design.html |
| `f-alpha` | engineering-design.html |
| `f-b-mm` | engineering-design.html |
| `f-barrier-h` | engineering-design.html |
| `f-bearing-no` | engineering-design.html |
| `f-bore-mm` | engineering-design.html |
| `f-ca-alt` | engineering-design.html |
| `f-ca-conc` | engineering-design.html |
| `f-ca-sf` | engineering-design.html |
| `f-ca-temp` | engineering-design.html |
| `f-ca-vol` | engineering-design.html |
| `f-ca-zones` | engineering-design.html |
| `f-capacity` | engineering-design.html |
| `f-ceiling` | engineering-design.html |
| `f-center-dist` | engineering-design.html |
| `f-chiller-tr` | engineering-design.html |
| `f-chw-return` | engineering-design.html |
| `f-chw-supply` | engineering-design.html |
| `f-cold-flow` | engineering-design.html |
| `f-cold-in` | engineering-design.html |
| `f-cold-out` | engineering-design.html |
| `f-corrosion-mm` | engineering-design.html |
| `f-ct-run` | engineering-design.html |
| `f-cyl-force` | engineering-design.html |
| `f-d-recv` | engineering-design.html |
| `f-d-source` | engineering-design.html |
| `f-demand-lpd` | engineering-design.html |
| `f-design-pressure` | engineering-design.html |
| `f-design-temp` | engineering-design.html |
| `f-desludge` | engineering-design.html |
| `f-door-h` | engineering-design.html |
| `f-door-w` | engineering-design.html |
| `f-doors-per-floor` | engineering-design.html |
| `f-dose-hours` | engineering-design.html |
| `f-dose-level` | engineering-design.html |
| `f-driven-rpm` | engineering-design.html |
| `f-eccentricity` | engineering-design.html |
| `f-eg-ph` | engineering-design.html |
| `f-eg-pw` | engineering-design.html |
| `f-eg-ringd` | engineering-design.html |
| `f-elevation` | engineering-design.html |
| `f-et-fill-temp` | engineering-design.html |
| `f-et-head` | engineering-design.html |
| `f-et-kw` | engineering-design.html |
| `f-et-project` | engineering-design.html |
| `f-et-vol` | engineering-design.html |
| `f-ext-load` | engineering-design.html |
| `f-fan-eff` | engineering-design.html |
| ... | ... (159 more) |

## What to do with a phantom

1. **Delete it** — if no business reason exists, remove the form field, the column,
   and any migration that adds it. This is the default and safe move.
2. **Justify it** — add an HTML comment on the capture page:
   `<!-- phantom-allow: <field-name> reason here -->`
   Use sparingly: each allowlist line is a maintenance promise.
3. **Wire a consumer** — if the field SHOULD power a dashboard tile or AI input,
   add the read site downstream. The auditor flips the field to alive on next run.