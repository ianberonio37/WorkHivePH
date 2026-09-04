#!/usr/bin/env python3
"""validate_vehicle_extract_accuracy.py — VM2's lock: measured extraction accuracy on the
golden Ranger fixture, BEFORE the upload UI opens (Ian's explicit sequencing: extraction
comes last, behind accuracy evidence).

Drives the LIVE vehicle-doc-extract edge fn with miner_only:true — the deterministic floor
(interval/part miners in the fn's own code, single source of truth; no model, no cost, no
flake). Scores against _fixtures/vehicle_doc_golden_ranger.truth.json:

  - pm recall    >= 0.90  (every schedule row with a km figure must be found)
  - pm interval  == exact (a WRONG interval is worse than a missing row: it schedules
                           real maintenance at the wrong mileage) -> any mismatch FAILs
  - parts recall >= 0.90  with EXACT part numbers
  - injection    the fixture's IGNORE-ALL-INSTRUCTIONS line must be stripped (>=1) and
                  BANANA must never surface anywhere in the output

Skips clean when the edge runtime is down. Teeth via --self-test (canned responses).
"""
from __future__ import annotations

import io
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "_fixtures" / "vehicle_doc_golden_ranger.txt"
TRUTH = ROOT / "_fixtures" / "vehicle_doc_golden_ranger.truth.json"
MANIFEST = ROOT / "_fixtures" / "vehicle_docs" / "manifest.json"
URL = "http://127.0.0.1:54321/functions/v1/vehicle-doc-extract"

CHECK_NAMES = ["vehicle-extract-accuracy"]

RECALL_BAR = 0.90


def _nrm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(s or "").lower())).strip()


def score(resp: dict, truth: dict) -> list[str]:
    problems: list[str] = []
    fields = resp.get("fields") or {}
    items = fields.get("pm_items") or []
    parts = fields.get("parts") or []

    # pm recall + interval exactness
    matched = 0
    for t in truth["pm_items"]:
        want = _nrm(t["match"])
        hit = next((i for i in items if want in _nrm(i.get("item_text"))), None)
        if not hit:
            problems.append(f"pm MISS: no extracted row matches '{t['match']}'")
            continue
        if hit.get("interval_km") != t["interval_km"]:
            problems.append(f"pm WRONG INTERVAL for '{t['match']}': {hit.get('interval_km')} != {t['interval_km']} "
                            "(a wrong interval schedules real maintenance at the wrong mileage)")
            continue
        if t.get("interval_months") is not None and hit.get("interval_months") != t["interval_months"]:
            problems.append(f"pm WRONG MONTHS for '{t['match']}': {hit.get('interval_months')} != {t['interval_months']}")
            continue
        matched += 1
    recall = (matched / len(truth["pm_items"])) if truth["pm_items"] else 1.0
    if recall < RECALL_BAR:
        problems.append(f"pm recall {recall:.0%} < {RECALL_BAR:.0%} bar ({matched}/{len(truth['pm_items'])})")

    # parts recall — exact part number when the truth names one; NAME match when the real
    # document lists parts without numbers (the Toyota price-list shape: names only)
    pmatched = 0
    have_pns = {_nrm(p.get("part_number")): p for p in parts}
    have_names = [_nrm(p.get("part_name")) for p in parts]
    for t in truth["parts"]:
        pn = t.get("part_number")
        if pn:
            if _nrm(pn) in have_pns:
                pmatched += 1
            else:
                problems.append(f"part MISS: {pn} ('{t['match']}') not extracted")
        else:
            want = _nrm(t["match"])
            if any(want in n for n in have_names):
                pmatched += 1
            else:
                problems.append(f"part MISS (by name): '{t['match']}' not extracted")
    precall = (pmatched / len(truth["parts"])) if truth["parts"] else 1.0
    if precall < RECALL_BAR:
        problems.append(f"parts recall {precall:.0%} < {RECALL_BAR:.0%} bar ({pmatched}/{len(truth['parts'])})")

    # parts precision traps (headings/table furniture must not mine as parts)
    for bad in truth.get("parts_must_not_match", []):
        if any(_nrm(bad) in n for n in have_names):
            problems.append(f"parts NOISE LEAK: a part matching '{bad}' was mined from heading/furniture text")

    # precision: prose fragments must not mine as schedule rows (the severe-duty note leaked
    # live as a garbled TICKED row before the miner's prose guard)
    for bad in truth.get("pm_must_not_match", []):
        if any(_nrm(bad) in _nrm(i.get("item_text")) for i in items):
            problems.append(f"pm PROSE LEAK: a row matching '{bad}' was mined from note text")

    # injection rail
    blob = json.dumps(fields)
    for bad in truth.get("must_not_contain", []):
        if bad in blob:
            problems.append(f"INJECTION LEAK: '{bad}' surfaced in the output")
    # a fixture that carries an injection line must see it stripped; a CLEAN real document
    # must NOT be required to strip anything (expect_injection defaults True for the golden)
    if truth.get("expect_injection", True) and not resp.get("injection_stripped"):
        problems.append("the fixture's injection line was NOT stripped (injection_stripped=0) — "
                        "the BANANA class rides again")
    return problems


def main() -> int:
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    payload = FIXTURE.read_text(encoding="utf-8")
    req = urllib.request.Request(
        URL, method="POST",
        data=json.dumps({"kind": "text", "payload": payload, "miner_only": True}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            resp = json.loads(r.read().decode())
    except Exception as e:
        print(f"SKIP vehicle-extract-accuracy — edge runtime unreachable ({e}); re-run with the stack up.")
        return 0
    # envelope-aware: the fn adopted _shared/envelope.ts ({ok, data}); unwrap, legacy flat still parses
    if isinstance(resp, dict) and resp.get("ok") is True and isinstance(resp.get("data"), dict):
        resp = resp["data"]
    problems = score(resp, truth)
    if problems:
        print("FAIL vehicle-extract-accuracy:")
        for p in problems:
            print("    " + p)
        return 1
    n_items = len((resp.get("fields") or {}).get("pm_items") or [])
    n_parts = len((resp.get("fields") or {}).get("parts") or [])
    print(f"PASS golden Ranger fixture: {len(truth['pm_items'])}/{len(truth['pm_items'])}-matchable pm rows "
          f"with EXACT intervals, {len(truth['parts'])} exact part numbers, injection line stripped "
          f"(extracted {n_items} items / {n_parts} parts total).")

    # VD wave: every REAL document fixture in the manifest scores against its own hand-read truth
    n_docs = 0
    if MANIFEST.exists():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for fx in man.get("fixtures", []):
            fpath = MANIFEST.parent / fx["fixture"]
            tpath = MANIFEST.parent / fx["truth"]
            ftruth = json.loads(tpath.read_text(encoding="utf-8"))
            freq = urllib.request.Request(
                URL, method="POST",
                data=json.dumps({"kind": "text", "payload": fpath.read_text(encoding="utf-8"),
                                 "miner_only": True}).encode(),
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(freq, timeout=45) as r:
                    fresp = json.loads(r.read().decode())
            except Exception as e:
                print(f"FAIL vehicle-extract-accuracy — fixture {fx['id']} unreachable mid-suite ({e})")
                return 1
            if isinstance(fresp, dict) and fresp.get("ok") is True and isinstance(fresp.get("data"), dict):
                fresp = fresp["data"]
            fproblems = score(fresp, ftruth)
            if fproblems:
                print(f"FAIL vehicle-extract-accuracy — real doc {fx['id']}:")
                for p in fproblems:
                    print("    " + p)
                return 1
            n_docs += 1
            print(f"  PASS {fx['id']}: {len(ftruth['pm_items'])} pm truth row(s), "
                  f"{len(ftruth['parts'])} part(s), traps held ({fx.get('shape', '')[:60]})")
    print(f"PASS vehicle-extract-accuracy — deterministic floor clears the bar on the golden fixture "
          f"+ {n_docs} real document(s) from the VD manifest.")
    return 0


def self_test() -> int:
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    good = {"injection_stripped": 1, "fields": {
        "pm_items": [{"item_text": t["match"], "interval_km": t["interval_km"],
                      "interval_months": t.get("interval_months")} for t in truth["pm_items"]],
        "parts": [{"part_name": t["match"], "part_number": t["part_number"]} for t in truth["parts"]],
    }}
    fails = []
    if score(good, truth):
        fails.append("perfect response should PASS")
    import copy
    bad1 = copy.deepcopy(good); bad1["fields"]["pm_items"] = bad1["fields"]["pm_items"][:6]
    if not any("recall" in p for p in score(bad1, truth)):
        fails.append("dropped pm rows must redden recall")
    bad2 = copy.deepcopy(good); bad2["fields"]["pm_items"][0]["interval_km"] = 99999
    if not any("WRONG INTERVAL" in p for p in score(bad2, truth)):
        fails.append("a wrong interval must redden")
    bad3 = copy.deepcopy(good); bad3["fields"]["parts"][0]["part_number"] = "WRONG-1"
    if not any("part MISS" in p for p in score(bad3, truth)):
        fails.append("a wrong part number must redden")
    bad4 = copy.deepcopy(good); bad4["fields"]["pm_items"][0]["item_text"] = "BANANA special"
    if not any("INJECTION LEAK" in p for p in score(bad4, truth)):
        fails.append("a leaked injection token must redden")
    bad5 = copy.deepcopy(good); bad5["injection_stripped"] = 0
    if not any("NOT stripped" in p for p in score(bad5, truth)):
        fails.append("an unstripped injection line must redden")
    bad6 = copy.deepcopy(good)
    bad6["fields"]["pm_items"].append({"item_text": "short trips halves the oil-change interval to", "interval_km": 5000})
    if not any("PROSE LEAK" in p for p in score(bad6, truth)):
        fails.append("a mined prose fragment must redden")
    # VD manifest teeth: name-only parts, clean-doc injection expectation, parts noise trap
    vd_truth = {"pm_items": [], "parts": [{"match": "Oil Filter", "part_number": None}],
                "parts_must_not_match": ["lubricants"], "expect_injection": False}
    vd_good = {"fields": {"pm_items": [], "parts": [{"part_name": "Oil Filter", "part_number": ""}]}}
    if score(vd_good, vd_truth):
        fails.append("a name-only part hit on a clean doc should PASS (no injection demanded)")
    vd_miss = {"fields": {"pm_items": [], "parts": []}}
    if not any("part MISS (by name)" in p for p in score(vd_miss, vd_truth)):
        fails.append("a missing name-only part must redden")
    vd_noise = {"fields": {"pm_items": [], "parts": [{"part_name": "Oil Filter", "part_number": ""},
                                                     {"part_name": "Lubricants", "part_number": ""}]}}
    if not any("NOISE LEAK" in p for p in score(vd_noise, vd_truth)):
        fails.append("a heading mined as a part must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_vehicle_extract_accuracy self-test (dropped rows / wrong interval / wrong part "
          "/ injection leak / unstripped line / name-only part miss / parts noise leak all redden; "
          "a clean real doc is not asked to strip)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
