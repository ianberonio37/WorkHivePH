"""
Deploy-Config Substrate Miner (Maturity Phase 3, 2026-06-16).
==============================================================
Closes the (H, G-1.5) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4.

The Hosting & Deployment layer fails when an edge fn exists on disk but is NOT
registered in config.toml or the deploy script — it silently ships stale (study
§2: "bad deploy breaks all pages; no rollback path"). This miner surfaces the
deploy SHAPE: which edge fns are registered/deployed vs orphaned, and whether
the rollback + pre-deploy harness is present.

Inputs:  supabase/functions/*/, supabase/config.toml, deploy-functions.ps1,
         netlify.toml, _headers, ROLLBACK_RUNBOOK.md
Output:  deploy_signals_report.json
Exit code: 0 (informational miner)
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FN_DIR = ROOT / "supabase" / "functions"
CONFIG = ROOT / "supabase" / "config.toml"
DEPLOY = ROOT / "deploy-functions.ps1"
REPORT = ROOT / "deploy_signals_report.json"

CHECK_NAMES = ["deploy_signals"]


def main() -> int:
    fns_on_disk = sorted(
        e.name for e in FN_DIR.iterdir()
        if FN_DIR.exists() and e.is_dir() and not e.name.startswith("_") and (e / "index.ts").exists()
    ) if FN_DIR.exists() else []

    cfg = CONFIG.read_text(encoding="utf-8", errors="replace") if CONFIG.exists() else ""
    registered = set(re.findall(r"\[functions\.([a-z0-9\-]+)\]", cfg))

    dep = DEPLOY.read_text(encoding="utf-8", errors="replace") if DEPLOY.exists() else ""
    deployed = {f for f in fns_on_disk if f in dep}

    unregistered = [f for f in fns_on_disk if f not in registered]
    undeployed = [f for f in fns_on_disk if f not in deployed]

    out = {
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "edge_fns_on_disk": len(fns_on_disk),
        "registered_in_config": len(registered & set(fns_on_disk)),
        "in_deploy_script": len(deployed),
        "unregistered_fns": unregistered,
        "undeployed_fns": undeployed,
        "rollback_runbook": (ROOT / "ROLLBACK_RUNBOOK.md").exists(),
        "pre_deploy_gate": (ROOT / "tools" / "pre_deploy_gate.py").exists(),
        "netlify_config": (ROOT / "netlify.toml").exists(),
        "cdn_headers": (ROOT / "_headers").exists(),
    }
    REPORT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"Deploy-signals miner: {len(fns_on_disk)} edge fns on disk.")
    print(f"  registered in config.toml: {out['registered_in_config']}  | in deploy script: {out['in_deploy_script']}")
    print(f"  unregistered: {len(unregistered)}  undeployed: {len(undeployed)}")
    for f in undeployed[:8]:
        print(f"    - {f} (not in deploy-functions.ps1 → ships stale)")
    print(f"  rollback runbook: {out['rollback_runbook']} · pre-deploy gate: {out['pre_deploy_gate']}")
    print(f"  See: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
