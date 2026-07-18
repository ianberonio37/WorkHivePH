"""
Grafana SLO Dashboard Gate (Arc T / T5, 2026-07-02).
====================================================
Locks the durably-provisioned golden-signal dashboard so it can't silently rot:
the provider config + the dashboard JSON must exist, the JSON must parse, carry
the expected uid, bind the `supabase_local` datasource, and have panels whose
queries reference wh_traces / the T3 rollup. Static (no running Grafana needed)
so it runs in --fast.

Exit: 0 valid ; 1 missing / malformed / mis-wired.
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
PROV = ROOT / "infra" / "mcp" / "grafana" / "provisioning" / "dashboards"
PROVIDER = PROV / "dashboards.yml"
DASH = PROV / "workhive-slo.json"
ALERTING = ROOT / "infra" / "mcp" / "grafana" / "provisioning" / "alerting" / "slo-alerts.yml"
REPORT = ROOT / "grafana_slo_dashboard_report.json"
CHECK_NAMES = ["grafana_slo_dashboard", "grafana-slo-dashboard"]

EXPECT_UID = "workhive-slo-arct"
EXPECT_DS = "supabase_local"


def main() -> int:
    issues: list[str] = []
    info: dict = {}

    if not PROVIDER.exists():
        issues.append(f"missing provider config {PROVIDER.relative_to(ROOT)}")
    else:
        ptxt = PROVIDER.read_text(encoding="utf-8", errors="replace")
        if "providers:" not in ptxt or "/etc/grafana/provisioning/dashboards" not in ptxt:
            issues.append("provider config missing providers: block or the dashboards path")

    if not DASH.exists():
        issues.append(f"missing dashboard JSON {DASH.relative_to(ROOT)}")
    else:
        try:
            d = json.loads(DASH.read_text(encoding="utf-8"))
        except Exception as e:
            issues.append(f"dashboard JSON does not parse: {e}")
            d = None
        if d is not None:
            info["uid"] = d.get("uid")
            panels = d.get("panels", [])
            info["panels"] = len(panels)
            if d.get("uid") != EXPECT_UID:
                issues.append(f"dashboard uid {d.get('uid')!r} != {EXPECT_UID!r}")
            if not panels:
                issues.append("dashboard has no panels")
            blob = json.dumps(d)
            if EXPECT_DS not in blob:
                issues.append(f"dashboard does not bind the {EXPECT_DS!r} datasource")
            if "wh_traces" not in blob and "v_wh_traces_slo" not in blob:
                issues.append("no panel query references wh_traces / v_wh_traces_slo")
            # every panel with a target should carry a rawSql (SQL datasource)
            missing_sql = [p.get("title", p.get("id")) for p in panels
                           if p.get("targets") and not any(t.get("rawSql") for t in p["targets"])]
            if missing_sql:
                issues.append(f"panels with targets but no rawSql: {missing_sql}")

    # T4: alert routing provisioning (rule + contact point + policy).
    if not ALERTING.exists():
        issues.append(f"missing alerting provisioning {ALERTING.relative_to(ROOT)}")
    else:
        atxt = ALERTING.read_text(encoding="utf-8", errors="replace")
        for needle, label in (("contactPoints:", "contactPoints"), ("groups:", "alert rule groups"),
                              ("wh_slo_edge_errors", "the SLO edge-errors rule uid"),
                              (EXPECT_DS, f"the {EXPECT_DS} datasource"), ("wh_traces", "a wh_traces query")):
            if needle not in atxt:
                issues.append(f"alerting provisioning missing {label}")
        info["alerting_present"] = True

    info["issues"] = issues
    REPORT.write_text(json.dumps(info, indent=2), encoding="utf-8")

    if issues:
        print(f"\033[91mFAIL: Grafana SLO dashboard provisioning invalid:\033[0m")
        for i in issues:
            print(f"  - {i}")
        return 1
    print(f"\033[92mPASS: provisioned dashboard {info.get('uid')} valid ({info.get('panels')} panels, {EXPECT_DS} datasource, wh_traces/rollup queries).\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
