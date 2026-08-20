# -*- coding: utf-8 -*-
"""Does NULL mean the same thing on both sides of the trigger->view seam?

The oracle names its own defect: *"NULL meant 'no cap' in the DB and arrived as a cap of ZERO in the
client."* A view that wraps an output column in COALESCE is the DB-side half of exactly that — the
substituted value crosses the boundary wearing the same clothes as a real one, and no error is raised.

WHAT MAKES THIS HARD TO MEASURE HONESTLY: most COALESCEs in this schema are correct, and a tool that
flags them all is worse than no tool. `COALESCE(count(x), 0)` is not a defect — for a COUNT, "no rows"
and "zero" are THE SAME FACT, and the coalesce only spells out what SQL already means. So the verdict
turns on the pair (what is substituted, what it is substituted FOR):

  absence-equals-zero   count()/sum() defaulted to 0 - absence IS zero. SAFE, and the largest bucket.
  collapses-nonadditive avg()/min()/max() defaulted to 0 - "no average" is NOT "an average of zero".
                        A rating of 0.0 and no ratings at all are opposite claims about a seller.
  invents-now           a timestamp defaulted to now() - absence becomes the FRESHEST POSSIBLE instant,
                        the single most misleading substitution available, and it changes per read
                        (which also makes the view non-idempotent - see prove_read_idempotency.py).
  invents-constant      a non-zero constant, e.g. a missing 0-100 risk score read as 50 - absence
                        becomes an assumed AVERAGE, and the composite never says so.
  collapses-to-legal    a plain nullable column defaulted to 0/''/false, where that value is legal -
                        the reward-cap class verbatim.
  fallback-to-sibling   defaulted to ANOTHER COLUMN, not a synthesized value - the distinction may
                        survive in the sibling, so this is reported, not failed.
  sentinel              defaulted to a marker outside the legal range ('_', 'unknown') - a reader can
                        still tell. Reported.

TWO THINGS THIS TOOL REFUSES TO DO.

It does not trust its own reading of the text. The viewdef is a LOCATOR; every located column is then
confirmed against the running database - `count(*) - count(col)` over the view must be 0, or the text
said "coalesced" about something that still emits NULL and the reading was wrong. A gate that parses
text and never asks the DB is how a false green ships.

It does not report a latent risk as a live defect. A collapse only harms someone if a NULL is actually
there, so for every flagged column whose source resolves to a base table the base is counted:
  live    - rows exist with NULL in the source right now; a reader is being misinformed today
  latent  - the collapse is real but no row has triggered it; the FIRST such row inherits it silently
Written after checking four textually-alarming candidates by hand (`skill_knowledge.updated_at`,
`automation_log.triggered_at`, `fault_knowledge`, `amc_briefings`) and finding ALL FOUR at zero NULLs.
Banked from the text alone they would have been four manufactured live findings.

    python tools/prove_null_semantics.py            # human report
    python tools/prove_null_semantics.py --gate     # exit 1 on a LIVE collapse
    python tools/prove_null_semantics.py --json
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "null_semantics_report.json")
GREEN, RED, YEL, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"

DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
      "-At", "-F", "\x1f"]

SAFE = {"absence-equals-zero", "preserved", "sentinel", "fallback-to-sibling"}
DEFECT = {"collapses-nonadditive", "invents-now", "invents-constant", "collapses-to-legal"}


def q(sql):
    p = subprocess.run(DB + ["-c", sql], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0:
        return None
    return [ln.split("\x1f") for ln in p.stdout.strip().splitlines() if ln.strip()]


def db_up():
    return q("SELECT 1") is not None


# ── LOCATING A COALESCE THAT IS ACTUALLY A BOUNDARY VALUE ────────────────────────────────────────
# A balanced-paren scan, NOT a fixed character window. The order-totality prover shipped a window that
# swallowed the next query's `.limit(` and reported 11 false NON-TOTALs on one page; a nested
# COALESCE(a, COALESCE(b, 0)) would break a window the same way.
def balanced(text, start):
    """start is the index of the '(' after COALESCE. Returns (inner, index_after_close)."""
    depth, i, q1, q2 = 0, start, False, False
    while i < len(text):
        c = text[i]
        if q1:
            q1 = c != "'"
        elif q2:
            q2 = c != '"'
        elif c == "'":
            q1 = True
        elif c == '"':
            q2 = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    return None, len(text)


def split_args(inner):
    out, depth, cur, q1 = [], 0, [], False
    for c in inner:
        if q1:
            cur.append(c)
            q1 = c != "'"
            continue
        if c == "'":
            q1 = True
            cur.append(c)
        elif c == "(":
            depth += 1
            cur.append(c)
        elif c == ")":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
    if cur:
        out.append("".join(cur).strip())
    return out


AS_RE = re.compile(r"""^\s*AS\s+"?([A-Za-z_][A-Za-z0-9_]*)"?""", re.I)
NUM_RE = re.compile(r"""^\(?\s*(-?\d+(?:\.\d+)?)\s*\)?(?:::[a-z ]+)?$""", re.I)
STR_RE = re.compile(r"""^'([^']*)'(?:::[a-z ]+)?$""", re.I)
COLREF_RE = re.compile(r"""^([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)$""")
AGG_RE = re.compile(r"""^(count|sum|avg|min|max|array_agg|jsonb_agg|string_agg)\s*\(""", re.I)
ALIAS_RE = re.compile(r"""\b(?:FROM|JOIN)\s+(?:LATERAL\s+)?([a-z_][a-z0-9_]*)\s+(?!ON\b|USING\b|WHERE\b|GROUP\b|ORDER\b|LEFT\b|RIGHT\b|INNER\b|JOIN\b|CROSS\b|LIMIT\b|UNION\b)([a-z_][a-z0-9_]*)\b""", re.I)


AGG_START_RE = re.compile(r"\b(count|sum|avg|min|max)\s*\(", re.I)
POST_AGG_RE = re.compile(r"""^\s*(?:FILTER\s*\()?""", re.I)


def agg_output_cols(ddl):
    """{output_column: aggregate_fn} for every `<agg>(...) [FILTER (...)][::cast] AS <col>` in the DDL.

    Balanced-scanned for the same reason the COALESCE locator is: a regex with a bounded inner-paren
    allowance missed `count(*) FILTER (WHERE visibility = 'public') AS public_posts` (a FILTER clause
    sits between the paren and the AS) and `sum(COALESCE(logbook.downtime_hours, (0)::numeric)) AS
    total_downtime_hours_30d` (two levels of nesting). Both were then reported as unsafe collapses
    when they are counts, which is the safe case.
    """
    out = {}
    for m in AGG_START_RE.finditer(ddl):
        fn = m.group(1).lower()
        _, after = balanced(ddl, m.end() - 1)
        rest = ddl[after:]
        fm = re.match(r"""^\s*FILTER\s*\(""", rest, re.I)
        if fm:
            _, a2 = balanced(rest, fm.end() - 1)
            rest = rest[a2:]
        rest = re.sub(r"""^\s*(?:::[a-z ]+)?""", "", rest, count=1, flags=re.I)
        am = AS_RE.match(rest)
        if am:
            out[am.group(1)] = fn
    return out


def classify_default(d):
    if re.match(r"^now\(\)$|^CURRENT_TIMESTAMP", d, re.I):
        return "now", "now()"
    m = NUM_RE.match(d)
    if m:
        return ("zero" if float(m.group(1)) == 0 else "constant"), m.group(1)
    m = STR_RE.match(d)
    if m:
        return ("empty-string" if m.group(1) == "" else "marker"), "'%s'" % m.group(1)
    if re.match(r"^(true|false)$", d, re.I):
        return "boolean", d.lower()
    if re.match(r"^'\{\}'::jsonb$|^'\[\]'::jsonb$", d, re.I):
        return "empty-json", d
    if COLREF_RE.match(d) or re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", d):
        return "sibling-column", d
    return "expression", d[:40]


def classify_source(s):
    m = AGG_RE.match(s)
    if m:
        fn = m.group(1).lower()
        return ("aggregate-additive" if fn in ("count", "sum") else "aggregate-nonadditive"), fn
    if "->>" in s or "->" in s:
        return "json-extract", None
    m = COLREF_RE.match(s)
    if m:
        return "column-ref", m.groups()
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", s):
        return "column-ref", (None, s)
    return "expression", None


def verdict_for(dkind, skind):
    if dkind == "sibling-column":
        return "fallback-to-sibling"
    if dkind == "marker":
        return "sentinel"
    if dkind == "now":
        return "invents-now"
    if dkind == "constant":
        return "invents-constant"
    if dkind in ("zero", "empty-string", "boolean", "empty-json"):
        if skind == "aggregate-additive" and dkind == "zero":
            return "absence-equals-zero"
        if skind == "aggregate-nonadditive":
            return "collapses-nonadditive"
        return "collapses-to-legal"
    return "sentinel"


def collect():
    # A VIEWDEF IS MULTI-LINE AND THE ROW SPLITTER IS LINE-BASED. Selecting `definition` raw made every
    # line of every view its own pseudo-row, so the locator found 0 COALESCEs where a hand-run psql
    # regex had found 45 - a tool reporting a clean bill of health because its input was shredded.
    # Collapse the whitespace in SQL so one view is one line.
    views = q("SELECT viewname, regexp_replace(definition, '\\s+', ' ', 'g') FROM pg_views "
              "WHERE schemaname='public' ORDER BY viewname")
    if views is None:
        return None
    base_tables = {r[0] for r in (q("SELECT tablename FROM pg_tables WHERE schemaname='public'") or [])}
    findings, nested, aliases_of = [], 0, {}
    for row in views:
        if len(row) < 2:
            continue
        vname, ddl = row[0], row[1]
        aliases = {a.lower(): rel.lower() for rel, a in ALIAS_RE.findall(ddl)}
        aliases_of[vname] = aliases
        aggs = agg_output_cols(ddl)
        for rel in base_tables:                       # an unaliased relation is its own alias
            aliases.setdefault(rel, rel)
        i = 0
        low = ddl.lower()
        while True:
            j = low.find("coalesce(", i)
            if j < 0:
                break
            inner, after = balanced(ddl, j + len("coalesce"))
            i = j + 9
            if inner is None:
                continue
            m = AS_RE.match(ddl[after:])
            if not m:
                nested += 1                            # a predicate/ORDER BY/CASE arm, not a boundary
                continue
            args = split_args(inner)
            if len(args) < 2:
                continue
            dkind, dval = classify_default(args[-1])
            skind, sinfo = classify_source(args[0])
            # ── AN AGGREGATE COMPUTED IN A CTE IS STILL AN AGGREGATE ─────────────────────────────
            # First cut called 23 columns `collapses-to-legal`, and most were LEFT JOINs onto a
            # counting subquery: `COALESCE(post_stats.total_posts, 0)`. The NULL there means "this
            # worker matched no rows in post_stats", which for a count IS zero - the safe case the
            # tool exists to separate out. It only looked unsafe because the count() sits in a CTE,
            # so the COALESCE's first argument is a column reference rather than `count(...)`. So
            # when the source alias is not a base table, ask how that column is DEFINED upstream.
            unresolved = skind == "column-ref" and sinfo and \
                (aliases.get((sinfo[0] or "").lower()) not in base_tables)
            if unresolved and sinfo[1]:
                fn = aggs.get(sinfo[1])
                if fn:
                    skind = ("aggregate-additive" if fn in ("count", "sum")
                             else "aggregate-nonadditive")
                    sinfo = None
            base = (aliases.get((sinfo[0] or "").lower())
                    if skind == "column-ref" and sinfo else None)
            findings.append({
                "view": vname, "column": m.group(1),
                "source": args[0][:90], "default": dval, "default_raw": args[-1],
                "default_kind": dkind, "source_kind": skind,
                "verdict": verdict_for(dkind, skind),
                "base": base if base in base_tables else None,
                "base_column": (sinfo[1] if skind == "column-ref" and sinfo else None),
                # EVERY non-default argument, because a 4-arg COALESCE only reaches its default when
                # ALL the siblings are NULL - see confirm().
                "fallbacks": args[:-1],
                "sole_table": (sorted({v for v in aliases.values() if v in base_tables})[0]
                               if len({v for v in aliases.values() if v in base_tables}) == 1
                               else None),
                "exposure": None, "nulls_emitted": None,
            })
    return findings, nested, base_tables, aliases_of


def confirm(findings, base_tables, aliases_of):
    """The DB, not the text, decides. Two questions per flagged column."""
    # (1) DOES THE VIEW REALLY EMIT NO NULL THERE? If it does emit NULLs, my reading of the text was
    #     wrong about this being the output path, and the row is dropped rather than reported.
    by_view = collections.defaultdict(list)
    for f in findings:
        by_view[f["view"]].append(f)
    for vname, fs in by_view.items():
        cols = sorted({f["column"] for f in fs})
        sel = ", ".join("count(*) - count(%s)" % c for c in cols)
        r = q("SELECT %s FROM %s" % (sel, vname))
        if not r or len(r[0]) != len(cols):
            continue
        got = dict(zip(cols, r[0]))
        for f in fs:
            try:
                f["nulls_emitted"] = int(got.get(f["column"], "0") or 0)
            except ValueError:
                f["nulls_emitted"] = None
    # (2) IS THE COLLAPSE LIVE? A COALESCE reaches its default only when EVERY fallback before it is
    #     NULL. The first cut tested the FIRST argument alone and so reported
    #     `COALESCE(knowledge, problem, action, '')` as a LIVE defect on the strength of 43 NULL
    #     `knowledge` values - while rows with all three NULL numbered ZERO, which I had already
    #     measured by hand. One argument tested where three were needed turned a latent risk into a
    #     fabricated live finding, which is the exact failure this whole bank exists to prevent.
    for f in findings:
        if f["verdict"] in SAFE:
            continue
        rel = f["base"] or f["sole_table"]
        if not rel or rel not in base_tables:
            continue
        preds = []
        for arg in f["fallbacks"]:
            m = COLREF_RE.match(arg)
            if m:                                     # alias.column - only usable if it is THIS table
                if (aliases_of.get(f["view"], {}).get(m.group(1).lower()) or m.group(1).lower()) != rel:
                    preds = None
                    break
                preds.append("%s IS NULL" % m.group(2))
            elif re.match(r"^\(?[A-Za-z_][A-Za-z0-9_]*\s*->", arg) or "->>" in arg:
                preds.append("(%s) IS NULL" % arg)    # a jsonb path on this table's own column
            elif re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", arg):
                preds.append("%s IS NULL" % arg)
            else:
                preds = None
                break
        if not preds:
            f["exposure"] = "unresolved-source"
            continue
        r = q("SELECT count(*) FILTER (WHERE %s), count(*) FROM %s" % (" AND ".join(preds), rel))
        if not r or len(r[0]) < 2:
            f["exposure"] = "unresolved-source"
            continue
        try:
            nulls, total = int(r[0][0]), int(r[0][1])
        except ValueError:
            continue
        f["source_nulls"], f["source_rows"], f["tested"] = nulls, total, " AND ".join(preds)
        f["exposure"] = "live" if nulls > 0 else "latent"
        # ── IS A "MARKER" DEFAULT ACTUALLY A LEGAL VALUE? ─────────────────────────────────────────
        # `COALESCE(severity, 'info')` looks like a sentinel until you notice 'info' is a real
        # severity the column already stores - at which point a missing severity arrives wearing a
        # genuine one and no reader can tell. The data answers this, so ask it rather than guess.
        if f["default_kind"] == "marker" and f["base_column"]:
            lit = f["default_raw"].split("::")[0]
            r2 = q("SELECT count(*) FROM %s WHERE %s = %s" % (rel, f["base_column"], lit))
            if r2 and r2[0][0].isdigit() and int(r2[0][0]) > 0:
                f["verdict"] = "collapses-to-legal"
                f["marker_occurs"] = int(r2[0][0])


def control(base_tables):
    """NON-VACUITY: can this instrument SEE a NULL at all? If every count(*)-count(col) in the schema
    came back 0 because the query shape is wrong, every verdict above would read as 'coalesced' and the
    tool would agree with itself forever. So find one view column that DOES emit NULL."""
    r = q("SELECT viewname FROM pg_views WHERE schemaname='public' ORDER BY viewname")
    for (vname,) in [(x[0],) for x in (r or [])][:40]:
        cols = q("SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
                 "AND table_name='%s' ORDER BY ordinal_position LIMIT 25" % vname)
        if not cols:
            continue
        names = [c[0] for c in cols]
        sel = ", ".join("count(*) - count(%s)" % c for c in names)
        got = q("SELECT %s FROM %s" % (sel, vname))
        if not got:
            continue
        for name, val in zip(names, got[0]):
            try:
                if int(val) > 0:
                    return {"ok": True, "view": vname, "column": name, "nulls": int(val)}
            except ValueError:
                pass
    return {"ok": False}


# ══ HALF B · THE CLIENT SIDE OF THE SAME SEAM ════════════════════════════════════════════════════
# The oracle's own example is a CLIENT defect: "NULL meant 'no cap' in the DB and arrived as a cap of
# ZERO in the client." Half A proves what the view emits; this proves what the page does with it.
#
# WHY THIS NEEDS A NARROW DEFINITION OR IT IS WORTHLESS: the 22 pages contain 1,557 sites matching
# `x.prop ?? 0` / `x.prop || ''`, and the overwhelming majority are not this defect at all - `opts.icon
# || ''` is a render option, `error.message || ''` is an exception, `target.value || ''` is the DOM,
# `postsRes.count ?? 0` is a PostgREST envelope field. Flagging 1,557 things would bury the handful that
# matter. So a site counts ONLY when all three hold:
#   1. the property IS a column of a relation THIS PAGE READS (from the live catalog, not a word list)
#   2. that column is NULLABLE there - if it is NOT NULL, the default is unreachable defensive code
#   3. the substituted value is LEGAL for the column's type - `next_due_date || ''` puts a non-date in
#      a date's place, which a reader SEES as blank; `xp_total || 0` puts a real, indistinguishable
#      quantity in a missing one's place, which is the defect
PROP_RE = re.compile(r"""([A-Za-z_$][\w$]*)\.([a-z_][a-z0-9_]*)\s*(\?\?|\|\|)\s*"""
                     r"""(0(?![\d.])|0\.0|''|""|false\b|'-'|'—')""")
NUMERIC_T = ("integer", "bigint", "smallint", "numeric", "real", "double precision")
TEXTUAL_T = ("text", "character varying", "character", "citext")


def client_catalog():
    rows = q("SELECT table_name, column_name, is_nullable, data_type FROM information_schema.columns "
             "WHERE table_schema='public'")
    cat = collections.defaultdict(dict)
    for r in rows or []:
        if len(r) >= 4:
            cat[r[1]][r[0]] = (r[2] == "YES", r[3])
    return cat


def page_reads(page):
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ot", os.path.join(ROOT, "tools",
                                                                     "prove_order_totality.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def client_half(cat, pages):
    ot = page_reads(None)
    out = []
    for page in pages:
        html = os.path.join(ROOT, page + ".html")
        if not os.path.exists(html):
            continue
        src = open(html, encoding="utf-8", errors="replace").read()
        side = os.path.join(ROOT, page + ".js")
        if os.path.exists(side):
            src += "\n" + open(side, encoding="utf-8", errors="replace").read()
        rels = {m.group(1) for m in ot.READ_RE.finditer(src)}
        need = collections.defaultdict(set)
        sites = []
        for m in PROP_RE.finditer(src):
            col, op, dflt = m.group(2), m.group(3), m.group(4)
            owners = {r: v for r, v in (cat.get(col) or {}).items() if r in rels}
            if not owners:
                continue                                   # not a column this page reads: not this seam
            nullable = [r for r, (n, _) in owners.items() if n]
            if not nullable:
                verdict, exposure = "not-null-in-db", "unreachable"
            else:
                dtype = owners[nullable[0]][1]
                # ── WHAT THE SUBSTITUTE DOES TO A READER, NOT WHAT TYPE IT IS ────────────────────
                # First cut called 224 sites `collapses-to-legal` on the rule "0 is legal for a number,
                # '' is legal for text". Reading the live ones killed that rule in both directions:
                #   `l.root_cause || ''` renders a BLANK, which is the honest presentation of "not
                #   recorded" - '' is legal for text in the type system and meaningless in the domain,
                #   so nobody stores an empty root cause and no reader is deceived by one.
                #   `(b.downtime_hours || 0) - (a.downtime_hours || 0)` is a SORT COMPARATOR. 0 is the
                #   defined floor for an unrecorded value and nothing is displayed. Both live numeric
                #   sites in the whole roster turned out to be this.
                # So text-to-blank is SAFE, and a numeric/boolean substitute is a CANDIDATE reported
                # with its exposure - not a failure, because this instrument deliberately does not try
                # to decide whether the value is displayed or computed with. Deciding that needs the
                # enclosing expression, and inferring it from backtick counting over inline script is
                # the brittle-validator trap this codebase has already been bitten by (a backtick in a
                # comment once broke a page outright). The candidates are few enough to read by hand,
                # which is the honest division of labour between a tool and a person.
                if dflt in ("0", "0.0") and dtype in NUMERIC_T:
                    verdict = "numeric-substitute"
                elif dflt == "false" and dtype == "boolean":
                    verdict = "boolean-substitute"
                elif dflt in ("''", '""') and dtype in TEXTUAL_T:
                    verdict = "text-blank"
                else:
                    verdict = "visible-placeholder"
                exposure = None
                if verdict in ("numeric-substitute", "boolean-substitute"):
                    need[nullable[0]].add(col)
            sites.append({"page": page, "column": col, "op": op, "default": dflt,
                          "relations": sorted(owners), "nullable_on": sorted(nullable),
                          "data_type": (owners[nullable[0]][1] if nullable else
                                        list(owners.values())[0][1]),
                          "verdict": verdict, "exposure": exposure,
                          "snippet": m.group(0)[:60]})
        # EXPOSURE, BATCHED ONE QUERY PER RELATION - is the NULL actually there?
        live = {}
        for rel, cols in need.items():
            cols = sorted(cols)
            sel = ", ".join("count(*) FILTER (WHERE %s IS NULL)" % c for c in cols)
            r = q("SELECT %s, count(*) FROM %s" % (sel, rel))
            if r and len(r[0]) == len(cols) + 1:
                for c, v in zip(cols, r[0]):
                    try:
                        live[(rel, c)] = (int(v), int(r[0][-1]))
                    except ValueError:
                        pass
        for s in sites:
            if s["verdict"] in ("numeric-substitute", "boolean-substitute") and s["nullable_on"]:
                k = (s["nullable_on"][0], s["column"])
                if k in live:
                    n, tot = live[k]
                    s["source_nulls"], s["source_rows"] = n, tot
                    s["exposure"] = "live" if n > 0 else "latent"
                else:
                    s["exposure"] = "unresolved-source"
        out.extend(sites)
    return out


ALL_PAGES = ["index", "hive", "logbook", "inventory", "pm-scheduler", "project-manager", "dayplanner",
             "asset-hub", "analytics", "alert-hub", "skillmatrix", "shift-brain", "voice-journal",
             "assistant", "community", "public-feed", "achievements", "engineering-design", "resume",
             "report-sender", "project-report", "analytics-report"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if not db_up():
        print("  %sSKIP%s local database not reachable (docker exec supabase_db_workhive)"
              % (YEL, RST))
        return 0

    got = collect()
    if got is None:
        print("  %sSKIP%s could not read pg_views" % (YEL, RST))
        return 0
    findings, nested, base_tables, aliases_of = got
    confirm(findings, base_tables, aliases_of)
    ctl = control(base_tables)

    # A located column the DB says still emits NULL was mis-read by the locator, not a defect.
    misread = [f for f in findings if f["nulls_emitted"]]
    findings = [f for f in findings if not f["nulls_emitted"]]

    counts = collections.Counter(f["verdict"] for f in findings)
    live = [f for f in findings if f["verdict"] in DEFECT and f["exposure"] == "live"]
    latent = [f for f in findings if f["verdict"] in DEFECT and f["exposure"] != "live"]

    csites = client_half(client_catalog(), ALL_PAGES)
    ccounts = collections.Counter(s["verdict"] for s in csites)
    clive = [s for s in csites if s["exposure"] == "live"]

    payload = {"columns": findings, "counts": dict(counts), "nested_not_boundary": nested,
               "control": ctl, "locator_misread": len(misread),
               "live": len(live), "latent": len(latent),
               "client_sites": csites, "client_counts": dict(ccounts), "client_live": len(clive)}
    with open(REPORT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    os.replace(REPORT + ".tmp", REPORT)

    if a.json:
        print(json.dumps(payload, indent=1))
        return 1 if live else 0

    print("  %sNULL SEMANTICS AT THE trigger->view SEAM%s  %d coalesced boundary column(s) in %d views"
          % (DIM, RST, len(findings), len({f["view"] for f in findings})))
    if not ctl.get("ok"):
        print("  %sCONTROL FAILED%s no view column in the schema emits a NULL, so this instrument "
              "cannot demonstrate it can see one. Every verdict below is unproven." % (RED, RST))
    else:
        print("  %scontrol: %s.%s emits %d NULL(s) - the instrument can see a NULL%s"
              % (DIM, ctl["view"], ctl["column"], ctl["nulls"], RST))
    print("  %s%d COALESCE(s) sit in a predicate/ORDER BY/CASE arm - not a boundary value, ignored%s"
          % (DIM, nested, RST))
    if misread:
        print("  %s%d located column(s) still emit NULL live, so the text reading was wrong about "
              "them - dropped rather than reported%s" % (DIM, len(misread), RST))

    print("\n  %sBY VERDICT%s" % (DIM, RST))
    for v, n in counts.most_common():
        mark = GREEN if v in SAFE else RED
        print("    %s%4d  %-22s%s %s" % (mark, n, v, RST,
              "absence and the default are the same fact" if v == "absence-equals-zero" else ""))

    for label, group, colour in (("LIVE", live, RED), ("LATENT", latent, YEL)):
        if not group:
            continue
        print("\n  %s%s%s (%d)" % (colour, label, RST, len(group)))
        for f in sorted(group, key=lambda x: (x["view"], x["column"])):
            src = ("%s.%s %s" % (f["base"], f["base_column"],
                                 "(%d/%d NULL)" % (f.get("source_nulls", 0), f.get("source_rows", 0))
                                 if f.get("source_rows") is not None else "")
                   if f["base"] else f["source"])
            print("    %-22s %s.%-26s <- %s  default %s"
                  % (f["verdict"], f["view"], f["column"], src, f["default"]))

    print("\n  %sCLIENT SIDE OF THE SAME SEAM%s  %d `?? default` site(s) that are genuinely a "
          "nullable column this page reads" % (DIM, RST, len(csites)))
    for v, n in ccounts.most_common():
        print("    %s%4d  %-22s%s %s" % (YEL if v.endswith("-substitute") else GREEN, n, v, RST,
              {"not-null-in-db": "the column is NOT NULL, so the default is unreachable",
               "text-blank": "'' renders as a BLANK - the honest presentation of 'not recorded'",
               "numeric-substitute": "CANDIDATE: read each by hand - displayed, or a sort/arithmetic identity?",
               "visible-placeholder": "the substitute is not a legal value of the type - a reader sees "
                                      "a blank, not a number"}.get(v, "")))
    risky_c = [s for s in csites if s["verdict"] in ("numeric-substitute",
                                                     "boolean-substitute")]
    if risky_c:
        for s in sorted(risky_c, key=lambda x: (x["exposure"] != "live", x["page"], x["column"]))[:24]:
            print("    %-6s %-19s %-40s %s.%s %s"
                  % (s["exposure"] or "?", s["page"], s["snippet"], s["nullable_on"][0], s["column"],
                     ("(%d/%d NULL)" % (s.get("source_nulls", 0), s.get("source_rows", 0)))
                     if s.get("source_rows") is not None else ""))

    print("\n  wrote %s" % os.path.relpath(REPORT, ROOT))
    if a.gate:
        if not ctl.get("ok"):
            print("  %sFAIL%s the non-vacuity control failed" % (RED, RST))
            return 1
        if live:
            print("  %sFAIL%s %d view boundary column(s) collapse a NULL that is present "
                  "RIGHT NOW" % (RED, RST, len(live)))
            return 1
        print("  %sPASS%s no view boundary column collapses a NULL that exists today (%d latent). "
              "%d client numeric/boolean substitute(s) are reported as CANDIDATES, not failed - this "
              "instrument does not adjudicate displayed-vs-computed, and every live one read by hand "
              "so far was a sort comparator." % (GREEN, RST, len(latent), len(risky_c)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
