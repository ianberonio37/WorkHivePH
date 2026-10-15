#!/usr/bin/env python3
"""prove_page_craft.py - SL sub-layer F5 (2026-10-15): "The platform must build this page from the design tokens and
the motion rules, with nothing the design detector flags."

Three readings per page, each from the instrument that owns it (never re-derived):
  detector   the design ratchet's own pipeline (prove_design_detector_ratchet: impeccable detect + the declared-dot leg,
             minus the measurement artifacts it proves) - the page's primary findings must be 0; the motion rules are
             part of it (bounce easing, layout transitions, forever-pulsing dots)
  radius     validate_design_tokens' own rule - every border-radius a var(--wh-radius*) or a value on DESIGN.md's
             scale (8/12/16px, 999px pills, 50%) - the page's rogue radii must be 0
  colour     a brand colour written in CSS (a <style> block or a style="" attribute) must be a token reference -
             var(--wh-*, #fallback) - never the bare hex; SVG presentation attributes, meta theme-color and JS
             colour constants are not CSS and are not counted
TEETH (in memory): a planted off-scale corner, a planted bare brand hex in a style block, and a planted 9px label each
make a clean page fail.

  python tools/prove_page_craft.py [--page a.html,...] [--json .tmp/page_craft_results.json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import prove_design_detector_ratchet as R  # noqa: E402

_spec = importlib.util.spec_from_file_location("vdt", ROOT / "validate_design_tokens.py")
VDT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(VDT)
TOK = {v.upper() for v in VDT.CANONICAL_TOKENS.values()}
SPAN = re.compile(r"var\((?:[^()]|\([^()]*\))*\)|url\([^)]*\)|#[0-9A-Fa-f]{6}\b")
STYLE_BLOCK = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.S | re.I)
STYLE_ATTR = re.compile(r"""(\sstyle\s*=\s*")([^"]*)(")""", re.I)


def rogue_radii(text: str) -> list[str]:
    body = VDT._strip_comments(text)
    out = []
    for mm in VDT.RADIUS_RE.finditer(body):
        val = re.split(r"[\"'<>]", mm.group(1))[0].strip().replace("!important", "").strip()   # the value ends where the attribute does
        if "var(" in val:
            continue
        parts = [re.sub(r"^\.(\d)", r"0.\1", x) for x in re.split(r"[\s/]+", val) if x]
        if parts and all(x in VDT.LEGAL_RADIUS for x in parts):
            continue
        out.append(val)
    return out


def bare_brand_hex(text: str) -> list[str]:
    out = []
    for mm in list(STYLE_BLOCK.finditer(text)) + list(STYLE_ATTR.finditer(text)):
        for t in SPAN.finditer(mm.group(2)):
            if t.group(0).startswith("#") and t.group(0).upper() in TOK:
                out.append(t.group(0))
    return out


def detector_counts(pages: list[str], cwd: Path = ROOT) -> dict[str, int]:
    c = R.with_declared_dots(R.without_scrim_artifacts(R.counts(R.detect(pages, cwd=cwd))), pages, root=cwd)
    per: dict[str, int] = {}
    for k, v in c.items():
        f = k.split(" :: ")[0]
        per[f] = per.get(f, 0) + v
    return per


def judge(page: str, text: str, det: int) -> dict:
    rr, hx = rogue_radii(text), bare_brand_hex(text)
    problems = []
    if det:
        problems.append(f"the design detector flags {det} primary finding(s)")
    if rr:
        problems.append(f"{len(rr)} corner(s) off the radius scale ({', '.join(sorted(set(rr))[:4])})")
    if hx:
        problems.append(f"{len(hx)} brand colour(s) written as bare hex in CSS ({', '.join(sorted(set(hx))[:4])})")
    return {"page": page, "detector": det, "rogue_radii": len(rr), "bare_hex": len(hx), "problems": problems, "ok": not problems}


def teeth(sample: str) -> dict:
    text = (ROOT / sample).read_text(encoding="utf-8", errors="replace")
    radius = judge(sample, text.replace("</style>", ".zz{border-radius:13px}</style>", 1), 0)["ok"] is False
    colour = judge(sample, text.replace("</style>", ".zz{color:#F7A21B}</style>", 1), 0)["ok"] is False
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "slop.html"
        p.write_text("<!doctype html><html><body><p style='font-size:9px'>XP this week</p>"
                     "<button style='font-size:9px'>Save</button></body></html>", encoding="utf-8")
        det = sum(detector_counts([str(p)], cwd=Path(d)).values()) > 0
    return {"sample": sample, "radius_caught": radius, "colour_caught": colour, "detector_caught": det,
            "bit": radius and colour and det}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page")
    ap.add_argument("--json", default=str(ROOT / ".tmp" / "page_craft_results.json"))
    ap.add_argument("--rebase", action="store_true", help="lower the per-page floors that fell (refuses if any rose)")
    a = ap.parse_args()
    reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    f5 = {t["sl"]["page"]: t.get("persona") for t in reg["trajectories"]
          if (t.get("sl") or {}).get("sublayer") == "F5" and t.get("status") != "descoped"}
    pages = a.page.split(",") if a.page else sorted(f5)
    det = detector_counts(pages)
    results, bad = [], 0
    for page in pages:
        r = judge(page, (ROOT / page).read_text(encoding="utf-8", errors="replace"), det.get(page, 0))
        r.update({"cast": f5.get(page), "engine": "static", "condition": "craft"})
        bad += 0 if r["ok"] else 1
        results.append(r)
        print(f"  {'ok  ' if r['ok'] else 'FAIL'} {page:<56} detector {r['detector']}, radii {r['rogue_radii']}, bare hex {r['bare_hex']}")
    t = teeth(next((p for p in pages if p.startswith("learn/")), pages[0]))
    print(f"\n  teeth - an off-scale corner, a bare brand hex and a 9px label: "
          f"{'all CAUGHT' if t['bit'] else 'NOT ALL CAUGHT'} ({t})")
    # ★A FLOOR PER PAGE (the gate) vs ZERO (the row). A page's F5 row closes only at 0; the GATE holds every page at its
    # floor so a count can only fall while the root pages are brought onto the scale one at a time. --rebase lowers.
    base_path = ROOT / "page_craft_baseline.json"
    base = json.loads(base_path.read_text(encoding="utf-8")) if base_path.exists() else {}
    floors = base.get("pages", {})
    count = {r["page"]: r["detector"] + r["rogue_radii"] + r["bare_hex"] for r in results}
    rose = [f"{p}: {floors.get(p, 0)} -> {c}" for p, c in count.items() if base and c > floors.get(p, 0)]
    if not base or "--rebase" in sys.argv:
        if rose and base:
            print(f"REFUSED --rebase: {len(rose)} page(s) rose: {rose[:5]}")
            return 1
        new = {p: c for p, c in count.items() if c and (not base or c <= floors.get(p, c))}
        base_path.write_text(json.dumps({"_doc": "Per-page F5 craft counts (detector + off-scale radii + bare brand hex) "
                                         "- tools/prove_page_craft.py. A page above its floor fails; 0 closes its row.",
                                         "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "pages": new}, indent=1) + "\n",
                             encoding="utf-8")
        print(f"  floor {'written' if not base else 'rebased'}: {len(new)} page(s) hold a non-zero floor ({sum(new.values())})")
    failed = len(rose) + (0 if t["bit"] else 1)
    for r in rose:
        print("  ROSE " + r)
    out = Path(a.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "sublayer": "F5", "pages": len(results),
                               "failed": failed, "teeth": t, "results": results}, indent=1), encoding="utf-8")
    print(f"\n{'FAIL' if failed else 'PASS'} page-craft - {len(results) - bad}/{len(results)} page(s) built from the tokens with "
          f"nothing the detector flags -> {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
