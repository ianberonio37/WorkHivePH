#!/usr/bin/env python3
"""source-chip-names-a-real-relation - a provenance chip must name a relation that EXISTS (2026-08-27).

MEASURED, not hypothesised: hive.html's readiness chip named `v_maturity_truth`, and there is no such
relation. The chip's own comment states the promise it was breaking - "every readiness number on the
page is reproducible by querying this view" - so a supervisor who followed it to run the ad-hoc query
got `relation "v_maturity_truth" does not exist`. The numbers were fine; the TRACE was a dead end,
which is the only thing a provenance chip is for.

★WHY THE EXISTING PROVER COULD NOT SEE IT. tools/prove_source_chip.mjs asks a sharper question - does
the chip name a relation the page ACTUALLY REQUESTED? - by capturing PostgREST traffic. But hive.html
renders readiness through the compute_hive_readiness RPC rather than a direct db.from(), so the chip
carries a `source-chip-allow` marker and is exempted from that check. The exemption is legitimate: the
page really does not request the view over REST. What no one noticed is that it exempted the chip from
EVERY check, so the name behind it was never tested against anything at all. An exemption should waive
the check it was written for, never the question of whether the claim is true.

SCOPE, deliberately narrow so it cannot cry wolf: chip sources are free prose ("Skill Matrix",
"platform_health.json", "v_logbook_truth via Postgres RPCs"), so only IDENTIFIER-SHAPED tokens are
tested - lower snake_case, at least one underscore, no dot. That covers every v_*_truth view and
every table name the chips actually cite, and skips the prose around them.

Re-drive: python tools/validate_source_chip_names_a_real_relation.py [--selftest]
"""
import io
import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"

SOURCE_DECL = re.compile(r"""source:\s*(?P<q>['"])(?P<val>[^'"]{1,200})(?P=q)""")
IDENT = re.compile(r"^[a-z][a-z0-9_]*$")

# Words that appear inside compound source strings as connectors, not relations.
CONNECTORS = {"via", "and", "only", "public", "posts", "from", "the", "plus", "with"}


def tokens_of(value: str):
    """Identifier-shaped tokens in one source string; prose and filenames are skipped."""
    out = []
    for raw in re.split(r"[+,/()\s]+", value):
        t = raw.strip()
        if not t or "." in t or t in CONNECTORS:
            continue
        if IDENT.match(t) and "_" in t:
            out.append(t)
    return out


def live_relations() -> set:
    # ★A CHIP MAY LEGITIMATELY CITE MORE THAN A TABLE, and the first cut of this gate flagged four
    # honest chips for it: 'qty_on_hand' / 'min_qty' / 'at_risk' are COLUMNS and 'get_hive_dashboard'
    # is an RPC FUNCTION. Those are exactly the kind of specific, traceable names a provenance chip
    # SHOULD carry, so counting them as fabrications would have trained the reader to ignore this
    # gate — the failure mode a false report always has. Tables, views, functions and column names
    # all count as real; a name that is none of them (v_maturity_truth) still has nothing behind it.
    q = ("select table_name from information_schema.tables where table_schema='public' "
         "union select table_name from information_schema.views where table_schema='public' "
         "union select routine_name from information_schema.routines where routine_schema='public' "
         "union select column_name from information_schema.columns where table_schema='public'")
    p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tAc", q],
                       capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200])
    return {ln.strip() for ln in p.stdout.splitlines() if ln.strip()}


def scan(pages, relations: set):
    """(claims, missing) — every identifier a chip names, and those with no relation behind them."""
    claims, missing = [], []
    for path in pages:
        body = io.open(path, encoding="utf-8", errors="replace").read()
        for m in SOURCE_DECL.finditer(body):
            line = body[:m.start()].count("\n") + 1
            for tok in tokens_of(m.group("val")):
                claims.append((path.name, line, tok))
                if tok not in relations:
                    missing.append((path.name, line, tok, m.group("val")[:60]))
    return claims, missing


def main() -> int:
    try:
        relations = live_relations()
    except Exception as e:
        print(f"\033[93m  SKIP\033[0m source-chip-names-a-real-relation — local DB unreachable: {e}")
        return 0

    pages = sorted(ROOT.glob("*.html"))
    claims, missing = scan(pages, relations)
    print("source-chip-names-a-real-relation — a provenance claim must survive its own trace")
    print(f"  pages scanned        : {len(pages)}")
    print(f"  relations live in db : {len(relations)}")
    print(f"  identifiers claimed  : {len(claims)}")
    print(f"  naming nothing real  : {len(missing)}")

    (ROOT / "source_chip_relation_report.json").write_text(json.dumps({
        "claims": len(claims), "missing": [
            {"page": p, "line": ln, "relation": t, "source": s} for p, ln, t, s in missing],
    }, indent=2), encoding="utf-8")

    if missing:
        print("\n\033[91mFAIL\033[0m — these chips promise a trace that dead-ends:")
        for p, ln, t, s in missing:
            print(f"    {p}:{ln}  names '{t}'  (source: \"{s}\")")
        return 1
    print("\n\033[92mPASS\033[0m — every relation a provenance chip names exists in the database.")
    return 0


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    chk("prose is not treated as a relation", tokens_of("Skill Matrix"), [])
    chk("a filename is not a relation", tokens_of("platform_health.json"), [])
    chk("a compound source yields each relation",
        tokens_of("logbook + asset_nodes + v_inventory_items_truth"),
        ["asset_nodes", "v_inventory_items_truth"])
    chk("connector words are dropped", tokens_of("v_logbook_truth via Postgres RPCs"), ["v_logbook_truth"])
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
