"""validate_page_rpcs_callable.py - BRH 9 AD (2026-10-21): a page never calls a function its reader is not allowed to run.

hive.html called compute_hive_readiness() on every board load past a day. 20260619000000 had revoked it from
authenticated (it was an ungated cross-tenant write) on the premise that "no browser code invokes it" - so from
2026-06-19 production refused the call to every member, nothing else ran it, and every hive's readiness stood still.
rpc-argument-consistency checks that a called function EXISTS and takes the keys passed; nothing checked that the
reader may EXECUTE it, which is the one fact that decides whether the call does anything.

LIVE    P1 every function the browser calls - db.rpc('<name>' in a served page or root script, comments blanked - is
           EXECUTE-able by authenticated in the local database (has_function_privilege: the catalogue is asked; the
           function is never called). A page that calls a server-only function is a refused call on every load.
SELF-TEST (--self-test): a page that calls compute_hive_readiness (server-only) is caught; the clean run is green.

    python tools/validate_page_rpcs_callable.py [--self-test]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from validate_list_caps_say_more import blank_comments  # noqa: E402

DB = "supabase_db_workhive"
CALL = re.compile(r"""\.rpc\(\s*['"`]([a-z_][a-z0-9_]*)['"`]""")


def browser_sources() -> dict[str, str]:
    """What the browser runs: every page and script the deployment ships (deploy_payload's allowlist - so a backup
    folder that never ships is not read), less the service worker, which calls nothing over the API."""
    import deploy_payload
    ship = sorted(f for f in deploy_payload.shipped() if f.endswith((".html", ".js", ".mjs")) and f != "sw.js")
    return {f: (ROOT / f).read_text(encoding="utf-8", errors="replace") for f in ship if (ROOT / f).is_file()}


def calls(sources: dict[str, str]) -> dict[str, list[str]]:
    """{function: ['page:line', ...]} for every rpc call outside a comment."""
    out: dict[str, list[str]] = {}
    for name, src in sources.items():
        body = blank_comments(src)
        for m in CALL.finditer(body):
            out.setdefault(m.group(1), []).append(f"{name}:{body.count(chr(10), 0, m.start()) + 1}")
    return out


def executable(names: list[str]) -> dict[str, bool] | None:
    """{function: authenticated may EXECUTE some overload} from the local catalogue; None if it cannot be read."""
    if not names:
        return {}
    arr = ",".join("'" + n + "'" for n in sorted(names))
    sql = ("select p.proname || '|' || bool_or(has_function_privilege('authenticated', p.oid, 'EXECUTE')) "
           "from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
           f"where n.nspname = 'public' and p.proname in ({arr}) group by p.proname")
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode:
        return None
    out = {}
    for line in r.stdout.splitlines():
        name, ok = line.split("|")
        out[name] = ok in ("t", "true")      # a boolean concatenated to text reads 'true', not psql's 't'
    return out


def check(sources: dict[str, str] | None = None) -> tuple[list[str], int, int]:
    found = calls(browser_sources() if sources is None else sources)
    grants = executable(list(found))
    if grants is None:
        return ["P1 LIVE could not read the local catalogue"], len(found), 0
    issues = []
    for fn, where in sorted(found.items()):
        if fn in grants and not grants[fn]:
            issues.append(f"P1 {fn}() is called by {', '.join(where[:3])}{' ...' if len(where) > 3 else ''} and a signed-in "
                          "reader may not EXECUTE it - the call is refused on every load; give the page a door its "
                          "reader may use, or stop calling it")
    return issues, len(found), sum(len(w) for w in found.values())


def self_test() -> list[str]:
    fails = []
    issues, _, _ = check()
    if issues:
        fails.append(f"the clean run is not green: {issues[:2]}")
    mut = {"hive.html": "<script>\n// db.rpc('get_hive_readiness_current') in a comment is not a call\n"
                        "await db.rpc('compute_hive_readiness', { p_hive_id: HIVE_ID });\n</script>"}
    got, _, _ = check(mut)
    if not any("compute_hive_readiness" in i for i in got):
        fails.append("mutant 'a page that calls the server-only compute_hive_readiness' was not caught")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (the server-only call is caught; the clean run is green)" if not fails
              else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    issues, fns, sites = check()
    print("Page RPCs callable (BRH 9 AD): every function the browser calls is one its signed-in reader may run")
    for i in issues:
        print("  [FAIL] " + i)
    print(f"  PASS - {fns} functions called from {sites} sites; a signed-in reader may run every one" if not issues
          else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
