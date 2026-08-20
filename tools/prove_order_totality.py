# -*- coding: utf-8 -*-
"""Prove (or refute) ORDER TOTALITY for a page's reads, from the page source plus the LIVE catalog.

WHY THIS EXISTS AS A TOOL. `ordering_totality` is owed or R7-stale on 42 rows across the 22 page banks,
and it is one of the few layer-contract oracles provable with no browser and no REST gateway: the ORDER
clauses live in the page, and whether a sort is TOTAL is a fact about the schema. Both are reachable
here (psql via `docker exec`), so this is the local-substitute path while the Playwright MCP is down.

WHAT "TOTAL" MEANS AND WHY IT MATTERS. A paginated read whose ORDER BY does not uniquely determine row
sequence may return the same row on two pages, or skip it entirely - Postgres is free to break ties
differently between the two queries. So an order is total only if its columns end in something unique
for that relation. This gate therefore asks two questions per read, and needs BOTH answers:
  1. does the ORDER chain end in a column that is actually UNIQUE on that relation (asked of the live
     catalog, not assumed from the name `id`); and
  2. if not, do TIES actually exist in the data on the leading columns (asked in SQL) - because a
     non-unique sort over a column with no duplicates is total in practice, and calling it a defect
     would be a false positive.
A row is only reported non-total when the sort is non-unique AND ties are present.

    python tools/prove_order_totality.py <page> [--json]
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_CONTAINER = "supabase_db_workhive"
GREEN, RED, YEL, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def psql(sql):
    """-> list of tuples. Read-only by construction: this tool only ever SELECTs from the catalog."""
    p = subprocess.run(["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                        "-tAF", "\x1f", "-c", sql],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise SystemExit("psql failed: %s" % (p.stderr or "")[:300])
    return [ln.split("\x1f") for ln in (p.stdout or "").strip().splitlines() if ln.strip()]


_UNIQ_CACHE = {}
_PREFETCHED = False


def prefetch_unique_columns():
    """One round trip for the WHOLE public schema instead of one per relation.

    Each `docker exec psql` costs about a second, and a 22-page sweep touches 100+ distinct relations,
    so the per-relation version could not finish inside a two-minute budget (it got through one page).
    The answer is the same either way; this just asks once.
    """
    global _PREFETCHED
    if _PREFETCHED:
        return
    rows = psql("""
        select c.relname, c.relkind::text,
               coalesce(string_agg(distinct a.attname, ','), '')
          from pg_class c
          join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
          left join pg_index i on i.indrelid = c.oid and i.indisunique and i.indnatts = 1
          left join pg_attribute a on a.attrelid = c.oid and a.attnum = any(i.indkey)
         where c.relkind in ('r', 'v', 'm', 'p')
         group by c.relname, c.relkind
    """)
    for r in rows:
        name = r[0]
        kind = r[1] if len(r) > 1 else "r"
        cols = r[2] if len(r) > 2 else ""
        _UNIQ_CACHE[name] = (kind, {c for c in cols.split(",") if c})
    _PREFETCHED = True


def unique_columns(relation):
    """Columns that alone determine a row on this relation: PK or single-column UNIQUE index.

    MEMOISED because each call is a `docker exec` round trip (~1s) and a page reads the same relation
    from several call sites; without this a 3-page run exceeded a 2-minute budget.

    Views are the interesting case and the reason this asks the catalog rather than trusting a name: a
    VIEW has no primary key at all, so `.order('id')` on `v_*_truth` is NOT self-evidently unique. The
    query therefore also reports whether the relation is a view, so the caller can say so out loud
    instead of quietly treating a view like a table.
    """
    prefetch_unique_columns()
    # The prefetch covers every relation in the public schema, so a miss means the name is not a
    # relation there at all (an RPC name, a typo, or a table in another schema) - not a cache gap.
    return _UNIQ_CACHE.get(relation, (None, set()))


def sql_lit(s):
    return "'" + str(s).replace("'", "''") + "'"


def tie_count(relation, cols):
    """Max number of rows sharing one value of the leading ORDER columns. 1 => no ties => total anyway."""
    if not cols:
        return None
    collist = ", ".join('"%s"' % c for c in cols)
    try:
        rows = psql("select coalesce(max(n),0) from (select count(*) n from public.%s group by %s) t"
                    % ('"%s"' % relation, collist))
    except SystemExit:
        return None            # a column named in the page does not exist on the relation
    return int(rows[0][0]) if rows else None


# SCOPED TO THE STATEMENT, NOT A CHARACTER WINDOW. The first cut took 1200 chars after `.from(`, so a
# `.limit(` belonging to the NEXT query fell inside the window and marked an unpaginated read as
# paginated - logbook reported 11 of 11 reads NON-TOTAL, and `project_links` at :2144 has no `.limit()`
# at all. An impossibly bad result is as much a signal as an impossibly good one. The tail now ends at
# the statement terminator, so only this query's own modifiers are read.
READ_RE = re.compile(r"""\.from\(\s*['"]([a-zA-Z0-9_]+)['"]\s*\)([^;]{0,900}?)(?=;|\.from\(|\Z)""", re.S)
ORDER_RE = re.compile(r"""\.order\(\s*['"]([a-zA-Z0-9_]+)['"]""")
# `.range(` IS pagination: it asks for a window by offset, so a second call can overlap or skip.
# A bare `.limit(N)` is NOT - it is a row cap on a single read, and this codebase marks the deliberate
# ones `limit-as-count-allow` / "bounded-by-nature". Conflating the two turned every capped registry
# read into a defect (v_pm_compliance_truth at :4280 is an asset-picker list of "dozens/hive").
PAGE_RE = re.compile(r"""\.range\(""")
CAP_RE = re.compile(r"""\.limit\(""")


def analyse(page):
    path = os.path.join(ROOT, page + ".html")
    if not os.path.exists(path):
        raise SystemExit("no such page file: %s" % path)
    src = open(path, encoding="utf-8").read()
    # a page may also read through its own .js (engineering-design does)
    side = os.path.join(ROOT, page + ".js")
    if os.path.exists(side):
        src += "\n" + open(side, encoding="utf-8").read()

    # COVERAGE IS REPORTED, NOT ASSUMED. A query built across STATEMENTS - `let q = db.from('x')...` then
    # `await q.order('created_at').limit(50)` in a later statement - is invisible to a statement-scoped
    # scan, and engineering-design.js does exactly that (loadHistory at :28118). Returning an empty list
    # for such a page would read as "no ordered reads exist" when it means "this lens could not see
    # them", so the caller is told the difference: total `.from(` sites vs sites this scan could analyse.
    from_sites = len(re.findall(r"\.from\(\s*['\"][a-zA-Z0-9_]+['\"]", src))
    builder = bool(re.search(r"(?:let|var|const)\s+\w+\s*=\s*(?:db|getDb\(\))\.from\(", src))

    seen, results = set(), []
    for m in READ_RE.finditer(src):
        rel, tail = m.group(1), m.group(2)
        orders = ORDER_RE.findall(tail)
        paginated = bool(PAGE_RE.search(tail))       # .range() only: a real offset window
        capped = bool(CAP_RE.search(tail))           # .limit(): a row cap, reported but not a defect
        # THE WORST CASE IS THE ONE WITH NO ORDER AT ALL, and an instrument that only inspects reads
        # which HAVE an order clause cannot see it. `.limit(n)` with no ORDER BY leaves row sequence
        # entirely to the planner, so two pages of the same query may overlap or skip - strictly worse
        # than a non-unique sort, and invisible to a lens keyed on `.order(`.
        if not orders:
            kind, _ = unique_columns(rel)
            if kind is None:
                continue
            if paginated:
                results.append({"relation": rel, "kind": "view" if kind == "v" else "table",
                                "orders": [], "paginated": True, "capped": capped,
                                "unique_single_cols": [], "max_ties": None, "verdict": "NON-TOTAL",
                                "detail": "uses .range() with NO order clause at all, so two pages of "
                                          "the same query may overlap or skip rows"})
            elif capped:
                results.append({"relation": rel, "kind": "view" if kind == "v" else "table",
                                "orders": [], "paginated": False, "capped": True,
                                "unique_single_cols": [], "max_ties": None, "verdict": "capped-unordered",
                                "detail": "a single .limit() read with no order: NOT pagination, so no "
                                          "row can appear twice - but WHICH rows the cap keeps is "
                                          "undefined if the set ever exceeds it"})
            continue
        key = (rel, tuple(orders), paginated)
        if key in seen:
            continue
        seen.add(key)
        kind, uniq = unique_columns(rel)
        if kind is None:
            results.append({"relation": rel, "orders": orders, "paginated": paginated,
                            "verdict": "relation-not-found", "detail": "not in the public schema"})
            continue
        last = orders[-1]
        total_by_unique = last in uniq
        # When the catalog cannot prove uniqueness, measure ties across the WHOLE chain including the
        # last column - not just the leading ones. On a view ordered by (created_at, id) with no unique
        # index, the question is whether (created_at, id) together have duplicates, and asking only
        # about created_at would report ties that the id already breaks.
        ties = None if total_by_unique else tie_count(rel, orders)
        if total_by_unique:
            verdict, detail = "total", "ends in %s, which is unique on this %s" % (
                last, "view" if kind == "v" else "table")
        elif ties is None:
            verdict, detail = "unknown", "could not measure ties (a named column may not exist)"
        elif ties <= 1:
            verdict, detail = "total-in-practice", (
                "no unique tiebreaker, but max ties on %s is %d, so the sort is total on today's data"
                % (",".join(orders), ties))
        else:
            verdict = "NON-TOTAL" if paginated else "ties-no-pagination"
            detail = ("no unique tiebreaker and up to %d rows share one value of %s%s"
                      % (ties, ",".join(orders),
                         " - and the read uses .range(), so a row can appear twice or never"
                         if paginated else " - but the read is not paginated, so the risk is "
                                           "display order only, not lost or doubled rows"))
        results.append({"relation": rel, "kind": "view" if kind == "v" else "table",
                        "orders": orders, "paginated": paginated,
                        "unique_single_cols": sorted(uniq), "max_ties": ties,
                        "verdict": verdict, "detail": detail})
    analysed = len({(r["relation"], tuple(r["orders"])) for r in results})
    if builder and analysed < from_sites:
        results.append({"relation": "(coverage)", "orders": [], "paginated": False,
                        "verdict": "not-analysed",
                        "detail": ("%d `.from(` site(s) present, %d analysable here: this page builds at "
                                   "least one query across STATEMENTS (`let q = db.from(...)` then "
                                   "`q.order(...)` later), which a statement-scoped scan cannot follow. "
                                   "Those reads are UNVERIFIED, not verified-clean."
                                   % (from_sites, analysed))})
    return results


ALL_PAGES = ["index", "hive", "logbook", "inventory", "pm-scheduler", "project-manager", "dayplanner",
             "asset-hub", "analytics", "alert-hub", "skillmatrix", "shift-brain", "voice-journal",
             "assistant", "community", "public-feed", "achievements", "engineering-design", "resume",
             "report-sender", "project-report", "analytics-report"]


def db_up():
    """A gate that cannot reach the database must SKIP, not fail. A red for an absent container teaches
    the suite's readers to ignore reds, which is worse than the gap it reports."""
    try:
        psql("select 1")
        return True
    except SystemExit:
        return False


def gate(argv):
    """Sweep every page. Exit 1 only on a real NON-TOTAL; a capped-unordered read is reported."""
    if not db_up():
        print("  %sSKIP%s — the database is not reachable (docker exec %s); order totality is a schema "
              "question and cannot be answered without it." % (YEL, RST, DB_CONTAINER))
        return 0
    report, bad_total, examined = {}, 0, 0
    for page in ALL_PAGES:
        try:
            rows = analyse(page)
        except SystemExit as e:
            report[page] = [{"verdict": "ERROR", "detail": str(e)[:160]}]
            continue
        report[page] = rows
        examined += len(rows)
        bad_total += sum(1 for r in rows if r["verdict"] == "NON-TOTAL")
    counts = {}
    for rows in report.values():
        for r in rows:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    with open(os.path.join(ROOT, "order_totality_report.json"), "w", encoding="utf-8") as fh:
        json.dump({"counts": counts, "pages": report}, fh, indent=1)
    print("  Order totality — %d ordered reads across %d pages" % (examined, len(ALL_PAGES)))
    for k in ("total", "total-in-practice", "capped-unordered", "ties-no-pagination", "NON-TOTAL",
              "unknown", "relation-not-found", "ERROR"):
        if counts.get(k):
            print("    %-20s %d" % (k, counts[k]))
    if bad_total:
        print("\n  %sFAIL%s — %d paginated read(s) cannot guarantee row sequence:"
              % (RED, RST, bad_total))
        for page, rows in report.items():
            for r in rows:
                if r["verdict"] == "NON-TOTAL":
                    print("    %-19s %s(%s) — %s" % (page, r["relation"],
                                                     ",".join(r.get("orders") or []) or "no order",
                                                     r["detail"][:90]))
        return 1
    print("\n  %sPASS%s — every paginated read ends in a tiebreaker, and every lone .limit() cap is "
          "recorded rather than counted as one." % (GREEN, RST))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("page", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gate", action="store_true", help="sweep all 22 pages; for run_platform_checks")
    a = ap.parse_args(argv)
    if a.gate:
        return gate(a)
    if not a.page:
        ap.error("give a page, or --gate to sweep all of them")
    res = analyse(a.page)
    if a.json:
        print(json.dumps(res, indent=1))
        return 0
    bad = [r for r in res if r["verdict"] == "NON-TOTAL"]
    print("  %s%s%s — %d ordered read(s) found" % (YEL, a.page, RST, len(res)))
    for r in res:
        colour = RED if r["verdict"] == "NON-TOTAL" else (GREEN if r["verdict"] == "total" else YEL)
        print("   %s%-18s%s %-46s %s" % (colour, r["verdict"], RST,
                                         "%s(%s)" % (r["relation"], ",".join(r["orders"])),
                                         r["detail"][:96]))
    print("\n  %d total · %d total-in-practice · %d capped-unordered · %d ties-no-pagination · "
          "%s%d NON-TOTAL%s · %d unknown"
          % (sum(1 for r in res if r["verdict"] == "total"),
             sum(1 for r in res if r["verdict"] == "total-in-practice"),
             sum(1 for r in res if r["verdict"] == "capped-unordered"),
             sum(1 for r in res if r["verdict"] == "ties-no-pagination"),
             RED if bad else DIM, len(bad), RST,
             sum(1 for r in res if r["verdict"] in ("unknown", "relation-not-found"))))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
