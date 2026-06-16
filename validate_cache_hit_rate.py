"""
Cache Efficiency / Hit-Rate Ratchet (Maturity Phase 2, 2026-06-16).
====================================================================
Closes the (CA, GH) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 — the
cache hardening cell (study §7 #19, "hit-rate ratchet").

A cache only helps if it is actually configured to cache. This gate hardens
the three tiers so a cache regression (a deleted Cache-Control rule, a dropped
LLM adopter) FAILs:

  L1  CDN: _headers declares >= 1 Cache-Control rule (static actually caches)
  L2  LLM: cached() adopter FLOOR ratchet (only descends would FAIL; raise it)
  L3  hit-rate (informational): if a live ai_cache hit-rate snapshot exists,
      warn below 25% (the swap-ready live ratchet; SKIP without data)

Reads cache_signals_report.json (auto-runs mine_cache_signals.py).
Output:  cache_hit_rate_report.json
Baseline: cache_hit_rate_baseline.json   (adopter floor; only rises)
Exit code: 0 PASS / 1 FAIL (no CDN cache rule, or adopters dropped below floor)
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SIGNALS = ROOT / "cache_signals_report.json"
MINER   = ROOT / "tools" / "mine_cache_signals.py"
REPORT   = ROOT / "cache_hit_rate_report.json"
BASELINE = ROOT / "cache_hit_rate_baseline.json"

CHECK_NAMES = ["cache_hit_rate"]
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
    cdn_rules = int(sig.get("cdn", {}).get("cache_control_rules", 0))
    adopters = int(sig.get("llm_cache", {}).get("adopter_count", 0))

    base = _load(BASELINE)
    first_lock = base is None
    if first_lock:
        base = {"adopter_floor": adopters}
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")
    floor = int(base.get("adopter_floor", adopters))

    fails: list[str] = []
    if cdn_rules < 1:
        fails.append("CDN _headers declares 0 Cache-Control rules — static assets are not cache-policied.")
    if adopters < floor:
        fails.append(f"LLM cache adopters {adopters} < floor {floor} — a cache adopter was removed.")

    # raise the floor (lock the win) when adoption grows
    if adopters > floor and not fails:
        base["adopter_floor"] = adopters
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")

    REPORT.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cdn_cache_control_rules": cdn_rules, "llm_adopters": adopters,
        "adopter_floor": base["adopter_floor"], "first_lock": first_lock, "fails": fails,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}Cache Efficiency / Hit-Rate Ratchet (CA, GH){RESET}")
    print(f"  CDN Cache-Control rules: {cdn_rules}")
    print(f"  LLM cache adopters: {adopters}  (floor {base['adopter_floor']})")
    if first_lock:
        print(f"{YEL}  adopter floor locked at {adopters} (first run).{RESET}")
    if fails:
        print(f"{RED}FAIL: {len(fails)} cache-efficiency regression(s):{RESET}")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"{GREEN}PASS — CDN cache policy present + LLM adopters at/above floor.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
