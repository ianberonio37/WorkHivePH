#!/usr/bin/env python3
"""validate_state_scope_registry.py — T120's lock instrument: the account-vs-device state split is
DOCUMENTED and correctly classified — identity/memberships/records live at the ACCOUNT level (follow you
across devices), while filters/drafts/offline-queues/active-hive/language live at the DEVICE level (stay
on the phone) — so cross-device continuity has a single, honest source of truth.

T120 documented the split (substrate/reference/state_scope_registry.json): account = identity + persona +
memberships + all records; device = G5 filters, X2 drafts, offline queues, ACTIVE HIVE selection,
language/TTS, one-shot notices — each with its rationale, plus named known tensions. This gate locks the
registry's shape and the two classifications most likely to be got wrong: the active hive is DEVICE-level
(picking a hive on your phone must not change it on your PC), and identity is ACCOUNT-level.

Assertions (each refutable — see the self-test):
  1. SHAPE — account_level and device_level are non-empty lists; every entry names a `thing` and a `store`;
     known_tensions is present.
  2. ACTIVE HIVE IS DEVICE-LEVEL — 'active hive' appears in device_level, not account_level.
  3. IDENTITY IS ACCOUNT-LEVEL — 'identity' appears in account_level.

Read-only; no browser; no DB. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "substrate" / "reference" / "state_scope_registry.json"

CHECK_NAMES = ["state-scope-registry"]


def _things(entries) -> str:
    return " | ".join(str(e.get("thing", "")) for e in entries if isinstance(e, dict)).lower()


def check(reg: dict) -> list[str]:
    problems: list[str] = []
    acct = reg.get("account_level"); dev = reg.get("device_level")
    if not isinstance(acct, list) or not acct:
        problems.append("account_level is missing or empty"); acct = []
    if not isinstance(dev, list) or not dev:
        problems.append("device_level is missing or empty"); dev = []
    if "known_tensions" not in reg:
        problems.append("known_tensions is missing (the deliberate-not-accidental caveats are unrecorded)")
    for lvl, entries in (("account_level", acct), ("device_level", dev)):
        for e in entries:
            if not isinstance(e, dict) or not e.get("thing") or not e.get("store"):
                problems.append(f"{lvl} has an entry missing 'thing' or 'store' (classification without a home)")
                break
    at, dt = _things(acct), _things(dev)
    if "active hive" not in dt:
        problems.append("the ACTIVE HIVE is not classified DEVICE-level — picking a hive on the phone would "
                        "wrongly change it on the PC (it must be per-device).")
    if "active hive" in at:
        problems.append("the active hive is wrongly listed at ACCOUNT level.")
    if "identity" not in at:
        problems.append("identity is not classified ACCOUNT-level (it must follow the person across devices).")
    return problems


def main() -> int:
    if not REG.exists():
        print("FAIL state-scope-registry: state_scope_registry.json not found"); return 1
    try:
        reg = json.loads(REG.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"FAIL state-scope-registry: unreadable JSON ({e})"); return 1
    problems = check(reg)
    if problems:
        print("FAIL state-scope-registry — the account-vs-device split is incomplete or misclassified:")
        for p in problems[:8]:
            print(f"    {p}")
        return 1
    print("PASS state-scope-registry — account/device split is well-formed; the active hive is device-level "
          "and identity is account-level (cross-device continuity has an honest source of truth).")
    return 0


def self_test() -> int:
    good = {"account_level": [{"thing": "identity (username)", "store": "worker_profiles"}],
            "device_level": [{"thing": "ACTIVE HIVE selection", "store": "localStorage"}],
            "known_tensions": ["notification read-state device-local"]}
    fails = []
    if check(good):
        fails.append("a well-formed correctly-classified registry should PASS")
    if not any("ACTIVE HIVE" in p for p in check({"account_level": [{"thing": "identity", "store": "x"}], "device_level": [{"thing": "filters", "store": "ls"}], "known_tensions": []})):
        fails.append("active hive missing from device_level should FAIL")
    if not any("wrongly listed at ACCOUNT" in p for p in check({"account_level": [{"thing": "identity", "store": "x"}, {"thing": "active hive", "store": "y"}], "device_level": [{"thing": "active hive", "store": "ls"}], "known_tensions": []})):
        fails.append("active hive at account level should FAIL")
    if not any("missing 'thing' or 'store'" in p for p in check({"account_level": [{"thing": "identity"}], "device_level": [{"thing": "active hive", "store": "ls"}], "known_tensions": []})):
        fails.append("an entry with no store should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_state_scope_registry self-test (misclassified active-hive / storeless entry redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
