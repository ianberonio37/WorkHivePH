"""
prove_calc_staging_not_stale.py — a staged page that would REVERT work already fixed on the live page.
======================================================================================================
`tools/build_calc_pages.py` writes to `seo_assets/calc_pages_staging/<slug>/index.html` and says so in
its own header: "STAGING, not the site root. Nothing ships until Ian reviews + moves it."

MEASURED 2026-09-16: all 60 staged pages have a served twin at `tools/<slug>/`, NOT ONE is
byte-identical, NOT ONE is new, and every one still carries constructs the live pages have already had
fixed — 180 sub-12px declarations, 120 thick callout borders, 60 copies of the 10.4px kicker and 60 of
the Windows-only monospace stack. So "move staging to the site root" reads like shipping new work and
would in fact revert those 420 declarations across 60 public pages, silently, because a file copy
leaves no diff to review. That is the loaded-trap shape: a path that looks like the normal next step
and is destructive because the world moved under it while it sat there.

★THE FIRST VERSION OF THIS GATE ASKED THE WRONG QUESTION, and the mistake is worth keeping. It compared
MTIMES — "is the staged file older than the live one?" — which is trivially defeated: re-running the
generator, or any touch at all, makes staging newer while its CONTENT is still the old template, and
the gate would go green with the trap fully intact. "Which file is older" was never the question.
"What would promoting this file UNDO" is, and that is answerable from the bytes.

So the gate asks the SWEEP TOOLS what each staged page would reintroduce — `fix_type_floor_sweep`,
`fix_public_funnel_kicker_floor`, `fix_callout_accent_border`, `fix_mono_stack_unify` — rather than
re-implementing their patterns, which would drift from the fixers the moment either changed. A staged
page passes when it would undo nothing, whatever its timestamp says. The self-test asserts exactly
that: it flags a regressing page, leaves a diverged-but-clean page alone, and then touches the
regressing page's timestamp to prove a refresh cannot clear it.

This promotes, moves and deletes nothing — promotion is Ian's gate. It refuses to let the trap stay
invisible. Two ways to clear it, neither of them a touch of the timestamps: fix the GENERATOR so a
rebuild is born correct, or delete the stale copies now their content has landed live.

Usage:  python tools/prove_calc_staging_not_stale.py [--self-test]
"""
from __future__ import annotations
import hashlib, io, sys
_ = sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from datetime import datetime
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
STAGING = ROOT / "seo_assets" / "calc_pages_staging"


def _regressions(text: str):
    """How many already-fixed constructs this staged page would REINTRODUCE if promoted.

    ★MTIME WAS THE WRONG QUESTION (2026-09-16). The first version compared timestamps, and a timestamp
    is trivially defeated: re-running the generator, or any touch, makes a staged page NEWER than live
    while its CONTENT is still the old template - so the gate would go green with the trap intact. The
    honest question is not "which file is older" but "what would promoting this file undo", and that is
    answerable from the bytes. Each sweep tool already knows its own construct, so the gate asks them
    rather than re-implementing the patterns and drifting from the fixers.
    """
    n = {}
    try:
        import fix_type_floor_sweep as TF, fix_public_funnel_kicker_floor as KF
        import fix_callout_accent_border as CB, fix_mono_stack_unify as MS
    except Exception:
        return n
    _, lifted, _ = TF.patch(text)
    if sum(lifted.values()): n["sub-12px type"] = sum(lifted.values())
    _, k = KF.patch(text)
    if sum(k.values()): n["10.4px kicker"] = sum(k.values())
    _, c = CB.patch(text)
    if sum(c.values()): n["thick callout border"] = sum(c.values())
    m = text.count(MS.OLD)
    if m: n["Windows-only mono stack"] = m


    return n


def classify():
    """-> (stale, identical, clean, orphan); stale entries carry what promoting them would undo."""
    stale, identical, clean, orphan = [], 0, 0, 0
    if not STAGING.exists():
        return stale, identical, clean, orphan
    for p in sorted(STAGING.glob("*/index.html")):
        q = ROOT / "tools" / p.parent.name / "index.html"
        if not q.exists():
            orphan += 1
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() == hashlib.sha256(q.read_bytes()).hexdigest():
            identical += 1
            continue
        # ★A CONSTRUCT PRESENT IN *BOTH* IS NOT A REGRESSION (2026-09-16, second correction to this
        # gate). The first content-based version counted what STAGING carries, which over-reports: the
        # live calculator pages still carry the thick callout border themselves, because that sweep is
        # queued behind a running walk. Promoting a construct the live page already has undoes nothing.
        # The regression set is the DIFFERENCE - what staging would bring that live has since lost.
        staged_regs = _regressions(p.read_text(encoding="utf-8", errors="replace"))
        live_regs = _regressions(q.read_text(encoding="utf-8", errors="replace"))
        regs = {k: v for k, v in staged_regs.items() if v > live_regs.get(k, 0)}
        if regs:
            stale.append((p.parent.name, p.stat().st_mtime, q.stat().st_mtime, regs))
        else:
            clean += 1
    return stale, identical, clean, orphan


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    stale, identical, clean, orphan = classify()
    total = len(stale) + identical + clean + orphan
    print("calc staging: %d staged page(s) — %d identical to live, %d diverged but carrying no known "
          "regression, %d genuinely new, %d that would REVERT fixed work"
          % (total, identical, clean, orphan, len(stale)))
    if not stale:
        print("PASS calc-staging-not-stale: promoting this directory would undo nothing that has been fixed.")
        return 0

    rolled = {}
    for _, _, _, regs in stale:
        for k, v in regs.items():
            rolled[k] = rolled.get(k, 0) + v
    print("FAIL calc-staging-not-stale: %d staged page(s) would REINTRODUCE constructs the live pages"
          % len(stale))
    print("     have already had fixed. Promotion is a file copy and leaves no diff to review, so this")
    print("     would revert silently. What would come back:")
    for k, v in sorted(rolled.items(), key=lambda x: -x[1]):
        print("       %-26s %d declaration(s)" % (k, v))
    print("     Clearing it is Ian's call, and neither way is a touch of the timestamps: fix the")
    print("     GENERATOR (tools/build_calc_pages.py) so a rebuild is born correct, or delete the")
    print("     stale copies now their content has landed live.")
    for slug, sm, qm, regs in stale[:5]:
        print("       %-40s staged %s · %s" % (
            slug, datetime.fromtimestamp(sm).strftime("%Y-%m-%d"),
            ", ".join("%s x%d" % (k, v) for k, v in regs.items())))
    if len(stale) > 5:
        print("       ... and %d more" % (len(stale) - 5))
    return 1


def self_test() -> int:
    """Prove the classifier on a temporary tree, touching nothing real."""
    import tempfile, os, shutil
    ok = True
    tmp = Path(tempfile.mkdtemp())
    global ROOT, STAGING
    real_root, real_staging = ROOT, STAGING
    try:
        ROOT = tmp
        STAGING = tmp / "seo_assets" / "calc_pages_staging"
        # one page that WOULD reintroduce a fixed construct (a 9px declaration), and one that would not
        REGRESSING = "<style>.a { font-size: 9px; }</style>"
        CLEAN = "<style>.a { font-size: 12px; }</style>"
        for slug, staged, served in (("regressing", REGRESSING, CLEAN),
                                     ("diverged-but-clean", CLEAN + "<!-- x -->", CLEAN),
                                     ("same-one", CLEAN, CLEAN)):
            (STAGING / slug).mkdir(parents=True)
            (tmp / "tools" / slug).mkdir(parents=True)
            (STAGING / slug / "index.html").write_text(staged, encoding="utf-8")
            (tmp / "tools" / slug / "index.html").write_text(served, encoding="utf-8")
        (STAGING / "brand-new").mkdir(parents=True)
        (STAGING / "brand-new" / "index.html").write_text(CLEAN, encoding="utf-8")

        stale, identical, clean, orphan = classify()
        if [x[0] for x in stale] != ["regressing"]:
            print("FAIL: expected exactly 'regressing' to be flagged, got %s" % [x[0] for x in stale])
            ok = False
        if identical != 1:
            print("FAIL: expected 1 byte-identical, got %d" % identical); ok = False
        if clean != 1:
            print("FAIL: a page that diverged WITHOUT reintroducing anything must pass, got %d" % clean)
            ok = False
        if orphan != 1:
            print("FAIL: a staged page with no served twin must pass (it is the genuine case)"); ok = False

        # ★THE POINT OF THE REWRITE: a NEWER timestamp must not clear the finding. The first, mtime-based
        # version of this gate went green right here - which is how a "refresh" could have hidden the trap
        # while every staged page still carried the old template.
        if stale:
            os.utime(STAGING / "regressing" / "index.html", None)   # make staging the newest file
            stale2, _, _, _ = classify()
            if [x[0] for x in stale2] != ["regressing"]:
                print("FAIL: touching the timestamp cleared the finding - the gate is still mtime-based")
                ok = False
    finally:
        ROOT, STAGING = real_root, real_staging
        shutil.rmtree(tmp, ignore_errors=True)
    print("self-test: %s" % ("PASS - flags only a page that would reintroduce a fixed construct, and a "
                             "newer timestamp does not clear it" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
