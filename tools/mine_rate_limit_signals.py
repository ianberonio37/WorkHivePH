"""
Rate-Limit Config Substrate Miner (Maturity Phase 2, 2026-06-16).
==================================================================
Closes the (RL, G-1.5) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4.

The Rate-Limiting layer's dominant failure mode (study §2) is "single noisy
worker starves hive; voice & RAG share bucket". Fairness depends on bucketing
on the SERVER-VERIFIED hive id (verifiedHiveId), not a client-supplied one.
This miner surfaces the SHAPE of rate-limit adoption + the per-fn bucketing key
so the (RL, GS) fairness sentinel can assert no fn buckets on a spoofable key.

Detects per edge fn:
  - which rate-limit primitives it calls (checkAI/User/Classed/Route/Solo)
  - whether it derives a verifiedHiveId (server-verified, fair bucketing)
  - "latent" fns: rate-limited but no verifiedHiveId binding (the Pillar-P
    latent backlog — value membership-verified upstream, adopt the var for clarity)

Inputs:  supabase/functions/*/index.ts
Output:  rate_limit_signals_report.json
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
REPORT = ROOT / "rate_limit_signals_report.json"

CHECK_NAMES = ["rate_limit_signals"]

RL_PRIMITIVES = [
    "checkAIRateLimit", "checkUserRateLimit", "checkClassedRateLimit",
    "checkRouteRateLimit", "checkSoloRateLimit",
]


def main() -> int:
    fns: list[dict] = []
    if FN_DIR.exists():
        for entry in sorted(FN_DIR.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            idx = entry / "index.ts"
            if not idx.exists():
                continue
            t = idx.read_text(encoding="utf-8", errors="replace")
            methods = [p for p in RL_PRIMITIVES if p in t]
            if not methods:
                continue
            # A bucket is FAIR (not spoofable) when EITHER it is identity/solo-bucketed
            # (no hive bucket at all), OR the hive it buckets on is SERVER-resolved
            # (verifiedHiveId var, or resolveTenancy from _shared/tenant-context.ts).
            # Only a hive-bucketed fn whose hive is NOT server-resolved is "latent".
            hive_bucket = ("checkAIRateLimit" in t) or ("checkClassedRateLimit" in t)
            server_resolved = ("verifiedHiveId" in t) or ("resolveTenancy" in t)
            fair = (not hive_bucket) or server_resolved
            fns.append({
                "fn": entry.name,
                "methods": methods,
                "hive_bucket": hive_bucket,
                "server_resolved": server_resolved,
                "verified_hive_binding": fair,
            })

    latent = [f["fn"] for f in fns if not f["verified_hive_binding"]]
    out = {
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rate_limited_fns": len(fns),
        "verified_binding_fns": sum(1 for f in fns if f["verified_hive_binding"]),
        "latent_binding_fns": sorted(latent),
        "latent_count": len(latent),
        "fns": sorted(fns, key=lambda x: x["fn"]),
    }
    REPORT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"Rate-limit-signals miner: {len(fns)} rate-limited edge fns.")
    print(f"  verifiedHiveId bound: {out['verified_binding_fns']}")
    print(f"  latent (no verifiedHiveId): {len(latent)}")
    for f in latent[:10]:
        print(f"    - {f}")
    print(f"  See: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
