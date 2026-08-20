r"""A SECURITY INVOKER function that writes a client-unwritable table breaks the user's statement.

WHY THIS GATE EXISTS. Migration 20260820000061 added an AFTER DELETE trigger on public.logbook to
reverse XP. It was LANGUAGE plpgsql with no SECURITY DEFINER, so it ran as the CALLING user, and it
INSERTs into public.achievement_xp_log -- a table granted SELECT and nothing else to anon and
authenticated (deliberately: a client that can write its own XP can self-deal). Result: a worker
deleting their OWN logbook entry hit 42501 inside the trigger and the DELETE failed. Nothing in the
suite caught it; it surfaced as "logbook CRUD failed" in an unrelated gate.

The award side it reverses, award_achievement_xp, has been SECURITY DEFINER + SET search_path since
2026-05. The asymmetry is the bug: a compensating write needs the privileges of the write it
compensates.

WHAT THIS CHECKS (static, no DB, safe to run any time):
  1. Build the CLIENT-UNWRITABLE set: tables that migrations grant to anon/authenticated with SELECT
     only, and never with INSERT/UPDATE/DELETE.
  2. Find every CREATE [OR REPLACE] FUNCTION body in supabase/migrations.
  3. If a body writes one of those tables AND the declaration lacks SECURITY DEFINER -> FAIL, naming
     the function, the table, and the migration.

WHAT IT DELIBERATELY DOES NOT CLAIM. Static SQL reading cannot see privileges granted outside
migrations, dynamic SQL, or a table whose grants changed across several files in ways this simple
union misses. So a PASS is "no INVOKER function writes a table this scan can prove is
client-unwritable", not "no privilege bug exists". The abstention count is printed rather than
hidden, because a gate that silently skips most of its subject reads identically to one that found
nothing.

  python .tmp/validate_trigger_writes_need_definer.py
  python .tmp/validate_trigger_writes_need_definer.py --selftest
"""
import io, os, re, sys, glob

MIGDIR = os.path.join('supabase', 'migrations')
G, R, Y, D, X = '\033[92m', '\033[91m', '\033[93m', '\033[2m', '\033[0m'

GRANT_RE = re.compile(r'\bGRANT\s+([A-Z ,]+?)\s+ON\s+(?:TABLE\s+)?([a-z_.]+)\s+TO\s+([a-z_, ]+)', re.I)
FUNC_RE = re.compile(
    r'CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+([a-z_.]+)\s*\((.*?)\)(.*?)AS\s+\$\$(.*?)\$\$',
    re.I | re.S)
WRITE_RE = re.compile(r'\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+((?:public\.)?[a-z_]+)', re.I)

def norm(t):
    return t.split('.')[-1].strip().lower()

def client_unwritable(files):
    """Tables the client may SELECT but never write, per the migrations' own GRANTs."""
    sel, wrt = set(), set()
    for f in files:
        for verbs, table, roles in GRANT_RE.findall(io.open(f, encoding='utf-8', errors='replace').read()):
            if not re.search(r'\b(anon|authenticated)\b', roles, re.I):
                continue
            v, t = verbs.upper(), norm(table)
            if 'ALL' in v or re.search(r'\b(INSERT|UPDATE|DELETE)\b', v): wrt.add(t)
            if 'SELECT' in v: sel.add(t)
    return sel - wrt

def scan(files, unwritable):
    findings, checked = [], 0
    for f in files:
        src = io.open(f, encoding='utf-8', errors='replace').read()
        for name, _args, decl, body in FUNC_RE.findall(src):
            checked += 1
            if re.search(r'SECURITY\s+DEFINER', decl, re.I):
                continue
            hits = {norm(t) for t in WRITE_RE.findall(body)} & unwritable
            for t in sorted(hits):
                findings.append((os.path.basename(f), norm(name), t))
    return findings, checked

def main():
    files = sorted(glob.glob(os.path.join(MIGDIR, '*.sql')))
    if not files:
        print(f"  {Y}no migrations found at {MIGDIR}{X}"); return 0
    unwritable = client_unwritable(files)

    if '--selftest' in sys.argv:
        # Teeth, both branches: a planted INVOKER writer must be caught, and a DEFINER one must not.
        import tempfile
        d = tempfile.mkdtemp()
        base = os.path.join(d, '00_base.sql')
        io.open(base, 'w', encoding='utf-8').write(
            "GRANT SELECT ON ledger_tbl TO anon, authenticated;\n")
        bad = os.path.join(d, '01_bad.sql')
        io.open(bad, 'w', encoding='utf-8').write(
            "CREATE FUNCTION f_bad() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "INSERT INTO ledger_tbl (a) VALUES (1); RETURN OLD; END; $$;\n")
        good = os.path.join(d, '02_good.sql')
        io.open(good, 'w', encoding='utf-8').write(
            "CREATE FUNCTION f_good() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER "
            "SET search_path = public AS $$ BEGIN INSERT INTO ledger_tbl (a) VALUES (1); "
            "RETURN OLD; END; $$;\n")
        fs = [base, bad, good]
        uw = client_unwritable(fs)
        found, _ = scan(fs, uw)
        names = {n for _f, n, _t in found}
        ok = ('ledger_tbl' in uw) and ('f_bad' in names) and ('f_good' not in names)
        print(f"  selftest: an INVOKER writer is caught, a DEFINER one is not")
        print(f"  {(G+'PASS'+X) if ok else (R+'FAIL'+X)} — unwritable={sorted(uw)} caught={sorted(names)}")
        return 0 if ok else 1

    findings, checked = scan(files, unwritable)
    print(f"\n  Trigger/function writes vs client grants — {len(files)} migrations, "
          f"{checked} function bodies, {len(unwritable)} client-unwritable table(s)")
    if not unwritable:
        print(f"  {Y}ABSTAINED{X} — no table proved client-unwritable from migration GRANTs alone.")
        return 0
    for f, fn, t in findings:
        print(f"  {R}FAIL{X}  {fn}() is SECURITY INVOKER and writes {t} — "
              f"a client that cannot write {t} will hit 42501 INSIDE the trigger, "
              f"taking its own statement down with it  {D}({f}){X}")
    if findings:
        print(f"\n  {R}FAIL{X} — {len(findings)} invoker-write(s). Add SECURITY DEFINER + SET search_path, "
              f"matching the function being mirrored.")
        return 1
    print(f"  {G}PASS{X} — every function writing a client-unwritable table is SECURITY DEFINER")
    print(f"  {D}scope: static migration reading only; grants made outside migrations or via dynamic "
          f"SQL are not visible to this gate{X}")
    return 0

sys.exit(main())
