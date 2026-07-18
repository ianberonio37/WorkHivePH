"""
SLO Burn-Rate Alert (Arc T / T3, 2026-07-02).
=============================================
The operational burn-rate alert rule over the T3 rollup. Multi-window (Google
SRE pattern): a route ALERTS only when BOTH a fast (1h) AND a slow (6h) window
exceed the burn threshold — the fast window catches fast burns, the slow window
suppresses one-off blips. Burn = observed error-rate / the 1% SLO error budget,
computed by slo_error_budget() given an expected request volume.

Volume (the RATE denominator wh_traces can't supply on its own) comes from
--expected-rpm or WH_SLO_EXPECTED_RPM (requests/min); with no volume the tool
reports error COUNTS + 'unknown_volume' and does NOT alert (never a fake rate).

Usage:  python tools/slo_burn_check.py [--expected-rpm N] [--route R]
Env override: WH_LOCAL_DB_CONTAINER, WH_SLO_EXPECTED_RPM.
Exit: 0 no active alert / skip ; 2 one or more routes burning (operational
signal, not a build failure).
"""
from __future__ import annotations
import argparse, io, json, os, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "slo_burn_report.json"
DB = os.environ.get("WH_LOCAL_DB_CONTAINER", "supabase_db_workhive")
FAST_MIN, SLOW_MIN = 60, 360          # fast 1h, slow 6h
FAST_BURN, SLOW_BURN = 2.0, 1.0       # fast must burn >=2x, slow >=1x (both)
CHECK_NAMES = ["slo_burn_check"]


def sh(args, timeout=30):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def running() -> bool:
    rc, out = sh(["docker", "ps", "--format", "{{.Names}}"])
    return rc == 0 and DB in out.splitlines()


def burn(route_filter, window_min, expected_for_window):
    """Return {route: {error_count, burn, status}} from slo_error_budget()."""
    rsql = "null" if route_filter is None else f"'{route_filter}'"
    vsql = "null" if expected_for_window is None else str(int(expected_for_window))
    sql = (f"select route, error_count, coalesce(budget_burn,-1), status "
           f"from slo_error_budget({rsql}, {window_min}, {vsql});")
    rc, out = sh(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-F", "|", "-c", sql])
    rows = {}
    if rc == 0:
        for line in out.strip().splitlines():
            p = line.split("|")
            if len(p) >= 4 and p[0]:
                rows[p[0]] = {"error_count": int(p[1]), "burn": float(p[2]), "status": p[3]}
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expected-rpm", type=float,
                    default=float(os.environ.get("WH_SLO_EXPECTED_RPM", 0)) or None)
    ap.add_argument("--route", default=None)
    args = ap.parse_args()

    if not running():
        REPORT.write_text(json.dumps({"status": "SKIP", "note": "db down"}, indent=2), encoding="utf-8")
        print(f"SKIP: db container {DB} not running")
        return 0

    rpm = args.expected_rpm
    fast_vol = int(rpm * FAST_MIN) if rpm else None
    slow_vol = int(rpm * SLOW_MIN) if rpm else None
    fast = burn(args.route, FAST_MIN, fast_vol)
    slow = burn(args.route, SLOW_MIN, slow_vol)

    alerts = []
    routes = sorted(set(fast) | set(slow))
    for r in routes:
        f, s = fast.get(r), slow.get(r)
        if rpm and f and s and f["burn"] >= FAST_BURN and s["burn"] >= SLOW_BURN:
            sev = "critical" if (f["burn"] >= 4 or s["burn"] >= 2) else "warning"
            alerts.append({"route": r, "severity": sev,
                           "burn_1h": f["burn"], "burn_6h": s["burn"],
                           "errors_1h": f["error_count"], "errors_6h": s["error_count"]})

    report = {"expected_rpm": rpm, "fast_window_min": FAST_MIN, "slow_window_min": SLOW_MIN,
              "routes_seen": routes, "alerts": alerts,
              "status": "ALERT" if alerts else ("OK" if rpm else "NO_VOLUME")}
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if alerts:
        print(f"\033[91mBURN ALERT: {len(alerts)} route(s) over budget (fast>={FAST_BURN}x AND slow>={SLOW_BURN}x):\033[0m")
        for a in alerts:
            print(f"  [{a['severity']}] {a['route']}: 1h burn {a['burn_1h']}x ({a['errors_1h']} err), 6h burn {a['burn_6h']}x ({a['errors_6h']} err)")
        return 2
    if not rpm:
        print(f"No --expected-rpm/WH_SLO_EXPECTED_RPM set: reporting error counts only, not alerting. Routes with errors: {[r for r in routes]}")
        return 0
    print(f"\033[92mOK: no route burning (fast>={FAST_BURN}x AND slow>={SLOW_BURN}x) at {rpm} rpm.\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
