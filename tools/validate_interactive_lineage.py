#!/usr/bin/env python3
"""
validate_interactive_lineage.py  --  Phase F of the INTERACTIVE_LINEAGE_ROADMAP.

Forward-only ratchet over the new TOPOLOGY/REDUNDANCY axis (Phases A-C). Mirrors the
platform's existing self-improving-gate discipline: the three audit artifacts must
stay present + well-formed, and the "debt" counters (dead-end fields, pending-review
redundancy clusters) may go DOWN or stay flat, never UP, without an explicit baseline bump.

Artifacts gated:
  - field_blast_radius.json      (Phase A)  -> dead_end_fields must not grow
  - display_anchor_sources.json  (Phase B)  -> resolved count must not drop
  - redundant_displays.json      (Phase C)  -> pending-review clusters must not grow
  - display_ladder.json          (Phase E)  -> ungrounded high-rung must not grow;
                                               grounded count must not drop

Baseline: interactive_lineage_baseline.json (auto-seeds on first run; auto-lowers debt).
Run:     python tools/validate_interactive_lineage.py            (gate)
         python tools/validate_interactive_lineage.py --update   (bump baseline intentionally)
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "field_blast_radius.json")
B = os.path.join(ROOT, "display_anchor_sources.json")
C = os.path.join(ROOT, "redundant_displays.json")
E = os.path.join(ROOT, "display_ladder.json")
P = os.path.join(ROOT, "display_provenance.json")
BASE = os.path.join(ROOT, "interactive_lineage_baseline.json")


def load(p):
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception as e:
        return {"_error": str(e)}


def regenerate():
    """Best-effort: re-run the 3 miners so the gate never judges stale artifacts."""
    import subprocess
    # display_ladder + display_provenance read display_anchor_sources.json, so run
    # them AFTER resolve_display_anchors (provenance also reads display_ladder).
    for miner in ("mine_field_blast_radius.py", "mine_edge_function_cascades.py",
                  "resolve_display_anchors.py",
                  "detect_redundant_displays.py", "classify_display_ladder.py",
                  "build_display_provenance.py"):
        try:
            subprocess.run([sys.executable, os.path.join(ROOT, "tools", miner)],
                           cwd=ROOT, capture_output=True, timeout=120)
        except Exception:
            pass  # gate will FAIL-loud on a missing/malformed artifact below


def main():
    update = "--update" in sys.argv
    if "--no-regen" not in sys.argv:
        regenerate()
    fails = []
    a, b, c, e, p = load(A), load(B), load(C), load(E), load(P)
    for name, d in (("field_blast_radius.json", a), ("display_anchor_sources.json", b),
                    ("redundant_displays.json", c), ("display_ladder.json", e),
                    ("display_provenance.json", p)):
        if d is None:
            fails.append(f"MISSING artifact: {name} (run its miner)")
        elif "_error" in d:
            fails.append(f"MALFORMED {name}: {d['_error']}")
    if fails:
        print("[interactive_lineage] FAIL\n  " + "\n  ".join(fails))
        return 1

    cur = {
        "dead_end_fields": a["totals"]["dead_end_fields"],
        "cascade_fields": a["totals"].get("fields_with_causal_cascade", 0),
        "anchors_resolved": b["totals"]["resolved"],
        "redundancy_pending_review": c["totals"]["verdicts_pending_review"],
        "ladder_grounded": e["totals"]["grounded"],
        "ladder_ungrounded_high_rung": e["totals"]["ungrounded_high_rung"],
        "provenance_trustworthy": p["totals"]["trustworthy_shown"],
    }

    if not os.path.exists(BASE) or update:
        json.dump({"_doc": "Forward-only baseline for the interactive-lineage axis (Phases A-C).",
                   "baseline": cur}, open(BASE, "w", encoding="utf-8"), indent=2)
        print(f"[interactive_lineage] baseline {'BUMPED' if update else 'SEEDED'}: {cur}")
        return 0

    base = json.load(open(BASE, encoding="utf-8"))["baseline"]
    msgs = []
    # debt counters: must not grow (guarded with `k in base` so a newly-added metric
    # seeds on this run rather than KeyError-ing against an older baseline).
    if "dead_end_fields" in base and cur["dead_end_fields"] > base["dead_end_fields"]:
        msgs.append(f"dead_end_fields grew {base['dead_end_fields']} -> {cur['dead_end_fields']} "
                    "(a new field has no consumer; wire it or justify, OR --update)")
    if "redundancy_pending_review" in base and cur["redundancy_pending_review"] > base["redundancy_pending_review"]:
        msgs.append(f"redundancy_pending_review grew {base['redundancy_pending_review']} -> {cur['redundancy_pending_review']} "
                    "(a new value-identity cluster needs a verdict, OR --update)")
    if "ladder_ungrounded_high_rung" in base and cur["ladder_ungrounded_high_rung"] > base["ladder_ungrounded_high_rung"]:
        msgs.append(f"ladder_ungrounded_high_rung grew {base['ladder_ungrounded_high_rung']} -> {cur['ladder_ungrounded_high_rung']} "
                    "(a new predictive/prescriptive display isn't grounded to a canonical source; ground it, OR --update)")
    # coverage counters: must not drop
    if "cascade_fields" in base and cur["cascade_fields"] < base["cascade_fields"]:
        msgs.append(f"cascade_fields dropped {base['cascade_fields']} -> {cur['cascade_fields']} "
                    "(a causal cross-page cascade was lost from causal_cascades.json, OR --update)")
    if "anchors_resolved" in base and cur["anchors_resolved"] < base["anchors_resolved"]:
        msgs.append(f"anchors_resolved dropped {base['anchors_resolved']} -> {cur['anchors_resolved']} "
                    "(a display lost its source link, OR --update)")
    if "ladder_grounded" in base and cur["ladder_grounded"] < base["ladder_grounded"]:
        msgs.append(f"ladder_grounded dropped {base['ladder_grounded']} -> {cur['ladder_grounded']} "
                    "(a display lost its canonical-source grounding, OR --update)")
    if "provenance_trustworthy" in base and cur["provenance_trustworthy"] < base["provenance_trustworthy"]:
        msgs.append(f"provenance_trustworthy dropped {base['provenance_trustworthy']} -> {cur['provenance_trustworthy']} "
                    "(a display lost its trustworthy 'where from?' provenance, OR --update)")
    if msgs:
        print("[interactive_lineage] FAIL\n  " + "\n  ".join(msgs))
        return 1

    # auto-lower debt / auto-raise coverage (forward-only follows reality the good way),
    # and persist whenever a new metric key appears so the baseline stays complete.
    new_keys = set(cur) - set(base)
    improved = bool(new_keys) or (
        cur["dead_end_fields"] < base.get("dead_end_fields", cur["dead_end_fields"])
        or cur["redundancy_pending_review"] < base.get("redundancy_pending_review", cur["redundancy_pending_review"])
        or cur["cascade_fields"] > base.get("cascade_fields", cur["cascade_fields"])
        or cur["anchors_resolved"] > base.get("anchors_resolved", cur["anchors_resolved"])
        or cur["ladder_ungrounded_high_rung"] < base.get("ladder_ungrounded_high_rung", cur["ladder_ungrounded_high_rung"])
        or cur["ladder_grounded"] > base.get("ladder_grounded", cur["ladder_grounded"])
        or cur["provenance_trustworthy"] > base.get("provenance_trustworthy", cur["provenance_trustworthy"]))
    if improved:
        json.dump({"_doc": "Forward-only baseline for the interactive-lineage axis (Phases A-C).",
                   "baseline": cur}, open(BASE, "w", encoding="utf-8"), indent=2)
        print(f"[interactive_lineage] PASS + baseline auto-improved -> {cur}")
    else:
        print(f"[interactive_lineage] PASS (flat) {cur}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
