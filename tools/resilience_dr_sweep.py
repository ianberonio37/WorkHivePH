#!/usr/bin/env python3
"""
resilience_dr_sweep.py - Arc S (Resilience / DR / Chaos) aggregate scorer (R0).
=====================================================================================
The ONE ratcheted, measured-% board for the platform's resilience posture, across the
four lenses (NEXT_ARC_STUDY_post_Q.md §3):

  F - Failure-tolerance  (each dependency down -> graceful degrade, never white-screen/5xx)
  R - Recovery           (backup/restore proven; RPO/RTO; no silent data-loss window)
  C - Consistency        (idempotent + atomic writes; no partial-write corruption; exactly-once)
  D - Degradation        (offline / read-only / queue-and-retry; the field-worker data survives)

INVENT NOTHING for the existing cells - it runs the platform's existing DR validators as
subprocesses (never imports a gate) and maps each to a lens + sub-layer. The existing
"Pillar DR" base (game_day, verify_backups, validate_idempotency, perf_l5_llm_resilience)
is scattered with its own exit contracts; this board unifies them into one measured-% frame.

NEW Arc-S cells with no validator yet are scored MISSING == "unswept failure mode" -
measured-not-credited: an honest baseline shows the gap rather than hiding it. As each new
gate lands (validate_dependency_timeout, validate_dr_claims, validate_atomic_writes,
validate_offline_resilience, ...) its cell flips to live.

Per-lens %  = PASS cells / total cells in lens.
Floors      : F 90 / R 95 / C 100 / D 85  (C runs at 100 - a lost/corrupt write is the worst class).
Ratchet     : resilience_dr_baseline.json - a lens %% may not regress below baseline.

Output : resilience_dr_results.json (+ console board)
Exit 0 : all floors met AND no lens regressed below baseline
Exit 1 : a floor missed or a regression
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
RESULTS = ROOT / "resilience_dr_results.json"
BASELINE = ROOT / "resilience_dr_baseline.json"

CHECK_NAMES = ["resilience_dr_sweep"]
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; C = "\033[96m"; X = "\033[0m"

FLOORS = {"F": 90, "R": 95, "C": 100, "D": 85}

# Each cell: (key, validator-stem-or-None, sublayer, note).
# validator None == a NEW Arc-S failure mode with no gate yet -> scored MISSING (unswept).
# Validators are resolved at ROOT first, then ROOT/tools.
LENSES = {
    "F": {  # Failure-tolerance
        "title": "Failure-tolerance",
        "cells": [
            ("gateway_failsafe",      "game_day",                      "S1", "AI gateway fails safe (4xx not 5xx, auth holds, health recovers)"),
            ("dependency_timeout",    "validate_dependency_timeout",   "S1", "data fetches bounded by a timeout + degraded UI (no infinite hang)"),
            ("ai_alldown_degrade",    "validate_ai_alldown_degrade",   "S1", "AI all-providers-down returns a structured error, not bare '{}'"),
            ("external_circuit_breaker","validate_circuit_breaker",    "S1", "external APIs (Stripe/Resend/CMMS) circuit-break like provider-health"),
            ("cdn_resilience",        "validate_cdn_resilience",       "S1", "CDN-loaded libs degrade gracefully when the CDN is unreachable"),
        ],
    },
    "R": {  # Recovery
        "title": "Recovery",
        "cells": [
            ("schema_backup",         "verify_backups",                "S2", "schema reproducible from migration lock + restore runbook present"),
            ("dr_claims_backed",      "validate_dr_claims",            "S2", "every RTO/RPO claim has a backing implementation (no false-sense doc)"),
            ("data_backup_restore",   "validate_data_backup",          "S2", "a logical data backup+restore path exists and is drilled"),
            ("dataloss_detection",    "validate_dataloss_detection",   "S5", "rowcount/checksum monitor surfaces silent row-deletions in-window"),
        ],
    },
    "C": {  # Consistency
        "title": "Consistency",
        "cells": [
            ("idempotency_6layer",    "validate_idempotency",          "S3", "6-layer webhook/upsert/external-API idempotency"),
            ("atomic_multistep",      "validate_atomic_writes",        "S3", "multi-step writes use an atomic RPC/txn (no partial-write corruption)"),
            ("optimistic_lock",       "validate_optimistic_lock",      "S3", "read-modify-write uses compare-and-set (no silent lost-update)"),
            ("dedup_constraints",     "validate_dedup_constraints",    "S3", "dedup-prone writes have a UNIQUE constraint / onConflict"),
            ("optimistic_ui_rollback","validate_optimistic_ui",        "S3", "optimistic UI rolls back on write failure (no phantom-saved row)"),
        ],
    },
    "D": {  # Degradation
        "title": "Degradation",
        "cells": [
            ("offline_write_queue",   "validate_offline_resilience",   "S4", "write-heavy pages wire the offline-write queue (no lost field write)"),
            ("queue_retry_strategy",  "validate_offline_queue_retry",  "S4", "the offline queue has retry/backoff/dead-letter (no stuck-forever item)"),
            ("precache_coverage",     "validate_precache_coverage",    "S4", "critical pages precached in sw.js (no blank page offline)"),
            ("backend_degraded_mode", "validate_degraded_mode",        "S4", "backend-degradation detected -> read-only banner / cached-data fallback"),
        ],
    },
}


def _resolve(stem: str) -> Path | None:
    for cand in (ROOT / f"{stem}.py", ROOT / "tools" / f"{stem}.py"):
        if cand.exists():
            return cand
    return None


def _run(stem: str | None) -> str:
    if stem is None:
        return "MISSING"          # NEW failure mode, no gate yet -> unswept
    p = _resolve(stem)
    if p is None:
        return "MISSING"
    try:
        r = subprocess.run([PY, str(p)], cwd=str(ROOT), capture_output=True, text=True, timeout=240)
        return "PASS" if r.returncode == 0 else "FINDINGS"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception:
        return "ERROR"


def main() -> int:
    cache: dict[str, str] = {}
    lens_out = {}
    for lens, spec in LENSES.items():
        rows = []
        for key, stem, sub, note in spec["cells"]:
            ck = stem or f"__new__{key}"
            if ck not in cache:
                cache[ck] = _run(stem)
            status = cache[ck]
            rows.append({"key": key, "validator": stem, "sublayer": sub,
                         "status": status, "note": note,
                         "covered": stem is not None and status != "MISSING"})
        total = len(rows)
        passed = sum(1 for r in rows if r["status"] == "PASS")
        pct = round(100 * passed / total, 1) if total else 0.0
        lens_out[lens] = {"title": spec["title"], "cells": rows,
                          "passed": passed, "total": total, "pct": pct,
                          "floor": FLOORS[lens]}

    baseline = {}
    if BASELINE.exists():
        try:
            baseline = json.loads(BASELINE.read_text(encoding="utf-8")).get("lenses", {})
        except Exception:
            baseline = {}

    floors_ok, regressions = True, []
    for lens, L in lens_out.items():
        if L["pct"] < L["floor"]:
            floors_ok = False
        base_pct = baseline.get(lens, {}).get("pct")
        if base_pct is not None and L["pct"] < base_pct - 0.05:
            regressions.append(f"{lens}: {L['pct']} < baseline {base_pct}")

    result = {
        "scored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lenses": {k: {"title": v["title"], "pct": v["pct"], "passed": v["passed"],
                       "total": v["total"], "floor": v["floor"], "cells": v["cells"]}
                   for k, v in lens_out.items()},
        "floors_ok": floors_ok, "regressions": regressions,
    }
    RESULTS.write_text(json.dumps(result, indent=2), encoding="utf-8")

    update = "--update-baseline" in sys.argv
    if update:
        BASELINE.write_text(json.dumps(
            {"updated_at": result["scored_at"],
             "lenses": {k: {"pct": v["pct"]} for k, v in lens_out.items()}}, indent=2),
            encoding="utf-8")

    print(f"{B}{C}Arc S - Resilience / DR / Chaos sweep{X}")
    for lens, L in lens_out.items():
        ok = L["pct"] >= L["floor"]
        bar = (G if ok else R) + f"{L['pct']:5.1f}%" + X
        print(f"  {lens} {L['title']:<22} {bar}  ({L['passed']}/{L['total']})  floor {L['floor']}")
        for c in L["cells"]:
            if c["status"] != "PASS":
                col = Y if c["status"] == "MISSING" else R
                print(f"      {col}{c['status']:<9}{X} {c['key']}  ({c['sublayer']}) - {c['note']}")

    if update:
        print(f"{G}baseline updated.{X}")
    if regressions:
        print(f"{R}REGRESSION: {'; '.join(regressions)}{X}")
        return 1
    if not floors_ok:
        print(f"{Y}floors not yet met (expected during the arc - ratchet up).{X}")
        return 1
    print(f"{G}PASS - all lens floors met, no regression.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
