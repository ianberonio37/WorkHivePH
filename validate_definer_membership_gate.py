"""
SECURITY DEFINER Hive-Membership Gate Validator (G0)
====================================================
Closes the gap validate_function_security.py leaves open. That validator checks
the `search_path` lockdown class (CVE-2018-1058 shadowing). This one checks the
*tenant-isolation* class: a SECURITY DEFINER function bypasses RLS, so any such
function that accepts a tenant id (`hive_id`) and is reachable by anon /
authenticated / PUBLIC is a cross-hive read/write (IDOR) vector UNLESS it
re-authenticates the caller itself. RLS-policy validators are blind to it
because the leak is *through the RPC*, not through a table policy.

A SECURITY DEFINER function taking a `hive_id` parameter is SAFE when EITHER:

  (A) it has an in-function membership gate -- its body references
      `hive_members` AND `auth.uid()`/`auth.role()` (the get_hive_dashboard
      pattern). This is required for browser-callable RPCs (user JWT present).

  (B) it is NOT reachable by anon/authenticated/PUBLIC -- i.e. EXECUTE is
      granted only to service_role (or owner). This is the correct boundary
      for backend-only RPCs called by an edge function via the service key,
      where an in-function auth.uid() gate would always fail.

Anything else -- exposed to anon/authenticated AND no gate -- is a FAIL.

The grant state is computed by replaying every GRANT/REVOKE across all
migrations in order (Postgres EXECUTE defaults to PUBLIC on first CREATE;
CREATE OR REPLACE preserves privileges). Function bodies use last-writer-wins.

Audit 2026-06-07 found 9 such functions ungated/exposed; migrations
20260607000003 (in-fn gates) + 20260607000004 (service_role lockdown) fix all
9, driving this validator to 0 findings. It is a FAIL-at-0 gate, not a debt
ratchet -- a NEW exposed-ungated DEFINER hive-fn trips it immediately.

Skills: security ("SECURITY DEFINER = an RLS bypass"), multitenant-engineer
("SECURITY DEFINER RPCs Must Self-Enforce Hive Membership"), data-engineer.

Exit codes:
  0  every SECURITY DEFINER hive-fn is gated OR not exposed (or allowlisted).
  1  one or more are exposed to anon/authenticated with no membership gate.
"""
from __future__ import annotations
import glob
import io
import json
import os
import re
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

MIGRATIONS_DIR = os.path.join("supabase", "migrations")
REPORT_PATH = "definer_membership_gate_report.json"

# Justified exceptions: (function_name) -> reason. A function here is exempt
# even if it looks exposed-and-ungated. Use ONLY for functions that are
# provably not a cross-hive vector (e.g. hive_id is not a tenant filter, or
# the fn intentionally serves cross-hive/public data). Each needs a reason.
ALLOWLIST: dict[str, str] = {
    # The gate PRIMITIVE itself (Arc H). Takes a hive_id and returns a BOOLEAN of
    # whether the CALLER (auth.uid(), via user_hive_ids()) may access it. It leaks
    # no cross-tenant data — it IS the membership check the other DEFINER fns call.
    # Self-scoped by user_hive_ids() (auth.uid()-derived), so it can't be abused to
    # read another tenant's rows. anon/authenticated EXECUTE is required (callers
    # gate on its boolean). Verified body: `... p_hive_id in (select user_hive_ids())`.
    "user_can_access_hive":
        "gate primitive: returns a bool about the CALLER's own membership "
        "(self-scoped via user_hive_ids()=auth.uid()); leaks no hive data.",
    "get_community_reputation":
        "cross-hive PORTABLE marketplace/person-card reputation bridge: returns "
        "PUBLIC-scoped aggregate ONLY (public posts/reactions/xp/voice-badge/seller), "
        "no post content, and its internal WHERE gate returns NO row for purely-private "
        "workers; deliberately serves cross-hive public data so a per-caller membership "
        "gate would defeat its purpose (Community PDDA X-axis bridge, "
        "20260711000001_community_reputation_bridge.sql).",
    "get_seller_community_reputation":
        "cross-hive marketplace seller-reputation bridge: auth-gated (auth.uid() required) thin "
        "wrapper that resolves an OPTED-IN marketplace seller by (worker_name, hive_id) then "
        "RETURN QUERYs get_community_reputation_by_auth — same PUBLIC-scoped aggregate ONLY "
        "(xp/public posts/reactions/trust-tier), no post content; returns NO row for a "
        "non-seller. Deliberately cross-hive (buyers see any seller's reputation on the "
        "marketplace) so a per-caller membership gate would defeat its purpose.",
}

DOLLAR = re.compile(r"\$(\w*)\$")
CREATE = re.compile(
    r'CREATE(?:\s+OR\s+REPLACE)?\s+FUNCTION\s+(?:(?:public|auth)\.)?"?(\w+)"?\s*\(',
    re.IGNORECASE,
)
GRANT_RE = re.compile(
    r'(GRANT|REVOKE)\s+(?:EXECUTE|ALL(?:\s+PRIVILEGES)?)\s+ON\s+FUNCTION\s+'
    r'(?:"?public"?\.)?"?(\w+)"?\s*\([^)]*\)\s+(?:TO|FROM)\s+([^;]+);',
    re.IGNORECASE,
)
EXPOSED_ROLES = {"public", "anon", "authenticated"}


def _walk_function_blocks(sql: str):
    """Yield (name, full_text) for each CREATE FUNCTION, dollar-quote aware."""
    pos = 0
    while True:
        m = CREATE.search(sql, pos)
        if not m:
            break
        i = m.end()
        tag = None
        end = -1
        while i < len(sql):
            if tag is None:
                if sql[i] == "$":
                    qm = DOLLAR.match(sql, i)
                    if qm:
                        tag = qm.group(1)
                        i = qm.end()
                        continue
                if sql[i] == ";":
                    end = i + 1
                    break
                i += 1
            else:
                close = f"${tag}$"
                idx = sql.find(close, i)
                if idx == -1:
                    i = len(sql)
                else:
                    i = idx + len(close)
                    tag = None
        if end < 0:
            end = i
        yield m.group(1), sql[m.start():end]
        pos = end


def _arg_list(full_text: str) -> str:
    """Return the parameter list (between the function name's parens)."""
    p = full_text.find("(")
    if p < 0:
        return ""
    depth = 0
    for j in range(p, len(full_text)):
        c = full_text[j]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return full_text[p + 1:j]
    return ""


def _roles(blob: str) -> set[str]:
    out = set()
    for r in blob.split(","):
        r = r.strip().strip('"').lower()
        if r:
            out.add(r)
    return out


def analyze():
    files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    final_body: dict[str, str] = {}     # name -> last-writer body
    granted: dict[str, set[str]] = {}   # name -> roles with EXECUTE

    for path in files:
        raw = open(path, encoding="utf-8").read()
        no_comments = re.sub(r"--[^\n]*", "", raw)
        for name, body in _walk_function_blocks(no_comments):
            if name not in granted:
                # First CREATE of this name: Postgres grants EXECUTE to PUBLIC.
                granted[name] = {"public"}
            final_body[name] = body  # last-writer-wins
        # Replay grants/revokes (on raw so we don't miss any; harmless).
        for verb, name, blob in GRANT_RE.findall(raw):
            if name not in granted:
                granted[name] = {"public"}
            roles = _roles(blob)
            if verb.upper() == "GRANT":
                granted[name] |= roles
            else:
                granted[name] -= roles

    rows = []
    for name, body in final_body.items():
        if not re.search(r"\bSECURITY\s+DEFINER\b", body, re.IGNORECASE):
            continue
        args = _arg_list(body)
        # Match p_hive_id / hive_id (underscore is a word char, so \b before
        # "hive" fails inside "p_hive_id" -- use a plain substring).
        if "hive_id" not in args.lower():
            continue
        # A function is gated if EITHER:
        #  (a) the original inline pattern — references hive_members AND auth.uid()/role()
        #      (the get_hive_dashboard idiom), OR
        #  (b) it calls the canonical membership helper user_can_access_hive(p_hive_id)
        #      (the Arc H idiom: `if not public.user_can_access_hive(p_hive_id) then return`
        #      or `... AND public.user_can_access_hive(p_hive_id)` in a WHERE). The helper is
        #      auth.uid()-scoped (via user_hive_ids()), so it IS a real membership gate. Before
        #      this branch the validator false-FAILed every helper-gated DEFINER fn (Arc H added
        #      5: semantic_search_kb/kg_facts, fetch_active_alerts, get_*_current) — the same
        #      "marker too narrow" class as the rate-limit/trace scan false-negatives.
        inline_gate = bool(
            re.search(r"\bhive_members\b", body, re.IGNORECASE)
            and re.search(r"auth\.(uid|role)\s*\(\)", body, re.IGNORECASE)
        )
        helper_gate = bool(re.search(r"user_can_access_hive\s*\(", body, re.IGNORECASE))
        has_gate = inline_gate or helper_gate
        roles = granted.get(name, {"public"})
        exposed = bool(roles & EXPOSED_ROLES)
        safe = has_gate or (not exposed)
        rows.append({
            "fn": name,
            "has_gate": has_gate,
            "exposed_to": sorted(roles & EXPOSED_ROLES),
            "exposed": exposed,
            "safe": safe,
            "allowlisted": name in ALLOWLIST,
        })
    return rows


def main() -> int:
    bar = "=" * 70
    print(bar)
    print("SECURITY DEFINER Hive-Membership Gate Validator (G0)")
    print(bar)

    rows = analyze()
    rows.sort(key=lambda r: r["fn"])
    findings = [r for r in rows if not r["safe"] and not r["allowlisted"]]

    print(f"  Scanned {len(rows)} SECURITY DEFINER function(s) taking a hive_id.\n")
    for r in rows:
        if r["safe"]:
            how = "in-fn gate" if r["has_gate"] else "service_role-only"
            mark = "\033[92mOK  \033[0m"
            print(f"  {mark} {r['fn']:38} ({how})")
        elif r["allowlisted"]:
            print(f"  \033[93mALLOW\033[0m {r['fn']:38} ({ALLOWLIST[r['fn']]})")
        else:
            exp = ",".join(r["exposed_to"]) or "PUBLIC"
            print(f"  \033[91mFAIL\033[0m {r['fn']:38} exposed to [{exp}] with NO membership gate")

    report = {
        "validator": "definer_membership_gate",
        "scanned": len(rows),
        "findings": len(findings),
        "rows": rows,
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print()
    if findings:
        print(f"\033[91m  {len(findings)} FAIL\033[0m — SECURITY DEFINER hive-fn(s) leak across tenants.")
        print("  Fix: add an in-function membership gate (hive_members + auth.uid(),")
        print("       the get_hive_dashboard pattern) for browser-callable RPCs, OR")
        print("       REVOKE EXECUTE FROM anon, authenticated for backend-only RPCs,")
        print("       OR justify in validate_definer_membership_gate.py ALLOWLIST.")
        print(bar)
        return 1
    print(f"\033[92m  All {len(rows)} SECURITY DEFINER hive-fn(s) are gated or service_role-only.\033[0m")
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
