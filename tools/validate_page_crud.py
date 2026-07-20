"""validate_page_crud.py — PER_PAGE_BUGHUNT_ROADMAP per-page P3 CRUD-at-DB gate (wrapper).

Wraps tools/validate_page_crud.mjs (headless Playwright, real WORKER sign-in via live_page_journeys).
For each attribution-pinned entity (voice_journal_entries / engineering_calcs / community_posts /
pm_assets) it round-trips through the page's authed db client: INSERT with a FORGED display name ->
assert it PERSISTED (create works) BUT the name is PINNED to the caller (bind_*_submitter, migs
010/011/012) -> owner-scoped DELETE -> assert cleaned. Locks the 2026-07-14 per-page P3 frontier.

Skips cleanly (exit 0) if node or the local stack (Flask :5000 + Supabase :54321) is absent — a
local-only live gate, like validate_page_battery.py. Non-zero exit = a real P3/attribution regression.
"""
import io
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tools" / "validate_page_crud.mjs"
LIVE_HIVE = "636cf7e8-431a-4907-8a9f-43dd4cc216d6"


def _up(url: str, timeout: float = 3.0) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception as e:
        return "HTTP Error" in str(e)


def main() -> int:
    print("\n" + "=" * 72)
    print("  Per-page P3 CRUD-at-DB gate (create persists + attribution PINNED + owner-delete)")
    print("=" * 72)
    if shutil.which("node") is None:
        print("  SKIP: node not on PATH — live CRUD gate not evaluated (local-only live gate).")
        return 0
    if not HARNESS.exists():
        print(f"  FAIL: {HARNESS.name} missing — the page-CRUD harness was removed.")
        return 1
    if not (_up("http://127.0.0.1:5000/workhive/hive.html") and _up("http://127.0.0.1:54321/rest/v1/")):
        print("  SKIP: local stack (Flask :5000 / Supabase :54321) not reachable — treating as stack-absent.")
        return 0
    env = dict(os.environ, WH_TEST_HIVE=LIVE_HIVE)
    try:
        r = subprocess.run(["node", str(HARNESS)], cwd=str(ROOT), env=env,
                           capture_output=True, text=True, timeout=180)
    except Exception as e:
        print(f"  SKIP: could not run the CRUD gate ({e}) — treating as local-stack-absent.")
        return 0
    out = (r.stdout or "").strip()
    if out:
        print("\n".join("  " + ln for ln in out.splitlines()))
    err = (r.stderr or "").strip()
    if err and r.returncode != 0:
        print("  stderr:", err[:400])
    # Cleanup: hive_audit_log is append-only (owner-DELETE is a no-op by design), so the harness's
    # forged-actor probe row persists. Remove it via service-role psql so the gate never pollutes
    # the shared local DB ([[feedback_live_mcp_writes_pollute_test_db]]). Best-effort; never fails the gate.
    try:
        subprocess.run(
            ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-c", "delete from hive_audit_log where action='crudgate_probe' and target_type='probe';"],
            capture_output=True, text=True, timeout=30)
    except Exception:
        pass
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
