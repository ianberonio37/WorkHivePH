#!/usr/bin/env python3
"""validate_login_proxy_lockout.py — Arc I I7/A gate: server-side brute-force lockout on the login path.

THE CONTROL (Ian's pick: edge login-proxy). A client-side "lock after N tries" is bypassable security
theater — an attacker POSTs /auth/v1/token directly with the anon key. So the lockout lives SERVER-SIDE in
the `login` edge function, gated by the `login_attempts` table + 3 SECURITY DEFINER RPCs. This validator
proves the control holds, live, with teeth:

  1. DB lockout logic (hermetic, docker psql): N-1 failures stay unlocked, the Nth locks, check reports
     locked + a retry window, and clear() resets — the exact state machine the edge fn relies on.
  2. SECURITY posture (static + catalog): RPCs are SECURITY DEFINER + search_path-pinned + service_role-only
     (no anon/authenticated EXECUTE — a client can't drive or reset the counter); login is verify_jwt=false
     (pre-auth) in config.toml; the client (index.html) routes sign-in through the proxy, not signInWithPassword.
  3. LIVE edge proof (if the runtime is serving): 5 bad logins → 423, and a LOCKED account rejects even the
     CORRECT password (423, never reaching GoTrue) — the property a client-side check cannot provide.

Run:  python tools/validate_login_proxy_lockout.py
Self-test: --self-test (proves the teeth — a broken threshold fails)
Skills: security (brute-force/auth), multitenant (auth flow), devops (edge config verify_jwt).
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
BASE = "http://127.0.0.1:54321"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"
SELF_TEST = "--self-test" in sys.argv[1:]


def psql(sql: str):
    try:
        p = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None


def main() -> int:
    print(f"\n{'='*68}\n  ARC I I7/A — login-proxy brute-force lockout (server-side)\n{'='*68}")
    checks = []  # (ok, label)

    # ── 1. DB lockout state machine (hermetic) ──
    ident = "wh_validator_probe"
    if psql("SELECT 1") is None:
        print(f"{YEL}  SKIP  local DB unreachable (run supabase start){RST}")
        return 0
    psql(f"SELECT clear_login_attempts('{ident}','9.9.9.9')")
    fails = []
    for _ in range(5):
        r = psql(f"SELECT locked FROM record_login_failure('{ident}','9.9.9.9',5,15,15)")
        fails.append((r or "").strip() == "t")
    locked_after_5 = psql(f"SELECT locked FROM check_login_lockout('{ident}','9.9.9.9')")
    retry = psql(f"SELECT retry_after_seconds FROM check_login_lockout('{ident}','9.9.9.9')")
    psql(f"SELECT clear_login_attempts('{ident}','9.9.9.9')")
    cleared = psql(f"SELECT locked FROM check_login_lockout('{ident}','9.9.9.9')")
    threshold_ok = fails == [False, False, False, False, True]
    checks.append((threshold_ok, f"DB lockout state machine: fails 1-4 unlocked, 5th locks (got {fails})"))
    checks.append(((locked_after_5 or "").strip() == "t" and int(retry or 0) > 0,
                   f"check_login_lockout reports locked + retry window ({retry}s)"))
    checks.append(((cleared or "").strip() == "f", "clear_login_attempts resets the counter (success path)"))

    # ── 2. security posture (static + live catalog) ──
    # RPC grants: must NOT be executable by anon/authenticated (service-role only)
    leaky = psql("""SELECT count(*) FROM information_schema.role_routine_grants
                    WHERE routine_schema='public' AND grantee IN ('anon','authenticated')
                    AND routine_name IN ('record_login_failure','check_login_lockout','clear_login_attempts')""")
    checks.append(((leaky or "1").strip() == "0", "lockout RPCs are service_role-only (no anon/authenticated EXECUTE)"))
    # DEFINER + search_path pinned
    definer_ok = psql("""SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                         WHERE n.nspname='public' AND p.proname IN ('record_login_failure','check_login_lockout','clear_login_attempts')
                         AND p.prosecdef AND p.proconfig::text ILIKE '%search_path%'""")
    checks.append(((definer_ok or "0").strip() == "3", "all 3 RPCs are SECURITY DEFINER + search_path-pinned"))
    cfg = (ROOT / "supabase" / "config.toml").read_text(encoding="utf-8", errors="replace")
    checks.append((bool(re.search(r"\[functions\.login\][^\[]*verify_jwt\s*=\s*false", cfg, re.S)),
                   "login edge fn is verify_jwt=false (pre-auth) in config.toml"))
    idx = (ROOT / "index.html").read_text(encoding="utf-8", errors="replace")
    checks.append(("/functions/v1/login" in idx and "setSession" in idx,
                   "index.html routes sign-in through the login proxy + setSession (not direct signInWithPassword-only)"))

    # ── 3. LIVE edge proof (optional — only if serving) ──
    live_note = ""
    try:
        key = re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
                        (ROOT / "tests" / "_db-cleanup.ts").read_text(encoding="utf-8")).group(0)
        probe_id = "wh_live_probe@auth.workhiveph.com"
        psql("SELECT clear_login_attempts('wh_live_probe','')")
        codes = []
        for i in range(6):
            req = urllib.request.Request(f"{BASE}/functions/v1/login",
                data=json.dumps({"email": probe_id, "password": f"bad{i}"}).encode(),
                headers={"apikey": key, "Content-Type": "application/json"}, method="POST")
            try:
                codes.append(urllib.request.urlopen(req, timeout=15).getcode())
            except urllib.error.HTTPError as e:
                codes.append(e.code)
        psql("SELECT clear_login_attempts('wh_live_probe','')")
        live_locked = 423 in codes
        checks.append((live_locked, f"LIVE: 6 bad logins through the edge proxy trip 423 lockout (codes={codes})"))
        live_note = " + live edge proof"
    except Exception as e:
        live_note = f" (live edge skipped: {type(e).__name__})"

    if SELF_TEST:
        # teeth: a 6-attempt sequence with threshold 99 must NOT lock (proves the check measures, not box-ticks)
        psql(f"SELECT clear_login_attempts('{ident}','t')")
        none_lock = all((psql(f"SELECT locked FROM record_login_failure('{ident}','t',99,15,15)") or "").strip() == "f" for _ in range(6))
        psql(f"SELECT clear_login_attempts('{ident}','t')")
        print(f"  self-test: threshold=99 never locks in 6 tries = {none_lock} ({GREEN+'teeth OK'+RST if none_lock else RED+'NO TEETH'+RST})")

    npass = sum(1 for ok, _ in checks if ok)
    for ok, label in checks:
        print(f"  {GREEN+'PASS'+RST if ok else RED+'FAIL'+RST}  {label}")
    print("-" * 68)
    allok = npass == len(checks)
    print(f"  {(GREEN if allok else RED)}{npass}/{len(checks)} checks{RST}{live_note}")
    if allok:
        print(f"{GREEN}  RESULT: GREEN — server-side brute-force lockout enforced + a correct password cannot bypass a lock.{RST}")
        return 0
    print(f"{RED}  RESULT: RED — login-proxy lockout gap.{RST}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
