#!/usr/bin/env python3
# DEEPWALK-CELL: * A
"""validate_edge_fn_auth_gate.py — per-page bughunt v3, L6 column: every edge fn must gate its caller.

THE FINDING (v3 matrix L6 sweep, 2026-07-20): a Supabase edge function runs with the SERVICE_ROLE key,
which BYPASSES RLS. If such a fn reads/writes tenant data keyed by a CLIENT-supplied `hive_id` WITHOUT first
proving the caller is entitled to that hive, any anon/browser caller can inject or read another hive's data
(cross-tenant write/read injection). The manual sweep of all 57 fns found every one already gated — this
gate LOCKS that: a NEW fn that touches `hive_id` but ships without a caller gate FAILS CI.

A "caller gate" is any of:
  - membership resolve:  resolveTenancy / resolveIdentity / requireServiceRole / requireAuth / assertMember
  - session auth:        auth.getUser(...) / .getUser(  (JWT introspection)
  - custom API-key auth:  authenticate(  (e.g. intelligence-api Bearer wh_...)
  - cron-only secret:     CRON_SECRET / "cron-only" / x-cron-secret bearer compare
  - platform JWT:         verify_jwt = true in supabase/config.toml for that fn

RULE: for every supabase/functions/<fn>/index.ts that references `hive_id`, at least one caller gate must
be present. Fns that never touch tenant data (pure health/util) are exempt. Baseline: 0 ungated.

USAGE: python tools/validate_edge_fn_auth_gate.py
"""
from __future__ import annotations
import re
import sys
import pathlib

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
CONFIG = ROOT / "supabase" / "config.toml"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"
RST = "\033[0m"

# Any ONE of these in the fn source proves the caller is gated before tenant data is touched.
AUTH_SIGNALS = [
    r"resolveTenancy", r"resolveIdentity", r"requireServiceRole", r"requireAuth",
    r"assertMember", r"checkMembership", r"v_worker_truth",
    r"auth\.getUser", r"\.getUser\(", r"authenticate\(",
    r"CRON_SECRET", r"cron-only", r"x-cron-secret",
]
# Fns that reference hive_id but provably do NOT use it to read/write tenant data.
# Each requires a human-verified reason; a NEW hive-touching fn is NOT here → it FAILs until reviewed.
EXEMPT = {
    "login": "auth entry point — CREATES the session, no hive-scoped tenant read.",
    # PUBLIC per-identity fns (verify_jwt=false): accept hive_id for back-compat/telemetry ONLY,
    # read/write NO hive-scoped tenant data; rate-limit keyed on auth_uid/IP not hive_id (Pillar P).
    # Verified by code inspection 2026-07-20 (per-page bughunt v3 L6):
    "resume-extract":      "hive_id accepted for back-compat but IGNORED; reads no hive data.",
    "resume-polish":       "hive_id accepted for back-compat but IGNORED; reads no hive data.",
    "voice-journal-agent": "hive_id used ONLY as ai_cost_log telemetry tag; no tenant read/write.",
}


def verify_jwt_fns() -> set[str]:
    """Fns declared `verify_jwt = true` in config.toml — gated by the platform before our code runs."""
    if not CONFIG.exists():
        return set()
    txt = CONFIG.read_text(encoding="utf-8", errors="replace")
    out, cur = set(), None
    for line in txt.splitlines():
        m = re.match(r"\s*\[functions\.([a-z0-9\-]+)\]", line)
        if m:
            cur = m.group(1); continue
        if cur and re.match(r"\s*verify_jwt\s*=\s*true", line):
            out.add(cur)
    return out


def main() -> int:
    if not FUNCS.is_dir():
        print(f"{RED}FAIL{RST} — no supabase/functions dir at {FUNCS}")
        return 1
    jwt_gated = verify_jwt_fns()
    ungated: list[str] = []
    checked = 0
    for d in sorted(FUNCS.iterdir()):
        if not d.is_dir() or d.name == "_shared":
            continue
        idx = d / "index.ts"
        if not idx.exists():
            continue
        checked += 1
        if d.name in EXEMPT:
            continue
        src = idx.read_text(encoding="utf-8", errors="replace")
        touches_tenant = bool(re.search(r"hive_id", src))
        if not touches_tenant:
            continue
        has_gate = any(re.search(s, src) for s in AUTH_SIGNALS) or d.name in jwt_gated
        if not has_gate:
            ungated.append(d.name)

    print("=" * 70)
    print("  per-page bughunt v3 · L6 — every hive-touching edge fn must gate its caller")
    print("=" * 70)
    if ungated:
        for n in ungated:
            print(f"  {RED}FAIL{RST}  {n}: references hive_id but has NO caller gate "
                  f"(add resolveTenancy/requireServiceRole/getUser or verify_jwt=true)")
        print(f"\n  Summary: {len(ungated)} ungated fn(s) of {checked} checked — cross-tenant injection risk")
        return 1
    print(f"  {GREEN}PASS{RST} — every tenant-touching edge fn gates its caller "
          f"({checked} fns scanned, {len(jwt_gated)} via verify_jwt, {len(EXEMPT)} exempt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
