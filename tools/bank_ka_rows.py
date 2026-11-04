#!/usr/bin/env python3
"""bank_ka_rows.py - bank keep-abreast rows on the reading their lens names (Wave KA, 2026-10-29).

KA-S (KA189..KA308), one row per sitemap URL: "this URL was pushed to the index (an IndexNow receipt) after its last
change; its indexed state is read when the Search Console credential exists, never assumed". A row closes only when
all three hold, each read now:
  1. the deployed origin serves the URL: a raw HTTP GET (no JS - what a crawler receives) answers 200, and the page's
     <link rel="canonical"> names that same URL;
  2. indexnow_receipts.json's per-URL map names the URL with an accepted push (HTTP 200/202) dated on or after its
     sitemap <lastmod> - the receipt kept every push since 2026-10-29, backfilled from the file's own git history;
  3. freshness_trip.py raises no push trip for it (the trip reads the same map, so 2 and 3 agree by construction - 3 is
     run anyway, because the trip is the row's declared close).
The indexed state is NOT read - no Search Console credential exists (KA-B) - and every basis says so rather than
implying it. A row that fails any check is left as it is and printed with the reason.

    python tools/bank_ka_rows.py --lens S [--dry] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bank_sl_walk as bsw  # noqa: E402
import freshness_trip as ft  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RECEIPTS = ROOT / "indexnow_receipts.json"
UA = "WorkHive-keep-abreast/1.0 (+https://workhiveph.com) raw-http"
CANON = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']|'
                   r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']', re.I)


def served(url: str) -> tuple[int | None, str | None, str]:
    """(status, canonical, note) from a plain GET of what the deployed origin serves."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(400_000).decode("utf-8", errors="replace")
            m = CANON.search(body)
            return r.status, (m.group(1) or m.group(2)) if m else None, ""
    except urllib.error.HTTPError as e:
        return e.code, None, str(e.reason)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, None, str(e)[:120]


def bank_s(dry: bool, limit: int | None) -> int:
    rec = json.loads(RECEIPTS.read_text(encoding="utf-8")) if RECEIPTS.exists() else {}
    pushed = rec.get("pushed") or {}
    if not pushed:
        print("  refused: indexnow_receipts.json has no per-URL map - run tools/indexnow_submit.py --backfill-history")
        return 1
    c = ft.census()
    push_trips = {t["unit"] for t in c["trips"] if t["kind"] == "push"}
    urls = {u["path"]: u for u in c["url_list"]}
    ok, last = bsw._run_gate(str(ROOT / "tools" / "freshness_trip.py"), "--check")
    print(f"  gate seo-trip (freshness_trip.py --check): {'PASS' if ok else 'FAIL'} - {last}")
    if not ok:
        print("  refused: a row is never banked on a red gate")
        return 1
    reg = bsw._load_registry()
    rows = [t for t in reg["trajectories"] if t.get("wave") == "KA-S" and t.get("status") not in ("locked", "descoped")]
    banked, left = 0, []
    for t in rows[: limit or None]:
        unit = (t.get("ka") or {}).get("unit")
        u = urls.get(unit)
        if not u:
            left.append(f"{t['id']} {unit}: not in the sitemap")
            continue
        loc, lastmod = u["loc"], u["lastmod"]
        at = pushed.get(loc) or {}
        at_ts = at.get("at") if isinstance(at, dict) else at
        code = at.get("response") if isinstance(at, dict) else None
        if not at_ts or (lastmod and at_ts[:10] < lastmod):
            left.append(f"{t['id']} {unit}: last push {at_ts or 'never'} is before its lastmod {lastmod}")
            continue
        if unit in push_trips:
            left.append(f"{t['id']} {unit}: freshness_trip still raises a push trip")
            continue
        status, canonical, note = served(loc)
        time.sleep(0.4)   # one URL at a time, politely - this is the live site
        if status != 200:
            left.append(f"{t['id']} {unit}: the deployed origin answered {status or 'nothing'} {note}")
            continue
        if canonical and canonical.rstrip("/") != loc.rstrip("/"):
            left.append(f"{t['id']} {unit}: served canonical {canonical} is not {loc}")
            continue
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        basis = (f"[{date.today().isoformat()}] pct -> {{pct}}. Measured live - a raw-http fetch of the deployed origin "
                 f"({now}): GET {loc} "
                 f"answered 200, canonical {'= that URL' if canonical else 'not declared'}. indexnow_receipts.json pushed "
                 f"it {at_ts} (HTTP {code or 200}) on or after its last change (<lastmod> {lastmod}); freshness_trip.py "
                 f"raises no push trip for it. Gate seo-trip. Indexed state NOT read: no Search Console credential (KA-B) "
                 f"- the row claims the push, never the index.")
        if dry:
            print(f"  would bank {t['id']} {unit}: pushed {at_ts}, lastmod {lastmod}, served 200")
        else:
            bsw._bank(reg, t["id"], basis, ["seo-trip"])
        banked += 1
    if not dry and banked:
        bsw._write_registry(reg)
    for line in left:
        print("  left open: " + line)
    print(f"{'would bank' if dry else 'banked'} {banked} KA-S row(s); {len(left)} left open")
    return 0


DECISION = re.compile(r"^##\s*Decision\b", re.M)


E_INSTRUMENT = "tools/night_crawler.py --refresh-stale re-fetched"


def bank_e(dry: bool, limit: int | None, restamp: bool = False) -> int:
    """KA-E (Wave JS follow-on, 2026-10-31), one row per cited external source: "this external source is within its TTL;
    when it is re-fetched a changed sha produces a diff note and a recorded decision on the lever it anchors". A row
    closes only when all three hold, each read now:
      1. the chunk was re-verified within its ttl_days (night_crawler.py --refresh-stale, one slice at a time);
      2. freshness_trip.py raises no evidence trip for it;
      3. EVERY change note the re-fetches left for it (substrate/external/_changes/<unit>.<date>.md) carries a
         '## Decision' section - which lever rests on the source and whether it moved. A change with no decision is
         exactly the silent rewrite this lens exists to stop, so the row stays open and says which note is owed."""
    c = ft.census()
    ev_trips = {t["unit"] for t in c["trips"] if t["kind"] == "evidence"}
    ok, last = bsw._run_gate(str(ROOT / "tools" / "freshness_trip.py"), "--check")
    print(f"  gate seo-trip (freshness_trip.py --check): {'PASS' if ok else 'FAIL'} - {last}")
    if not ok:
        print("  refused: a row is never banked on a red gate")
        return 1
    ext = ROOT / "substrate" / "external"
    reg = bsw._load_registry()
    rows = [t for t in reg["trajectories"] if t.get("wave") == "KA-E" and t.get("status") not in ("locked", "locking", "descoped")]
    if restamp:
        # ★THE BASIS NAMES THE RE-FETCH THAT TOOK THE READING (2026-11-04). The first 66 KA-E bases said "Re-fetched by
        # night_crawler.py" in words the live-walk ledger reads as prose, and the rows routed to a browser + database
        # walk that cannot answer "is this source inside its TTL". Each banked row is re-read by the same three
        # conditions, and only a row that still holds gains a segment naming the live re-fetch (appended, newest last).
        rows = [t for t in reg["trajectories"] if t.get("wave") == "KA-E" and t.get("status") == "locking"
                and E_INSTRUMENT not in (t.get("basis") or "")]
    banked, left = 0, []
    for t in rows[: limit or None]:
        unit = (t.get("ka") or {}).get("unit")
        chunk = ext / f"{unit}.md"
        if not unit or not chunk.exists():
            left.append(f"{t['id']} {unit}: no chunk on disk")
            continue
        if unit in ev_trips:
            left.append(f"{t['id']} {unit}: still past its TTL - re-fetch it (night_crawler.py --refresh-stale --only)")
            continue
        fm = ft._frontmatter(ft._rd(chunk))
        # The chunk's OWN age, not the trip list: freshness_trip ages only SEO-topic or cited chunks, so a UX source
        # 101 days past its 30-day TTL raised no trip - and the first dry run would have banked three of them.
        ttl = int(re.sub(r"\D", "", str(fm.get("ttl_days", "30"))) or 30)
        age = ft._age(ft._d(fm.get("last_verified")) or ft._d(fm.get("fetched_at")), date.today())
        if age is None or age > ttl:
            left.append(f"{t['id']} {unit}: {age if age is not None else '?'} days since verified against a {ttl}-day TTL - "
                        "re-fetch it (night_crawler.py --refresh-stale --only)")
            continue
        notes = sorted((ext / "_changes").glob(f"{unit}.*.md"))
        owed = [n for n in notes if not DECISION.search(n.read_text(encoding="utf-8"))]
        if owed:
            left.append(f"{t['id']} {unit}: changed - decision owed in {owed[-1].relative_to(ROOT).as_posix()}")
            continue
        verified = fm.get("last_verified") or fm.get("fetched_at")
        decided = []
        for n in notes:
            m = re.search(r"^##\s*Decision\b[^\n]*\n+(.+)", n.read_text(encoding="utf-8"), re.M)
            decided.append(f"{n.name.rsplit('.', 2)[-2]}: {m.group(1).strip()[:200] if m else ''}")
        basis = (f"[{date.today().isoformat()}] pct -> {{pct}}. Measured live {verified}: {E_INSTRUMENT} "
                 f"{fm.get('source') or unit} from its origin (sha {fm.get('source_sha')}, ttl {fm.get('ttl_days')}d); "
                 f"freshness_trip.py raises no evidence trip for it. "
                 + (f"Changes on re-fetch, each with its recorded decision: {' | '.join(decided)}." if decided
                    else "The source had not changed since its last fetch (sha matched), so no lever was in question.")
                 + " Gate seo-trip.")
        if dry:
            print(f"  would bank {t['id']} {unit}: verified {verified}, {len(notes)} change note(s), all decided")
        else:
            bsw._bank(reg, t["id"], basis, ["seo-trip"])
        banked += 1
    if not dry and banked:
        bsw._write_registry(reg)
    for line in left:
        print("  left open: " + line)
    print(f"{'would bank' if dry else 'banked'} {banked} KA-E row(s); {len(left)} left open")
    return 0


SURFACES = ROOT / "freshness_surfaces_report.json"
SURFACES_TEETH = ROOT / "freshness_surfaces_teeth.json"


def bank_r(dry: bool, limit: int | None) -> int:
    """KA-R (KA1..KA120), one row per sitemap URL: "this page's five freshness surfaces agree; it is inside its kind's
    window or holds an open refresh". The 58 rows of 2026-10-30 were banked from this reading by hand; this is the same
    reading as a tool (2026-10-31). A row closes only when, read now:
      1. tools/prove_freshness_surfaces.mjs read the DEPLOYED origin within 6 h and found the page's JSON-LD dateModified,
         its visible 'Last updated' line at phone-390 and desktop-1280, and its sitemap <lastmod> to be one date, its
         markdown twin the repository's, and an IndexNow push on or after the change;
      2. the prover's --teeth run (a <lastmod> moved a day early) reddened the same day - a prover that cannot fail does
         not get to pass anything;
      3. freshness_trip.py raises no refresh or sitemap-promise trip for the page."""
    if not SURFACES.exists():
        print("  refused: no freshness_surfaces_report.json - run node tools/prove_freshness_surfaces.mjs after the deploy")
        return 1
    rep = json.loads(SURFACES.read_text(encoding="utf-8"))
    ran = datetime.fromisoformat(rep["ran"].replace("Z", "+00:00"))
    age_h = (datetime.now(timezone.utc) - ran).total_seconds() / 3600
    if rep.get("teeth") or age_h > 6:
        print(f"  refused: the surfaces report is {'a teeth run' if rep.get('teeth') else f'{age_h:.1f} h old'} - re-run the prover")
        return 1
    teeth = json.loads(SURFACES_TEETH.read_text(encoding="utf-8")) if SURFACES_TEETH.exists() else {}
    # the planted fault is a <lastmod> a day before the page's own date: the teeth run must have failed THAT disagreement,
    # not merely failed something (a page already wrong on production would also make `failed` non-zero)
    caught = any(not x.get("ok") and x.get("lastmod") and x.get("jsonld") and x["lastmod"] < x["jsonld"]
                 for x in (teeth.get("rows") or {}).values())
    if not teeth.get("teeth") or not caught or (teeth.get("ran") or "")[:10] != rep["ran"][:10]:
        print("  refused: no same-day --teeth run that reddened - run node tools/prove_freshness_surfaces.mjs --teeth")
        return 1
    ok, last = bsw._run_gate(str(ROOT / "tools" / "freshness_trip.py"), "--check")
    print(f"  gate seo-trip (freshness_trip.py --check): {'PASS' if ok else 'FAIL'} - {last}")
    if not ok:
        print("  refused: a row is never banked on a red gate")
        return 1
    c = ft.census()
    tripped = {t["unit"] for t in c["trips"] if t["kind"] in ("refresh", "sitemap-promise")}
    by_local = {r.get("local"): (url, r) for url, r in rep["rows"].items()}
    reg = bsw._load_registry()
    rows = [t for t in reg["trajectories"] if t.get("wave") == "KA-R" and t.get("status") not in ("locked", "locking", "descoped")]
    banked, left = 0, []
    for t in rows[: limit or None]:
        ka = t.get("ka") or {}
        unit = ka.get("unit")
        hit = by_local.get(unit)
        if not hit:
            left.append(f"{t['id']} {unit}: not in the prover's reading of production's sitemap")
            continue
        url, r = hit
        if tripped & ({unit} | set(ka.get("aliases") or [])):
            left.append(f"{t['id']} {unit}: freshness_trip still raises a refresh or sitemap-promise trip")
            continue
        vis = r.get("visible") or {}
        dates = {r.get("jsonld"), vis.get("phone-390"), vis.get("desktop-1280"), r.get("lastmod")}
        if not r.get("ok") or r.get("status") != 200 or len(dates) != 1 or None in dates or r.get("twin") != "current" \
                or not r.get("pushed_after_change") or not r.get("in_window"):
            left.append(f"{t['id']} {unit}: production disagrees - jsonld {r.get('jsonld')}, visible {vis}, lastmod "
                        f"{r.get('lastmod')}, twin {r.get('twin')}, pushed {r.get('pushed')}")
            continue
        d = r["lastmod"]
        basis = (f"[{date.today().isoformat()}] pct -> {{pct}}. Measured live {rep['ran'][:16]}Z - tools/prove_freshness_surfaces.mjs "
                 f"read the deployed origin for {url}: HTTP 200; JSON-LD dateModified {d}; the visible 'Last updated' <time> {d} "
                 f"at phone-390 and {d} at desktop-1280 (rendered and visible); sitemap <lastmod> {d}; the deployed markdown twin "
                 f"is the repository's (current); IndexNow pushed {r.get('pushed')}, on or after the change; no refresh trip "
                 f"(inside its kind's window). One date on all five surfaces. Teeth: the same-day --teeth run moved a <lastmod> "
                 f"a day early and it read as disagreement. Gate freshness-surfaces (with sitemap-promise, md-twins-current, "
                 f"seo-trip).")
        if dry:
            print(f"  would bank {t['id']} {unit}: one date {d} on five surfaces")
        else:
            bsw._bank(reg, t["id"], basis, ["freshness-surfaces", "seo-trip"])
        banked += 1
    if not dry and banked:
        bsw._write_registry(reg)
    for line in left:
        print("  left open: " + line)
    print(f"{'would bank' if dry else 'banked'} {banked} KA-R row(s); {len(left)} left open")
    return 0


SOV_RUNS = ROOT / "geo_sov_runs"
QUERIES = ROOT / "prompt_audit_queries.json"
_PATH_IN = re.compile(r"(/[\w./-]+/?)")


def expected_page(expected: str) -> Path:
    """The local file of the page a prompt expects to be cited ('workhiveph.com or /learn/x/' -> learn/x/index.html)."""
    m = _PATH_IN.search(expected or "")
    if not m:
        return ROOT / "index.html"
    p = m.group(1).strip("/")
    return ROOT / p if p.endswith(".html") else ROOT / p / "index.html"


def bank_v(dry: bool, limit: int | None) -> int:
    """KA-V (KA309..): "the page this prompt expects to be cited is citation-eligible now (answer-first, twin current,
    facts inside their window); the monthly run records cited / mentioned / recommended per engine; a drop trips a
    review". A row closes when, read now:
      1. the expected page exists, carries its answer-first block, and its markdown twin is current (validate_md_twins);
      2. freshness_trip raises no trip for that page, and no voice trip (the month's sheet is scored and in window);
      3. this month's run (geo_sov_runs/<YYYY-MM>.json, tools/geo_sov_free_run.py on the free-tier engines) recorded a
         reading - not None - for the row's prompt on EVERY engine the run declares.
    Whether WorkHive was cited is RECORDED in the basis, never required: the row asks that the measurement exists and
    that a drop trips, not that the brand is already cited."""
    import validate_md_twins as vmt
    missing, drifted, _ = vmt.audit()
    twin_bad = set(missing) | set(drifted)
    c = ft.census()
    voice = [t for t in c["trips"] if t["kind"] == "voice"]
    if voice:
        print(f"  refused: a voice trip is open - {voice[0]['detail'][:160]}")
        return 1
    ok, last = bsw._run_gate(str(ROOT / "tools" / "freshness_trip.py"), "--check")
    print(f"  gate seo-trip (freshness_trip.py --check): {'PASS' if ok else 'FAIL'} - {last}")
    if not ok:
        print("  refused: a row is never banked on a red gate")
        return 1
    runs = sorted(SOV_RUNS.glob("*.json"))
    if not runs:
        print("  refused: no monthly run on disk - python tools/geo_sov_free_run.py")
        return 1
    sheet = json.loads(runs[-1].read_text(encoding="utf-8"))
    month, engines = sheet["_meta"].get("month"), sheet["_meta"].get("engines") or []
    queries = {q["id"]: q for q in json.loads(QUERIES.read_text(encoding="utf-8"))["queries"]}
    reg = bsw._load_registry()
    rows = [t for t in reg["trajectories"] if t.get("wave") == "KA-V" and t.get("status") not in ("locking", "locked", "descoped")]
    banked, left = 0, []
    for t in rows[: limit or None]:
        unit = (t.get("ka") or {}).get("unit")
        q = queries.get(unit)
        if not q:
            left.append(f"{t['id']} {unit}: not in prompt_audit_queries.json")
            continue
        page = expected_page(q.get("expected_cite", ""))
        rel = page.relative_to(ROOT).as_posix()
        if not page.exists():
            left.append(f"{t['id']} {unit}: the expected page {rel} does not exist")
            continue
        html = page.read_text(encoding="utf-8", errors="replace")
        if rel != "index.html" and 'class="answer-first' not in html:
            left.append(f"{t['id']} {unit}: {rel} carries no answer-first block")
            continue
        if rel in twin_bad:
            left.append(f"{t['id']} {unit}: {rel}'s markdown twin is missing or stale")
            continue
        slug = rel[:-len("/index.html")] if rel.endswith("/index.html") else rel
        trips = [x for x in c["trips"] if x.get("unit") in (rel, slug, "/" + slug + "/", slug.split("/")[-1])]
        if trips:
            left.append(f"{t['id']} {unit}: freshness_trip raises {trips[0]['kind']} for {rel}")
            continue
        cells = (sheet["results"].get(unit) or {})
        unread = [e for e in engines if (cells.get(e) or {}).get("cited") is None]
        if unread:
            left.append(f"{t['id']} {unit}: the {month} run has no reading yet from {', '.join(unread)}")
            continue
        reading = "; ".join(f"{e} cited {cells[e]['cited']} / mentioned {cells[e]['mentioned']} / recommended "
                            f"{cells[e]['recommended']} ({cells[e]['evidence'].get('sources', 0)} live sources)" for e in engines)
        basis = (f"[{date.today().isoformat()}] pct -> {{pct}}. Measured: {rel} is citation-eligible now (served file, an "
                 f"answer-first block, its markdown twin current, no freshness trip). The {month} share-of-voice run "
                 f"(tools/geo_sov_free_run.py, free-tier engines that search the live web as they answer) asked "
                 f"'{q['query']}': {reading}. A drop trips the voice review through freshness_trip's window. Gate seo-trip.")
        if dry:
            print(f"  would bank {t['id']} {unit}: {rel}; " + ", ".join(
                f"{e} {'C' if cells[e]['cited'] else '-'}{'M' if cells[e]['mentioned'] else '-'}" for e in engines))
        else:
            bsw._bank(reg, t["id"], basis, ["seo-trip"])
        banked += 1
    if not dry and banked:
        bsw._write_registry(reg)
    for line in left:
        print("  left open: " + line)
    print(f"{'would bank' if dry else 'banked'} {banked} KA-V row(s); {len(left)} left open")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lens", choices=["S", "E", "R", "V"], required=True)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--restamp", action="store_true", help="E only: re-read the banked rows and name the live re-fetch")
    a = ap.parse_args()
    if a.restamp:
        return bank_e(a.dry, a.limit, restamp=True)
    return {"E": bank_e, "S": bank_s, "R": bank_r, "V": bank_v}[a.lens](a.dry, a.limit)


if __name__ == "__main__":
    sys.exit(main())
