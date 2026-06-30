# §13 Column-Terminus Map — the 196 capture fields

> EVIDENCE-BASED static analysis of each surface's page JS. This is a **terminus map** (where each captured field lands), **not** a value-verification. Only the PERSISTED set is eligible for the live round-trip value check.

## Buckets

| Bucket | Count | Meaning |
|---|---|---|
| PERSISTED | 46 | direct `column: getElementById(id)` into insert/upsert — value-verifiable |
| PERSISTED? | 59 | inside a persisting function; column indirected — live-confirm |
| AI_EDGE | 9 | sent to a fetch/edge fn (AI box, intent) — correctly not a DB column |
| TRANSIENT_UI | 75 | filter/search/render control — correctly not persisted |
| NO_TERMINUS | 0 | captured-but-dropped — **investigate** |
| UNRESOLVED | 7 | no clear signal in window — needs live confirm |

**Value-verifiable set = 105 fields** (PERSISTED + PERSISTED?). Value-correctness is the next pass (live DB round-trip), only on this set.
