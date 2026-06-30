"""
freeze_intuition_baseline.py — Arc Y (THE INTUITION GRADIENT) · Y0.5 baseline freeze
====================================================================================
Reads the live harness output (intuition_gradient_report.json) and freezes the
forward-only ratchet baseline (intuition_gradient_baseline.json). The gate
(validate_arc_y_intuition.py) then asserts no page regresses below this floor.

Ratchet semantics frozen here (per page):
  - novice_floor   : worker intuition % — must NOT drop (jitter band in the gate)
  - worker_fp / sup_fp : first-paint interactive count — must NOT grow (overwhelm ceiling)
  - back           : in-app back affordance present — must NOT flip Y->N (deterministic)
  - jargon         : jargon-without-gloss count — must NOT grow (deterministic)
  - dead_unlbl     : dead-links + unlabeled-inputs — must NOT grow (deterministic, L6)
  - l4             : 1 if the displayed value matched DB truth — must NOT go 1->0

Usage:  python tools/freeze_intuition_baseline.py            # freeze from current report
        python tools/freeze_intuition_baseline.py --check    # print drift, don't write
"""
from __future__ import annotations
import io, sys, json
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REPORT   = ROOT / "intuition_gradient_report.json"
BASELINE = ROOT / "intuition_gradient_baseline.json"


def _page_floor(card: dict) -> dict:
    w = card.get("worker") or {}
    s = card.get("supervisor") or {}
    l4w = (w.get("l4") or {})
    l4s = (s.get("l4") or {})
    # l4 "truthful" if EITHER session proved the displayed value == DB truth this run
    l4_ok = 0
    for chk in (l4w, l4s):
        sh, tr = chk.get("shown"), chk.get("truth")
        if sh is not None and tr is not None and sh == tr:
            l4_ok = 1
    return {
        "novice_floor": card.get("novice_floor"),
        "gradient":     card.get("gradient"),
        "worker_fp":    w.get("firstPaintInteractive"),
        "sup_fp":       s.get("firstPaintInteractive"),
        "back":         bool(w.get("backAffordance") or s.get("backAffordance")),
        "jargon":       len(w.get("jargonNoGloss") or []) + 0,  # worker view is the novice bar
        "jargon_sup":   len(s.get("jargonNoGloss") or []) + 0,
        "dead_unlbl":   (w.get("deadLinks") or 0) + (w.get("unlabeledInputs") or 0),
        "l4":           l4_ok,
    }


def main():
    check = "--check" in sys.argv
    if not REPORT.exists():
        print(f"  ERROR: {REPORT.name} not found — run the harness first: node tools/intuition_gradient_harness.mjs --all")
        sys.exit(1)
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    cards = rep.get("cards", [])
    pages = {}
    for c in cards:
        if c.get("novice_floor") is None:
            continue
        pages[c["page"]] = _page_floor(c)

    baseline = {
        "arc": "Y",
        "frozen_from": REPORT.name,
        "overwhelm_budget": rep.get("overwhelm_budget", 12),
        "pages_frozen": len(pages),
        "avg_novice_floor_pct": rep.get("avg_novice_floor_pct"),
        "avg_gradient_pts": rep.get("avg_gradient_pts"),
        "jitter": {"floor_pts": 3, "fp_grow": 3},   # live-run tolerance for the % / count signals
        "pages": pages,
    }

    if check:
        if not BASELINE.exists():
            print("  no baseline yet — would freeze", len(pages), "pages")
            return
        old = json.loads(BASELINE.read_text(encoding="utf-8"))
        oldp = old.get("pages", {})
        print(f"  drift vs frozen baseline ({len(oldp)} pages):")
        for slug, cur in sorted(pages.items()):
            o = oldp.get(slug)
            if not o:
                print(f"    NEW  {slug}  novice={cur['novice_floor']}%")
                continue
            d = (cur["novice_floor"] or 0) - (o["novice_floor"] or 0)
            if d:
                print(f"    {'+' if d>0 else ''}{d:>3}  {slug}  {o['novice_floor']}->{cur['novice_floor']}%")
        return

    BASELINE.write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  FROZE {BASELINE.name}: {len(pages)} pages · avg novice-floor {baseline['avg_novice_floor_pct']}% · avg gradient {baseline['avg_gradient_pts']}pts")
    worst = sorted(pages.items(), key=lambda kv: kv[1]["novice_floor"] or 0)[:8]
    print("  worst novice-floor frozen:")
    for slug, p in worst:
        print(f"    {p['novice_floor']:>3}%  {slug:<26} back:{'Y' if p['back'] else 'N'} jargon:{p['jargon']} fp:{p['worker_fp']} dead+unlbl:{p['dead_unlbl']}")

    # Arc Y Y6 (make the loop VISIBLE): emit a human-readable scorecard so the
    # intuition-gradient measurement isn't buried in JSON — the team can SEE each
    # page's novice-floor + the per-lens signal that pulls it down, and review the
    # gradient (worker vs engineer/supervisor) at a glance.
    md = [f"# Arc Y — Intuition-Gradient Scorecard",
          f"",
          f"_Generated from `{REPORT.name}`. avg novice-floor **{baseline['avg_novice_floor_pct']}%** · avg persona spread **{baseline['avg_gradient_pts']}pts** · {len(pages)} pages._",
          f"",
          f"Novice-floor = the worker (novice) persona's intuition %. The gate "
          f"(`validate_arc_y_intuition.py`) ratchets each page no-worse-than-baseline AND fails any page below the 50% floor.",
          f"",
          f"| Page | Novice-floor | Back | Jargon | First-paint | Dead+unlabeled | L4 truth |",
          f"|---|---|---|---|---|---|---|"]
    for slug, p in sorted(pages.items(), key=lambda kv: kv[1]["novice_floor"] or 0):
        nf = p["novice_floor"]
        flag = " ⚠️" if (nf is not None and nf < 60) else ""
        md.append(f"| {slug} | **{nf}%**{flag} | {'✓' if p['back'] else '—'} | {p['jargon']} | {p['worker_fp']} | {p['dead_unlbl']} | {'✓' if p['l4'] else '·'} |")
    (ROOT / "intuition_gradient_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"  WROTE intuition_gradient_report.md (human-readable scorecard — Y6 loop-visibility)")


if __name__ == "__main__":
    main()
