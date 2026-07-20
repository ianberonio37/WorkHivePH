"""
Grafana-Reader Read-Path Gate (Operator-Console→Grafana arc, 2026-07-18).
=========================================================================
Every Grafana dashboard/alert reads Postgres as the `grafana_reader` role. That
role is SELECT-only and RLS-subject (no BYPASSRLS, by design — least privilege).
A `GRANT SELECT` is a NO-OP under RLS without a matching policy, so a table can be
SILENTLY BLIND to Grafana even though the grant looks fine. Twice now that has
bitten us: `wh_traces` (Arc T — the SLO alert could never fire) and the whole
founder-console observe set (`analytics_events` 7081→0, `hive_audit_log` ERROR on
a function the reader can't execute, …). A later RLS-hardening migration can
re-blind any of them, undetected, because the static Grafana-provisioning gate
only checks the dashboard JSON parses — not that the datasource role can READ.

This gate is the durable guard: it LIVE-queries each dashboard-dependency table AS
`grafana_reader` and fails if the read errors OR sees fewer rows than a superuser
(partial RLS blindness). Forward-only — as the arc moves more pages to Grafana,
add their tables to REQUIRED.

Password: GRAFANA_PG_READER_PASSWORD (env or infra/mcp/.env.mcp); default = the
local placeholder. SKIPs cleanly if the DB is unreachable.

Usage:  python validate_grafana_reader_reads.py
Exit:   0 pass/skip · 1 a required table is blind or partially filtered
"""
from __future__ import annotations
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
DB = os.environ.get("WH_LOCAL_DB_CONTAINER", "supabase_db_workhive")
GREEN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
CHECK_NAMES = ["grafana_reader_reads", "grafana-reader-reads"]

# Tables the Grafana dashboards/alerts depend on. Grow this as pages migrate.
REQUIRED = [
    # Arc T (SLO)
    "wh_traces",
    # Operator-Console P1 (founder-console observe sections)
    "analytics_events", "ai_cost_log", "hive_readiness", "marketplace_orders",
    "marketplace_listings", "marketplace_sellers", "marketplace_disputes",
    "hive_audit_log", "platform_feedback", "ops_artifact_metrics",
    "ai_reply_feedback", "agentic_rag_traces", "hives",
    # G4 other-observability (cron-health): postgres-owned view over cron.job_run_details
    "v_cron_health",
    # G4 DB & Security Health drill-down (auth signals)
    "login_attempts", "auth_session_events", "ai_rate_limits",
    # G4.4 storage-health (postgres-owned aggregate view over storage.objects)
    "v_storage_health",
    # G4.4b DB-size trend history
    "ops_db_size_history",
]


def _env_or_mcp(key: str, default: str) -> str:
    v = os.environ.get(key)
    if v:
        return v
    envfile = ROOT / "infra" / "mcp" / ".env.mcp"
    if envfile.exists():
        for line in envfile.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(rf"\s*{re.escape(key)}\s*=\s*(.+?)\s*$", line)
            if m:
                return m.group(1).strip().strip('"').strip("'")
    return default


def _reader_password() -> str:
    return _env_or_mcp("GRAFANA_PG_READER_PASSWORD", "CHANGE_ME_grafana_reader")


def datasource_health():
    """Assert Grafana can ACTUALLY connect to Postgres as grafana_reader.

    The per-table checks above connect via `-h 127.0.0.1`, which pg_hba maps to
    `trust` (no password check) — so they validate RLS/grants but are BLIND to a
    datasource<->role PASSWORD MISMATCH. Grafana connects over the Docker network
    (scram-sha-256), which DOES check the password. On 2026-07-18 the datasource
    silently 400'd ("password authentication failed for user grafana_reader") on a
    3-way drift (.env.mcp vs stale container env vs role) while this gate stayed
    green — every panel showed "No data". This check closes that blind spot by
    hitting the Grafana datasource-health API (basic-auth, creds from .env.mcp),
    which transitively exercises the real password path.

    Returns (state, detail): state in {"ok","fail","skip"}.
    """
    url = _env_or_mcp("GRAFANA_URL", "http://127.0.0.1:3001").rstrip("/")
    # MCP uses host.docker.internal; from the host the gate must hit localhost.
    url = url.replace("host.docker.internal", "127.0.0.1")
    user = _env_or_mcp("GRAFANA_ADMIN_USER", "admin")
    pw = _env_or_mcp("GRAFANA_ADMIN_PASSWORD", "")
    ds_uid = os.environ.get("GRAFANA_DS_UID", "supabase_local")
    if not pw:
        return "skip", "GRAFANA_ADMIN_PASSWORD not set (env or infra/mcp/.env.mcp)"
    rc, out = sh(["curl", "-s", "-u", f"{user}:{pw}",
                  f"{url}/api/datasources/uid/{ds_uid}/health"], timeout=15)
    if rc != 0 or not out.strip():
        return "skip", f"grafana not reachable at {url} ({out[:80]})"
    try:
        body = json.loads(out)
    except Exception:
        return "skip", f"non-JSON health response ({out[:80]})"
    if body.get("status") == "OK":
        return "ok", body.get("message", "OK")
    return "fail", f"{body.get('status')}: {body.get('message', out[:120])}"


def sh(args, timeout=30):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def running() -> bool:
    rc, out = sh(["docker", "ps", "--format", "{{.Names}}"])
    return rc == 0 and DB in out.splitlines()


def count_as(user: str, table: str, password: str | None):
    """Return (ok, value_or_error). ok=False means the read errored (blind)."""
    base = ["docker", "exec"]
    if password is not None:
        base += ["-e", f"PGPASSWORD={password}"]
    base += [DB, "psql", "-U", user, "-d", "postgres", "-tA"]
    if password is not None:
        base += ["-h", "127.0.0.1"]
    base += ["-c", f"SELECT count(*) FROM {table};"]
    rc, out = sh(base)
    out = out.strip()
    if rc != 0 or not out.isdigit():
        return False, out[:120]
    return True, int(out)


def main() -> int:
    print("\033[1mGrafana-Reader Read-Path Gate (Operator-Console→Grafana)\033[0m")
    print("=" * 60)
    if not running():
        print(f"SKIP: db container {DB} not running (live read-path gate needs local Supabase)")
        return 0

    # Datasource-health first: the ONE check that exercises the real (password-checked)
    # Grafana->Postgres path the trust-auth per-table reads below can't see.
    ds_state, ds_detail = datasource_health()
    ds_fail = ds_state == "fail"
    if ds_state == "ok":
        print(f"  {GREEN}ok{RST}   datasource: Grafana connects to Postgres — {ds_detail}")
    elif ds_state == "skip":
        print(f"  {YEL}skip{RST} datasource-health: {ds_detail}")
    else:
        print(f"  {RED}FAIL{RST} datasource: Grafana CANNOT connect — {ds_detail}")
        print(f"       (dashboards will show 'No data'. Check the grafana_reader password "
              f"matches across infra/mcp/.env.mcp, the running container's env, and the DB role.)")
    print("-" * 60)

    pw = _reader_password()
    failures, rows = [], []
    for t in REQUIRED:
        ok_su, truth = count_as("postgres", t, None)
        ok_gr, seen = count_as("grafana_reader", t, pw)
        if not ok_su:
            print(f"  {YEL}skip{RST} {t}: cannot read as postgres ({truth}) — table missing?")
            rows.append({"table": t, "status": "skip", "reason": "not readable as postgres"})
            continue
        if not ok_gr:
            print(f"  {RED}FAIL{RST} {t}: grafana_reader read ERRORED — {seen}")
            failures.append(t)
            rows.append({"table": t, "status": "fail", "truth": truth, "error": str(seen)})
            continue
        if seen < truth:
            print(f"  {RED}FAIL{RST} {t}: grafana_reader sees {seen}/{truth} rows (RLS partially blinds it)")
            failures.append(t)
            rows.append({"table": t, "status": "fail", "truth": truth, "seen": seen})
            continue
        print(f"  {GREEN}ok{RST}   {t}: grafana_reader sees {seen}/{truth}")
        rows.append({"table": t, "status": "ok", "truth": truth, "seen": seen})

    try:
        (ROOT / "grafana_reader_reads_report.json").write_text(
            json.dumps({"required": REQUIRED, "failures": failures, "tables": rows,
                        "datasource_health": {"state": ds_state, "detail": ds_detail}}, indent=2),
            encoding="utf-8")
    except Exception:
        pass

    print()
    if ds_fail:
        print(f"  {RED}Grafana datasource unhealthy{RST} — the role/datasource password path is broken, "
              f"so ALL panels are dark regardless of RLS. Fix before shipping.")
        return 1
    if failures:
        print(f"  {RED}{len(failures)} table(s) blind to grafana_reader{RST} — the Grafana dashboard/alert "
              f"reading them is empty or dark. Add a `<t>_grafana_read` SELECT policy in "
              f"infra/mcp/grafana/grafana_reader.sql (least-privilege, per-table).")
        return 1
    print(f"  {GREEN}PASS{RST} — grafana_reader reads all {len(REQUIRED)} dashboard-dependency tables "
          f"through RLS, and Grafana's datasource connects over the password-checked path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
