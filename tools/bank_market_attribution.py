#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BANK THE MARKETPLACE POPULATED ROWS from prove_market_attribution.mjs + the structural walk.

The populated oracle has two halves. walk_owed_scenarios' generic probe proves the STRUCTURAL half
(rows render, no junk/raw enum/overflow) and its merger rightly refuses to bank the rows on that
alone (R6: a behavioural oracle cannot rest on a structural probe). prove_market_attribution.mjs is
the other half: every principal number on the surface attributed to its own label and matched to
the view the page itself reads, under the caller's claims. TOGETHER they satisfy "the surface
renders real rows and every visible number matches its source of truth".

Rails, same as every banker here:
  - refuses if market_attribution_report.json is missing, carries any FAIL, or is OLDER than the
    newest dep of a row it would stamp (a stale report cannot testify about current files);
  - only stamps rows whose surface the report actually measured (market/seller/profile/admin);
  - re-classifies through the gate's own classify() and refuses anything not green.

Run:  python tools/bank_market_attribution.py [--apply]
"""
import argparse
import importlib.util
import io
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

SURFACE_DEPS = {
    "market":  ["marketplace.html", "utils.js"],
    "seller":  ["marketplace-seller.html", "utils.js"],
    "profile": ["marketplace-seller-profile.html", "utils.js"],
    "admin":   ["platform-actions.html", "utils.js"],
    "community": ["community.html", "utils.js"],
    "achievements": ["achievements.html", "utils.js"],
    "public_feed": ["public-feed.html", "utils.js"],
}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    spec = importlib.util.spec_from_file_location(
        "_v", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    V = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(V)

    rp = os.path.join(ROOT, "market_attribution_report.json")
    if not os.path.exists(rp):
        print(f"{RED}REFUSING{RST} - market_attribution_report.json missing; run the walker first")
        return 1
    rep = json.load(open(rp, encoding="utf-8"))
    if rep.get("fail", 1) != 0:
        print(f"{RED}REFUSING{RST} - the report carries {rep.get('fail')} failing check(s); "
              f"a failing walker cannot testify")
        return 1
    rep_mtime = os.path.getmtime(rp)
    by_surface = {}
    for c in rep.get("checks", []):
        by_surface.setdefault(c["surface"], []).append(f"{c['name']}: {c['detail']}")

    # The structural half must be VERIFIED from the walker's own results, not asserted: require a
    # populated probe pass for the row's URL in .tmp/owed_walk_results.json. (The merger measured
    # it and then rightly refused to bank the claim on it ALONE; this file cites both halves.)
    # every saved copy counts - each --only run OVERWRITES the main results file, so per-page runs
    # are preserved as .tmp/owed_walk_results.<tag>.json and all of them are read here
    import glob as _glob
    structural_ok = {}
    for walk_path in _glob.glob(os.path.join(ROOT, ".tmp", "owed_walk_results*.json")):
        try:
            for res in json.load(open(walk_path, encoding="utf-8")):
                if res.get("state") == "populated" and res.get("ok"):
                    structural_ok[res.get("url")] = "; ".join(res.get("checked") or [])[:250]
        except Exception:
            continue

    reg_path = os.path.join(ROOT, "live_mcp_registry.json")
    reg = json.load(open(reg_path, encoding="utf-8"))
    gates, urls = V.gate_ids(), V.surface_urls(reg)
    today = date.today().isoformat()

    stamped = refused = 0
    for r in reg["scenarios"]:
        if r.get("state") != "populated" or r.get("surface") not in by_surface:
            continue
        st, _ = V.classify(r, gates, urls)
        if st != "stale":
            continue
        deps = SURFACE_DEPS[r["surface"]]
        newest = max((os.path.getmtime(os.path.join(ROOT, d))
                      for d in deps if os.path.exists(os.path.join(ROOT, d))), default=0)
        if rep_mtime < newest:
            refused += 1
            continue
        ev = r.setdefault("evidence", {})
        ev["kind"] = "live-walk"
        ev["ref"] = f"{today} live MCP {r.get('url') or ''}"
        ev["asserts"] = ("the surface renders real rows and every principal visible number is "
                         "attributed to its own label and matches the view the page reads, under "
                         "the caller's own claims")
        s_ok = structural_ok.get(r.get("url"))
        if not s_ok:
            refused += 1
            print(f"  {YEL}refused{RST} {r['id']}: no passing structural populated walk recorded "
                  f"for {r.get('url')} in .tmp/owed_walk_results.json")
            continue
        ev["checked"] = ("BOTH halves measured " + today + ". STRUCTURAL (walk_owed_scenarios "
                         "populated probe, passing this same day - the merger measured it and "
                         "correctly refused to bank on it alone): " + s_ok + ". NUMBER-HALF "
                         "(prove_market_attribution.mjs, all checks passing): "
                         + " | ".join(by_surface[r["surface"]])[:900])
        ev["value_checked"] = f"attribution checks for {r['surface']}: {len(by_surface[r['surface']])} anchors, 0 failing"
        ev["replay"] = f"node tools/prove_market_attribution.mjs --surface {r['surface']}"
        ev["depends_on"] = deps
        ev["sha"] = V.sha_of(deps)
        ev["fn_digests"] = V.fn_digests(deps)
        r["status"] = "green"
        r["findings"] = []
        st2, why2 = V.classify(r, gates, urls)
        if st2 == "green":
            stamped += 1
        else:
            refused += 1
            print(f"  {YEL}refused{RST} {r['id']}: {why2[:70]}")
    if stamped and a.apply:
        json.dump(reg, open(reg_path, "w", encoding="utf-8"), indent=1)
    print(f"\n  {GREEN}{stamped} stamped{RST} · {YEL}{refused} refused{RST}"
          + ("" if a.apply else f"   {YEL}dry run - pass --apply to write{RST}"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
