#!/usr/bin/env python3
"""validate_client_write_grants.py — the LOCK for the 42501 "permission denied for table" class.

THE BUG (measured live, Arc-K MS3, 2026-07-22): marketplace-seller.html does
`db.from('marketplace_sellers').upsert({…}, {onConflict:'worker_name'})`, but the `authenticated`
role was granted INSERT/UPDATE/DELETE on that table and NOT SELECT — and an upsert's ON CONFLICT
read + PostgREST RETURNING both need SELECT. Result: 42501 "permission denied for table",
evaluated at the GRANT layer BEFORE RLS, so every seller's messenger/cert save was broken
platform-wide. It was masked because the page READS via a truth VIEW, so the base-table SELECT
miss never surfaced on the read path. (See feedback_permission_denied_table_is_grant_not_rls.)

THE RULE (deterministic, live, forward-only): for every base table a client page WRITES via
`.from('T').insert|upsert|update|delete`, the `authenticated` role (or PUBLIC) must hold the
matching table privilege:
    insert -> INSERT     update -> UPDATE     delete -> DELETE
    upsert -> INSERT + UPDATE + SELECT   (conflict-read + RETURNING)
A missing grant = a latent 42501 the moment that path runs. Complements the OPPOSITE-direction
`validate_migration_grant_regression` (which catches OVER-granting EXECUTE on locked DEFINER fns).

  python tools/validate_client_write_grants.py             # check (forward ratchet)
  python tools/validate_client_write_grants.py --update-baseline
  python tools/validate_client_write_grants.py --self-test  # no DB
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "client_write_grants_baseline.json"
DB = "supabase_db_workhive"

# op -> the table privileges `authenticated` must hold for that client call to not 42501.
OP_PRIVS = {
    "insert": {"INSERT"},
    "update": {"UPDATE"},
    "delete": {"DELETE"},
    "upsert": {"INSERT", "UPDATE", "SELECT"},   # ON CONFLICT read + RETURNING
}
FROM_RE = re.compile(r"\.from\(\s*['\"]([a-z_][a-z0-9_]*)['\"]\s*\)")
OP_RE = re.compile(r"\.\s*(upsert|insert|update|delete)\b")
ALLOW = "grant-check-allow"


def scan(repo: Path) -> dict[str, dict]:
    """{table: {ops:set, sites:[file:line]}} for every client .from('T').<write>."""
    out: dict[str, dict] = {}
    for f in sorted(repo.glob("*.html")):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in FROM_RE.finditer(text):
            table = m.group(1)
            # the statement is from here up to the next ';' or the next '.from(' (whichever first)
            tail = text[m.end(): m.end() + 400]
            cut = len(tail)
            nxt_from = tail.find(".from(")
            nxt_semi = tail.find(";")
            for c in (nxt_from, nxt_semi):
                if c != -1:
                    cut = min(cut, c)
            stmt = tail[:cut]
            om = OP_RE.search(stmt)
            if not om:
                continue
            # honor an inline allow marker on the from-line (rare, audited)
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            if ALLOW in text[line_start: line_end if line_end != -1 else len(text)]:
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            e = out.setdefault(table, {"ops": set(), "sites": []})
            e["ops"].add(om.group(1))
            e["sites"].append(f"{f.name}:{line_no}")
    return out


def db_grants() -> dict[str, set] | None:
    """{table: {PRIVILEGE,...}} granted to authenticated OR PUBLIC. None if DB unreachable."""
    try:
        r = subprocess.run(
            ["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-F", "\t", "-c",
             "SELECT table_name, privilege_type FROM information_schema.role_table_grants "
             "WHERE table_schema='public' AND grantee IN ('authenticated','PUBLIC');"],
            capture_output=True, text=True, timeout=25)
        if r.returncode != 0:
            return None
        g: dict[str, set] = {}
        for ln in r.stdout.splitlines():
            if "\t" in ln:
                t, p = ln.split("\t", 1)
                g.setdefault(t.strip(), set()).add(p.strip().upper())
        return g
    except Exception:
        return None


def evaluate(writes: dict, grants: dict) -> list[dict]:
    """Missing-grant findings: a (table, op) whose required privilege authenticated lacks."""
    findings = []
    for table, e in sorted(writes.items()):
        held = grants.get(table)
        if held is None:
            continue   # table not in DB (dynamic/typo/renamed) — not a grant finding
        need = set().union(*(OP_PRIVS[op] for op in e["ops"]))
        missing = need - held
        if missing:
            findings.append({"table": table, "ops": sorted(e["ops"]),
                             "missing": sorted(missing), "site": e["sites"][0]})
    return findings


def self_test() -> int:
    fails = []
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / "p.html").write_text(
            "x = db.from('sellers').upsert({a:1}, {onConflict:'w'});\n"       # needs I+U+S
            "y = db.from('logs').insert(row);\n"                              # needs I
            "z = db.from('v_truth').select('*').eq('h', hid);\n"             # read — not a write
            "q = db.from('allowed').update({b:2}); // grant-check-allow: intentional\n",  # exempt
            encoding="utf-8")
        w = scan(repo)
        if "sellers" not in w or w["sellers"]["ops"] != {"upsert"}:
            fails.append(f"upsert not captured: {w.get('sellers')}")
        if "v_truth" in w:
            fails.append("a .select() read must NOT be counted as a write")
        if "allowed" in w:
            fails.append("grant-check-allow marker should exempt the line")
        # sellers has only INSERT/UPDATE/DELETE (the real bug) -> SELECT missing must flag
        grants = {"sellers": {"INSERT", "UPDATE", "DELETE"}, "logs": {"INSERT"}}
        fnd = evaluate(w, grants)
        sel = next((f for f in fnd if f["table"] == "sellers"), None)
        if not sel or sel["missing"] != ["SELECT"]:
            fails.append(f"missing SELECT on upsert table should flag: {fnd}")
        if any(f["table"] == "logs" for f in fnd):
            fails.append("a fully-granted insert table must NOT flag")
    if fails:
        print("FAIL validate_client_write_grants self-test:")
        for f in fails:
            print("  - " + f)
        return 1
    print("PASS validate_client_write_grants self-test (write-scan · read-skip · allow-marker · upsert-needs-SELECT)")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        return self_test()
    writes = scan(ROOT)
    grants = db_grants()
    if grants is None:
        print("SKIP client-write-grants: local DB unreachable (docker psql) — cannot verify grants.")
        return 0
    findings = evaluate(writes, grants)
    n_tables = len(writes)
    print(f"client-write-grants: {n_tables} client-written tables · {len(findings)} missing-grant finding(s)")
    for f in findings:
        print(f"  ✗ {f['table']} ({'/'.join(f['ops'])}) missing {','.join(f['missing'])} for authenticated "
              f"→ 42501 on {f['site']}  (GRANT {','.join(f['missing'])} ON public.{f['table']} TO authenticated;)")
    if "--update-baseline" in argv:
        BASELINE.write_text(json.dumps({"missing": len(findings),
                                        "tables": sorted({f["table"] for f in findings})}, indent=2),
                            encoding="utf-8")
        print(f"baseline banked: missing={len(findings)}")
        return 0
    base = json.loads(BASELINE.read_text(encoding="utf-8")).get("missing", 0) if BASELINE.exists() else 0
    if len(findings) > base:
        print(f"FAIL client-write-grants: {len(findings)} missing-grant > baseline {base} (a write path will 42501)")
        return 1
    print(f"PASS client-write-grants: {len(findings)} <= baseline {base} (ratchet held)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
