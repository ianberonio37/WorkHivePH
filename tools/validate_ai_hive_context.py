#!/usr/bin/env python3
"""
validate_ai_hive_context.py - AI-context hive-resolution consistency gate (2026-07-19).
========================================================================================
Locks the fix for a live assistant.html bug: the AI-gateway / semantic-RAG calls resolved the hive as
`const hiveId = localStorage.getItem('wh_hive_id') || null` — the LEGACY key alone. In the modern flow
`wh_hive_id` is null (sign-in / hive-switch sets `wh_active_hive_id`), so the assistant sent NULL hive
context and answered WITHOUT the team knowledge base, even for a user who IS in a hive. Every data read
on the page correctly uses `wh_active_hive_id || wh_hive_id`; the AI calls must too.

THE RULE: a hive-id VARIABLE must never be ASSIGNED from `wh_hive_id` alone. The canonical resolution is
`localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id') || <default>`. Legit
legacy reads are exempt because they don't match the bug shape: `const legId = getItem('wh_hive_id');`
(no `|| null` default — a deliberate backfill read) and `'wh_notifs_read_' + (getItem('wh_hive_id')||'')`
(string concat, not an `=` assignment).

Exit 0 = no legacy-only hive-context assignment. `--selftest` proves teeth. Static, fast, no stack.
"""
from __future__ import annotations
import io, sys, re
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_ai_hive_context"]

# Bug shape: `<var> = localStorage.getItem('wh_hive_id') || (null|'')` — a hive var assigned the LEGACY key
# alone with a null/'' fallback. The correct form starts with getItem('wh_active_hive_id'), so it won't
# match (its first getItem is the active key). `legId = getItem('wh_hive_id');` (no `|| null`) is exempt.
LEGACY_ONLY = re.compile(r"""=\s*localStorage\.getItem\(\s*['"]wh_hive_id['"]\s*\)\s*\|\|\s*(?:null|'')""")


def scan(text: str, label: str) -> list[str]:
    fails = []
    for m in LEGACY_ONLY.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        fails.append(f"{label}:{line} hive var assigned LEGACY-ONLY wh_hive_id "
                     f"(use `wh_active_hive_id || wh_hive_id` so AI/data get the ACTIVE hive)")
    return fails


def self_test() -> bool:
    ok = True
    bad = "const hiveId = localStorage.getItem('wh_hive_id') || null;"
    good1 = "const hiveId = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id') || null;"
    good2 = "const legId = localStorage.getItem('wh_hive_id');"       # deliberate backfill read
    good3 = "const NOTIF_KEY = 'wh_notifs_read_' + (localStorage.getItem('wh_hive_id') || '');"
    if not scan(bad, "b"): print(f"{R}self-test FAIL: missed the legacy-only bug form.{X}"); ok = False
    if scan(good1, "g1"): print(f"{R}self-test FAIL: flagged the correct active-first form.{X}"); ok = False
    if scan(good2, "g2"): print(f"{R}self-test FAIL: flagged a deliberate legId backfill read.{X}"); ok = False
    if scan(good3, "g3"): print(f"{R}self-test FAIL: flagged a notif-key string concat.{X}"); ok = False
    print((G + "self-test PASS - ai-hive-context gate has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    print(f"{B}AI-context hive-resolution gate (no legacy-only wh_hive_id feeding AI/data){X}")
    fails, scanned = [], 0
    for p in sorted(list(ROOT.glob("*.html")) + list(ROOT.glob("*.js"))):
        try:
            fails.extend(scan(p.read_text(encoding="utf-8", errors="replace"), p.name)); scanned += 1
        except Exception:
            continue
    for f in fails:
        print(f"  {R}FAIL{X} {f}")
    if fails:
        print(f"{R}FAIL: {len(fails)} legacy-only hive-context assignment(s) across {scanned} files.{X}")
        return 1
    print(f"{G}PASS - every hive-context assignment across {scanned} files is active-first.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
