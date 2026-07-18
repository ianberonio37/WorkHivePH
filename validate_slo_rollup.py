"""
SLO Rollup Gate (Arc T / T3, 2026-07-02).
========================================
Locks the T3 error-budget rollup over wh_traces (migration
20260702000001_slo_error_budget_rollup.sql): the `v_wh_traces_slo` view and the
`slo_error_budget()` RPC must exist AND compute correctly. Proven by seeding
crafted traces in a ROLLED-BACK txn and asserting the rollup + burn math in SQL
(a RAISE aborts the txn -> psql non-zero -> FAIL). Zero pollution, zero external
deps — the same self-proving pattern as tools/observability_fault_walk.py.

SKIPs cleanly (exit 0) if the local DB is unreachable — it is a live gate, not a
static one; a real assertion failure is exit 1.

Env override: WH_LOCAL_DB_CONTAINER.
Exit: 0 pass/skip ; 1 rollup missing or math wrong.
"""
from __future__ import annotations
import io, json, os, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "slo_rollup_report.json"
DB = os.environ.get("WH_LOCAL_DB_CONTAINER", "supabase_db_workhive")
CHECK_NAMES = ["slo_rollup", "slo-rollup"]

# Crafted fixture: 2 real errors (one within 1h, one 2h ago), 1 policy 403
# (must be EXCLUDED), 1 success 200 (excluded). Then assert every derived value.
# All inside a txn that ROLLS BACK. A RAISE aborts -> psql exits non-zero.
SELFTEST_SQL = r"""
begin;
insert into wh_traces(trace_id, route, status, error_code, created_at) values
  ('slo_selftest_a', '__slo_selftest__', 500, 'unhandled_error', now()),
  ('slo_selftest_b', '__slo_selftest__', 500, 'db_timeout',      now() - interval '2 hours'),
  ('slo_selftest_c', '__slo_selftest__', 403, null,              now()),
  ('slo_selftest_d', '__slo_selftest__', 200, null,              now());
do $$
declare
  v   record;
  b   numeric;
  st  text;
begin
  select * into v from v_wh_traces_slo where route = '__slo_selftest__';
  if v.traced_total      <> 4 then raise exception 'traced_total %=<>4', v.traced_total; end if;
  if v.error_count       <> 2 then raise exception 'error_count %<>2', v.error_count; end if;
  if v.policy_rejections <> 1 then raise exception 'policy_rejections %<>1 (403 not excluded)', v.policy_rejections; end if;
  if v.errors_6h         <> 2 then raise exception 'errors_6h %<>2', v.errors_6h; end if;
  if v.errors_1h         <> 1 then raise exception 'errors_1h %<>1 (window wrong)', v.errors_1h; end if;

  select budget_burn, status into b, st from slo_error_budget('__slo_selftest__', 360, 100);
  if b  <> 2.0        then raise exception 'budget_burn %<>2.0 (2 err/100 req = 2%% = 2x the 1%% budget)', b; end if;
  if st <> 'critical' then raise exception 'status %<>critical', st; end if;

  select status into st from slo_error_budget('__slo_selftest__', 360, null);
  if st <> 'unknown_volume' then raise exception 'null-volume status %<>unknown_volume (fake denominator?)', st; end if;

  raise notice 'slo_rollup self-test OK: error_count=2, burn=2.0/critical, null-vol=unknown_volume';
end $$;
rollback;
"""


def sh(args, timeout=30, stdin=None):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, input=stdin)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def running() -> bool:
    rc, out = sh(["docker", "ps", "--format", "{{.Names}}"])
    return rc == 0 and DB in out.splitlines()


def main() -> int:
    result = {"objects": {}, "status": None, "note": None}
    if not running():
        result.update(status="SKIP", note=f"db container {DB} not running")
        REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"SKIP: db container {DB} not running (live SLO-rollup gate needs local Supabase)")
        return 0

    # 1) objects exist
    rc, out = sh(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c",
                  "select "
                  "(select count(*) from pg_views where viewname='v_wh_traces_slo'), "
                  "(select count(*) from pg_proc where proname='slo_error_budget');"])
    parts = (out.strip().split("|") if "|" in out else out.strip().split())
    view_ok = parts and parts[0].strip() == "1"
    func_ok = len(parts) > 1 and parts[1].strip() == "1"
    result["objects"] = {"v_wh_traces_slo": view_ok, "slo_error_budget": func_ok}
    if not (view_ok and func_ok):
        result.update(status="FAIL", note=f"missing rollup objects: {result['objects']} (migration 20260702000001 applied?)")
        REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\033[91mFAIL: {result['note']}\033[0m")
        return 1

    # 2) math self-test in a rolled-back txn
    rc, out = sh(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                  "-v", "ON_ERROR_STOP=1"], stdin=SELFTEST_SQL)
    ok = rc == 0 and "self-test OK" in out
    result["selftest_output"] = out.strip()[-500:]
    if not ok:
        result.update(status="FAIL", note="rollup math self-test failed")
        REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\033[91mFAIL: rollup math self-test failed:\n{out.strip()[-400:]}\033[0m")
        return 1

    # 3) the Grafana datasource role can READ the signal through RLS (Arc T/T4+T5
    #    defect guard, added 2026-07-17 after a live fault-walk found the alert
    #    was blind). wh_traces has RLS + only an `authenticated`-scoped policy, so
    #    a SELECT grant is NOT enough for grafana_reader — it needs BYPASSRLS or a
    #    dedicated SELECT policy, else the SLO dashboard panels are empty AND the
    #    wh_slo_edge_errors alert can never fire. Only asserted when grafana_reader
    #    exists (it is a manual infra role); otherwise noted, not failed.
    rc, out = sh(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c",
                  "select "
                  "exists(select 1 from pg_roles where rolname='grafana_reader'), "
                  "coalesce((select rolbypassrls from pg_roles where rolname='grafana_reader'), false) "
                  "  or exists(select 1 from pg_policies where tablename='wh_traces' "
                  "            and cmd in ('SELECT','ALL') and 'grafana_reader' = any(roles));"])
    parts = out.strip().split("|")
    reader_exists = parts and parts[0].strip() == "t"
    reader_can_read = len(parts) > 1 and parts[1].strip() == "t"
    result["grafana_reader"] = {"exists": reader_exists, "can_read_wh_traces": reader_can_read}
    if reader_exists and not reader_can_read:
        result.update(status="FAIL", note="grafana_reader exists but cannot read wh_traces through RLS "
                      "— the SLO dashboard + wh_slo_edge_errors alert are BLIND (grant SELECT is not "
                      "enough under RLS; needs the wh_traces_grafana_slo_read policy or BYPASSRLS)")
        REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\033[91mFAIL: {result['note']}\033[0m")
        return 1

    reader_note = ("grafana_reader can read wh_traces through RLS" if reader_exists
                   else "grafana_reader role not present (infra setup pending) — read-path check skipped")
    result.update(status="PASS", note=f"rollup objects present + math self-test passed (rolled back); {reader_note}")
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("\033[92mPASS: v_wh_traces_slo + slo_error_budget present; seeded self-test math correct (rolled back); "
          f"{reader_note}.\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
