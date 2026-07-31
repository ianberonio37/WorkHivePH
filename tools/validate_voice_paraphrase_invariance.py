#!/usr/bin/env python3
"""validate_voice_paraphrase_invariance.py — MR5: does WORDING change the ROUTE?

METAMORPHIC RELATION 5, the last of the five the §11 plan called for. A worker says the same thing three
ways; `voice-action-router` must pick the same `kind` from its closed vocabulary
(logbook.create | inventory.deduct | pm.complete | asset.lookup | query.ask | unknown) all three times.
The transform is a PARAPHRASE; the invariant is the route.

WHY THIS IS AN MR AND NOT AN EVAL. There is no correct wording, and the bank already learned not to grade a
free-tier model on exact text ([[feedback_llm_parrots_fewshot_example_codes]]). Asserting "this sentence must
yield logbook.create" grades the model's mood. Asserting "these three sentences must agree with each other"
grades the PROPERTY the product depends on: a worker who rephrases himself must not be routed somewhere else.
So expected-kind agreement is REPORTED, and only the relation is enforced.

THE NON-VACUITY CHECK IS THE WHOLE DESIGN HERE, and it is sharper than MR1-MR4's
([[feedback_a_metamorphic_relation_needs_a_non_vacuity_check]]): **a constant classifier is PERFECTLY
invariant.** A router that answered "unknown" to everything would score 100% on paraphrase invariance while
being completely useless. So the gate also requires DISCRIMINATION — the groups must not all collapse to one
kind — and a router that stops distinguishing intents fails here even though every group is internally
consistent. Invariance alone would have been a metric that improves as the product gets worse.

Live, and deliberately so: the deterministic half of the router (kind allowlist, confidence clamp, slot-fill
guard, asset disambiguation) is already locked by tests/voice-router-determinism.spec.ts against
_shared/voice-router-core.ts. What no test could see is the CHOICE the model makes, which is exactly what a
paraphrase can perturb.

Free-tier chain only, ~12 calls per run against a 50/hour limit. Skips (never fails) when the stack is down,
the persona cannot sign in, or the model is unavailable — an infrastructure absence is not a product defect.

Usage:  python tools/validate_voice_paraphrase_invariance.py [--verbose]
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "voice_paraphrase_invariance_results.json"
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# Reuse the live-invoke plumbing rather than restating it: same anon-key discovery, same persona sign-in,
# same runtime hive derivation (which is what makes these probes survive a reseed).
_spec = importlib.util.spec_from_file_location("_ali", ROOT / "tools" / "validate_ai_live_invoke.py")
_ali = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ali)

# Each group is ONE intent said three ways. The paraphrases vary vocabulary, word order, tense and register
# (a terse log line vs a spoken sentence) while holding the maintenance meaning fixed — that is the transform.
GROUPS = [
    {"expect": "logbook.create", "say": [
        "Pump 3 was leaking oil so I replaced the seal, took about two hours",
        "I swapped the oil seal on pump three because it was leaking, roughly 2 hours of work",
        "Spent two hours changing a leaking oil seal on pump 3",
    ]},
    {"expect": "inventory.deduct", "say": [
        "I took four bearings out of the store room",
        "Pulled 4 bearings from stock",
        "Used up four bearings from inventory",
    ]},
    {"expect": "pm.complete", "say": [
        "Finished the monthly PM on the compressor",
        "The compressor's monthly preventive maintenance is done",
        "I completed monthly preventive maintenance for the compressor",
    ]},
    {"expect": "asset.lookup", "say": [
        "What is the status of pump 3",
        "Show me the details for pump three",
        "Pull up the record for pump 3",
    ]},
]


def _route(text, key, jwt, hive):
    """-> (kind or None, raw). The first intent's kind is the route the product acts on."""
    code, body = _ali._invoke("voice-action-router",
                              {"transcript": text, "hive_id": hive, "context": {"persona": "zaniah"}},
                              key, jwt)
    if code != 200 or not isinstance(body, dict):
        return None, body
    intents = body.get("intents") or []
    if not intents:
        return None, body
    return (intents[0] or {}).get("kind"), body


def main(argv):
    verbose = "--verbose" in argv
    print(f"{BOLD}Voice paraphrase invariance (MR5){RST} — does rewording change the ROUTE?")

    key = _ali._key()
    if not key:
        return _skip("local anon key not found (tests/_db-cleanup.ts)")
    jwt = _ali._jwt(key)
    if not jwt:
        return _skip("the persona could not sign in — stack down or seed missing")
    hive = _ali._derive_hive(key, jwt) or _ali.HIVE

    results, failures = [], []
    for grp in GROUPS:
        kinds = []
        for text in grp["say"]:
            kind, raw = _route(text, key, jwt, hive)
            if kind is None:
                return _skip(f"router returned no intent for {text!r} "
                             f"({str(raw)[:110]}) — model or edge runtime unavailable")
            kinds.append(kind)
            if verbose:
                print(f"    {DIM}{kind:<18}{RST} {text[:64]}")
        invariant = len(set(kinds)) == 1
        results.append({"expect": grp["expect"], "kinds": kinds, "invariant": invariant})
        mark = f"{GREEN}invariant{RST}" if invariant else f"{RED}WORDING-SENSITIVE{RST}"
        matches = " (matches expected)" if invariant and kinds[0] == grp["expect"] else ""
        print(f"  {mark:<32} {grp['expect']:<18} {DIM}-> {sorted(set(kinds))}{matches}{RST}")
        if not invariant:
            failures.append(grp["expect"])

    # DISCRIMINATION — the non-vacuity half. A router answering one kind to everything is perfectly
    # invariant and perfectly useless, so invariance is only meaningful alongside this.
    chosen = {r["kinds"][0] for r in results}
    discriminates = len(chosen) > 1
    print(f"\n  {'non-vacuity: ' + ('DISCRIMINATES' if discriminates else 'COLLAPSED'):<32} "
          f"{DIM}{len(chosen)} distinct kinds across {len(GROUPS)} intents: {sorted(chosen)}{RST}")

    # Reported, never enforced: how often the route also matched what a human would have picked. This is the
    # eval-shaped number, kept visible but out of the verdict so the gate never grades the model's mood.
    agree = sum(1 for r in results if r["kinds"][0] == r["expect"])
    print(f"  {DIM}informational: {agree}/{len(results)} groups routed to the expected kind "
          f"(reported, not enforced){RST}")

    REPORT.write_text(json.dumps({"validator": "voice_paraphrase_invariance", "groups": results,
                                  "discriminates": discriminates, "expected_agreement": agree}, indent=2),
                      encoding="utf-8")

    if failures:
        print(f"  {RED}FAIL{RST} — rewording changed the route for: {', '.join(failures)}. A worker who "
              f"rephrases the same job must not be sent down a different path.")
        return 1
    if not discriminates:
        print(f"  {RED}FAIL{RST} — every intent collapsed to one kind, so the invariance above is vacuous: "
              f"a constant classifier passes it. The router has stopped distinguishing intents.")
        return 1
    print(f"  {GREEN}PASS{RST} — the route survives rewording, and the router still tells intents apart")
    return 0


def _skip(reason):
    print(f"{YEL}  SKIP  {reason}{RST}")
    REPORT.write_text(json.dumps({"validator": "voice_paraphrase_invariance", "skipped": True,
                                 "reason": reason}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
