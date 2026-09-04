#!/usr/bin/env python3
"""no-write-only-tables - a table the UI writes should have a reader (2026-08-27, T105).

The table-level twin of captured-columns-reach-a-reader. That gate asks which COLUMNS never reach a
person; this asks which whole TABLES the UI fills and never opens again.

It found a real defect on its first run. marketplace-seller WRITES push_subscriptions when a
provider enables job alerts and never reads one back - and the in-context push card renders only
while `Notification.permission !== 'granted'`, so the moment permission is granted the card
disappears forever. Browser permission and a live subscription are two different facts: the endpoint
rotates, the service worker is replaced, an upsert fails, a row is cleared - and permission stays
'granted' through all of it. The provider is shown nothing while believing the page's own promise
that they will "hear new hails with this tab closed". The table having no reader is exactly what
allowed the page to never check. Fixed by giving the card a third state, which also gave the table
its reader.

*READS THROUGH VIEWS COUNT, and this is the whole difficulty. Naively, 14 of 54 written tables
looked write-only - including community_posts, hives and service_requests, which are plainly read
all day. They are read through TRUTH VIEWS (community reads v_community_posts_truth). Resolving
view -> base table from information_schema took 14 down to 2, and the two survivors were both real.
A sweep that cannot see through a view manufactures a dozen false findings.

A RATCHET: the single survivor is baselined with its reason. A NEW name means a table was just
built to be filled and never opened.

Needs the local database for the view map, so it SKIPS when the stack is down rather than guessing.

Self-test: `--selftest`.
"""
import collections
import glob
import io
import re
import socket
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

FROM_WRITE = re.compile(r"\.from\(\s*['\"]([a-z0-9_]+)['\"]\s*\)\s*\n?\s*\.(insert|update|upsert)\s*\(", re.S)
FROM_READ = re.compile(r"\.from\(\s*['\"]([a-z0-9_]+)['\"]\s*\)\s*\n?\s*\.select\s*\(", re.S)

# name -> why it may have no in-app reader (triaged 2026-08-27)
BASELINE = {
    "early_access_emails":
        "IAN DECISION, recorded on T67 - the landing page's waitlist, 24 rows, read by no page. "
        "Unlike the others its RLS grants SELECT to service_role ONLY, so surfacing it needs a new "
        "policy on 24 real people's email addresses or a service-role function. is_platform_admin() "
        "already exists, so it is one line once Ian says whether the owner should read it in-app.",
}


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def view_map() -> dict:
    """view -> {base tables}, straight from the database."""
    out = collections.defaultdict(set)
    r = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-F", "|", "-c",
         "select view_name, table_name from information_schema.view_table_usage where view_schema='public';"],
        capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
        env={**__import__("os").environ, "MSYS_NO_PATHCONV": "1"})
    for line in (r.stdout or "").splitlines():
        if "|" in line:
            v, t = line.strip().split("|", 1)
            out[v].add(t)
    return out


def sweep(page_srcs: dict, script_srcs: dict, views: dict) -> dict:
    written, read = {}, set()
    for name, src in page_srcs.items():
        for m in FROM_WRITE.finditer(src):
            written.setdefault(m.group(1), set()).add(name)
        for m in FROM_READ.finditer(src):
            read.add(m.group(1))
    for src in script_srcs.values():
        for m in FROM_READ.finditer(src):
            read.add(m.group(1))
    reached = set(read)
    for n in list(read):
        reached |= views.get(n, set())
    return {t: sorted(ws) for t, ws in written.items() if t not in reached}


def live_sources():
    pages, scripts = {}, {}
    for p in sorted(glob.glob(str(ROOT / "*.html"))):
        n = Path(p).name
        if n.startswith("_") or "backup" in n or "-test" in n:
            continue
        pages[n] = io.open(p, encoding="utf-8", errors="replace").read()
    for p in sorted(glob.glob(str(ROOT / "*.js"))):
        scripts[Path(p).name] = io.open(p, encoding="utf-8", errors="replace").read()
    return pages, scripts


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    w = {"a.html": "db.from('t').insert({x:1});"}
    chk("a written-never-read table is found", sorted(sweep(w, {}, {})), ["t"])

    wr = {"a.html": "db.from('t').insert({x:1});", "b.html": "db.from('t').select('*');"}
    chk("read on another page counts", sweep(wr, {}, {}), {})

    # the case that produced a dozen false findings
    via_view = {"a.html": "db.from('community_posts').insert({x:1});",
                "b.html": "db.from('v_community_posts_truth').select('*');"}
    chk("a read THROUGH A VIEW counts",
        sweep(via_view, {}, {"v_community_posts_truth": {"community_posts"}}), {})
    chk("...and without the view map it would not",
        sorted(sweep(via_view, {}, {})), ["community_posts"])

    chk("a shared script counts as a reader",
        sweep({"a.html": "db.from('t').insert({x:1});"}, {"utils.js": "db.from('t').select('*');"}, {}), {})

    if _port_open(54321):
        pages, scripts = live_sources()
        found = sweep(pages, scripts, view_map())
        chk("no NEW write-only table", sorted(set(found) - set(BASELINE)), [])
        gone = sorted(set(BASELINE) - set(found))
        print(f"\n  (baseline {len(BASELINE)}, live {len(found)}"
              + (f", gained a reader since: {', '.join(gone)}" if gone else "") + ")")
    else:
        print("  (live check skipped - database not reachable)")
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if not _port_open(54321):
        print("SKIP no-write-only-tables - local database not reachable (needs the view map)")
        return 0
    pages, scripts = live_sources()
    views = view_map()
    if not views:
        print("SKIP no-write-only-tables - could not read the view map")
        return 0
    found = sweep(pages, scripts, views)
    new = sorted(set(found) - set(BASELINE))
    gone = sorted(set(BASELINE) - set(found))
    print("a table the UI writes should have a reader")
    print(f"  write-only: {len(found)}  ·  baselined: {len(BASELINE)}  ·  new: {len(new)}"
          f"  ·  views resolved: {len(views)}")
    if gone:
        print(f"  gained a reader since the baseline: {', '.join(gone)}")
    if not new:
        print("\n  PASS - every table the UI fills is opened again by someone.")
        return 0
    print("\n  FAIL - these are written by the UI and read by nobody:")
    for t in new:
        print(f"    {t}  (written by {', '.join(found[t])})")
    print("\n  Give it a reader, or baseline it here with the reason it needs none.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
