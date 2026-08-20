# -*- coding: utf-8 -*-
"""Prove that a page's reads are IDEMPOTENT: the same request twice returns the same bytes.

WHY IT BUILDS ON ORDER TOTALITY. A repeat read can only be byte-identical if its row sequence is
determined, so this is the natural second half of tools/prove_order_totality.py: that tool asks whether
the ORDER pins the sequence, this one asks whether two executions actually agree. Running it on reads
whose order is NOT total is how you learn the difference between "total in theory" and "stable in fact".

HOW THE REPEAT IS MADE HONEST. The two executions are TWO SEPARATE psql invocations - two connections,
two planner passes. Running them as two CTEs in one statement would let Postgres compute the scan once
and compare it with itself, which passes by construction and proves nothing: the same class of vacuous
result as an injection that intercepts zero requests. Each side hashes the full ordered projection
(`md5(string_agg(t::text, '|'))`), so a difference in ANY column of ANY row moves the digest.

WHAT IT CANNOT SEE, stated so a pass is not over-read: this measures the DB's answer, not PostgREST's
serialisation of it. `envelope_shape` and `status_body_agreement` are about the HTTP envelope and are
not inferable from here.

CORRECTION, 2026-08-12: this docstring used to say those two oracles were unreachable "because kong
publishes no host port". **That was false, and stating it here is what kept them owed.** `docker ps`
shows `supabase_kong_workhive  0.0.0.0:54321->8000/tcp`, and `curl -H "apikey: <publishable>"
http://127.0.0.1:54321/rest/v1/<table>` answers 200. A ceiling written into a tool's own documentation
outlives the five minutes it would have taken to test it — so the claim is corrected rather than
deleted, and those oracles are reachable work rather than a limit.

    python tools/prove_read_idempotency.py <page> [--json]
    python tools/prove_read_idempotency.py --gate
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import prove_order_totality as OT  # noqa: E402  (psql, regexes, prefetch, ALL_PAGES all reused)

GREEN, RED, YEL, DIM, RST = OT.GREEN, OT.RED, OT.YEL, OT.DIM, OT.RST
LIMIT_N_RE = re.compile(r"""\.limit\(\s*(\d+)""")


VOLATILE_RE = re.compile(r"\bnow\(\)|\bcurrent_(?:date|time|timestamp)\b|\bclock_timestamp\(\)|"
                         r"\btimeofday\(\)|\brandom\(\)", re.I)


def volatile_columns(relation):
    """Output columns of a VIEW whose expression depends on the clock (or random()).

    Parsed from `pg_get_viewdef(..., true)`, which pretty-prints one output column per line as
    `<expr> AS <name>`. A column whose expression mentions now() is SUPPOSED to change between two
    reads, so excluding it is what separates "the rows changed" from "time passed".
    """
    try:
        rows = OT.psql("select coalesce(pg_get_viewdef('public.%s'::regclass, true), '')" % relation)
    except SystemExit:
        return set()
    if not rows:
        return set()
    body = " ".join(r[0] for r in rows if r and r[0])
    out = set()
    for line in body.replace(",", ",\n").splitlines():
        if VOLATILE_RE.search(line):
            # the trailing comma survives the split, so the alias is not at end-of-line: matching
            # `AS <name>$` found nothing at all on v_ai_reports_truth, whose hours_since_generated is
            # exactly the column this function exists to find.
            m = re.search(r"\bAS\s+([a-zA-Z0-9_]+)\s*,?\s*$", line.strip(), re.I)
            if m:
                out.add(m.group(1))
    return out


def digest(relation, orders, limit, exclude=None):
    """One psql invocation -> md5 of the ordered projection, or None if the query is not runnable.

    `exclude` drops named columns from the projection, which is how a clock-relative column is taken out
    of the comparison without pretending it does not exist.
    """
    order_sql = ", ".join('"%s"' % c for c in orders) if orders else "1"
    lim = ("limit %d" % limit) if limit else ""
    if exclude:
        # WRAPPED, because this helper can raise and it sits on a DIAGNOSTIC path. Unwrapped, one failing
        # projection lookup aborted the entire 22-page sweep with a bare "psql failed:" - a diagnostic
        # that takes the whole measurement down with it is worse than one that degrades.
        try:
            cols = OT.psql(
                "select string_agg(quote_ident(a.attname), ', ' order by a.attnum) "
                "from pg_attribute a join pg_class c on c.oid = a.attrelid "
                "join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public' "
                "where c.relname = %s and a.attnum > 0 and not a.attisdropped "
                "and a.attname::text <> all(%s::text[])"
                % (OT.sql_lit(relation),
                   "array[" + ",".join(OT.sql_lit(c) for c in sorted(exclude)) + "]"))
            proj = cols[0][0] if cols and cols[0] and cols[0][0] else "*"
        except SystemExit:
            proj = "*"          # degrade to the full projection rather than abort the sweep
    else:
        proj = "*"
    sql = ("select coalesce(md5(string_agg(t::text, '|')), 'EMPTY') from "
           "(select %s from public.%s order by %s %s) t" % (proj, '"%s"' % relation, order_sql, lim))
    try:
        rows = OT.psql(sql)
    except SystemExit:
        return None
    return rows[0][0] if rows and rows[0] else None


def analyse(page):
    path = os.path.join(ROOT, page + ".html")
    if not os.path.exists(path):
        raise SystemExit("no such page file: %s" % path)
    src = open(path, encoding="utf-8").read()
    side = os.path.join(ROOT, page + ".js")
    if os.path.exists(side):
        src += "\n" + open(side, encoding="utf-8").read()

    OT.prefetch_unique_columns()
    seen, out = set(), []
    for m in OT.READ_RE.finditer(src):
        rel, tail = m.group(1), m.group(2)
        orders = OT.ORDER_RE.findall(tail)
        if not orders:
            continue                      # no order => nothing stable to compare; that is the OTHER tool's finding
        lm = LIMIT_N_RE.search(tail)
        limit = int(lm.group(1)) if lm else None
        key = (rel, tuple(orders), limit)
        if key in seen:
            continue
        seen.add(key)
        kind, uniq = OT.unique_columns(rel)
        if kind is None:
            continue
        a = digest(rel, orders, limit)
        b = digest(rel, orders, limit)     # SECOND connection: a real repeat, not a self-comparison
        # NON-VACUITY CONTROL. Two identical SELECTs against a database nobody is writing to will match
        # almost by definition, so "idempotent" on its own is a pass that cost nothing and proves nothing
        # (the metamorphic-relation trap: a relation with no demonstrated sensitivity is decoration).
        # The digest must therefore be shown to MOVE when the result set genuinely differs: the same
        # projection over one fewer row must produce a different hash. If it does not, the instrument is
        # blind and the reading is refused rather than reported.
        sensitive = None
        if a and a != "EMPTY":
            # THE CONTROL PROVES THE DIGEST RESPONDS TO CONTENT - it does NOT need to perturb the read's
            # own limit, and trying to was wrong twice. `limit - 1` compares a `.limit(1)` read with
            # itself; and worse, a limit ABOVE the relation's size makes limit and limit-1 return the
            # same rows, so hive_members (18 rows, .limit(500)), equipment_reading_templates (15, 500)
            # and pm_completions (1591, 2000) were all reported control-failed while the digest was
            # demonstrably sensitive. Comparing ONE row against TWO on the same relation and order
            # settles sensitivity independently of whatever cap the page happens to use.
            one, two = digest(rel, orders, 1), digest(rel, orders, 2)
            if one is not None and two is not None:
                sensitive = (one != two)
                if one == two:
                    # only legitimate when the relation cannot supply two distinct rows
                    sensitive = False
        if sensitive is False:
            out.append({"relation": rel, "orders": orders, "limit": limit,
                        "verdict": "control-failed",
                        "detail": ("one row and two rows of this relation hashed IDENTICALLY, so the "
                                   "digest cannot distinguish two different answers here and the reading "
                                   "is refused rather than reported as idempotent. The honest reading is "
                                   "that the relation cannot supply two distinct rows under this order")})
            continue
        if a is None or b is None:
            out.append({"relation": rel, "orders": orders, "limit": limit,
                        "verdict": "unknown",
                        "detail": "the query could not be executed (a named column may not exist here)"})
        elif a == b:
            out.append({"relation": rel, "orders": orders, "limit": limit, "digest": a[:12],
                        "control_sensitive": sensitive,
                        "verdict": "idempotent" if sensitive else "idempotent-uncontrolled",
                        "detail": ("two separate connections returned the same md5 over the full ordered "
                                   "projection, and the digest was PROVEN sensitive on this relation (one "
                                   "row and two rows hash differently)" if sensitive else
                                   "two connections agreed, but sensitivity could not be demonstrated%s "
                                   "- recorded as uncontrolled rather than claimed"
                                   % (" (relation is empty)" if a == "EMPTY" else ""))})
        else:
            # A DIFFERENCE IS NOT AUTOMATICALLY A DEFECT, and this is where the first version was wrong.
            # It failed v_ai_reports_truth on hive and report-sender - a real byte difference, but the
            # view exposes `EXTRACT(epoch FROM now() - generated_at) AS hours_since_generated` plus
            # `fresh_24h` / `fresh_8h` derived from now(). Those columns are SUPPOSED to advance; the
            # answer to "how old is this report?" changes by definition. The row SET was identical both
            # times (45 rows, same order). So the question has to be narrowed: did the ROWS change, or
            # only a clock-relative projection of them?
            clock_cols = volatile_columns(rel)
            stable_a = digest(rel, orders, limit, exclude=clock_cols)
            stable_b = digest(rel, orders, limit, exclude=clock_cols)
            if clock_cols and stable_a is not None and stable_a == stable_b:
                out.append({"relation": rel, "orders": orders, "limit": limit,
                            "verdict": "idempotent-modulo-clock", "clock_columns": sorted(clock_cols),
                            "detail": ("the row set is IDENTICAL on repeat once the clock-relative "
                                       "columns are excluded (%s - each derived from now() in the view "
                                       "definition, so they advance by design). Recorded rather than "
                                       "failed: a cached copy of this view WILL disagree with a live "
                                       "read about freshness, and `fresh_24h` is a boolean cliff, but "
                                       "the rows themselves repeat"
                                       % ", ".join(sorted(clock_cols))[:90])})
            else:
                out.append({"relation": rel, "orders": orders, "limit": limit,
                            "verdict": "NOT-IDEMPOTENT",
                            "detail": ("two executions of the identical query disagreed: %s vs %s"
                                       % (a[:12], b[:12])
                                       + ("; and it is NOT explained by clock-relative columns - the "
                                          "rows themselves differ" if clock_cols else ""))})
    return out


def render(page, rows):
    print("  %s%s%s — %d repeatable read(s)" % (YEL, page, RST, len(rows)))
    for r in rows:
        colour = GREEN if r["verdict"] == "idempotent" else (RED if r["verdict"] == "NOT-IDEMPOTENT" else YEL)
        print("   %s%-16s%s %-44s %s" % (colour, r["verdict"], RST,
                                         "%s(%s)" % (r["relation"], ",".join(r["orders"])),
                                         r["detail"][:88]))


def gate():
    if not OT.db_up():
        print("  %sSKIP%s — the database is not reachable; read idempotency cannot be measured without it."
              % (YEL, RST))
        return 0
    report, bad, n = {}, 0, 0
    for page in OT.ALL_PAGES:
        try:
            rows = analyse(page)
        except SystemExit as e:
            report[page] = [{"verdict": "ERROR", "detail": str(e)[:140]}]
            continue
        report[page] = rows
        n += len(rows)
        bad += sum(1 for r in rows if r["verdict"] == "NOT-IDEMPOTENT")
    counts = {}
    for rows in report.values():
        for r in rows:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    with open(os.path.join(ROOT, "read_idempotency_report.json"), "w", encoding="utf-8") as fh:
        json.dump({"counts": counts, "pages": report}, fh, indent=1)
    print("  Read idempotency — %d repeatable reads across %d pages" % (n, len(OT.ALL_PAGES)))
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print("    %-18s %d" % (k, v))
    if bad:
        print("\n  %sFAIL%s — %d read(s) returned different bytes on a repeat:" % (RED, RST, bad))
        for page, rows in report.items():
            for r in rows:
                if r["verdict"] == "NOT-IDEMPOTENT":
                    print("    %-19s %s(%s) — %s" % (page, r["relation"], ",".join(r["orders"]),
                                                     r["detail"][:80]))
        return 1
    print("\n  %sPASS%s — every repeatable read returned identical bytes across two separate connections."
          % (GREEN, RST))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("page", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args(argv)
    if a.gate:
        return gate()
    if not a.page:
        ap.error("give a page, or --gate to sweep all of them")
    rows = analyse(a.page)
    if a.json:
        print(json.dumps(rows, indent=1))
        return 0
    render(a.page, rows)
    bad = [r for r in rows if r["verdict"] == "NOT-IDEMPOTENT"]
    print("\n  %d idempotent · %s%d NOT-IDEMPOTENT%s · %d unknown"
          % (sum(1 for r in rows if r["verdict"] == "idempotent"),
             RED if bad else DIM, len(bad), RST,
             sum(1 for r in rows if r["verdict"] == "unknown")))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
