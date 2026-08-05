#!/usr/bin/env python3
"""build_page_live_mcp_bank.py -- emit one page's 200-scenario live-MCP bank from its GROUNDED anatomy.

THE FAILURE MODE THIS TOOL EXISTS TO PREVENT IS AUTHORING FICTION AT SCALE (2026-08-05). 4,400
grounded rows and 4,400 plausible ones look identical in a JSON file. So nothing here invents a
subject: every view, component, layer, seam and persona a row is built from must arrive in
page_bank_anatomy/<page>.json carrying `seen: {how, ref}` -- a file:line someone actually read or a
live enumeration someone actually ran -- and a subject without that receipt refuses to build (A7).

THE FRAME IS FIXED ARITHMETIC (PAGE_TESTBANK_ROADMAP.md section 1): 15 families, rows 1-200 numbered
identically on every page, 60 architecture + 50 UFAI + 45 UI + 45 UX. Exactly 200 or the build fails
(A8) -- under-supply means the Ground pass is incomplete, and padding is how a denominator lies.

ORACLE TEXT IS IMPORTED, NEVER COPIED. The templated families take their oracle sentences verbatim
from ORACLES in build_live_mcp_registry.py -- a second wording of the same oracle is a second source
of truth, and two copies of one sentence is what let the credits-back chip drift. The bespoke halves
(CD invariants x6, CI domain truths x8) are hand-authored per page IN THE ANATOMY, because that is
where the judgement lives; this tool only checks they exist and are non-empty.

VACUITY IS RECORDED, NEVER COUNTED (A10). An oracle with no subject on a page (public-feed has no
writes, so `offline_refusal` has nothing to refuse) is declared in the anatomy's `na` list with a
reason AND a `replace_with` row from the page's ranked tail. The bank still totals exactly 200
scored rows; the vacuity survives in the bank's `declared_na` block with its receipt.

Usage:  python tools/build_page_live_mcp_bank.py <page> [--out banks/<page>_live_mcp_bank.json]
        python tools/build_page_live_mcp_bank.py --all
        python tools/build_page_live_mcp_bank.py --selftest
"""
from __future__ import annotations
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANATOMY_DIR = os.path.join(ROOT, "page_bank_anatomy")
BANKS_DIR = os.path.join(ROOT, "banks")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_live_mcp_registry import ORACLES          # noqa: E402  (the ONE oracle vocabulary)

# ── the frame: (family, mandate, subject_axis, take_n, oracle_keys) in row order ─────────────────
# subject_axis names the anatomy list the family consumes; take_n is how many of its head it takes.
# The row numbering is the concatenation, 1-200, identical on every page -- PB-<page>-078 means the
# same (family, subject-slot, oracle-slot) everywhere, which is what makes pages comparable.
FRAME = [
    ("CA-layer-contract", "F1-architecture", "layers", 4,
     ["envelope_shape", "status_body_agreement", "idempotency", "ordering_totality",
      "units_declared"]),
    ("CB-seam", "F1-architecture", "seams", 5,
     ["value_survives", "name_survives", "null_semantics", "partial_write"]),
    ("CC-failure-injection", "F1-architecture", "views", 2,
     ["fail_500", "fail_401", "fail_timeout", "fail_partial", "fail_slow", "fail_offline",
      "fail_null_field"]),
    ("CD-invariant", "F1-architecture", "invariants", 6, None),        # bespoke: 1 oracle per subject
    ("CE-ufai-U", "F2-ufai", "views", 2,
     ["one_vocabulary", "source_chip_true", "units_visible", "no_raw_enum", "number_explained"]),
    ("CF-ufai-F", "F2-ufai", "views", 2,
     ["effect_in_db", "effect_visible", "count_matches_source", "money_matches_ledger",
      "idempotent_repeat", "cross_surface_agreement"]),
    ("CG-ufai-A", "F2-ufai", "views", 2,
     ["offline_refusal", "retry_path", "rate_limit_legible", "fallback_engaged", "slow_honest"]),
    ("CH-ufai-I", "F2-ufai", "identity_personas", 2,
     ["bola_object", "bfla_function", "tenant_boundary", "jwt_not_body", "boundary_not_emptiness"]),
    ("CI-domain-truth", "F2-ufai", "domain_truths", 8, None),          # bespoke: 1 oracle per subject
    ("CJ-ui-layout", "F3-ui", "views", 3,
     ["w390_overflow", "w641_overflow", "w1280_overflow", "tap_target_44", "safe_area"]),
    ("CK-ui-state", "F3-ui", "components", 3,
     ["component_loading", "component_skeleton", "component_disabled", "component_busy",
      "component_populated"]),
    ("CL-ui-visual", "F3-ui", "views", 3,
     ["contrast_wcag", "contrast_apca", "focus_visible", "reduced_motion", "icon_only_name"]),
    ("CM-ux-comprehension", "F4-ux", "views", 3,
     ["what_is_this_number", "what_happens_next", "what_does_it_cost", "why_refused",
      "reward_explained"]),
    ("CN-ux-journey", "F4-ux", "journey_personas", 3,
     ["first_run_to_value", "repeat_visit", "cross_surface_handoff", "two_sided_same_object",
      "abandon_resume"]),
    ("CO-ux-recovery", "F4-ux", "views", 3,
     ["double_tap", "back_out", "session_died", "wrong_then_fix", "did_it_land"]),
]

# The family's design question, printed onto every row so a finding is always actionable without
# opening the roadmap. One sentence each, same register as the marketplace CATEGORIES table.
QUESTIONS = {
    "CA-layer-contract": "does each layer this page rests on honour its own contract - envelope, "
                         "status/body agreement, idempotency, total ordering, declared units?",
    "CB-seam": "does what one side of this page's seams writes arrive intact, named the same, "
               "meaning the same, on the other side?",
    "CC-failure-injection": "when a dependency fails under this view, does the page degrade "
                            "honestly - or invent a number, an emptiness, or a fake all-clear?",
    "CD-invariant": "the cross-layer facts about THIS page that must hold at every instant, "
                    "asserted from the source of truth rather than from a screen",
    "CE-ufai-U": "UNDERSTANDABLE - one vocabulary, visible units, no raw enums, and every number "
                 "explicable from the surface alone",
    "CF-ufai-F": "FUNCTIONAL - the happy-path effect is real in the database and visible to the "
                 "person who caused it, counts and money matching their source",
    "CG-ufai-A": "AVAILABLE - offline, slow, failing or limited, the surface refuses out loud and "
                 "recovers honestly",
    "CH-ufai-I": "IDENTITY - authN from the JWT, authZ at the server, boundaries stated as "
                 "boundaries and never rendered as emptiness",
    "CI-domain-truth": "the domain facts THIS page trades in - is every domain number computed by "
                       "its stated definition and labelled with its own denominator?",
    "CJ-ui-layout": "layout under real content at three VERIFIED widths - innerWidth, never the "
                    "requested viewport",
    "CK-ui-state": "every component's induced states - loading, skeleton, disabled, busy, "
                   "populated - distinguishable and honest",
    "CL-ui-visual": "contrast, focus, motion and naming - the facts a screenshot cannot confirm "
                    "and a measurement can",
    "CM-ux-comprehension": "can a person say what this number means, what happens next, and what "
                           "it costs, from the surface alone?",
    "CN-ux-journey": "multi-step flows end to end per persona, including the two-sided ones a "
                     "single identity cannot walk",
    "CO-ux-recovery": "mistakes, reversals and interruption - and after a slow tap: did my thing "
                      "land?",
}

REQUIRED_COUNTS = {"layers": 4, "seams": 5, "invariants": 6, "domain_truths": 8}
REQUIRED_MIN = {"views": 3, "components": 3, "journey_personas": 3, "identity_personas": 2}


class BuildRefused(SystemExit):
    """A refusal is an exit with a stated reason -- the rails firing, not an error to catch."""


def _fail(msg):
    raise BuildRefused(f"REFUSED: {msg}")


def check_anatomy(a):
    """A7 + A8's supply half + A10's declaration shape. Returns nothing; refuses loudly."""
    page = a.get("page") or _fail("anatomy has no `page`")
    if not a.get("url"):
        _fail(f"{page}: anatomy has no `url`")
    for axis, n in REQUIRED_COUNTS.items():
        got = a.get(axis) or []
        if len(got) < n:
            _fail(f"{page}: axis `{axis}` supplies {len(got)}, frame needs {n} (A8: an "
                  f"under-supplied axis means the Ground pass is incomplete)")
    for axis, n in REQUIRED_MIN.items():
        got = a.get(axis) or []
        if len(got) < n:
            _fail(f"{page}: axis `{axis}` supplies {len(got)}, frame needs at least {n}")
    # A7: every subject the frame will consume carries seen{how, ref}. The tail beyond the frame's
    # take_n is exempt -- it is recorded, not scored -- but a scored subject with no receipt is the
    # exact fiction this tool exists to refuse.
    for fam, _mand, axis, take, _keys in FRAME:
        for s in (a.get(axis) or [])[:take]:
            seen = s.get("seen") or {}
            if not (seen.get("how") and seen.get("ref")):
                _fail(f"{page}: {axis}/{s.get('key', '?')} feeds {fam} but carries no "
                      f"seen{{how, ref}} receipt (A7: a subject must be OBSERVED, not assumed)")
        # bespoke families: the oracle lives on the subject and must be non-empty prose
        if _keys is None:
            for s in (a.get(axis) or [])[:take]:
                if not (s.get("oracle") or "").strip():
                    _fail(f"{page}: {axis}/{s.get('key', '?')} has no bespoke oracle text")
    # A10: an na declaration needs reason AND replace_with, and must point at a real frame cell
    for na in a.get("na") or []:
        if not (na.get("reason") or "").strip():
            _fail(f"{page}: na entry {na.get('cell')} has no reason (A10: vacuity is recorded "
                  f"with its receipt, never waved through)")
        if not isinstance(na.get("replace_with"), dict):
            _fail(f"{page}: na entry {na.get('cell')} has no replace_with (A10: the frame "
                  f"back-fills so 200 still holds)")


def rows_for(a):
    """The 200, in fixed order. An `na` declaration swaps a cell's oracle/subject for its
    replacement and the swap is stamped onto the row so a reader can see it happened."""
    page, url = a["page"], a["url"]
    na_by_cell = {n["cell"]: n for n in a.get("na") or []}
    rows, n = [], 0
    for fam, mand, axis, take, keys in FRAME:
        subjects = (a.get(axis) or [])[:take]
        per_subject = keys if keys is not None else [None]
        for s in subjects:
            for ok in per_subject:
                n += 1
                cell = f"{fam}/{s['key']}/{ok or 'bespoke'}"
                oracle_key, oracle, subject, note = ok, None, s, None
                if cell in na_by_cell:
                    na = na_by_cell[cell]
                    rw = na["replace_with"]
                    oracle_key = rw.get("oracle_key", ok)
                    subject = rw.get("subject", s)
                    note = f"replaces na cell {cell}: {na['reason']}"
                if oracle_key is None:                      # bespoke: CD / CI
                    oracle = subject["oracle"]
                    oracle_key = subject["key"]
                else:
                    if oracle_key not in ORACLES:
                        _fail(f"{page}: row {n} names oracle {oracle_key!r} which is not in the "
                              f"ORACLES table -- the strict-lookup rule, same as the marketplace "
                              f"builder: an unwritten oracle must raise, never inherit")
                    oracle = ORACLES[oracle_key]
                row = {
                    "id": f"PB-{page}-{n:03d}-{fam}-{subject['key']}-{oracle_key}",
                    "n": n,
                    "page": page,
                    "category": fam,
                    "mandate": mand,
                    "question": QUESTIONS[fam],
                    "surface": page,
                    "url": url,
                    "subject": {k: subject[k] for k in ("key", "name", "seen") if k in subject},
                    "oracle_key": oracle_key,
                    "oracle": oracle,
                    "status": "owed",
                    "findings": [],
                }
                if note:
                    row["note"] = note
                rows.append(row)
    if len(rows) != 200:
        _fail(f"{page}: frame produced {len(rows)} rows, not 200 (A8) -- the arithmetic is the "
              f"contract, and a bank that cannot count cannot be trusted to measure")
    return rows


def build(page):
    apath = os.path.join(ANATOMY_DIR, f"{page}.json")
    if not os.path.exists(apath):
        _fail(f"no anatomy at {os.path.relpath(apath, ROOT)} -- Ground the page first; this tool "
              f"authors from receipts, never from a page's name")
    a = json.load(open(apath, encoding="utf-8"))
    check_anatomy(a)
    rows = rows_for(a)
    return {
        "_doc": ("Page live-MCP bank, derived from page_bank_anatomy/%s.json by "
                 "tools/build_page_live_mcp_bank.py -- do not hand-edit rows; edit the anatomy and "
                 "regenerate. `status` moves owed -> green only via a LIVE MCP walk with typed "
                 "evidence (validate_live_mcp_bank rules R1-R7); findings accumulate so a re-walk "
                 "proves a fix rather than re-discovering it." % a["page"]),
        "page": a["page"],
        "url": a["url"],
        "frame": "PAGE_TESTBANK_ROADMAP.md section 1 (60 arch + 50 UFAI + 45 UI + 45 UX = 200)",
        "declared_na": a.get("na") or [],
        "deferred": a.get("deferred") or [],
        "writes_classified": a.get("writes") or [],
        "total": len(rows),
        "scenarios": rows,
    }


def emit(page, out=None):
    bank = build(page)
    out = out or os.path.join(BANKS_DIR, f"{page}_live_mcp_bank.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # merge-preserve, same contract as the marketplace builder: never wipe a walk's findings or
    # evidence by regenerating. Keyed on id; the id embeds (page, n, family, subject, oracle), so a
    # changed frame slot is a NEW claim and correctly starts owed.
    if os.path.exists(out):
        old = {s["id"]: s for s in (json.load(open(out, encoding="utf-8")) or {}).get("scenarios", [])}
        for s in bank["scenarios"]:
            if s["id"] in old:
                s["status"] = old[s["id"]].get("status", s["status"])
                s["findings"] = old[s["id"]].get("findings", [])
                if "evidence" in old[s["id"]]:
                    s["evidence"] = old[s["id"]]["evidence"]
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(bank, f, indent=1, ensure_ascii=False)
    os.replace(tmp, out)            # atomic: open(w) truncates before the write, and a crash
    return out                      # mid-dump would otherwise leave a dead bank on disk


# ── selftest: each rail must FIRE on a rigged anatomy, and a well-formed one must build ──────────
def _good_anatomy():
    seen = {"how": "static-read", "ref": "selftest.html:1"}
    mk = lambda k, i: {"key": f"{k}{i}", "name": f"{k} {i}", "seen": dict(seen)}
    return {
        "page": "_selftest", "url": "/workhive/_selftest.html",
        "layers": [mk("L", i) for i in range(1, 5)],
        "seams": [mk("S", i) for i in range(1, 6)],
        "views": [mk("V", i) for i in range(1, 4)],
        "components": [mk("C", i) for i in range(1, 4)],
        "journey_personas": [mk("P", i) for i in range(1, 4)],
        "identity_personas": [mk("I", i) for i in range(1, 3)],
        "invariants": [{**mk("CD", i), "oracle": f"invariant {i} holds"} for i in range(1, 7)],
        "domain_truths": [{**mk("CI", i), "oracle": f"truth {i} holds"} for i in range(1, 9)],
    }


def selftest():
    ok = True

    def expect_refusal(anat, label):
        nonlocal ok
        try:
            check_anatomy(anat)
            rows_for(anat)
            print(f"  FAIL - {label}: the build was supposed to refuse and did not")
            ok = False
        except BuildRefused:
            pass

    # the frame's own arithmetic, on a well-formed anatomy
    good = _good_anatomy()
    check_anatomy(good)
    rows = rows_for(good)
    if len(rows) != 200:
        print(f"  FAIL - frame arithmetic: {len(rows)} rows, not 200")
        ok = False
    if [r["n"] for r in rows] != list(range(1, 201)):
        print("  FAIL - row numbering is not a clean 1..200")
        ok = False
    mandates = {}
    for r in rows:
        mandates[r["mandate"]] = mandates.get(r["mandate"], 0) + 1
    if mandates != {"F1-architecture": 60, "F2-ufai": 50, "F3-ui": 45, "F4-ux": 45}:
        print(f"  FAIL - mandate split is {mandates}, not 60/50/45/45")
        ok = False
    if any(r["status"] != "owed" for r in rows):
        print("  FAIL - a freshly authored row must start owed")
        ok = False

    # A7: a scored subject with no receipt refuses
    a7 = _good_anatomy()
    del a7["views"][0]["seen"]
    expect_refusal(a7, "A7 unsourced subject")

    # A8: an under-supplied axis refuses
    a8 = _good_anatomy()
    a8["seams"] = a8["seams"][:3]
    expect_refusal(a8, "A8 under-supplied axis")

    # A8 the other direction: over-supply is taken from the head, tail untouched, still 200
    a8b = _good_anatomy()
    a8b["views"].append({"key": "V9", "name": "tail view", "seen": {"how": "x", "ref": "y"}})
    check_anatomy(a8b)
    if len(rows_for(a8b)) != 200:
        print("  FAIL - a ranked tail beyond the frame must not change the count")
        ok = False

    # bespoke oracles must be prose, not placeholders
    ab = _good_anatomy()
    ab["invariants"][2]["oracle"] = "  "
    expect_refusal(ab, "bespoke invariant with empty oracle")

    # A10: na without reason refuses; na without replace_with refuses; a correct na swaps in place
    a10 = _good_anatomy()
    a10["na"] = [{"cell": "CG-ufai-A/V1/offline_refusal", "reason": "",
                  "replace_with": {"oracle_key": "retry_path"}}]
    expect_refusal(a10, "A10 na without reason")
    a10b = _good_anatomy()
    a10b["na"] = [{"cell": "CG-ufai-A/V1/offline_refusal", "reason": "no writes on this page"}]
    expect_refusal(a10b, "A10 na without replace_with")
    a10c = _good_anatomy()
    a10c["na"] = [{"cell": "CG-ufai-A/V1/offline_refusal", "reason": "no writes on this page",
                   "replace_with": {"oracle_key": "slow_honest"}}]
    check_anatomy(a10c)
    swapped = [r for r in rows_for(a10c) if r.get("note")]
    if len(swapped) != 1 or swapped[0]["oracle_key"] != "slow_honest" \
            or swapped[0]["oracle"] != ORACLES["slow_honest"]:
        print("  FAIL - A10: a declared na must swap the cell and stamp the swap onto the row")
        ok = False

    # strict oracle lookup: an unwritten key must raise, never inherit (the marketplace lesson)
    astrict = _good_anatomy()
    astrict["na"] = [{"cell": "CG-ufai-A/V1/offline_refusal", "reason": "x",
                      "replace_with": {"oracle_key": "no_such_oracle"}}]
    expect_refusal(astrict, "strict ORACLES lookup")

    print("  PASS - frame=200 (60/50/45/45), numbering 1..200, all rows owed; A7/A8/A10 and the "
          "strict-oracle rule each fire on a rigged anatomy" if ok else "  selftest FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    if args.all:
        pages = sorted(f[:-5] for f in os.listdir(ANATOMY_DIR) if f.endswith(".json"))
        for p in pages:
            print("wrote", os.path.relpath(emit(p), ROOT))
        return
    if not args.page:
        ap.error("name a page, or --all, or --selftest")
    print("wrote", os.path.relpath(emit(args.page, args.out), ROOT))


if __name__ == "__main__":
    main()
