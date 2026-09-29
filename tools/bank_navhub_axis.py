"""
bank_navhub_axis.py — bank a whole nav-hub axis from one receipt, and REFUSE a receipt that straddles edits.
============================================================================================================
`prove_w4_navhub.mjs --axis "<axis>"` walks every host and writes one receipt. Banking those rows is
30 near-identical calls to bank_mcp_navhub_walk.py, which is a loop, not a decision.

THE GUARD IS THE POINT, and it comes from a mistake made on 2026-09-16. A 30-host walk ran for 40
minutes while the type-floor sweep rewrote 143 served pages underneath it. It passed 30/30 - and it
was still not bankable, because each host was measured against whichever version of the platform
happened to exist when its turn came. A green receipt that straddles an edit wave proves something
about a mixture of two builds and nothing about either.

Nothing in the pipeline could see that: the receipt records when it was GENERATED, the rows record
that they are green, and no check compared the two against the files. So this does:

    every served page's mtime  <  the walk's START,   or the bank is REFUSED.

That is the same shape as the SW shell gate ("no precached file is newer than sw.js"), applied to
evidence instead of to a cache. The comparison point is the walk's START and not its `generated`
stamp, which is written when the walk ENDS: a file edited at minute 20 of a 40-minute walk
invalidates every host after it while still being older than `generated`, so comparing against the
end is the very hole this exists to close. `prove_w4_navhub.mjs` now stamps `startedAt` in the
receipt, so the comparison uses the real start; `--started-at` overrides it, and a receipt written
before that stamp existed falls back to `generated - --window` (75 minutes, comfortably longer than
an observed 40-minute run).

Usage:
  python tools/bank_navhub_axis.py --axis "phone-390 en" [--dry-run] [--receipt <path>]
                                   [--started-at <ISO>] [--window <minutes>]
  --dry-run   print what would be banked, write nothing
"""
from __future__ import annotations
import argparse, io, json, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from served_page_set import served_pages as _served, shared_chrome as _chrome


def build_under_test(receipt: dict):
    """The files this walk's result actually depends on: the pages it LOADED, plus the shared chrome.

    ★SCOPED BY THE RECEIPT, NOT BY THE WHOLE TREE (2026-09-16). The first version compared every
    served page - 157 of them - against the walk's start. That is over-broad and it has a cost: it
    blocks work the walk cannot possibly be affected by. Measured on this axis's own receipt, the walk
    loads exactly 30 root/app pages and ZERO learn or calculator pages, so an edit to a calculator
    page cannot change what it measured. Holding 120 queued border fixes hostage to that was caution
    with no evidence behind it.

    The scope comes from the receipt's own `steps[].page` records - what the walk SAYS it loaded -
    rather than from an assumption about what a nav-hub walk covers. Shared chrome is always in scope
    because every walked page loads it; that list is derived from sw.js's SHELL_FILES (see
    served_page_set), which is how `wh-icons.css` stopped being missing from it.

    A receipt with no step records falls back to the whole served set, because a walk that cannot say
    what it read cannot be narrowed safely.
    """
    walked = set()
    for r in receipt.get("results", []):
        for st in r.get("steps", []):
            pg = st.get("page")
            if pg:
                walked.add(pg.lstrip("/"))
    if not walked:
        return _served(ROOT) + _chrome(ROOT), "every served page (the receipt records no steps)"
    out = [ROOT / w for w in sorted(walked)]
    out = [q for q in out if q.is_file()] + _chrome(ROOT)
    return out, "%d page(s) this walk loaded + %d shared-chrome file(s)" % (len(walked), len(_chrome(ROOT)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--axis", required=True)
    ap.add_argument("--receipt")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--started-at", help="the walk's real start (ISO); otherwise generated - --window")
    ap.add_argument("--window", type=int, default=75,
                    help="minutes to subtract from `generated` to approximate the walk's start (default 75, "
                         "comfortably longer than an observed 40-minute 30-host run)")
    a = ap.parse_args()

    slug = a.axis.replace(" ", "-")
    rp = Path(a.receipt) if a.receipt else ROOT / ".tmp" / ("full_journeys_w4navhub_%s.json" % slug)
    if not rp.exists():
        print("no receipt at %s - run: node tools/prove_w4_navhub.mjs --axis \"%s\"" % (rp, a.axis))
        return 1

    d = json.loads(rp.read_text(encoding="utf-8"))
    gen = d.get("generated")
    walked, bad = d.get("walked"), d.get("bad")
    print("receipt %s\n  axis %s · walked %s · bad %s · generated %s" % (rp.name, d.get("axis"), walked, bad, gen))

    if d.get("axis") != a.axis:
        print("REFUSED: the receipt's axis is %r, not %r." % (d.get("axis"), a.axis)); return 1
    if bad:
        print("REFUSED: %d host(s) did not hold. Fix them and re-walk." % bad); return 1

    # ── THE STRADDLE GUARD ───────────────────────────────────────────────────────────────────────
    gen_dt = datetime.fromisoformat(gen.replace("Z", "+00:00")) if gen else None
    if gen_dt is None:
        print("REFUSED: the receipt carries no `generated` timestamp, so it cannot be dated against the build.")
        return 1

    # ★`generated` IS STAMPED WHEN THE WALK ENDS, NOT WHEN IT STARTS - and the first version of this
    # guard compared against it, which is the very hole it exists to close. A 30-host walk takes ~40
    # minutes; a file edited at minute 20 invalidates every host after it and is still OLDER than
    # `generated`, so it would have passed. The receipt cannot say which hosts ran when, so the
    # comparison point is the walk's START, approximated conservatively as `generated - WINDOW`.
    # The prover now stamps `startedAt`, so that branch is preferred; the window is the fallback for
    # receipts written before the stamp existed.
    if a.started_at:
        start_dt = datetime.fromisoformat(a.started_at.replace("Z", "+00:00"))
        basis = "--started-at"
    elif d.get("startedAt"):
        # prove_w4_navhub.mjs stamps this from 2026-09-16 on, so the guard compares against the real
        # start rather than approximating it.
        start_dt = datetime.fromisoformat(str(d["startedAt"]).replace("Z", "+00:00"))
        basis = "the receipt's own startedAt"
    else:
        start_dt = gen_dt - timedelta(minutes=a.window)
        basis = "generated - %d min (conservative: the walk's start is not recorded)" % a.window
    print("  comparison point: %s  [%s]" % (start_dt.isoformat(timespec="seconds"), basis))

    scope, scope_desc = build_under_test(d)
    print("  scope: %s" % scope_desc)
    newer = []
    for p in scope:
        mt = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        if mt > start_dt:
            newer.append((p.relative_to(ROOT).as_posix(), mt))
    if newer:
        newer.sort(key=lambda x: -x[1].timestamp())
        print("REFUSED: %d file(s) changed AFTER this walk started, so the receipt straddles an edit wave\n"
              "         and describes a mixture of two builds. Re-walk the axis." % len(newer))
        for n, mt in newer[:6]:
            print("           %-44s %s" % (n, mt.isoformat(timespec="seconds")))
        if len(newer) > 6:
            print("           ... and %d more" % (len(newer) - 6))
        return 1
    print("  straddle guard: PASS - no served page or shared-chrome file is newer than the walk's start.")

    results = d.get("results") or []
    ok = [r for r in results if r.get("ok") and not r.get("unbuilt")]
    print("  bankable rows: %d of %d" % (len(ok), len(results)))

    banked, failed = 0, []
    for r in ok:
        cast = (r.get("cast") or "").split(" (")[0]
        cmd = [sys.executable, str(ROOT / "tools" / "bank_mcp_navhub_walk.py"),
               "--id", r["id"], "--axis", a.axis, "--cast", cast]
        if a.dry_run:
            cmd.append("--dry-run")
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode:
            failed.append((r["id"], (p.stdout or "") + (p.stderr or "")))
        else:
            banked += 1
    print("\n%s %d row(s)%s" % ("WOULD bank" if a.dry_run else "banked", banked,
                                ("; %d FAILED" % len(failed)) if failed else ""))
    for i, msg in failed[:10]:
        # THE END OF A TRACEBACK IS THE PART THAT SAYS WHAT HAPPENED. This used to print the first
        # 200 characters with the newlines stripped, which for a Python failure is the child's
        # success chatter followed by the words "Traceback (most recent call last): File" and
        # nothing else - visible and undiagnosable at once (measured 2026-09-16, 30 rows).
        tail = [ln for ln in (msg or "").strip().splitlines() if ln.strip()][-4:]
        print("   %s FAILED:" % i)
        for ln in tail:
            print("       %s" % ln.strip()[:200])
    if len(failed) > 10:
        print("   ... and %d more failure(s) not shown" % (len(failed) - 10))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
