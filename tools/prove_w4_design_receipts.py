#!/usr/bin/env python3
"""prove_w4_design_receipts.py - the `w4-design` gate: a design-lens row stays banked only while its evidence holds.

Every receipt in .tmp/mcp_walks/W4*.json whose `w4.lens` is set is checked for shape (the lens, BOTH viewports with a
`fit` dict on every step, a detector file, after-scores for the scored lenses, both languages for copy, the Figma
nodes for figma) and its page is RE-SCANNED with `impeccable detect --json` now - not the file saved at bank time.
A page that regressed (a later edit re-introduced a tiny label, a nested card, a gradient heading) fails this gate
by name, which is how a banked row is reopened: the platform gate goes red until the page is clean again or the row
is reverted. Kin of prove_w4_confusions_receipt_shape.py.

  python tools/prove_w4_design_receipts.py --check
  python tools/prove_w4_design_receipts.py --self-test   # a good receipt passes; a thin one is refused at write time
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# ONE definition, two consumers. The ratchet owns the rule ("a low-contrast finding whose
# FOREGROUND colour appears inside an @media print block and nowhere outside it is measuring
# paper against the screen"); this gate reads the same detector and must not carry a second
# copy of it - two implementations of one rule is precisely how a fix lands in the half nobody
# calls.
from prove_design_detector_ratchet import is_measurement_artifact  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
DETECTOR = Path(os.environ.get("IMPECCABLE_HOME", str(Path.home() / ".claude" / "skills" / "impeccable"))) / "scripts" / (
    "impeccable.cmd" if os.name == "nt" else "impeccable")
VIEWPORTS = {"phone-390", "desktop-1280"}


def design_receipts() -> list[tuple[str, dict]]:
    out = []
    for path in sorted(glob.glob(str(ROOT / ".tmp" / "mcp_walks" / "W4*.json"))):
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        for res in doc.get("results") or []:
            if (res.get("w4") or {}).get("lens"):
                out.append((os.path.relpath(path, ROOT), res))
    return out


def shape_problems(res: dict) -> list[str]:
    w4 = res.get("w4") or {}
    steps = res.get("steps") or []
    p = []
    if not res.get("ok"):
        p.append("receipt not ok")
    if not VIEWPORTS <= set(w4.get("viewports") or []):
        p.append("not both viewports")
    page = _page_of(res)
    if not page:
        p.append("no page step carries a viewport")
    else:
        got = {s.get("viewport") for s in steps if s.get("page") == page}
        if not VIEWPORTS <= got:
            p.append(f"{page} not walked at both viewports")
    if any(not isinstance(s.get("fit"), dict) for s in steps):
        p.append("a step has no fit record")
    if not w4.get("detector") or not (ROOT / w4["detector"]).exists():
        p.append("detector file missing")
    lens = w4.get("lens")
    if lens in ("audit", "critique"):
        after = (w4.get("scores") or {}).get("after") or {}
        if not after:
            p.append("no after-scores")
        else:
            low = [k for k, v in after.items() if isinstance(v, (int, float)) and v < 3]
            if low:
                p.append("scores below 3: " + ", ".join(low))
    if lens == "copy" and not {"en", "fil"} <= set(w4.get("languages") or []):
        p.append("copy lens not in both languages")
    if lens == "figma" and not w4.get("figma"):
        p.append("figma lens without file/node ids")
    return p


def _page_of(res: dict) -> str:
    for s in res.get("steps") or []:
        if s.get("viewport"):
            return s.get("page") or ""
    return ""


def rescan(pages: set[str]) -> dict[str, int]:
    """page -> primary findings now (see rescan_by_kind for the per-antipattern breakdown)."""
    if not pages:
        return {}
    r = subprocess.run([str(DETECTOR), "detect", "--json", "--no-advisory", *sorted(pages)], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    findings = json.loads((r.stdout or "").strip() or "[]")
    counts = {p: 0 for p in pages}
    for f in findings:
        if f.get("severity") == "advisory":
            continue
        if is_measurement_artifact(f):
            continue          # paper's colour measured against the screen's background
        rel = os.path.relpath(f.get("file") or "", ROOT).replace("\\", "/")
        if rel in counts:
            counts[rel] += 1
    return counts


def rescan_by_kind(pages: set[str]) -> dict[str, dict[str, int]]:
    """page -> {antipattern: count} now. Feeds the disproven-claims re-check below."""
    if not pages:
        return {}
    r = subprocess.run([str(DETECTOR), "detect", "--json", "--no-advisory", *sorted(pages)], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    findings = json.loads((r.stdout or "").strip() or "[]")
    out: dict[str, dict[str, int]] = {p: {} for p in pages}
    for f in findings:
        if f.get("severity") == "advisory":
            continue
        if is_measurement_artifact(f):
            continue          # paper's colour measured against the screen's background
        rel = os.path.relpath(f.get("file") or "", ROOT).replace("\\", "/")
        if rel in out:
            k = f.get("antipattern") or "?"
            out[rel][k] = out[rel].get(k, 0) + 1
    return out


def check() -> int:
    receipts = design_receipts()
    if not receipts:
        print("PASS w4-design: no design-lens receipts banked yet (nothing to hold)")
        return 0
    fails = []
    pages = set()
    for path, res in receipts:
        probs = shape_problems(res)
        if probs:
            fails.append(f"{res.get('id')} ({path}): " + "; ".join(probs))
        pg = _page_of(res)
        if pg:
            pages.add(pg)
    now = rescan(pages)
    by_kind = rescan_by_kind(pages)
    for path, res in receipts:
        pg = _page_of(res)
        if not pg or now.get(pg, 0) <= 0:
            continue
        # ★A RECEIPT MAY CARRY FINDINGS A LIVE MEASUREMENT DISPROVED - PINNED TO THEIR COUNT (2026-09-15).
        # analytics-report.html holds a dark app shell AND a white printed document in one file, so the
        # detector pairs the shell's white text with the document's white ground: nine low-contrast findings,
        # while a live sampler over the GENERATED report measured 0 of 609 nodes below threshold. The claim is
        # only honoured while the count still MATCHES - one new finding of that kind, or any finding of a kind
        # the receipt never claimed, and the row fails exactly as before. The exception cannot widen itself.
        claimed = ((res.get("w4") or {}).get("detectorDisproven") or {})
        kinds = by_kind.get(pg, {})
        unclaimed = {k: v for k, v in kinds.items() if k not in claimed}
        # ONLY AN INCREASE IS DRIFT. The rule this enforces is the comment above - "the exception
        # cannot widen itself" - and a count that FALLS narrows it: fewer findings are being
        # excused than the receipt measured. Failing a page for having been FIXED is what `!=`
        # did here: asset-hub.html's six side-tab findings went to 0 and took six banked rows
        # down with them (2026-09-16).
        drifted = {k: (c.get("count"), kinds.get(k, 0)) for k, c in claimed.items()
                   if kinds.get(k, 0) > (c.get("count") or 0)}
        healed = sorted(k for k, c in claimed.items() if kinds.get(k, 0) < (c.get("count") or 0))
        if not unclaimed and not drifted:
            if healed:
                print("   note: %s (%s on %s) carries a disproven pin for %s that the page no longer "
                      "reports at that count - the page improved; the pin is stale, not wrong."
                      % (res.get("id"), (res.get("w4") or {}).get("lens"), pg, ", ".join(healed)))
            continue
        detail = "; ".join(f"{k} x{v}" for k, v in sorted(unclaimed.items()))
        for k, (want, got) in sorted(drifted.items()):
            detail += f"; '{k}' was disproven at {want}, now {got}"
        fails.append(f"{res.get('id')} ({(res.get('w4') or {}).get('lens')} on {pg}): the page now reports "
                     f"{now[pg]} primary detector finding(s) not covered by this receipt - {detail}; "
                     "fix, or re-bank with the live measurement that disproves them")
    if fails:
        print(f"FAIL w4-design: {len(fails)} of {len(receipts)} design-lens receipt(s) no longer hold:")
        for f in fails[:30]:
            print("   -", f[:220])
        return 1
    print(f"PASS w4-design: {len(receipts)} design-lens receipt(s) hold shape, and their {len(pages)} page(s) "
          f"re-scan clean today")
    return 0


def self_test() -> int:
    from record_mcp_walk import build_receipt  # noqa: E402
    with tempfile.TemporaryDirectory(dir=str(ROOT / ".tmp")) as d:
        det = Path(d) / "x.detect.json"
        det.write_text("[]", encoding="utf-8")
        rel = os.path.relpath(det, ROOT).replace("\\", "/")
        good_steps = [{"page": "index.html", "chars": 900, "identityKept": True, "fit": {"findings": 0}},
                      {"page": "achievements.html", "viewport": "phone-390", "chars": 2000, "identityKept": True, "fit": {"findings": 0}},
                      {"page": "achievements.html", "viewport": "desktop-1280", "chars": 2100, "identityKept": True, "fit": {"findings": 0}}]
        good = build_receipt("W4x", "playwright-mcp", "normal", "A Worker", good_steps, "n", "s",
                             w4={"axis": "phone-390 en", "lens": "slop", "viewports": "phone-390,desktop-1280", "detector": rel})
        r = good["results"][0]
        if not r["ok"] or shape_problems(r):
            print(f"FAIL self-test: a good design receipt did not hold: {shape_problems(r)}")
            return 1
        try:
            build_receipt("W4y", "playwright-mcp", "normal", "A Worker", good_steps, "n", "s",
                          w4={"axis": "phone-390 en", "lens": "slop", "viewports": "phone-390", "detector": rel})
            print("FAIL self-test: a one-viewport design receipt was written")
            return 1
        except ValueError:
            pass
        try:
            build_receipt("W4z", "playwright-mcp", "normal", "A Worker", good_steps, "n", "s",
                          w4={"axis": "phone-390 en", "lens": "slop", "viewports": "phone-390,desktop-1280"})
            print("FAIL self-test: a design receipt without a detector file was written")
            return 1
        except ValueError:
            pass
        thin = dict(r, w4=dict(r["w4"], lens="audit"))
        if "no after-scores" not in "; ".join(shape_problems(thin)):
            print("FAIL self-test: an audit receipt without after-scores held")
            return 1
    print("PASS w4-design self-test: a two-viewport receipt with a detector file holds; one viewport, no detector, "
          "and a scored lens without after-scores are refused")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    return check()


if __name__ == "__main__":
    sys.exit(main())
