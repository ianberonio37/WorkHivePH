#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BANK ROWS FROM A LIVE MCP WALK — the only instrument allowed to produce `live-walk` evidence
═══════════════════════════════════════════════════════════════════════════════════════════════════

Ian's anti-drift rule, stated 2026-08-04 and restated 2026-08-05: **live-MCP only for `live-walk`;
headless may triage, never bank.** A headless spec and a live MCP walk are not interchangeable
evidence — the headless run is a gate that locks behaviour in CI, while the walk is a person driving
the real browser and reading the real screen. The bank's `live-walk` rows claim the latter.

So this reads readings captured during an actual MCP browser session — `.tmp/live_walk.json`, a list
of

    {"category": "...", "state": "...", "surface": "...", "url": "...",
     "ok": true, "checked": ["...", "..."], "notes": ""}

— and writes them, with the gate's own classify() run before each row is kept, exactly as the other
bankers do. Anything the gate would call invalid goes back.

A reading with "ok": false is written OWED, carrying its notes. A state with no reading is untouched.

Run:  python tools/bank_live_walk.py            # dry run
      python tools/bank_live_walk.py --apply
"""
import argparse
import importlib.util
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READINGS = os.path.join(ROOT, ".tmp", "live_walk.json")
REGISTRY = os.path.join(ROOT, "live_mcp_registry.json")
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

PAGES = {
    "market": "marketplace.html", "market_svc": "marketplace.html",
    "seller": "marketplace-seller.html", "admin": "platform-actions.html",
    "profile": "marketplace-seller-profile.html", "community": "community.html",
    "public-feed": "public-feed.html",
}


def narrowed_fn_digests(V, deps, exercised):
    """Stamp digests for ONLY the functions a walk reports its oracle exercised.

    THE DEFECT THIS CLOSES. R4b exists so an edit to a shared library expires only the claims that
    rest on the edited code. It never delivered that, because the stamp was derived from the FILES a
    walk loaded rather than the CODE its oracle exercised: a single row about a seller empty-state
    recorded ~168 keys from utils.js, and one row here carries **1,675**. A digest set that names
    everything is exactly as blunt as a whole-file hash for a MODIFY. Measured on the current bank:
    484 rows carry fn_digests and 0 of them hold, because 7 keys out of 1,675 changed — all 7 from
    an unrelated session-notice feature. That is four bank collapses from one root
    (752 green -> 34; then 342, ~365, ~320 rows), each previously misread as "shared-library edits
    are expensive, batch them".

    `exercised` is a list of "<file>::<fn>" keys the walk MEASURED as executed (v3 coverage), so the
    narrowing is observed, not inferred. Inferring which functions a claim rests on is precisely the
    fiction R7 exists to stop, so when a reading does not carry coverage this returns the full map
    unchanged and the caller warns — a wide-but-true stamp, never a narrow guess.

    `fn_digests_still_hold` already ignores names absent from a recorded map, so a narrowed map needs
    no verifier change; it simply stops volunteering keys the claim never rested on.
    """
    # v4, not v3: v3 counted brackets inside COMMENTS, so one prose line naming `getDb(`
    # re-segmented the whole top-level stream and vanished all 881 of utils.js's keys.
    # Re-walking under v3 would rebuild evidence that collapses at the next comment edit.
    full = V.fn_digests(deps, version=4)
    if not exercised:
        return full, False
    want = set(exercised)
    # TOP-LEVEL KEYS ARE ALWAYS RETAINED, and dropping them was a real bug in the first cut of
    # this function. `exercised` holds only FUNCTION keys, so filtering by it alone deleted every
    # "::top:" statement hash — and a row that records no top-level statement cannot notice a
    # change to top-level code, which DID run: loading a file executes its top level. That is
    # under-sensitivity, i.e. a false green, which is strictly worse than the over-sensitivity
    # this whole change exists to remove. Under v4 the top-level set is small and honest anyway
    # (69 real statements for utils.js, against 881 under v3 where 93% of it was prose), so
    # keeping it costs almost nothing and preserves the safety direction.
    out = {k: v for k, v in full.items()
           if k in want or k == "::v" or "::top:" in k or k.endswith("::toplevel")}
    if not any(k != "::v" and "::top:" not in k and not k.endswith("::toplevel") for k in out):
        # Coverage that matches nothing in the dependency files is a broken capture, not a claim
        # resting on no code. Falling through to the full map keeps the row TRUE and merely wide.
        return full, False
    return out, True


def load_coverage():
    """Coverage captured per URL by capture_walk_coverage.py, keyed for lookup by a reading.

    Closing the loop matters: without this the WIDE warning tells an operator to run a tool and
    then nothing consumes its output, so the default stays wide and the advice is decoration.
    A reading may still carry its own `fns_exercised`, which wins — this only fills the gap.

    Accepts either a single capture ({"url":..., "fns_exercised":[...]}) or a list of them, so
    one file can hold a whole walk. Missing or malformed: return {} and stamp wide, because a
    wide-but-true stamp is always preferable to a narrow guess.
    """
    path = os.path.join(ROOT, ".tmp", "coverage.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {}
    entries = raw if isinstance(raw, list) else [raw]
    out = {}
    for e in entries:
        if isinstance(e, dict) and e.get("url") and e.get("fns_exercised"):
            out[e["url"]] = e["fns_exercised"]
    return out


def _gate():
    spec = importlib.util.spec_from_file_location(
        "_vlmb", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    V = _gate()
    if not os.path.exists(READINGS):
        print(f"  {RED}FAIL{RST} — {READINGS} not found. Capture the walk first.")
        return 1
    readings = json.load(open(READINGS, encoding="utf-8"))
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    rows = reg["scenarios"] if isinstance(reg, dict) and "scenarios" in reg else reg
    gates, urls = V.gate_ids(), V.surface_urls(reg)
    today = date.today().isoformat()

    # A reading may name a specific category, or "*" for "whatever category holds this (state,
    # surface) cell". The lens walk produces the latter: `populated` on the seller surface is claimed
    # by several families at once, and the lens settled the property, not one family's copy of it.
    index, wild = {}, {}
    for r in readings:
        if r["category"] == "*":
            wild[(r["state"], r["surface"])] = r
        else:
            index[(r["category"], r["state"], r["surface"])] = r

    banked = failed = unmatched = 0
    misses = []
    wide = []
    coverage = load_coverage()
    for row in rows:
        key = (row.get("category"), row.get("state"), row.get("surface"))
        rd = index.get(key) or wild.get((row.get("state"), row.get("surface")))
        if rd is None:
            continue
        if not rd.get("ok"):
            row["status"] = "owed"
            row["findings"] = [f"live MCP walk {today} — {rd.get('url','')}: {rd.get('notes') or 'failed'}"]
            failed += 1
            misses.append((key, (rd.get("notes") or "")[:100]))
            continue
        page = PAGES.get(row.get("surface"))
        deps = sorted({page, "utils.js"}) if page else ["utils.js"]
        before = (row.get("status"), row.get("evidence"), row.get("findings"))
        row["status"] = "green"
        row["findings"] = []
        # the reading's own coverage wins; the capture file only fills a gap
        _exercised = rd.get("fns_exercised") or coverage.get(rd.get("url"))
        _fd, _narrowed = narrowed_fn_digests(V, deps, _exercised)
        if not _narrowed:
            wide.append(key)
        ev = {
            "kind": "live-walk",
            "ref": f"live MCP session {today} · {rd.get('url')} ({rd.get('state')})",
            "asserts": row.get("oracle") or "",
            "checked": "; ".join(rd.get("checked") or []),
            "depends_on": deps,
            "sha": V.sha_of(deps),
            "walked_at": today,
            # R4b, and the reason this bank kept collapsing: until now a marketplace walk recorded a
            # WHOLE-FILE sha and no fn_digests, so any touch anywhere in utils.js expired every row
            # that had ever loaded it — 752 green fell to 34 after three unrelated edits (an rgba
            # value, a transport wrapper, a notice helper). Stamping v3 digests means an APPEND to a
            # shared library expires nothing, because v3's top-level digest is a SET of per-statement
            # hashes rather than one string over the whole file.
            #
            # It is NOT a full fix and must not be read as one: this stamps every function in the
            # dependency files, and a digest set that names everything is as blunt as a file hash for
            # a MODIFY — one colour change inside renderCompactStat still expires every row naming it.
            # Narrowing it needs the walk to report which functions its oracle exercised, which the
            # readings do not carry yet. See feedback_naming_every_function_is_naming_none.
            "fn_digests": _fd,
        }
        # R6's escape hatch, and it is NOT a blanket one. A reading may declare `value_checked` only
        # when the walk compared a VALUE against an independent source rather than observing that the
        # page rendered. `source_chip_true` qualifies: the chip's phrase is compared against the
        # friendly name of the relations the page ACTUALLY requested, read from the browser's own
        # resource timings — two measured values, not a rendering. A reading that merely looked at the
        # screen must never set this, or R6 stops being the rule that caught the false 343.
        if rd.get("value_checked"):
            ev["value_checked"] = rd["value_checked"]
        row["evidence"] = ev
        st, why = V.classify(row, gates, urls)
        if st == "invalid":
            row["status"], row["evidence"], row["findings"] = before
            row["findings"] = [f"the live walk passed but the gate rejects the evidence: {why}"]
            failed += 1
        else:
            banked += 1

    seen_keys = {(r.get("category"), r.get("state"), r.get("surface")) for r in rows}
    seen_wild = {(r.get("state"), r.get("surface")) for r in rows}
    unmatched = (sum(1 for k in index if k not in seen_keys)
                 + sum(1 for k in wild if k not in seen_wild))

    print(f"{BOLD}Banking from the live MCP walk{RST}")
    if wide:
        # A wide stamp is TRUE but fragile: the row will expire on any edit to any function in
        # its dependency files, which is the failure that collapsed this bank four times. Say so
        # at bank time, where it can still be fixed, rather than discovering it at the next
        # shared-library edit.
        print(f"  {YEL}{len(wide)} row(s) stamped WIDE{RST} - the reading carried no "
              f"`fns_exercised`, so EVERY function in the dependency files was recorded.")
        print(f"    {DIM}These expire on ANY edit to those files. Capture coverage with "
          f"tools/capture_walk_coverage.py to stamp only what the oracle ran.{RST}")
        for k in wide[:6]:
            print(f"      {DIM}wide:{RST} {k}")
    print(f"  {GREEN}{banked} banked green{RST} · {RED}{failed} owed{RST}"
          + (f" · {DIM}{unmatched} reading(s) matched no row{RST}" if unmatched else ""))
    for k, why in misses[:6]:
        print(f"    {RED}✗{RST} {k[0]} {k[1]} @ {k[2]}\n      {DIM}{why}{RST}")
    if not a.apply:
        print(f"\n  {YEL}dry run — pass --apply to write{RST}")
        return 0
    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1, ensure_ascii=False)
    os.replace(tmp, REGISTRY)
    print(f"\n  {GREEN}written{RST} — {REGISTRY}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
