#!/usr/bin/env python3
"""validate_faithfulness_rail.py — lock the CL10 faithfulness rails on the assistant/chat surface.

The companion BRAIN (agent=assistant -> ai-orchestrator) is read-only advisory. Two live-caught
fabrication classes must stay guarded before an answer ships (2026-07-08, Leandro/Baguio):

  1. ACTION fabrication — the model claimed it PERFORMED a system write it cannot do from chat
     ("Updated maintenance record for CT-001", "Log entry added to CT-001 maintenance history").
     Verified against the DB: 0 new logbook rows, 0 agent_followups. A confident false "I did X" in a
     safety-adjacent maintenance context. Rail = _shared/action_provenance.ts stripFalseActionClaims().
  2. NUMERIC/KPI fabrication — an ungrounded % dressed as "from records" OR stated as the worker's
     current-state metric with no provenance phrase ("Your split is 41% planned."). The old phrase-only
     rail (a) leaked the no-provenance form and (b) had a coincidental-substring false-negative (a stray
     "41" made "41%" look grounded). Hardened rail = token-accurate grounding via extractNumberCores +
     the possessive-current-state hedge.

This is a STATIC source-assertion gate (a naive revert/deletion of either rail FAILs it):
  A. _shared/action_provenance.ts exists and EXPORTS stripFalseActionClaims + ACTION_HONEST_CLARIFIER.
  B. _shared/action_provenance.test.ts exists (committed regression contract — the map found the old
     numeric rail's '5/5' test was uncommitted/ephemeral; don't repeat that).
  C. ai-orchestrator IMPORTS stripFalseActionClaims (action rail) and extractNumberCores (token-accurate
     numeric grounding).
  D. ai-orchestrator CALLS both rails on the final answer before the synthesis return: it invokes
     stripFalseKpiProvenance(answer, ...) AND stripFalseActionClaims(answer), and the numeric rail is
     token-accurate (extractNumberCores) + covers the no-provenance form (POSSESSIVE_CURRENT_STATE_RE),
     and both fire BEFORE `return { answer, agents_used`.
  E. GUTTED-REPLY resolver (CL2/CL10, 2026-07-08): the floating companion (voice-journal-agent, 32 pages)
     runs the numeric-provenance gate; when it strips a spec/KPI number the >15-char remnant can be an
     INCOHERENT FRAGMENT ("Cross-pattern, three passes. Check the OEM manual though.") — live-caught on
     "what torque for an M20 8.8 bolt?". _shared/gutted_reply.ts resolveProvenanceRemnant() routes a gutted
     remnant to an honest DOMAIN-AWARE pointer (spec ask -> OEM manual + Engineering Design calculator;
     else -> live metrics). Guarded: gutted_reply.ts exports resolveProvenanceRemnant + SPEC/METRIC pointers;
     gutted_reply.test.ts is committed; voice-journal-agent calls resolveProvenanceRemnant(prov.clean, ...)
     (a naive revert to `prov.clean.length >= 15 ? ...` FAILs).

Usage:  python tools/validate_faithfulness_rail.py [--json]
Exit 0 = both rails intact + wired · 1 = a rail is missing / unwired (fabrication guard regressed).
"""
import re
import sys
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHARED = ROOT / "supabase" / "functions" / "_shared"
ACTION = SHARED / "action_provenance.ts"
ACTION_TEST = SHARED / "action_provenance.test.ts"
NUMERIC = SHARED / "numeric_provenance.ts"
ORCH = ROOT / "supabase" / "functions" / "ai-orchestrator" / "index.ts"
# E. Gutted-reply resolver (CL2/CL10, 2026-07-08): the floating companion
# (voice-journal-agent) runs the numeric-provenance gate; when it strips a spec/KPI
# number the surviving remnant can be an INCOHERENT FRAGMENT ("Check the OEM manual
# though."). The resolver routes a gutted remnant to an honest, domain-aware pointer
# instead. A naive revert to `prov.clean.length >= 15 ? prov.clean : ...` FAILs here.
GUTTED = SHARED / "gutted_reply.ts"
GUTTED_TEST = SHARED / "gutted_reply.test.ts"
VJA = ROOT / "supabase" / "functions" / "voice-journal-agent" / "index.ts"


def analyze():
    viols = []

    # A. action_provenance module + exports
    if not ACTION.exists():
        viols.append({"issue": f"missing {ACTION.relative_to(ROOT)} (the CL10 action-fabrication rail)"})
    else:
        asrc = ACTION.read_text(encoding="utf-8", errors="ignore")
        if not re.search(r"export\s+function\s+stripFalseActionClaims\b", asrc):
            viols.append({"issue": "action_provenance.ts no longer EXPORTS stripFalseActionClaims()"})
        if "ACTION_HONEST_CLARIFIER" not in asrc:
            viols.append({"issue": "action_provenance.ts no longer exports ACTION_HONEST_CLARIFIER (the honest fallback)"})

    # B. committed regression test
    if not ACTION_TEST.exists():
        viols.append({"issue": f"missing {ACTION_TEST.relative_to(ROOT)} (the committed CL10 regression test — don't ship a rail with an ephemeral test)"})

    if not NUMERIC.exists():
        viols.append({"issue": f"missing {NUMERIC.relative_to(ROOT)} (extractNumberCores source)"})

    if not ORCH.exists():
        viols.append({"issue": f"missing {ORCH.relative_to(ROOT)}"})
        return viols
    src = ORCH.read_text(encoding="utf-8", errors="ignore")

    # C. imports
    if "stripFalseActionClaims" not in src or "action_provenance.ts" not in src:
        viols.append({"issue": "ai-orchestrator does not import stripFalseActionClaims from _shared/action_provenance.ts"})
    if "extractNumberCores" not in src:
        viols.append({"issue": "ai-orchestrator does not import extractNumberCores — the numeric rail is not token-accurate (coincidental-substring false-negative can return)"})

    # D. wiring: both rails called before the synthesis return
    if "stripFalseKpiProvenance(answer" not in src:
        viols.append({"issue": "the numeric KPI rail (stripFalseKpiProvenance) is not called on the answer"})
    if "POSSESSIVE_CURRENT_STATE_RE" not in src:
        viols.append({"issue": "the no-provenance current-state hedge (POSSESSIVE_CURRENT_STATE_RE) is gone — a fabricated 'Your split is X%' with no provenance phrase ships verbatim"})
    if "stripFalseActionClaims(answer" not in src:
        viols.append({"issue": "the action-fabrication rail (stripFalseActionClaims) is not called on the answer — 'Log entry added' fabrications can ship"})

    # Both rails must fire BEFORE the synthesis return `{ answer, agents_used`.
    ret = src.find("return { answer, agents_used")
    if ret != -1:
        head = src[:ret]
        if "stripFalseActionClaims(answer" not in head:
            viols.append({"issue": "stripFalseActionClaims is not invoked BEFORE the synthesis `return { answer, agents_used ...}` — the rail runs too late / never on the shipped answer"})
        if "stripFalseKpiProvenance(answer" not in head:
            viols.append({"issue": "stripFalseKpiProvenance is not invoked BEFORE the synthesis return"})

    # E. Gutted-reply resolver (voice-journal-agent, the floating companion on 32 pages).
    if not GUTTED.exists():
        viols.append({"issue": f"missing {GUTTED.relative_to(ROOT)} (the CL2/CL10 gutted-reply resolver)"})
    else:
        gsrc = GUTTED.read_text(encoding="utf-8", errors="ignore")
        if not re.search(r"export\s+function\s+resolveProvenanceRemnant\b", gsrc):
            viols.append({"issue": "gutted_reply.ts no longer EXPORTS resolveProvenanceRemnant()"})
        if "SPEC_POINTER" not in gsrc or "METRIC_POINTER" not in gsrc:
            viols.append({"issue": "gutted_reply.ts no longer defines the honest SPEC_POINTER / METRIC_POINTER fallbacks"})
    if not GUTTED_TEST.exists():
        viols.append({"issue": f"missing {GUTTED_TEST.relative_to(ROOT)} (the committed gutted-reply regression test — don't ship a rail with an ephemeral test)"})
    if not VJA.exists():
        viols.append({"issue": f"missing {VJA.relative_to(ROOT)}"})
    else:
        vsrc = VJA.read_text(encoding="utf-8", errors="ignore")
        if "resolveProvenanceRemnant" not in vsrc or "gutted_reply.ts" not in vsrc:
            viols.append({"issue": "voice-journal-agent does not import resolveProvenanceRemnant from _shared/gutted_reply.ts"})
        # The resolver must consume the gate's output — a naive revert to the old
        # `prov.clean.length >= 15 ? prov.clean : <pointer>` FAILs this assertion.
        if not re.search(r"resolveProvenanceRemnant\(\s*prov\.clean", vsrc):
            viols.append({"issue": "voice-journal-agent does not call resolveProvenanceRemnant(prov.clean, ...) — a G1-gutted spec/KPI reply can ship as an incoherent fragment"})
    return viols


def main():
    as_json = "--json" in sys.argv
    viols = analyze()
    if as_json:
        print(json.dumps({"violations": viols, "count": len(viols)}, indent=2))
    else:
        print("CL10 faithfulness rails (assistant/chat: action-fabrication + ungrounded-KPI must be guarded before ship)")
        if not viols:
            print("  PASS: action_provenance rail + committed test present; both rails imported, token-accurate, and wired before the synthesis return")
        else:
            print(f"  FAIL: {len(viols)} issue(s):")
            for v in viols:
                print(f"    - {v['issue']}")
    return 1 if viols else 0


if __name__ == "__main__":
    sys.exit(main())
