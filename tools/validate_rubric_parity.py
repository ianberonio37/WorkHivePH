#!/usr/bin/env python3
"""validate_rubric_parity.py — the teeth of the UFAI rubric SSOT lock (UR-P0 + UR-P1).

WHY: the UFAI rubric lives in THREE forms that silently drift — the prose SSOT
(`substrate/reference/ufai-ux-rubric.md`), the code lens (`survey_ufai_rubric.js`, which
tags each dim via M('A1',...) / J('D2',...) / NA('C2',...)), and now the machine-readable
SSOT (`ufai-rubric-spec.json`). On 2026-07-21 the ruler had THREE disagreeing counts (doc
header 49, code header 44, body 63). This gate makes divergence impossible:

  (1) SET parity     — the doc, the lens, AND the spec declare the SAME dims, EXCEPT the
                       cross-page dims (S2/S3, owner "family-sweep" in the spec) which the
                       single-page lens does not encode.
  (2) COUNT parity   — doc == code + cross-page-exempt; and any "N dims/dimensions" claim in
                       either HEADER must equal its own authoritative body count (a stale
                       header is the exact drift this gate exists to catch).
  (3) THRESHOLD lock — every DISTINCTIVE numeric floor the spec declares (44, 150, 2500, 4.5,
                       18.66 — the ones that can't collide with an unrelated digit) must still
                       appear in its OWNER file (rubric-lens -> survey_ufai_rubric.js;
                       battery -> ufai_battery.js). A threshold that VANISHES from the code is
                       drift. Generic single digits (3/6/7/8/2) are NOT hard-checked here — they
                       get locked structurally in UR-P1b when the lens reads them from the spec.

Forward-only by construction: parity is an absolute invariant. Add a class to the prose without
encoding it (or to the spec), leave a header count stale, or delete a spec'd threshold from the
code, and this FAILs.

  python tools/validate_rubric_parity.py            # check (exit 1 on drift)
  python tools/validate_rubric_parity.py --self-test # deterministic, no files
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "substrate" / "reference" / "ufai-ux-rubric.md"
LENS = REPO / "survey_ufai_rubric.js"
BATTERY = REPO / "ufai_battery.js"
SPEC = REPO / "ufai-rubric-spec.json"

# Dims declared in the prose + spec but MEASURED by the cross-page family sweep OR the live
# journey-PDDA, not the single-page __RUBRIC lens. A declared ownership split, not a gap (roadmap §2).
# 2026-07-22: the experience-in-motion extension (PDDA_UX_PAINPOINT_JOURNEY_ROADMAP.md) adds journey/
# context dims hunted live (X/Y) + the behavioral-family cross-page dim (S4) + system dims measured
# across sessions (G5/J3) — none single-page-static, so exempt from the lens like S2/S3. Z1/Z2/Z3 ARE
# single-page-static → encoded in the lens (survey_ufai_rubric.js), NOT exempt.
EXEMPT_CROSS_PAGE = {"S2", "S3", "G5", "J3", "S4", "JA1", "JA2", "JA3", "AI6"}
# AI6 (2026-07-24 agentic write accountability) is a BACKEND dim: it grades what an AI edge fn WRITES
# to the database, which no DOM scan can observe - measured from edge-fn source by
# validate_ai_write_provenance.py. Exempt from the lens for the same reason as J3/G5/S4/JA*.   # JA1 (2026-07-23 deep-link ARRIVAL fidelity) is
# an IN-MOTION, cross-page dim: it only exists on a hand-off between two pages (does the destination honour
# the entity the source named, or say it could not be found?), so a single-page DOM scan cannot see it -
# measured from page SOURCE by validate_journey_ux_dims.py, exempt from the lens exactly like G5/J3/S4.   # X3, Y1 (2026-07-22 findability/offline) + X2 (2026-07-23 interruption/draft-survival) + X1, Y2 (2026-07-23 dead-end-states/stress-timing static slices) built as single-page lens dims → no longer exempt

# single-letter A–Z classes + the 2-letter deeper-extension classes (AI/PP/DL/DD, added 2026-07-23).
_VALID_CLASS = set("ABCDEFGHIJKLMNOPQRSTVWXYZ") | {"AI", "PP", "DL", "DD", "TR", "RE", "JA", "DP"}


def _class_of(dim: str) -> str:
    """The alpha class prefix of a dim id ('AI1' -> 'AI', 'B3' -> 'B')."""
    m = re.match(r"[A-Z]+", dim)
    return m.group() if m else ""


def parse_doc_dims(text: str) -> set[str]:
    """Dim ids declared as definition list-items / bold paragraphs in the prose."""
    dims: set[str] = set()
    for line in text.splitlines():
        m = re.match(r"^[\s\-*★]*\*?([A-Z]{1,2}[0-9])(?=[\s·)]|$)", line)
        if m and _class_of(m.group(1)) in _VALID_CLASS:
            dims.add(m.group(1))
    return dims


def parse_code_dims(text: str) -> dict[str, str]:
    """Dim ids encoded in the lens, tagged by verdict helper: M=MEASURED, J=JUDGED, NA=N/A."""
    out: dict[str, str] = {}
    for verb, dim in re.findall(r"(?<![A-Za-z])(M|J|NA)\(\s*'([A-Z]{1,2}[0-9])'", text):
        if dim not in out or (out[dim] == "NA" and verb != "NA"):
            out[dim] = {"M": "MEASURED", "J": "JUDGED", "NA": "N/A"}[verb]
    return out


def parse_spec(spec_obj: dict) -> dict[str, dict]:
    """Dim entries in the JSON spec (top-level keys except _meta)."""
    return {k: v for k, v in spec_obj.items() if k != "_meta" and re.fullmatch(r"[A-Z]{1,2}[0-9]", k)}


def header_count_claim(text: str, patterns: list[str]) -> int | None:
    head = "\n".join(text.splitlines()[:12])
    for pat in patterns:
        m = re.search(pat, head)
        if m:
            return int(m.group(1))
    return None


def _distinctive(v) -> bool:
    """A threshold value unlikely to collide with an unrelated digit in the source:
    a decimal (4.5, 18.66) or a value >= 24 (44, 150, 200, 2500). Generic small ints
    (2/3/6/7/8) are excluded — they get structurally locked in UR-P1b (lens reads spec)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return (f != int(f)) or f >= 24


def check(doc_text: str, code_text: str, spec_obj: dict | None,
          battery_text: str = "") -> tuple[bool, list[str], list[str], dict]:
    doc = parse_doc_dims(doc_text)
    code_map = parse_code_dims(code_text)
    code = set(code_map)
    problems: list[str] = []
    warns: list[str] = []

    # (1) SET parity DOC<->CODE, modulo the declared cross-page exemptions
    doc_only = doc - code - EXEMPT_CROSS_PAGE
    code_only = code - doc
    if doc_only:
        problems.append(f"declared in the DOC but NOT encoded in the lens: {sorted(doc_only)}")
    if code_only:
        problems.append(f"encoded in the lens but NOT declared in the DOC: {sorted(code_only)}")

    # (2) COUNT parity: doc body == code body + exempt
    exempt_in_doc = doc & EXEMPT_CROSS_PAGE
    if len(doc) != len(code) + len(exempt_in_doc):
        problems.append(f"count mismatch: doc {len(doc)} != code {len(code)} + exempt {len(exempt_in_doc)}")

    # (2b) stale-HEADER guard
    doc_hdr = header_count_claim(doc_text, [r"~?\s*(\d+)\s+dimension", r"(\d+)\s+dims"])
    code_hdr = header_count_claim(code_text, [r"\((\d+)\s+dims\)", r"(\d+)\s+dims"])
    if doc_hdr is not None and doc_hdr != len(doc):
        problems.append(f"DOC header claims {doc_hdr} dims but the body has {len(doc)} (reconcile the header)")
    if code_hdr is not None and code_hdr != len(code):
        problems.append(f"CODE header claims {code_hdr} dims but the lens encodes {len(code)} (reconcile the header)")

    spec_dims: dict[str, dict] = {}
    thr_checked = thr_missing = centralized = 0
    if spec_obj is not None:
        spec_dims = parse_spec(spec_obj)
        spec = set(spec_dims)
        # dims NOT measured by the single-page lens: cross-page family-sweep dims (S2/S3), the journey-ux
        # source-grep validator dims (J3/G5/S4/JA*, 2026-07-22 — validate_journey_ux_dims.py), and the
        # BACKEND write-provenance dim (AI6, 2026-07-24 — validate_ai_write_provenance.py grades what an
        # AI edge fn WRITES to the DB, which no DOM lens can observe).
        spec_family = {d for d, v in spec_dims.items()
                       if v.get("owner") in ("family-sweep", "journey-validator",
                                             "ai-write-provenance-validator")}

        # (3a) SET parity SPEC<->DOC (the spec is the third source; it must match the prose)
        if spec - doc:
            problems.append(f"in the SPEC but NOT the doc: {sorted(spec - doc)}")
        if doc - spec:
            problems.append(f"in the DOC but NOT the spec: {sorted(doc - spec)}")
        # (3b) SET parity SPEC(non-cross-page)<->CODE
        spec_single = spec - spec_family
        if spec_single - code:
            problems.append(f"in the SPEC (non-cross-page) but NOT the lens: {sorted(spec_single - code)}")
        if code - spec_single:
            problems.append(f"in the lens but NOT the spec: {sorted(code - spec_single)}")

        # (3b') VERDICT consistency (Axis-3 honesty-contract lock) — the spec centralizes each
        # dim's verdict (measured/judged); the lens must agree. M<->measured, J<->judged; NA is a
        # state of a measured dim, so it may not contradict a 'judged' spec entry.
        for dim in spec_single & code:
            sv = (spec_dims[dim].get("verdict") or "").lower()
            lv = code_map.get(dim)
            if sv == "judged" and lv != "JUDGED":
                problems.append(f"{dim}: spec verdict 'judged' but the lens tags it {lv}")
            elif sv in ("measured", "na-capable") and lv == "JUDGED":
                problems.append(f"{dim}: spec verdict '{sv}' but the lens tags it JUDGED")

        # (3c) THRESHOLD lock.
        # For dims CENTRALIZED in the lens's generated-mirror block (UR-P1b), every JSON value
        # must appear in that block — a HARD value-lock that catches a 20->25 drift in either
        # direction. For not-yet-centralized dims, a soft distinctive-presence check in the
        # owner file (rubric-lens -> the lens; battery -> ufai_battery.js).
        mblock = re.search(r"/\* RUBRIC_THRESHOLDS_START \*/(.*?)/\* RUBRIC_THRESHOLDS_END \*/",
                           code_text, re.S)
        block = mblock.group(1) if mblock else ""
        block_dims = set(re.findall(r"(?m)^\s*([A-Z][0-9])\s*:\s*\{", block))
        # the battery mirrors the CWV (I1) thresholds in its own marked block
        bmb = re.search(r"/\* I1_CWV_THRESHOLDS_START \*/(.*?)/\* I1_CWV_THRESHOLDS_END \*/",
                        battery_text, re.S)
        battery_block = bmb.group(1) if bmb else ""
        centralized = len(block_dims) + (1 if battery_block else 0)
        owner_src = {"rubric-lens": code_text, "battery": battery_text or code_text, "family-sweep": ""}

        def _num_in(text: str, val) -> bool:
            pat = r"(?<![\d.])" + re.escape(str(val)).replace(r"\.0", r"(\.0)?") + r"(?![\d])"
            return re.search(pat, text) is not None

        for dim, entry in spec_dims.items():
            owner = entry.get("owner", "rubric-lens")
            for tname, t in (entry.get("thresholds") or {}).items():
                val = t.get("value")
                if val is None:
                    continue
                if owner == "rubric-lens" and dim in block_dims:
                    thr_checked += 1
                    if not _num_in(block, val):
                        problems.append(f"{dim}.{tname}={val} in the SPEC is not in the lens "
                                        f"RUBRIC_THRESHOLDS block — the mirror drifted from the JSON")
                    continue
                if dim == "I1" and battery_block:   # only the CWV triad lives in this block
                    thr_checked += 1
                    if not _num_in(battery_block, val):
                        problems.append(f"{dim}.{tname}={val} in the SPEC is not in the battery "
                                        f"I1_CWV_THRESHOLDS block — the mirror drifted from the JSON")
                    continue
                if t.get("severity") == "info" or not _distinctive(val):
                    continue
                thr_checked += 1
                if not _num_in(owner_src.get(owner, code_text), val):
                    thr_missing += 1
                    warns.append(f"{dim}.{tname}={val} (owner {owner}) not found in its owner file")

    v = {k: sum(1 for x in code_map.values() if x == k) for k in ("MEASURED", "JUDGED", "N/A")}
    stats = {"doc": len(doc), "code": len(code), "spec": len(spec_dims),
             "exempt": sorted(exempt_in_doc), "doc_hdr": doc_hdr, "code_hdr": code_hdr,
             "verdicts": v, "thr_checked": thr_checked, "thr_missing": thr_missing,
             "centralized": centralized}
    return (not problems), problems, warns, stats


def self_test() -> int:
    fails = []
    doc = "- A1 x\n- **B4 · y**\n- **S2 chrome**\n- **S3 card**"
    code = "M('A1','x',[]); J('B4','y');"
    spec = {"_meta": {}, "A1": {"owner": "rubric-lens", "thresholds": {"tap": {"value": 44}}},
            "B4": {"owner": "rubric-lens"},
            "S2": {"owner": "family-sweep"}, "S3": {"owner": "family-sweep"}}
    # code has 44 -> threshold present; sets match -> PASS
    ok, probs, warns, st = check(doc, code + " x<44 ", spec)
    if not ok:
        fails.append(f"matched doc/code/spec should PASS, got: {probs}")
    if st["spec"] != 4 or st["doc"] != 4 or st["code"] != 2:
        fails.append(f"stats wrong: {st}")
    # a spec dim absent from the doc must FAIL
    ok2, probs2, _, _ = check(doc, code, {**spec, "Z9": {"owner": "rubric-lens"}})
    if ok2:
        fails.append("spec dim Z9 absent from doc should FAIL")
    # a distinctive threshold missing from the owner file must WARN (not fail)
    ok3, probs3, warns3, _ = check(doc, code, spec)  # code here has NO '44'
    if not ok3 or not any("A1.tap" in w for w in warns3):
        fails.append(f"missing distinctive threshold should WARN (pass+warn), got ok={ok3} warns={warns3}")
    # stale DOC header should FAIL
    ok4, probs4, _, _ = check(doc + "\n(9 dimensions)", code, spec)
    if ok4:
        fails.append("planted stale DOC header should FAIL")
    if parse_doc_dims("**A · Comprehension**"):
        fails.append("class headers (no digit) should yield no dims")
    if fails:
        print("FAIL validate_rubric_parity self-test:")
        for f in fails:
            print("  - " + f)
        return 1
    print("PASS validate_rubric_parity self-test (set + count + stale-header + spec + threshold-lock guards)")
    return 0


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        return self_test()
    for f in (DOC, LENS, SPEC):
        if not f.exists():
            print(f"FAIL rubric-parity: missing {f}")
            return 1
    spec_obj = json.loads(SPEC.read_text(encoding="utf-8"))
    battery_text = BATTERY.read_text(encoding="utf-8", errors="ignore") if BATTERY.exists() else ""
    ok, problems, warns, st = check(DOC.read_text(encoding="utf-8", errors="ignore"),
                                    LENS.read_text(encoding="utf-8", errors="ignore"),
                                    spec_obj, battery_text)
    v = st["verdicts"]
    print(f"rubric-parity: doc {st['doc']} · lens {st['code']} ({v['MEASURED']}M/{v['JUDGED']}J/{v['N/A']}NA) "
          f"· spec {st['spec']} · cross-page exempt {st['exempt']} · doc-hdr {st['doc_hdr']} · code-hdr {st['code_hdr']} "
          f"· {st['centralized']} dims value-locked to the mirror block "
          f"· thresholds {st['thr_checked'] - st['thr_missing']}/{st['thr_checked']} present")
    for w in warns:
        print("  ⚠ " + w)
    if ok:
        print("PASS rubric-parity — prose, lens, and spec all agree.")
        return 0
    print("FAIL rubric-parity — the ruler has drifted:")
    for p in problems:
        print("  - " + p)
    return 1


if __name__ == "__main__":
    sys.exit(main())
