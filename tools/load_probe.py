#!/usr/bin/env python3
"""load_probe.py - Pillar C (Compute & Resilience): a LOCAL load test, no k6.
================================================================================
`tools/load_test.k6.js` is the full rig but needs the k6 binary + ideally a
staging env. This is the zero-dependency local counterpart: a stdlib concurrent
driver that hammers the gateway's request-handling path and checks the latency +
error-rate SLOs from GATEWAY_SLO.md. It drives the PUBLIC /health surface (and
optionally a cheap rejected path) so it measures the edge's throughput/latency
WITHOUT burning LLM tokens - gateway capacity, not model capacity.

SLO assertions (GATEWAY_SLO.md):
  p95 latency < 2000 ms   ·   error rate < 1%

On PASS it stamps the shared gate marker (`.last-fullstack-gate-pass` -> load_test:PASS)
so `fullstack_dev.py pillars` credits the C "load-test executed" criterion.

Usage:
  python tools/load_probe.py            # 8 workers x 40 reqs = 320 calls
  python tools/load_probe.py --vus 16 --reqs 60
Exit 0 = SLOs met; 1 = an SLO breached; 2 = edge unreachable (nothing to test).
"""
from __future__ import annotations
import argparse
import io
import json
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MARKER = ROOT / ".last-fullstack-gate-pass"
REPORT = ROOT / "load_probe_report.json"
EDGE = "http://127.0.0.1:54321/functions/v1"

P95_SLO_MS = 2000
ERR_SLO    = 0.01
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"

# Round-robin a few /health surfaces (public, no LLM cost).
TARGETS = ["/ai-gateway/health", "/platform-gateway/health", "/agentic-rag-loop/health",
           "/voice-action-router/health", "/asset-brain-query/health"]


def _one(path: str) -> tuple[float, bool]:
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(f"{EDGE}{path}", timeout=15) as r:
            r.read(256)
            ok = 200 <= r.status < 300
    except urllib.error.HTTPError as e:
        ok = 200 <= e.code < 300
    except Exception:  # noqa: BLE001
        ok = False
    return (time.perf_counter() - t0) * 1000.0, ok


def _pct(sorted_ms: list[float], p: float) -> float:
    if not sorted_ms:
        return 0.0
    i = min(len(sorted_ms) - 1, max(0, int(round(p * len(sorted_ms))) - 1))
    return sorted_ms[i]


def edge_up() -> bool:
    return _one("/ai-gateway/health")[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vus", type=int, default=8)
    ap.add_argument("--reqs", type=int, default=40)
    a = ap.parse_args()

    print(f"{BOLD}\nLOAD PROBE (Pillar C) - {EDGE}{RESET}")
    print("=" * 60)
    if not edge_up():
        print(f"{YEL}SKIP (exit 2){RESET}: local edge not reachable - start it to load-test.")
        return 2

    total = a.vus * a.reqs
    plan = [TARGETS[i % len(TARGETS)] for i in range(total)]
    print(f"  driving {total} requests ({a.vus} concurrent workers x {a.reqs}) across {len(TARGETS)} surfaces...")

    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=a.vus) as ex:
        results = list(ex.map(_one, plan))
    wall = time.perf_counter() - t_start

    lat = sorted(r[0] for r in results)
    errors = sum(1 for r in results if not r[1])
    err_rate = errors / len(results) if results else 1.0
    rps = len(results) / wall if wall else 0.0
    p50, p95, p99 = _pct(lat, 0.50), _pct(lat, 0.95), _pct(lat, 0.99)

    p95_ok = p95 < P95_SLO_MS
    err_ok = err_rate < ERR_SLO
    print(f"  throughput : {rps:6.1f} req/s   ({wall:.1f}s wall)")
    print(f"  latency    : p50 {p50:.0f}ms · p95 {p95:.0f}ms · p99 {p99:.0f}ms   "
          f"{(GREEN+'OK'+RESET) if p95_ok else (RED+'BREACH'+RESET)} (SLO p95<{P95_SLO_MS}ms)")
    print(f"  error rate : {100*err_rate:.2f}%   "
          f"{(GREEN+'OK'+RESET) if err_ok else (RED+'BREACH'+RESET)} (SLO <{100*ERR_SLO:.0f}%)")

    passed = p95_ok and err_ok
    REPORT.write_text(json.dumps({
        "requests": total, "vus": a.vus, "rps": round(rps, 1), "wall_s": round(wall, 2),
        "p50_ms": round(p50), "p95_ms": round(p95), "p99_ms": round(p99),
        "error_rate": round(err_rate, 4), "p95_slo_ms": P95_SLO_MS, "err_slo": ERR_SLO,
        "result": "PASS" if passed else "FAIL",
    }, indent=2), encoding="utf-8")

    if passed:
        marker = {}
        if MARKER.exists():
            try: marker = json.loads(MARKER.read_text(encoding="utf-8"))
            except Exception: marker = {}
        marker["load_test"] = "PASS"
        marker["load_test_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        MARKER.write_text(json.dumps(marker, indent=2), encoding="utf-8")
        print(f"\n{GREEN}{BOLD}  LOAD PROBE: PASS{RESET} - SLOs met; marked load_test=PASS.")
        return 0
    print(f"\n{RED}{BOLD}  LOAD PROBE: FAIL{RESET} - an SLO was breached (see above).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
