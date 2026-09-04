#!/usr/bin/env python3
"""unconfirmed-write-is-not-a-failure - an empty RETURNING is not a failed write (2026-08-27, T176).

supabase-js resolves `.insert(...).select(...)` with `{ data: [], error: null }` when the INSERT
SUCCEEDED and the RETURNING read was refused - RLS gates SELECT separately from INSERT. So a branch
on `if (!data || !data.length)` has learned exactly one thing: the write is UNCONFIRMED. It has not
learned that it failed.

Eighteen sites branch this way and eight told the user their work was lost. Two of those were
actively dangerous, because the advice was "try again":

  - the service hail: re-hailing broadcasts a SECOND job to every nearby provider for work the
    client wants done once;
  - provider registration: a second provider profile for the same hive.

Both are fixed, and each turned out to be TWO sites rather than one - the hail has a catalog path
and a custom-scope path, registration has a hive path and a freelancer path. A sweep that
deduplicates by message hides twins; the editor refusing an ambiguous match is what exposed them.

*THE PLATFORM ALREADY KNEW THE RIGHT SHAPE, which is what makes the eight a drift rather than a
gap: "Couldn't update - the job may have moved on", "No change saved: that top-up was already
decided", "This project changed since you opened it, reloading". Those admit uncertainty and point
somewhere useful.

A RATCHET with a FULLY TRIAGED baseline. Each survivor was checked against the database, not
waved through: an idempotent UPDATE, or an INSERT the schema makes un-duplicatable. Where a retry
cannot cost anything, "try again" is honest advice even though "didn't save" is imprecise - a
low-severity wording item, not a hazard. A baseline holding UNTRIAGED entries would launder
unknowns as accepted, which is the failure na-premise-holds was built to prevent.

Self-test: `--selftest`.
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

WRITE = re.compile(r"\.(?:insert|update|upsert)\(", re.S)
NO_ROWS = re.compile(
    r"if\s*\(\s*!\s*data\b[^)]{0,60}\)\s*\{?\s*(?:\{\s*)?showToast\(\s*"
    r"(?P<q>['\"])(?P<msg>(?:[^'\"\\]|\\.){0,160}?)(?P=q)", re.S)

CLAIMS_FAILURE = re.compile(r"didn'?t save|could ?n'?t|failed|not saved|try again", re.I)
ADMITS = re.compile(r"may have|might have|could not confirm|couldn'?t confirm|unconfirmed|"
                    r"already (decided|rated|filed)|changed since|moved on|reloading", re.I)

# message -> why asserting failure here costs nothing (each checked against the schema 2026-08-27)
BASELINE = {
    "Not saved. Are you signed in as the platform admin?":
        "voucher INSERT, and service_vouchers_code_key is UNIQUE on code - a retry is refused, never duplicated",
    "Couldn't change availability - refresh and try again":
        "an idempotent UPDATE of the provider's own availability",
    "Couldn't cancel - refresh and try again":
        "an idempotent UPDATE of a request's status",
    "Couldn't save the alert subscription. Try again.":
        "an UPSERT with onConflict:endpoint - retrying writes the same row",
    "Couldn't update. Refresh and try again.":
        "service_requests.update(...).eq(id) - idempotent",
    "Rating didn't save. Try again.":
        "marketplace_reviews_one_per_request_direction is UNIQUE - a second rating is refused by the database",
}


def scan(src: str, label: str = "source") -> list:
    """Find every `!data` branch that follows a returning write, and judge its message.

    ★ANCHORED BACKWARD FROM THE BRANCH, not forward from the write - and the first version was
    anchored the other way, with a fixed 900-character forward window. It MISSED a live site: the
    top-up in marketplace-seller has a seven-line comment between its .insert() and the branch, so
    the branch fell outside the window and a money message reading "Couldn't file the top-up. Try
    again." went unreported. A fixed character window is brittle by construction - the same class
    that produced three false readings in this repo's gates before it produced this false silence.
    Starting from the branch and looking back for the write it belongs to has no such horizon.
    """
    out = []
    for c in NO_ROWS.finditer(src):
        msg = re.sub(r"\\(.)", r"\1", c.group("msg")).strip()
        if len(msg) < 6:
            continue
        if not CLAIMS_FAILURE.search(msg) or ADMITS.search(msg):
            continue
        if msg in BASELINE:
            continue
        # the branch must belong to a write that asked for its rows back
        before = src[max(0, c.start() - 2500):c.start()]
        sel = before.rfind(".select(")
        if sel < 0 or not WRITE.search(before[max(0, sel - 600):sel]):
            continue
        line = src[:c.start()].count("\n") + 1
        out.append(f'{label}:{line} tells the user the write failed when it is only '
                   f'UNCONFIRMED - "{msg[:70]}"')
    return out


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    bad = ("db.from('t').insert({a:1}).select('id');"
           "if (!data || !data.length) { showToast('Request didn\\'t save - please try again', 'error'); return; }")
    chk("asserting failure on an empty return fails", len(scan(bad)), 1)

    good = ("db.from('t').insert({a:1}).select('id');"
            "if (!data || !data.length) { showToast('It may have been sent - we could not confirm it.', 'error'); return; }")
    chk("admitting the uncertainty passes", len(scan(good)), 0)

    moved = ("db.from('t').update({a:1}).select('id');"
             "if (!data || !data.length) { showToast('Couldn\\'t update - the job may have moved on.', 'error'); }")
    chk("the platform's existing idiom passes", len(scan(moved)), 0)

    based = ("db.from('t').update({a:1}).select('id');"
             "if (!data || !data.length) { showToast('Couldn\\'t cancel - refresh and try again', 'error'); }")
    chk("a triaged baseline entry is allowed", len(scan(based)), 0)

    noread = "db.from('t').insert({a:1});"
    chk("a write with no RETURNING branch is out of scope", len(scan(noread)), 0)

    live = []
    for f in sorted(glob.glob(str(ROOT / "*.html"))):
        n = Path(f).name
        if n.startswith("_") or "backup" in n or "-test" in n:
            continue
        live += scan(io.open(f, encoding="utf-8", errors="replace").read(), n)
    chk("no NEW site asserts failure on an unconfirmed write", live, [])
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    problems, sites = [], 0
    for f in sorted(glob.glob(str(ROOT / "*.html"))):
        n = Path(f).name
        if n.startswith("_") or "backup" in n or "-test" in n:
            continue
        src = io.open(f, encoding="utf-8", errors="replace").read()
        sites += len(WRITE.findall(src))
        problems += scan(src, n)
    print("an empty RETURNING is an unconfirmed write, not a failed one")
    print(f"  write sites: {sites}  ·  triaged baseline: {len(BASELINE)}  ·  new: {len(problems)}")
    if not problems:
        print("\n  PASS - no site tells a user their work was lost when it may have landed.")
        return 0
    print("\n  FAIL - these assert a failure the code cannot know about:")
    for p in problems:
        print(f"    {p}")
    print("\n  Say what is known ('may have been sent - we could not confirm it') and send them to\n"
          "  the list, or baseline it here once you have checked a retry cannot duplicate anything.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
