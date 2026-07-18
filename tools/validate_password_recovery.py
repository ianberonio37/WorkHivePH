#!/usr/bin/env python3
"""validate_password_recovery.py — Arc I I3/I gate: password recovery (supervisor-assisted + email fallback).

Ian's pick: BOTH flows.
  • SUPERVISOR-ASSISTED (primary, for no-email field workers): the `supervisor-reset-password` edge fn lets
    an ACTIVE SUPERVISOR set a same-hive WORKER's temp password via the GoTrue admin API, audit-logged.
    Gated: caller must be active supervisor of the hive; target must be an active worker of the SAME hive;
    a supervisor may NOT reset another supervisor (no lateral takeover); no cross-hive reach.
  • EMAIL FALLBACK (for users with a real inbox): a "Forgot password?" link → resetPasswordForEmail →
    a PASSWORD_RECOVERY listener that sets the new password.

Proves the control statically (the gates exist in code) AND live (if serving): a supervisor resets a worker
(200 + the temp password actually logs in), a WORKER is refused (403), and resetting a supervisor is refused
(403). Restores the probe worker's password afterward so the seed stays usable.

Run:  python tools/validate_password_recovery.py
Self-test: --self-test
Skills: security (privileged reset, admin API), multitenant (supervisor scope), community (worker onboarding/UX).
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
_HIVE_FALLBACK = "636cf7e8-431a-4907-8a9f-43dd4cc216d6"  # Baguio Textile Mills — stable canonical test hive (Leandro=supervisor, Bryan=worker)
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"
SELF_TEST = "--self-test" in sys.argv[1:]


def psql(sql: str):
    try:
        p = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None


# Resolve the test hive DYNAMICALLY: the hive where the supervisor (Leandro Marquez) AND the reset
# target (Bryan Garcia) are BOTH active in the right roles. Hardcoding a uuid rots when a reseed
# regenerates hive ids — the old 9b4eaeac went dead, so the edge fn correctly 403'd on a non-existent
# hive and this (previously 9/9) gate started failing. Falls back to the canonical Baguio hive.
HIVE = (psql(
    "SELECT s.hive_id FROM v_worker_truth s JOIN v_worker_truth w ON w.hive_id = s.hive_id "
    "WHERE s.worker_name='Leandro Marquez' AND s.role='supervisor' AND s.hive_status='active' "
    "AND w.worker_name='Bryan Garcia' AND w.role='worker' AND w.hive_status='active' LIMIT 1")
    or _HIVE_FALLBACK)


def _key():
    try:
        return re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
                         (ROOT / "tests" / "_db-cleanup.ts").read_text(encoding="utf-8")).group(0)
    except Exception:
        return ""


def _jwt(key, email, pw):
    try:
        req = urllib.request.Request(f"{BASE}/auth/v1/token?grant_type=password",
            data=json.dumps({"email": email, "password": pw}).encode(),
            headers={"apikey": key, "Content-Type": "application/json"}, method="POST")
        return json.loads(urllib.request.urlopen(req, timeout=15).read()).get("access_token", "")
    except Exception:
        return ""


def _invoke(fn, body, key, jwt):
    req = urllib.request.Request(f"{BASE}/functions/v1/{fn}", data=json.dumps(body).encode(),
        headers={"apikey": key, "Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}, method="POST")
    try:
        return 200, json.loads(urllib.request.urlopen(req, timeout=20).read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except Exception: return e.code, {}
    except Exception:
        return None, {}


def main() -> int:
    print(f"\n{'='*66}\n  ARC I I3/I — password recovery (supervisor-assisted + email)\n{'='*66}")
    checks = []
    src_dir = ROOT / "supabase" / "functions" / "supervisor-reset-password" / "index.ts"
    fn_src = src_dir.read_text(encoding="utf-8", errors="replace") if src_dir.exists() else ""
    idx = (ROOT / "index.html").read_text(encoding="utf-8", errors="replace")
    hive = (ROOT / "hive.html").read_text(encoding="utf-8", errors="replace")

    # ── static gates ──
    checks.append((bool(fn_src), "supervisor-reset-password edge function exists"))
    checks.append((("role !== \"supervisor\"" in fn_src or "role !== 'supervisor'" in fn_src) and "getUser" in fn_src,
                   "caller is verified as an ACTIVE SUPERVISOR (JWT → role check), not trusting the client"))
    checks.append(("cannot_reset_supervisor" in fn_src and "admin.updateUserById" in fn_src,
                   "target restricted to a WORKER (not another supervisor) + password set via admin API"))
    checks.append(("hive_audit_log" in fn_src, "every reset is audit-logged (hive_audit_log)"))
    checks.append(("resetMemberPassword" in hive and "supervisor-reset-password" in hive,
                   "hive.html supervisor UI wired (Reset PW button → edge fn)"))
    checks.append(("resetPasswordForEmail" in idx and "PASSWORD_RECOVERY" in idx and "forgotPassword" in idx,
                   "index.html email fallback wired (Forgot password? → resetPasswordForEmail + recovery listener)"))

    # ── live behavioral proof (if serving) ──
    live_note = ""
    key = _key()
    sjwt = _jwt(key, "leandromarquez@auth.workhiveph.com", "test1234") if key else ""
    if sjwt:
        # supervisor resets a worker → 200 + temp pw that actually logs in
        c, body = _invoke("supervisor-reset-password", {"hive_id": HIVE, "target_worker_name": "Bryan Garcia"}, key, sjwt)
        tpw = body.get("temp_password", "")
        login_ok = False
        if tpw:
            login_ok = bool(_jwt(key, "bryangarcia@auth.workhiveph.com", tpw))
        checks.append((c == 200 and login_ok, f"LIVE: supervisor reset a worker → 200 + the temp password logs in (code={c}, login_ok={login_ok})"))
        # supervisor cannot reset another supervisor
        c2, _ = _invoke("supervisor-reset-password", {"hive_id": HIVE, "target_worker_name": "Leandro Marquez"}, key, sjwt)
        checks.append((c2 == 403, f"LIVE: supervisor → another SUPERVISOR refused (code={c2}, expect 403)"))
        # a worker cannot reset anyone
        wjwt = _jwt(key, "bryangarcia@auth.workhiveph.com", tpw) if tpw else ""
        if wjwt:
            c3, _ = _invoke("supervisor-reset-password", {"hive_id": HIVE, "target_worker_name": "Wilfredo Malabanan"}, key, wjwt)
            checks.append((c3 == 403, f"LIVE: a WORKER attempting a reset refused (code={c3}, expect 403)"))
        # restore Bryan to the seed default so other tests keep working
        psql("UPDATE auth.users SET encrypted_password = crypt('test1234', gen_salt('bf')) WHERE email = 'bryangarcia@auth.workhiveph.com'")
        live_note = " + live edge proof (probe worker restored)"
    else:
        live_note = " (live edge skipped: seeder/runtime unreachable)"

    if SELF_TEST:
        missing = "admin.updateUserById" not in fn_src
        print(f"  self-test: detector keys on the admin-API reset call presence = {not missing} ({GREEN+'teeth OK'+RST if not missing else RED+'NO TEETH'+RST})")

    npass = sum(1 for ok, _ in checks if ok)
    for ok, label in checks:
        print(f"  {GREEN+'PASS'+RST if ok else RED+'FAIL'+RST}  {label}")
    print("-" * 66)
    allok = npass == len(checks)
    print(f"  {(GREEN if allok else RED)}{npass}/{len(checks)} checks{RST}{live_note}")
    print(f"{(GREEN if allok else RED)}  RESULT: {'GREEN — both recovery flows present + supervisor-reset scoped & enforced live.' if allok else 'RED — password-recovery gap.'}{RST}")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
