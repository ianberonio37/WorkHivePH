# -*- coding: utf-8 -*-
"""Does a quantity carry its UNIT where it crosses the DB boundary?

THE ORACLE, verbatim from the registry: "the value carries its unit at the boundary (pesos vs credits vs
percent vs whole-percent) - the class that made a knob of 10 mean 1000%". So this is not a naming-style
check. It hunts one specific, expensive confusion: a number whose unit is decided by convention rather
than declared, where two callers can disagree about the scale and nothing errors.

TWO QUESTIONS PER COLUMN, and the second is the one with teeth:

  1. IS THE UNIT DECLARED? A quantity column is declared if the schema pins its meaning: a CHECK that
     bounds its range (`pct between 0 and 100` says whole-percent out loud), a column COMMENT naming the
     unit, a sibling unit column in the same table (`unit`, `uom`, `currency`), or a name that carries the
     unit itself (`..._pct`, `..._hours`, `..._days`, `..._minutes`, `..._php`). Nothing else counts,
     because "everyone knows it's a percentage" is precisely the assumption that made a knob of 10 mean
     1000%.

  2. DO THE STORED VALUES AGREE WITH ONE SCALE? Asked in SQL, per column: a percent-ish column holding
     values in (0,1] AND values > 1 is storing fractions and whole percents in the same place - two
     callers reading one column under two conventions. That is the defect itself rather than a smell, and
     it is reported as MIXED-SCALE. A column whose values are all > 1 is whole-percent; all <= 1 is a
     fraction; either is fine ONCE DECLARED, and the pairing of question 1 with question 2 is what makes
     the verdict actionable instead of stylistic.

WHY THE EMPIRICAL HALF MATTERS. A schema check alone would pass a column that is bounded 0..100 but holds
0.85 in half its rows through a path that bypassed the constraint (added later, NOT VALIDATED). Asking the
data as well as the catalog is the difference between "the declaration exists" and "the declaration holds".

Needs psql only - no browser, no REST gateway.

    python tools/prove_units_at_boundary.py [--gate] [--json]
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import prove_order_totality as OT  # noqa: E402  (psql + db_up reused; one connection helper, not two)

GREEN, RED, YEL, DIM, RST = OT.GREEN, OT.RED, OT.YEL, OT.DIM, OT.RST

# Columns whose unit is decided by CONVENTION unless something declares it. Deliberately narrow: this is
# the pesos/credits/percent/whole-percent family the oracle names, not every numeric column in the schema.
PERCENTISH = re.compile(r"(?:^|_)(pct|percent|percentage|rate|ratio|share|compliance|utilisation|"
                        r"utilization|availability|quality|oee)(?:_|$)", re.I)
# TIGHTENED AFTER READING THE FIRST RUN'S OUTPUT. `total` alone matched total_tokens, total_chunks and
# xp_total - counts of tokens, chunks and points, none of them money - so bare `total` and `value` are
# gone and money must be named by a currency word or paired with an amount word.
MONEYISH = re.compile(r"(?:^|_)(price|cost|balance|fee|budget|credits?|php|peso|usd)(?:_|$)"
                      r"|(?:^|_)(?:total|sub)_?(?:amount|price|cost|due|paid)(?:_|$)"
                      r"|(?:^|_)amount(?:_|$)", re.I)
# `min` was the worst offender: it matched min_chars (a character count) and reward_min_per_listing (a
# MINIMUM, not minutes). Minutes must be spelled minute/minutes/mins, never a bare `min`.
TIMEISH = re.compile(r"(?:^|_)(duration|hours?|days?|minutes?|mins|seconds?|secs?|mtbf|mttr|downtime|"
                     r"uptime|interval|age|ms)(?:_|$)", re.I)
# A name that carries its unit ANYWHERE needs nothing else: `hours_worked`, `days_to_failure`,
# `duration_ms`, `day_count` and `minute_count` are all self-declaring, and a SUFFIX-only test called
# every one of them undeclared. The unit token may lead, trail or sit in the middle.
SELF_DECLARING = re.compile(r"(?:^|_)(pct|percent|percentage|hours?|days?|minutes?|mins|seconds?|secs?|"
                            r"ms|millis|milliseconds?|php|usd|credits?|kg|grams?|litres?|liters?|pcs|"
                            r"units?|metres?|meters?|chars?|tokens?|chunks?|bytes?|rows?|count)(?:_|$)",
                            re.I)
UNIT_SIBLINGS = {"unit", "units", "uom", "unit_of_measure", "currency", "currency_code", "unit_type",
                 "measure", "measure_unit", "scale"}


def numeric_columns():
    rows = OT.psql("""
        select c.relname, a.attname, format_type(a.atttypid, a.atttypmod),
               coalesce(col_description(c.oid, a.attnum), ''),
               c.relkind::text
          from pg_class c
          join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
          join pg_attribute a on a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped
         where c.relkind in ('r', 'p')
           and format_type(a.atttypid, a.atttypmod) ~
               '^(numeric|decimal|real|double precision|integer|bigint|smallint)'
         order by c.relname, a.attname
    """)
    return [r for r in rows if len(r) >= 5]


def checks_by_table():
    out = {}
    for r in OT.psql("""
        select c.relname, pg_get_constraintdef(con.oid)
          from pg_constraint con
          join pg_class c on c.oid = con.conrelid
          join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
         where con.contype = 'c'
    """):
        if len(r) >= 2:
            out.setdefault(r[0], []).append(r[1])
    return out


def columns_by_table(cols):
    out = {}
    for rel, col, typ, comment, kind in cols:
        out.setdefault(rel, set()).add(col)
    return out


def value_scale(rel, col):
    """-> (n_nonnull, n_fraction, n_gt_one, max) or None. The empirical half of the oracle.

    ★FRACTION EVIDENCE IS THE OPEN INTERVAL (0,1), not (0,1] (2026-08-31). The original filter
    counted a value of EXACTLY 1 as fraction-scale evidence and produced a false MIXED-SCALE
    accusation against hive_readiness.data_quality_score: its producer provably writes integer
    points 0-100 (LEAST(100, ...)::int), and the flagged '1' was a legitimate 1-point score on a
    hive whose fixture data is older than the 30-day window. A value of exactly 1 is valid in BOTH
    scales (1% whole, or 100% as a fraction) and therefore proves nothing alone — while every value
    strictly inside (0,1) is non-integer and CAN only be a fraction. The oracle must decline what
    it cannot know rather than guess (its own stated rule)."""
    try:
        rows = OT.psql("""select count(%s), count(*) filter (where %s > 0 and %s < 1),
                                 count(*) filter (where %s > 1), coalesce(max(%s), 0)
                            from public.%s""" % ('"%s"' % col, '"%s"' % col, '"%s"' % col,
                                                 '"%s"' % col, '"%s"' % col, '"%s"' % rel))
    except SystemExit:
        return None
    if not rows or len(rows[0]) < 4:
        return None
    try:
        return tuple(float(x) for x in rows[0][:4])
    except ValueError:
        return None


def analyse():
    OT.psql("select 1")
    cols = numeric_columns()
    checks = checks_by_table()
    tbl_cols = columns_by_table(cols)
    results = []
    for rel, col, typ, comment, kind in cols:
        fam = ("percent" if PERCENTISH.search(col) else
               "money" if MONEYISH.search(col) else
               "time" if TIMEISH.search(col) else None)
        if not fam:
            continue
        self_declared = bool(SELF_DECLARING.search(col))
        sibling = sorted(UNIT_SIBLINGS & tbl_cols.get(rel, set()))
        col_checks = [c for c in checks.get(rel, []) if re.search(r'\b%s\b' % re.escape(col), c)]
        commented = bool(comment.strip())
        declared_by = []
        if self_declared:
            declared_by.append("its own name")
        if col_checks:
            declared_by.append("a CHECK (%s)" % col_checks[0][:60])
        if commented:
            declared_by.append("a column comment")
        if sibling:
            declared_by.append("a sibling unit column (%s)" % ",".join(sibling))

        # EXPOSURE IS ASKED FOR EVERY FAMILY, not just percent, because "undeclared" means something very
        # different for an empty column than for a populated one. Of the seven undeclared columns in the
        # first honest run, six held 0 rows (or 12 identical values) - a LATENT ambiguity a future writer
        # will resolve by guessing - while service_credit_ledger.amount held real money-or-credits data.
        # Ranking them equally would bury the one that is already exposed.
        scale = value_scale(rel, col)
        mixed = bool(scale and fam == "percent" and scale[1] > 0 and scale[2] > 0)
        populated = bool(scale and scale[0] > 0)

        if mixed:
            verdict = "MIXED-SCALE"
            detail = ("%d non-integer value(s) in (0,1) AND %d value(s) > 1 in one column (max %g): fractions and "
                      "whole numbers stored together, so two callers can read one column under two "
                      "conventions - the knob-of-10-means-1000%% class, measured rather than suspected"
                      % (scale[1], scale[2], scale[3]))
        elif declared_by:
            verdict = "declared"
            detail = "unit pinned by " + " and ".join(declared_by)
            if scale:
                detail += ("; values all %s" % ("<= 1 (fraction)" if scale[2] == 0 and scale[1] > 0
                                                else "> 1 (whole)" if scale[1] == 0 and scale[2] > 0
                                                else "absent"))
        else:
            verdict = "UNDECLARED" if populated else "undeclared-latent"
            detail = ("a %s quantity with no CHECK, no comment, no sibling unit column and a name that "
                      "does not carry its unit: the scale is convention only" % fam)
            if populated:
                detail += ("; and it IS POPULATED (%d row(s), max %g), so the ambiguity is live rather "
                           "than theoretical" % (scale[0], scale[3]))
            else:
                detail += ("; the column holds NO rows yet, so the ambiguity is LATENT - the first writer "
                           "picks a convention and every later reader inherits the guess")
        results.append({"relation": rel, "column": col, "type": typ, "family": fam,
                        "verdict": verdict, "detail": detail,
                        "declared_by": declared_by, "scale": scale})
    return results


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args(argv)
    if not OT.db_up():
        print("  %sSKIP%s — the database is not reachable; unit declaration is a schema question."
              % (YEL, RST))
        return 0
    res = analyse()
    if a.json:
        print(json.dumps(res, indent=1))
        return 0
    mixed = [r for r in res if r["verdict"] == "MIXED-SCALE"]
    undecl = [r for r in res if r["verdict"] == "UNDECLARED"]
    latent = [r for r in res if r["verdict"] == "undeclared-latent"]
    with open(os.path.join(ROOT, "units_at_boundary_report.json"), "w", encoding="utf-8") as fh:
        json.dump({"counts": {"declared": len(res) - len(mixed) - len(undecl) - len(latent),
                              "UNDECLARED": len(undecl), "undeclared-latent": len(latent),
                              "MIXED-SCALE": len(mixed)},
                   "columns": res}, fh, indent=1)
    print("  Units at the DB boundary — %d unit-bearing quantity columns examined" % len(res))
    print("    %-14s %d\n    %-14s %d\n    %-14s %d"
          % ("declared", len(res) - len(mixed) - len(undecl) - len(latent),
             "UNDECLARED-live", len(undecl), "undecl-latent", len(latent)))
    print("    %-14s %d" % ("MIXED-SCALE", len(mixed)))
    for r in mixed:
        print("   %sMIXED-SCALE%s %s.%s — %s" % (RED, RST, r["relation"], r["column"], r["detail"][:110]))
    for r in undecl[:25]:
        print("   %sUNDECLARED%s  %s.%s (%s) — %s" % (YEL, RST, r["relation"], r["column"],
                                                      r["family"], r["detail"][:88]))
    if len(undecl) > 25:
        print("   %s... %d more UNDECLARED (see units_at_boundary_report.json)%s"
              % (DIM, len(undecl) - 25, RST))
    if mixed:
        print("\n  %sFAIL%s — %d column(s) store two scales at once." % (RED, RST, len(mixed)))
        return 1
    print("\n  %s%s%s — no column mixes two scales; %d carry their unit only by convention and are "
          "reported, not failed." % (GREEN, "PASS" if not undecl else "PASS (with debt)", RST, len(undecl)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
