"""
Arc Y - THE INTUITION GRADIENT : forward-only RATCHET gate
==========================================================
The deterministic ratchet for Arc Y. The live harness
(tools/intuition_gradient_harness.mjs) measures every feature page on the 5
intuitiveness lenses for 3 personas and banks intuition_gradient_report.json;
freeze_intuition_baseline.py freezes intuition_gradient_baseline.json. This gate
asserts NO page regresses below its frozen floor — intuitiveness can only ratchet
forward (same discipline as Arc V/W visual/effort ratchets).

Per page, a REGRESSION (RC1) is any of:
  - novice_floor drops more than the jitter band (live % wobble)            [worker intuition %]
  - first-paint interactive count GROWS beyond the jitter band              [L3 overwhelm ceiling]
  - the in-app back affordance flips present -> absent                       [L5, deterministic]
  - jargon-without-gloss count GROWS                                        [L1, deterministic]
  - dead-links + unlabeled-inputs GROWS                                     [L6, deterministic]
  - a displayed value that matched DB truth now mismatches (l4 1 -> 0)      [L4, deterministic]

Hard signals (back/jargon/dead+unlbl/l4) have NO tolerance — they're computed
deterministically from the DOM/DB, not subject to render-timing jitter. Only the
% and fp-count signals get a small jitter band (set in the baseline).

This is teeth-proven at build time: corrupting the banked report (drop a back
affordance / add jargon / grow fp) drives RC1; the clean report drives RC0.

Usage:  python validate_arc_y_intuition.py
Output: arc_y_intuition_report.json   (RC1 on any regression)
"""
import io, sys, json
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "intuition_gradient_baseline.json"
REPORT   = ROOT / "intuition_gradient_report.json"


def _l4_ok(card):
    ok = 0
    for sess in ("worker", "supervisor"):
        chk = (card.get(sess) or {}).get("l4") or {}
        sh, tr = chk.get("shown"), chk.get("truth")
        if sh is not None and tr is not None and sh == tr:
            ok = 1
    return ok


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nArc Y - THE INTUITION GRADIENT : forward-only ratchet"))
    print("=" * 72)

    if not BASELINE.exists():
        print(f"  ERROR: {BASELINE.name} not found — freeze it: python tools/freeze_intuition_baseline.py")
        sys.exit(1)
    if not REPORT.exists():
        print(f"  ERROR: {REPORT.name} not found — run: node tools/intuition_gradient_harness.mjs --all")
        sys.exit(1)

    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    rep  = json.loads(REPORT.read_text(encoding="utf-8"))
    jitter = base.get("jitter", {"floor_pts": 3, "fp_grow": 3})
    bpages = base.get("pages", {})

    # index the current report by page
    cur = {}
    for c in rep.get("cards", []):
        if c.get("novice_floor") is None:
            continue
        w = c.get("worker") or {}
        s = c.get("supervisor") or {}
        cur[c["page"]] = {
            "novice_floor": c.get("novice_floor"),
            "worker_fp": w.get("firstPaintInteractive"),
            "sup_fp": s.get("firstPaintInteractive"),
            "back": bool(w.get("backAffordance") or s.get("backAffordance")),
            "jargon": len(w.get("jargonNoGloss") or []),
            "dead_unlbl": (w.get("deadLinks") or 0) + (w.get("unlabeledInputs") or 0),
            "l4": _l4_ok(c),
        }

    regressions = []
    missing = []
    checked = 0
    for slug, b in bpages.items():
        c = cur.get(slug)
        if not c:
            missing.append(slug)
            continue
        checked += 1
        # % floor (jitter band)
        if c["novice_floor"] is not None and b["novice_floor"] is not None \
           and c["novice_floor"] < b["novice_floor"] - jitter["floor_pts"]:
            regressions.append(f"{slug}: novice-floor {b['novice_floor']}% -> {c['novice_floor']}% (drop > {jitter['floor_pts']}pt band)")
        # overwhelm ceiling (jitter band) — worker session is the novice bar
        if c["worker_fp"] is not None and b["worker_fp"] is not None \
           and c["worker_fp"] > b["worker_fp"] + jitter["fp_grow"]:
            regressions.append(f"{slug}: first-paint interactives {b['worker_fp']} -> {c['worker_fp']} (grew > {jitter['fp_grow']}; overwhelm)")
        # back affordance — hard
        if b["back"] and not c["back"]:
            regressions.append(f"{slug}: in-app BACK affordance was present, now absent (L5 regression)")
        # jargon — hard
        if c["jargon"] > b["jargon"]:
            regressions.append(f"{slug}: jargon-without-gloss {b['jargon']} -> {c['jargon']} (L1 regression)")
        # dead links + unlabeled inputs — hard
        if c["dead_unlbl"] > b["dead_unlbl"]:
            regressions.append(f"{slug}: dead-links+unlabeled {b['dead_unlbl']} -> {c['dead_unlbl']} (L6 regression)")
        # l4 truthful loop went silent — hard
        if b["l4"] == 1 and c["l4"] == 0:
            regressions.append(f"{slug}: displayed value matched DB truth, now mismatches (L4 cross-surface regression)")

    # Y6 ABSOLUTE FLOOR — the ratchet's floor half: EVERY scored page (including a
    # brand-NEW page not in the baseline) must clear the novice-intuition minimum, so
    # a new surface can't ship below the bar Ian set ("intuitive to ALL users"). The
    # per-page regression checks above protect existing pages; this protects new ones.
    FLOOR_MIN = 50
    for slug, c in cur.items():
        nf = c.get("novice_floor")
        if nf is not None and nf < FLOOR_MIN:
            tag = "" if slug in bpages else " (NEW page — not yet baselined)"
            regressions.append(f"{slug}: novice-floor {nf}% is below the {FLOOR_MIN}% novice-intuition floor{tag} — a field worker can't comprehend it; fix before shipping")

    n_fail = len(regressions)
    if n_fail == 0:
        print(f"\033[92m  RATCHET HELD — {checked} pages, no intuitiveness regression below the frozen floor.\033[0m")
        if missing:
            print(f"  ({len(missing)} baselined pages absent from this report run: {', '.join(missing[:6])}{'...' if len(missing)>6 else ''})")
    else:
        print(f"\033[91m  {n_fail} REGRESSION(S):\033[0m")
        for r in regressions:
            print(f"    - {r}")

    report = {
        "validator": "arc_y_intuition",
        "arc": "Y",
        "pages_checked": checked,
        "pages_missing_from_run": missing,
        "regressions": regressions,
        "failed": n_fail,
        "avg_novice_floor_pct": rep.get("avg_novice_floor_pct"),
        "avg_gradient_pts": rep.get("avg_gradient_pts"),
    }
    (ROOT / "arc_y_intuition_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
