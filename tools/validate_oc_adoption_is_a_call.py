#!/usr/bin/env python3
"""validate_oc_adoption_is_a_call.py — loading the concurrency helper is not using it.

WHY THIS EXISTS (W3-LC, 2026-09-09). `oc-helper.js` was written to close PRODUCTION_FIXES #43. Four
pages load it, and the question nothing was asking is whether any of them GUARD their writes. Two did
not: marketplace.html settled a job and cancelled a job filtered on id alone, so a second confirm
re-settled an already-settled request and overwrote settled_at (proven in psql: :53.827 -> :55.047),
and a cancel could land on work a provider had already started. marketplace-admin.html moderated a
listing filtered on id alone, so a seller editing mid-review meant the moderator approved content
they never saw, stamped with their name (proven: the listing ended "seller changed it | published |
by Admin A"). Both are fixed and all four pages now guard; the ratchet holds the line at 0.

WHAT IT CHECKS, AND THE LESSON IT COST. For every root page that loads `oc-helper.js`, at least one
write must be guarded. "Guarded" is a PROPERTY, not a name -- and this gate got that wrong three
times in a row before it got it right, each time reporting a correctly-written page as hollow:

  1. It knew only `updateWithOC` and missed `ocUpdate`, the SECOND helper for the same fix living in
     utils.js:3789 with a different return shape. inventory.html uses it and was called hollow.
  2. It counted helper calls only and missed an INLINE stamp guard. marketplace-seller.html appends
     `.eq('updated_at', _stamp)` by hand and disambiguates zero-rows three ways; its own comment
     explains it did not delegate to ocUpdate because that helper filtered id + stamp only and would
     have dropped `.eq('seller_name', ...)` -- widening who may edit a listing.
  3. It expected a timestamp and missed a TRANSITION guard. A state machine guards the state it is
     legal to LEAVE: `.eq('status','completed')` for settle, `.in('status', SVC_OPEN.slice(0,5))` for
     cancel. Comparing updated_at there would have been the weaker check, since what must not happen
     is settling twice, not saving over an edit.

So it counts all three shapes. A gate that recognises one blessed spelling does not measure adoption,
it measures conformity to itself -- and its failure mode is manufacturing work on code that is
already right. Point 2 also explains why adoption stalled at all: `updateWithOC` filtered on id, while
every real update here is scoped by tenancy too, so adopting it as written traded a concurrency bug
for an authorization one. It now takes an optional trailing `filters` argument.

Deliberately narrow in one respect: it never guesses which pages OUGHT to have concurrency control --
that is a judgement about which rows two people can plausibly edit at once, and a gate that guessed
would produce noise. It only holds a page to the intention the page itself declared by loading the file.

FORWARD-ONLY RATCHET. The ceiling lives in `.oc_adoption_ceiling`, now 0. The gate FAILS if the count
rises, so a page cannot be wired up hollow. `--selftest` runs deterministic cases, no filesystem scan.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CEILING_FILE = REPO / ".oc_adoption_ceiling"

INCLUDE_RE = re.compile(r"""<script[^>]+src\s*=\s*["'](?:\./)?oc-helper\.js["']""", re.I)
# ★THIS PLATFORM HAS TWO CONCURRENCY HELPERS FOR THE SAME FIX, and a gate that knows only one of them
# reports a page that IS guarded as unguarded. PRODUCTION_FIXES #43 produced BOTH `updateWithOC` in
# oc-helper.js and `ocUpdate` in utils.js:3789 - same idea, different return shapes ({error, conflict,
# data} vs {ok, error}). inventory.html adopted `ocUpdate` and guards its edit path properly, with a
# long comment explaining exactly why the stamp moves; the first draft of this gate knew only
# `updateWithOC` and called that page hollow. Recognise both, or the gate manufactures work on a page
# that already did it right. (The duplication itself is worth retiring one day - two helpers for one
# rule is a reason adoption stalls - but a gate is not the place to force that choice.)
CALL_RE = re.compile(r"\b(?:updateWithOC|readAndUpdateWithOC|ocUpdate)\s*\(")
# ★AND THE THIRD READING WAS STILL WRONG, FOR THE SAME REASON ONE LAYER UP: this gate was counting a
# NAME when the thing that matters is a PROPERTY. marketplace-seller.html's listing edit - the costliest
# write on the page - carries a full hand-rolled guard: it holds the row's stamp, appends
# `.eq('updated_at', _stamp)` to the chain, and disambiguates zero-rows between "someone saved first",
# "it stopped being yours" and "RLS refused" instead of confidently naming the wrong one. Its comment
# even states why it did NOT delegate to ocUpdate - that helper filters id + stamp only and this update
# must keep `.eq('seller_name', …)`, so delegating would have widened who may edit a listing. That is
# the same conclusion this gate's own `filters` work reached, written down before I got there.
# A page that compares a stamp before overwriting HAS optimistic concurrency, whatever it calls it.
INLINE_GUARD_RE = re.compile(r"""\.\s*eq\s*\(\s*['"]updated_at['"]""")
# ★AND A STATE MACHINE GUARDS ITS TRANSITION, NOT A TIMESTAMP - the fourth time this gate read a name
# instead of the property. marketplace.html's settle and client-cancel both change `status`, and both
# are now guarded by filtering on the state it is legal to LEAVE: `.eq('status','completed')` and
# `.in('status', SVC_OPEN.slice(0,5))`. That is optimistic concurrency in the form the data actually
# takes - a repeat or a stale decision matches zero rows - and comparing updated_at there would have
# been the weaker check, since what must not happen is settling twice, not saving over an edit.
# Counted only when the chain BOTH sets status and filters on it, so an ordinary status-scoped query
# is never mistaken for a guard.
_UPDATE_CHAIN_RE = re.compile(r"\.\s*update\s*\(.{0,700}?(?:\.select\s*\(|;)", re.S)
_SETS_STATUS_RE = re.compile(r"""status\s*:\s*['"]""")
_FILTERS_STATUS_RE = re.compile(r"""\.\s*(?:eq|in)\s*\(\s*['"]status['"]""")


def _transition_guards(body: str) -> int:
    return sum(
        1 for m in _UPDATE_CHAIN_RE.finditer(body)
        if _SETS_STATUS_RE.search(m.group(0)) and _FILTERS_STATUS_RE.search(m.group(0))
    )
# a write the guard would have wrapped, used only to say how much is unguarded
WRITE_RE = re.compile(r"\.\s*(?:update|upsert)\s*\(")
ALLOW_RE = re.compile(r"oc-adoption-allow:\s*(\S.*)")

BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT_RE = re.compile(r"^\s*//.*$", re.M)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def strip_commentary(src: str) -> str:
    """A page that only MENTIONS updateWithOC in a comment has not called it.

    This matters here more than usual: the pages in question are heavily annotated, and a note
    reading "we should use updateWithOC on this save" is the opposite of evidence that it was done.
    """
    return LINE_COMMENT_RE.sub("", BLOCK_COMMENT_RE.sub(" ", HTML_COMMENT_RE.sub(" ", src)))


def classify(src: str) -> tuple[bool, int, int, str | None]:
    """-> (includes_helper, guarded_saves, write_sites, allow_reason).

    guarded_saves counts BOTH shapes that satisfy the property: a call to one of the platform's
    concurrency helpers, and an inline `.eq('updated_at', stamp)` on an update chain. Counting only
    the helper names reported two correctly-guarded pages as hollow across two successive drafts.
    """
    allow = ALLOW_RE.search(src)
    body = strip_commentary(src)
    guards = len(CALL_RE.findall(body)) + len(INLINE_GUARD_RE.findall(body)) + _transition_guards(body)
    return (
        bool(INCLUDE_RE.search(body)),
        guards,
        len(WRITE_RE.findall(body)),
        allow.group(1).strip() if allow else None,
    )


def read_ceiling() -> int | None:
    try:
        return int(CEILING_FILE.read_text(encoding="utf-8").split("#", 1)[0].strip())
    except (OSError, ValueError):
        return None


def write_ceiling(n: int) -> None:
    CEILING_FILE.write_text(
        f"{n}  # validate_oc_adoption_is_a_call.py forward-only ratchet; lower is better\n",
        encoding="utf-8",
    )


def run(repo: Path) -> int:
    hollow: list[tuple[str, int]] = []
    real: list[tuple[str, int]] = []
    exempt: list[tuple[str, str]] = []

    for page in sorted(repo.glob("*.html")):
        try:
            src = page.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        includes, calls, writes, allow = classify(src)
        if not includes:
            continue
        if calls:
            real.append((page.name, calls))
        elif allow:
            exempt.append((page.name, allow))
        else:
            hollow.append((page.name, writes))

    print(f"oc-adoption: {len(real)} page(s) call the helper · {len(exempt)} exempt · "
          f"{len(hollow)} load it without ever calling it")
    for name, calls in real:
        print(f"  CALLS   {name} ({calls} guarded save(s))")
    for name, reason in exempt:
        print(f"  EXEMPT  {name} -- {reason}")
    for name, writes in hollow:
        print(f"  HOLLOW  {name} loads oc-helper.js, never calls updateWithOC ({writes} write site(s) unguarded)")

    ceiling = read_ceiling()
    count = len(hollow)
    if ceiling is None:
        write_ceiling(count)
        print(f"oc-adoption: ceiling initialised at {count}")
        return 0
    if count > ceiling:
        print(
            f"FAIL oc-adoption: {count} page(s) load oc-helper.js without calling it, ceiling {ceiling}.\n"
            "  Loading the file is not concurrency control. Adoption is a CALL:\n"
            "    const { error, conflict } = await updateWithOC(db, table, id, patch, row.updated_at);\n"
            "    if (conflict) { /* tell the person their copy is stale - do NOT overwrite silently */ }\n"
            "  The row's table needs an updated_at column for the stamp to compare against; without one\n"
            "  the helper cannot be adopted at all and the fix starts with a migration.\n"
            "  If a page genuinely needs no guard, say why:  <!-- oc-adoption-allow: <reason> -->"
        )
        return 1
    if count < ceiling:
        write_ceiling(count)
        print(f"oc-adoption: ratchet lowered {ceiling} -> {count}")
    return 0


def selftest() -> int:
    cases = [
        ("loads the helper and calls it",
         '<script src="oc-helper.js"></script><script>await updateWithOC(db,"t",id,p,s);</script>',
         (True, 1)),
        ("loads the helper and never calls it",
         '<script src="oc-helper.js"></script><script>await db.from("t").update(p);</script>',
         (True, 0)),
        ("does not load the helper at all",
         '<script>await db.from("t").upsert(row);</script>', (False, 0)),
        ("a JS comment mentioning the call is not a call",
         '<script src="oc-helper.js"></script><script>\n// TODO: use updateWithOC( here\n'
         'await db.from("t").update(p);</script>', (True, 0)),
        ("an HTML comment mentioning the call is not a call",
         '<script src="oc-helper.js"></script><!-- updateWithOC( would go here -->'
         '<script>await db.from("t").update(p);</script>', (True, 0)),
        ("a block comment mentioning the call is not a call",
         '<script src="oc-helper.js"></script><script>/* updateWithOC( someday */'
         'await db.from("t").update(p);</script>', (True, 0)),
        ("a commented-OUT include is not an include",
         '<!-- <script src="oc-helper.js"></script> --><script>await db.from("t").update(p);</script>',
         (False, 0)),
        ("a TRANSITION guard counts - sets status AND filters on it (marketplace.html settle)",
         '<script src="oc-helper.js"></script><script>const r = await db.from("service_requests")'
         '.update({ status: "settled", settled_at: n }).eq("id", id).eq("status", "completed").select("id");</script>',
         (True, 1)),
        ("a status-SCOPED read is not a transition guard",
         '<script src="oc-helper.js"></script><script>const r = await db.from("t")'
         '.select("id").eq("status", "draft");await db.from("t").update({ title: x }).eq("id", id);</script>',
         (True, 0)),
        ("an INLINE stamp guard is optimistic concurrency (marketplace-seller.html's listing edit)",
         '<script src="oc-helper.js"></script><script>let q = db.from("marketplace_listings")'
         '.update(p).eq("id", id).eq("seller_name", W); if (_stamp) q = q.eq("updated_at", _stamp);</script>',
         (True, 1)),
        ("the platform's OTHER helper counts as adoption (utils.js ocUpdate, inventory.html)",
         '<script src="oc-helper.js"></script><script>const r = await ocUpdate(db,"inventory_items",id,p,prev.updated_at);</script>',
         (True, 1)),
        ("./ prefixed include still counts",
         '<script src="./oc-helper.js"></script><script>updateWithOC(db,"t",1,{},s)</script>',
         (True, 1)),
    ]
    bad = 0
    for label, src, (want_inc, want_calls) in cases:
        inc, calls, _writes, _allow = classify(src)
        if (inc, calls) != (want_inc, want_calls):
            print(f"  FAIL {label}: include={inc} (want {want_inc}) calls={calls} (want {want_calls})")
            bad += 1
        else:
            print(f"  ok   {label}")

    _i, _c, _w, reason = classify('<!-- oc-adoption-allow: read-only console -->'
                                  '<script src="oc-helper.js"></script>')
    if not reason:
        print("  FAIL exemption marker not read")
        bad += 1
    else:
        print("  ok   exemption marker read with its reason")

    print("selftest:", "PASS" if not bad else f"{bad} FAILED")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(run(REPO))
