"""
Rate-Limit Fairness Sentinel (Maturity Phase 2, 2026-06-16).
=============================================================
Closes the (RL, GS) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4.

Fairness invariant: a rate-limited edge fn must bucket on the SERVER-VERIFIED
hive id (`verifiedHiveId`), never a client-supplied one — else one tenant can
spoof another's id to drain its bucket (the Pillar-P cross-tenant DoS class).

This sentinel ratchets the count of "latent" fns (rate-limited but with no
verifiedHiveId binding) FORWARD-ONLY: a NEW rate-limited fn that doesn't bind
the verified id raises the count and FAILs. Existing latents (value is
membership-verified upstream — not exploitable, but should adopt the var for
clarity) are frozen at baseline and driven down over time.

L_keystone: ai-gateway (the main anon-capable front door) MUST bind verifiedHiveId.

Reads rate_limit_signals_report.json (auto-runs mine_rate_limit_signals.py).
Output:  rate_limit_fairness_report.json
Baseline: rate_limit_fairness_baseline.json   (latent count; only descends)
Exit code: 0 PASS / 1 FAIL (new spoofable-key fn, or keystone unbound)
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SIGNALS = ROOT / "rate_limit_signals_report.json"
MINER   = ROOT / "tools" / "mine_rate_limit_signals.py"
REPORT   = ROOT / "rate_limit_fairness_report.json"
BASELINE = ROOT / "rate_limit_fairness_baseline.json"

CHECK_NAMES = ["rate_limit_fairness"]
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _signals() -> dict:
    if not SIGNALS.exists() and MINER.exists():
        subprocess.run([sys.executable, str(MINER)], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=60)
    return _load(SIGNALS) or {}


def main() -> int:
    sig = _signals()
    latent = sorted(sig.get("latent_binding_fns", []))
    cur = len(latent)
    fns = {f["fn"]: f for f in sig.get("fns", [])}

    base = _load(BASELINE)
    first_lock = base is None
    if first_lock:
        base = {"latent": cur, "fns": latent}
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")
    baseline_n = int(base.get("latent", cur))
    new_latent = [f for f in latent if f not in set(base.get("fns", []))]

    fails: list[str] = []
    # keystone: ai-gateway must be fair (verifiedHiveId)
    ag = fns.get("ai-gateway")
    if ag is not None and not ag.get("verified_hive_binding"):
        fails.append("ai-gateway (keystone anon-capable front door) does not bind verifiedHiveId — spoofable bucket.")
    if cur > baseline_n:
        fails.append(f"latent rate-limit bindings {cur} > baseline {baseline_n} — a new fn rate-limits on a spoofable key: {', '.join(new_latent)}")

    if cur < baseline_n and not fails:
        base["latent"] = cur; base["fns"] = latent
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")

    REPORT.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "latent": cur, "baseline": baseline_n, "new_latent": new_latent,
        "keystone_ai_gateway_fair": (ag or {}).get("verified_hive_binding"),
        "first_lock": first_lock, "fails": fails,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}Rate-Limit Fairness Sentinel (RL, GS){RESET}")
    print(f"  latent (rate-limited, no verifiedHiveId): {cur}  (baseline {baseline_n})")
    print(f"  keystone ai-gateway binds verifiedHiveId: {(ag or {}).get('verified_hive_binding')}")
    if first_lock:
        print(f"{YEL}  baseline locked at {cur} (first run) — drive to 0 over Phase 2+.{RESET}")
    if fails:
        print(f"{RED}FAIL: {len(fails)} fairness violation(s):{RESET}")
        for f in fails:
            print(f"  - {f}")
        return 1
    if cur < baseline_n:
        print(f"{GREEN}PASS: fairness tightened {baseline_n} → {cur}.{RESET}")
        return 0
    print(f"{GREEN}PASS — no new spoofable-key rate limiter; keystone fair.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
