# -*- coding: utf-8 -*-
"""Does every field name a page uses still exist on the relation it uses it against?

The CB `name_survives` oracle: *"the field keeps its name and meaning across the seam; a rename on one
side that the other still reads by the old name is a silent null."* That is a real and quiet failure
shape on this stack, and it fails differently depending on where the stale name sits:

  in a .select() list   PostgREST 400s the whole request, so ONE stale name blanks an entire panel
  in an .eq()/.order()  same - the request 400s and the surface shows an error or an empty state
  in an .insert()/.update() object   the write 400s, so a capture silently fails
  in `row.old_name` after .select('*')   NOTHING errors: the property is `undefined`, and combined
                                        with `?? 0` or `|| ''` it renders as a real value

Every name is checked against the LIVE CATALOG (information_schema.columns), never against a hand-kept
list, because a hand-kept list is a second source of truth that drifts from the schema it describes.

SCOPE, STATED SO A PASS IS NOT OVER-READ. This proves the names a page uses in a query it BUILDS as a
literal. Three things are deliberately out of scope and reported as counts rather than silently dropped:
select lists built by string concatenation (the name is not in the source to check), PostgREST embedded
resources (`other_table!fk(cols)`, whose inner columns belong to the embedded relation), and bare
`row.property` reads after `.select('*')` — that last one is the silent case above, and catching it needs
the property-to-relation resolution that prove_null_semantics.py's client half does. Named here so the
gap is visible.

NON-VACUITY CONTROL: a name known NOT to exist is injected into the checker and must be caught. Without
it, a matcher whose regex silently matched nothing would report "0 stale names" over 0 names checked and
look identical to a clean bill of health.

    python tools/prove_field_names_survive.py            # human report
    python tools/prove_field_names_survive.py --gate     # exit 1 if any name is stale
    python tools/prove_field_names_survive.py --json
"""
import argparse
import collections
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "field_names_report.json")
GREEN, RED, YEL, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
      "-At", "-F", "\x1f"]

ALL_PAGES = ["index", "hive", "logbook", "inventory", "pm-scheduler", "project-manager", "dayplanner",
             "asset-hub", "analytics", "alert-hub", "skillmatrix", "shift-brain", "voice-journal",
             "assistant", "community", "public-feed", "achievements", "engineering-design", "resume",
             "report-sender", "project-report", "analytics-report"]

# `.from('x')` then `.select(...)`, allowing a newline and chained calls between them.
SELECT_RE = re.compile(r"""\.from\(\s*['"]([a-z_0-9]+)['"]\s*\)\s*\n?\s*\.select\(\s*[`'"]([^`'"]{0,900})[`'"]""")
# A filter/order call anywhere inside the same `.from(...)` chain, bounded by the next `.from(` or `;`.
CHAIN_RE = re.compile(r"""\.from\(\s*['"]([a-z_0-9]+)['"]\s*\)(.{0,1200}?)(?=;|\.from\(|$)""", re.S)
FILTER_RE = re.compile(r"""\.(?:eq|neq|gt|gte|lt|lte|like|ilike|is|in|contains|order)\(\s*['"]([a-z_][a-z0-9_]*)['"]""")
IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def q(sql):
    p = subprocess.run(DB + ["-c", sql], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0:
        return None
    return [ln.split("\x1f") for ln in p.stdout.strip().splitlines() if ln.strip()]


def catalog():
    rows = q("SELECT table_name, column_name FROM information_schema.columns "
             "WHERE table_schema='public'")
    if rows is None:
        return None
    cat = collections.defaultdict(set)
    for r in rows:
        if len(r) >= 2:
            cat[r[0]].add(r[1])
    return cat


def _strip_comments(text):
    """Read CODE, not prose — reusing the stripper the order-totality gate already carries.

    This tool's first run reported exactly one stale name, `v_project_truth.id` in a filter, and it was
    FALSE. project-report.html carries a seven-line comment explaining why `.order('id')` totalises the
    ITEMS query, and that prose sits between the v_project_truth chain and the next `.from(`, so the
    chain window matched `.order('id')` inside the explanation. The paginated-order-totality gate was
    bitten by the same file shape and already solved it, which is why this imports its stripper instead
    of hand-rolling a second one.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_pot", os.path.join(ROOT, "tools", "validate_paginated_order_totality.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.strip_comments(text)


def source_of(page):
    src = ""
    for f in (page + ".html", page + ".js"):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            src += "\n" + open(p, encoding="utf-8", errors="replace").read()
    return _strip_comments(src)


def check_names(page, src, cat):
    """Every literal field name this page uses, and whether the relation really has it."""
    checked, stale, skipped = [], [], collections.Counter()

    def note(rel, col, where):
        if rel not in cat:
            skipped["relation not in the public catalog (%s)" % rel] += 1
            return
        checked.append((rel, col, where))
        if col not in cat[rel]:
            stale.append({"page": page, "relation": rel, "column": col, "where": where})

    for m in SELECT_RE.finditer(src):
        rel, cols = m.group(1), m.group(2)
        for raw in re.split(r"[,\s]+", cols):
            c = raw.strip()
            if not c or c == "*":
                continue
            if "(" in c or "!" in c:
                skipped["embedded resource (inner columns belong to another relation)"] += 1
                continue
            if ":" in c:                       # alias:column — the real name is on the right
                c = c.split(":", 1)[1]
            c = c.split(".")[0]
            if not IDENT_RE.match(c):
                skipped["not a literal identifier (built or computed)"] += 1
                continue
            note(rel, c, "select")

    for m in CHAIN_RE.finditer(src):
        rel, tail = m.group(1), m.group(2)
        for fm in FILTER_RE.finditer(tail):
            note(rel, fm.group(1), "filter/order")

    return checked, stale, skipped


def control(cat):
    """The checker must CATCH a name that certainly does not exist."""
    rel = next((t for t in ("logbook", "community_posts", "inventory_items") if t in cat), None)
    if not rel:
        return {"ok": False, "note": "no known relation available to test against"}
    fake = "wh_column_that_cannot_exist_%s" % rel
    src = ".from('%s').select('id, %s')" % (rel, fake)
    _, stale, _ = check_names("_control", src, cat)
    return {"ok": any(s["column"] == fake for s in stale), "relation": rel, "injected": fake,
            "note": "an injected non-existent column must be reported, or a silent regex failure "
                    "would read as a clean bill of health"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    cat = catalog()
    if cat is None:
        print("  %sSKIP%s local database not reachable" % (YEL, RST))
        return 0

    ctl = control(cat)
    pages, all_stale = [], []
    for page in ALL_PAGES:
        src = source_of(page)
        if not src.strip():
            continue
        checked, stale, skipped = check_names(page, src, cat)
        all_stale.extend(stale)
        pages.append({"page": page, "checked": len(checked),
                      "relations": sorted({r for r, _, _ in checked}),
                      "stale": stale, "skipped": dict(skipped),
                      "verdict": "all-names-current" if not stale else "STALE-NAME"})

    total = sum(p["checked"] for p in pages)
    payload = {"pages": pages, "control": ctl, "total_checked": total,
               "stale": all_stale, "catalog_columns": sum(len(v) for v in cat.values())}
    with open(REPORT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    os.replace(REPORT + ".tmp", REPORT)
    if a.json:
        print(json.dumps(payload, indent=1))
        return 1 if all_stale else 0

    print("  %sFIELD NAMES ACROSS THE SEAM%s  %d literal name use(s) checked against %d catalog "
          "column(s), %d page(s)" % (DIM, RST, total, payload["catalog_columns"], len(pages)))
    if not ctl["ok"]:
        print("  %sCONTROL FAILED%s the checker did not catch an injected non-existent column - every "
              "verdict below is unproven" % (RED, RST))
    else:
        print("  %scontrol: an injected `%s` was caught, so the checker can see a stale name%s"
              % (DIM, ctl["injected"], RST))

    skipped = collections.Counter()
    for p in pages:
        for k, v in p["skipped"].items():
            skipped[k] += v
    for k, v in skipped.most_common():
        print("    %sskipped %4d  %s%s" % (DIM, v, k, RST))

    if all_stale:
        print("\n  %sSTALE NAMES%s" % (RED, RST))
        for s in all_stale:
            print("    %-19s %s.%s  (%s)" % (s["page"], s["relation"], s["column"], s["where"]))
    else:
        print("\n  %severy literal field name still exists on the relation it is used against%s"
              % (GREEN, RST))

    print("\n  wrote %s" % os.path.relpath(REPORT, ROOT))
    if a.gate:
        if not ctl["ok"]:
            print("  %sFAIL%s the non-vacuity control failed" % (RED, RST))
            return 1
        if all_stale:
            print("  %sFAIL%s %d field name(s) no longer exist on their relation"
                  % (RED, RST, len(all_stale)))
            return 1
        print("  %sPASS%s %d field name(s) checked, none stale" % (GREEN, RST, total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
