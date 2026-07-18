"""
AV-Adoption Ratchet (L0) — FULLSTACK_COMPONENT_LIBRARY_ROADMAP Layer AV.
================================================================================
The offline canonical set (offline-banner / offline-queue / connectivity-widget /
session-timeout / device-fingerprint) ships as ONE unit on every non-exempt family
page (wave completed 29/29 on 2026-07-17). This ratchet recomputes adoption live
and fails any page dropping ANY of the five (floors forward-only, auto-tighten).
Exempt (av_component_registry.json): the chrome-less trio.
Output: av_adoption_gate_report.json. Exit 1 on a drop, else 0.
"""
from __future__ import annotations

import datetime
import io
import json
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SCRIPTS = ["offline-banner.js", "offline-queue.js", "connectivity-widget.js",
           "session-timeout.js", "device-fingerprint.js"]
BASELINE = ROOT / "av_adoption_baseline.json"
REPORT = ROOT / "av_adoption_gate_report.json"


def main() -> int:
    reg = json.loads((ROOT / "av_component_registry.json").read_text(encoding="utf-8"))
    exempt = set(reg["components"][0].get("exempt", []))
    fam = json.loads((ROOT / "family_rubric_baseline.json").read_text(encoding="utf-8"))
    pages = sorted(set(fam["pages"].keys() if isinstance(fam["pages"], dict) else fam["pages"]) - exempt)

    adopters, partial = [], {}
    for p in pages:
        f = ROOT / p
        if not f.exists():
            continue
        src = f.read_text(encoding="utf-8", errors="ignore")
        have = [x for x in SCRIPTS if x in src]
        if len(have) == len(SCRIPTS):
            adopters.append(p)
        elif have:
            partial[p] = sorted(set(SCRIPTS) - set(have))

    floor = 0
    if BASELINE.exists():
        try:
            floor = json.loads(BASELINE.read_text(encoding="utf-8")).get("floors", {}).get("AV1", 0)
        except Exception:
            floor = 0
    failures = []
    if len(adopters) < floor:
        failures.append(f"AV1 adoption fell {floor} -> {len(adopters)}")
    for p, missing in partial.items():
        failures.append(f"{p} PARTIAL set — missing: {', '.join(missing)} (the set ships as one unit)")

    ok = not failures
    if ok:
        BASELINE.write_text(json.dumps({
            "_doc": "Layer AV adoption baseline. Floors forward-only.",
            "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "rows": [{"id": "AV1", "mode": "measured", "adopters_n": len(adopters),
                      "need_n": len(pages), "pct": round(100 * len(adopters) / len(pages)) if pages else None,
                      "adopters": adopters, "gap": sorted(set(pages) - set(adopters))}],
            "floors": {"AV1": max(len(adopters), floor)},
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    REPORT.write_text(json.dumps({
        "ok": ok, "adopters": len(adopters), "need": len(pages), "failures": failures,
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"av-adoption: {len(adopters)}/{len(pages)} full-set adopters (floor {floor})")
    for f in failures:
        print(f"  FAIL {f}")
    print("  " + ("PASS (forward-only floor held)" if ok else f"{len(failures)} FAILURE(S)"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
