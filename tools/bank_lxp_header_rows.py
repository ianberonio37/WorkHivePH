#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bank the LXP-H rows whose OWN page's served headers hold, from the receipt the prover just wrote.

THE LENS. "The platform must serve this page correctly from the edge." 120 LAYER-UX x PERSONA rows carry it and
sat in the re-walk queue wanting a raw-http reading - while tools/prove_w4_layer_headers.py was already taking
exactly that reading for the 246 W4 rows and simply was not looking at these (it selected on `w4.kind == layer`
and an LXP row carries its layer under `lx`). That prover now serves both waves, so this banker only has to
read what it wrote.

*WHY THE RECEIPT AND NOT THE PROVER'S EXIT CODE. A green run says "all 366 rows hold"; a row's basis has to say
what was true of ITS page. Each receipt carries the per-row `w4.witness` - the actual header findings for that
page - so the basis quotes achievements.html's own headers rather than the sweep's summary. A row whose receipt
is missing, not ok, or older than the page it describes is left alone.

USAGE  python tools/bank_lxp_header_rows.py [--apply]
"""
import argparse
import io
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "trajectory_registry.json")
WALKS = os.path.join(ROOT, ".tmp", "mcp_walks")
GATE_ID = "w4-layer-headers"          # as registered in run_platform_checks.py


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    reg = json.load(open(REGISTRY, encoding="utf-8"))
    # *the LXC floor rows (kind "layer-floor", 2026-10-06) carry the identical H sentence on the identical `lx` block;
    # the prover reads both kinds since 2026-10-08, so the banker must too - a want must carry its reader
    rows = [t for t in reg["trajectories"]
            if (t.get("lx") or {}).get("kind") in ("layer-ux", "layer-floor")
            and (t.get("lx") or {}).get("layer") == "H"
            and t.get("status") != "descoped"]

    banked, skipped = [], []
    for t in rows:
        page = (t.get("lx") or {}).get("page")
        rp = os.path.join(WALKS, t["id"] + ".json")
        if not os.path.exists(rp):
            skipped.append((t["id"], page, "no receipt on disk"))
            continue
        rec = json.load(open(rp, encoding="utf-8"))
        res = next((r for r in rec.get("results", []) if r.get("id") == t["id"]), None)
        if not res or not res.get("ok"):
            skipped.append((t["id"], page, "receipt is not ok"))
            continue
        witness = ((res.get("w4") or {}).get("witness") or res.get("note") or "").strip()
        if not witness:
            skipped.append((t["id"], page, "receipt carries no witness to quote"))
            continue
        # *THE RECEIPT MUST NOT BE OLDER THAN THE PAGE IT DESCRIBES - a stale reading cannot testify.
        pf = os.path.join(ROOT, page) if page else None
        if pf and os.path.exists(pf) and os.path.getmtime(rp) < os.path.getmtime(pf):
            skipped.append((t["id"], page, "receipt is older than the page - re-run the prover"))
            continue

        basis = (
            "[{0}] pct -> 60. WALKED with the registered prover tools/prove_w4_layer_headers.py (gate `{1}`) "
            "against the LOCAL Vercel-headers substitute tools/serve_vercel_headers.py, which applies "
            "vercel.json's own rules the way the edge does - so this is a raw-http reading of the served header "
            "layer, the instrument this lens asks for, and it needs no browser and no deploy. Headers do not "
            "depend on the viewport or the language, which is why one reading answers the row at both of its "
            "viewports rather than being taken twice. MEASURED ON {2}'s OWN RESPONSE: {3}. The reading is tied "
            "to this page by its own receipt (.tmp/mcp_walks/{4}.json), and the receipt is refused if it is "
            "older than the page it describes, so a stale green cannot be re-banked. The same prover graded "
            "every H-layer row of both waves in one pass, which is deliberate: a second reader of the same "
            "headers is how two gates come to disagree about one fact.{5}"
        ).format(date.today().isoformat(), GATE_ID, page, witness, t["id"],
                 # *THE PERSONA IS PART OF THE ROW, so the basis says why one reading is this person's reading - and
                 # only when the receipt's witness carries the prover's own check that no header rule is conditional
                 (" AS {0}: the receipt above checked vercel.json for any rule conditioned on a cookie, header or "
                  "query (has/missing) and found none, so nothing this person sends can change the served headers."
                  .format((t.get("lx") or {}).get("persona"))
                  if "has/missing" in witness and (t.get("lx") or {}).get("persona") else ""))

        prev = t.get("basis") or ""
        if "prove_w4_layer_headers.py" not in prev:
            t["basis"] = (basis + " || " + prev) if prev else basis
        if t.get("status") in ("specced", "fixing"):
            t["status"] = "locking"
        t["pct"] = max(int(t.get("pct") or 0), 60)
        art = t.setdefault("artifacts", {})
        gates = art.setdefault("gates", [])
        if GATE_ID not in gates:
            gates.append(GATE_ID)
        banked.append((t["id"], page))

    print("LX H rows (LXP + LXC): {0}  ->  banked {1} - left open {2}".format(len(rows), len(banked), len(skipped)))
    for i, p in banked[:5]:
        print("   bank {0:8} {1}".format(i, p))
    if banked[5:]:
        print("   ... and {0} more".format(len(banked) - 5))
    for i, p, why in skipped[:10]:
        print("   OPEN {0:8} {1:28} {2}".format(i, p, why))
    if not a.apply:
        print("\n(dry run - pass --apply to write)")
        return 0
    tmp = REGISTRY + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, REGISTRY)          # atomic: open(w) truncates before the write
    print("\nWROTE {0} row(s) to trajectory_registry.json".format(len(banked)))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    sys.exit(main())
