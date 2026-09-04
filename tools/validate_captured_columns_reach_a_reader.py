#!/usr/bin/env python3
"""captured-columns-reach-a-reader - a column written for a person must reach one (2026-08-27, T15).

logbook captured loto_applied, permit_reference, readings_json and failure_consequence on its form,
stored them on the row, restored them into the EDIT FORM when an entry was edited, and rendered them
to a reader NOWHERE. 1,767 of 3,811 entries carried equipment readings nobody could see.

The phantom-column auditor cannot catch this: it asks whether a column has a READ CONSUMER, and a
`.select('loto_applied')` satisfies it. SELECTED IS NOT RENDERED - which is the whole finding.

Asked platform-wide over 121 written columns it returned 9, and project_roles.assigned_by was a
real one (36 of 36 rows record who assigned a project role; the pill showed the name alone, so
"who put me on this?" had no answer). It is fixed, and this gate keeps the rest honest.

A RATCHET, not a cliff. Every remaining entry is BASELINED WITH ITS VERDICT below, because the
triage is the valuable part and re-deriving it costs another hour. Of the original 9:
  - THREE ARE FIXED and deliberately NOT in the baseline, so a regression would fail this gate:
    assigned_by (the role pill names who assigned it), variance_reason and provider_type;
  - three are NOT defects (two timestamps whose fact the rendered status already carries; a total
    the page already shows as its two parts);
  - two are unused rather than withheld - MEASURED at 0 rows, so nothing is being hidden;
  - one is a raw auth uid, which showing would trade this defect for the no-raw-internals one.
A NEW name appearing here means a column was just built for a reader who cannot see it. That fails.

*A FIXED ENTRY LEAVES THE BASELINE. Leaving it in would let the regression pass silently, which is
how a ratchet loosens ([[feedback_gates_that_measure_prose_and_ratchets_that_loosen]]).

*SCOPE IS PLATFORM-WIDE ON PURPOSE. Scoped per-page, this reported ~30 false candidates: actor,
target_id, target_name and target_type topped nearly every list, because pages WRITE audit rows and
the AUDIT-LOG page renders them. A column written on page A and read on page B is normal.

*CREDENTIAL COLUMNS ARE EXCLUDED OUTRIGHT (key_hash, p256dh, auth uids, tokens). Not rendering
those is the security property; flagging them would invert it into a defect.

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

# Structural columns: an id or a timestamp the ORM manages is not written "for a reader".
SKIP_KEYS = {"id", "created_at", "updated_at", "hive_id", "user_id", "worker_id", "author_id"}
# Secrets and transport internals: their absence from the glass is the point.
NEVER_RENDER = {"key_hash", "p256dh", "auth", "endpoint", "user_agent", "payer_auth_uid",
                "token", "secret", "password", "signature", "ip_address"}

# name -> why it is allowed to be unrendered today (triaged 2026-08-27)
BASELINE = {
    # variance_reason was here and is FIXED: the provider's finished-job card now reports the
    # amount, the method, the reference and the payer's reason. Left out of the baseline on
    # purpose - if it ever stops reaching a reader again, this gate should say so.
    "confirmed_by":    "not a defect - a raw auth uid; the payment it belongs to is rendered now, and showing a UID would be the no-raw-internals defect",
    "settled_at":      "not a defect - the rendered status 'settled' carries the fact; this is its timestamp",
    "cancelled_at":    "not a defect - the rendered status cancelled_by_client/provider carries the fact",
    "rows_attempted":  "not a defect - the import history renders rows_written and rows_failed, whose sum this is",
    "live_location":   "unused, not withheld - MEASURED 0 of 7 providers carry one; the geolocation write exists but has never populated a row, so nothing is being hidden from a client",
    # provider_type was here and is FIXED: the quote card now says "Hive team" or "Freelancer" at
    # the moment a buyer chooses. Removed from the baseline rather than left in it, because a
    # fixed entry that stays baselined lets the REGRESSION pass silently - that is how a ratchet
    # loosens ([[feedback_gates_that_measure_prose_and_ratchets_that_loosen]]).
    "acted_by":        "unused, not withheld - 4 staging recommendations exist, 0 have been acted on",
}

PAYLOAD = re.compile(r"\.(insert|update|upsert)\s*\(\s*(\{.*?\})", re.S)
KEY = re.compile(r"([a-z][a-z0-9_]{2,})\s*:", re.I)
SELECT = re.compile(r"\.select\s*\(\s*['\"`]([^'\"`]*)['\"`]", re.S)
FORM_RESTORE = re.compile(r"\.(value|checked)\s*=")


def sweep(srcs: dict, writer_pages=None):
    """Columns written by some PAGE and rendered by no page and no shared script.

    ★WRITERS AND RENDERERS ARE NOT THE SAME SET, and conflating them cost a wrong answer. The
    shared scripts are included so a column rendered by utils.js counts as reached - but when they
    were also treated as WRITERS, ten AI-telemetry columns written by shared JS (response_time_ms,
    model_confidence, question_category, answer_quality_rating...) arrived as candidates. Telemetry
    is written for a machine, not a reader, and this gate is about columns built FOR A PERSON. So
    writers come from the pages; renderers are everything.
    """
    writers, spans = {}, {}
    for p, src in srcs.items():
        pay, keys = [], set()
        for m in PAYLOAD.finditer(src):
            body = m.group(2)[:4000]
            pay.append((m.start(2), m.start(2) + len(body)))
            for k in KEY.findall(body):
                lk = k.lower()
                if lk not in SKIP_KEYS and lk not in NEVER_RENDER:
                    keys.add(k)
        spans[p] = {"payload": pay,
                    "select": [(m.start(1), m.end(1)) for m in SELECT.finditer(src)]}
        if writer_pages is not None and p not in writer_pages:
            continue
        for k in keys:
            writers.setdefault(k, set()).add(p)

    def renders(key, page):
        src, sp = srcs[page], spans[page]
        for m in re.finditer(r"\b" + re.escape(key) + r"\b", src):
            pos = m.start()
            if any(a <= pos <= b for a, b in sp["select"]):
                continue
            if any(a <= pos <= b for a, b in sp["payload"]):
                continue
            ls = src.rfind("\n", 0, pos) + 1
            le = src.find("\n", pos)
            if FORM_RESTORE.search(src[ls:le if le > 0 else len(src)]):
                continue
            return True
        return False

    out = {}
    for key, ws in writers.items():
        if not any(renders(key, p) for p in srcs):
            out[key] = sorted(ws)
    return out


def live_sources():
    """Returns (all sources, the page names that count as WRITERS)."""
    srcs, pages = {}, set()
    for p in sorted(glob.glob(str(ROOT / "*.html"))):
        name = Path(p).name
        if name.startswith("_") or "backup" in name or "-test" in name:
            continue
        srcs[name] = io.open(p, encoding="utf-8", errors="replace").read()
        pages.add(name)
    # shared scripts RENDER (a column shown by utils.js is not invisible) but do not count as
    # writers - see the note in sweep().
    for p in sorted(glob.glob(str(ROOT / "*.js"))):
        srcs[Path(p).name] = io.open(p, encoding="utf-8", errors="replace").read()
    return srcs, pages


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    write_only = {"a.html": "db.from('t').insert({ loto_applied: v, machine: m });"
                            "el.innerHTML = `${r.machine}`;"}
    chk("a written-but-unrendered column is found", "loto_applied" in sweep(write_only), True)
    chk("a rendered column is not", "machine" in sweep(write_only), False)

    cross = {"a.html": "db.from('t').insert({ target_id: x });",
             "b.html": "el.innerHTML = `${row.target_id}`;"}
    chk("rendered on ANOTHER page counts as reached", sweep(cross), {})

    secret = {"a.html": "db.from('t').insert({ key_hash: h });"}
    chk("a credential column is out of scope", sweep(secret), {})

    restore = {"a.html": "db.from('t').insert({ loto_applied: v });"
                         "document.getElementById('f-loto').checked = e.loto_applied;"}
    chk("restoring into a form is not rendering", "loto_applied" in sweep(restore), True)

    srcs, pages = live_sources()
    found = sweep(srcs, pages)
    new = sorted(set(found) - set(BASELINE))
    chk("no NEW captured-but-unrendered column", new, [])
    gone = sorted(set(BASELINE) - set(found))
    print(f"\n  (baseline {len(BASELINE)}, live {len(found)}"
          + (f", fixed since baseline: {', '.join(gone)}" if gone else "") + ")")
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    srcs, pages = live_sources()
    found = sweep(srcs, pages)
    new = sorted(set(found) - set(BASELINE))
    gone = sorted(set(BASELINE) - set(found))
    print("a column written for a person must reach one")
    print(f"  written-but-unrendered: {len(found)}  ·  baselined: {len(BASELINE)}  ·  new: {len(new)}")
    if gone:
        print(f"  reached a reader since the baseline: {', '.join(gone)}")
    if not new:
        print("\n  PASS - no column was built for a reader who cannot see it.")
        return 0
    print("\n  FAIL - these are captured, stored, and rendered to nobody:")
    for k in new:
        print(f"    {k}  (written by {', '.join(found[k])})")
    print("\n  Render it, or baseline it in this gate with the reason it need not be shown.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
