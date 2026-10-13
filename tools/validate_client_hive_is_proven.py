#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D24
"""validate_client_hive_is_proven.py - a hive the CALLER names must be proven before an edge function reads it.

THE FINDING (LM-X walk, 2026-10-07). voice-transcribe took `hive_id` from the multipart form and read that hive's
asset tags on the service-role client to prime its speech recognition. Its only check was resolveIdentity, which
proves WHO is calling and nothing about WHICH hive they belong to. The tags were described as "never returned", but
the same step repairs a garbled code to the nearest tag, so the transcript carried another plant's real asset tags
back to whoever named that plant's hive.

validate_edge_fn_auth_gate.py did not catch it, and by its own rule it was right not to: it asks whether a caller
gate EXISTS, and resolveIdentity is one. Identity is not membership. This gate asks the narrower question.

RULE: an edge function that takes a hive id from the request (body / form / query / destructured JSON) must carry a
MEMBERSHIP proof somewhere in its source:
  - resolveTenancy(...)                                      the shared Pillar-I check
  - requireServiceRole(...)                                  a service-only function: no person can name a hive
  - a v_worker_truth / hive_members read keyed by auth_uid   the inline form several functions use
  - user_hive_ids / is_hive_member                           the database's own membership helpers
  - a user-JWT client (anon key + the caller's Authorization) every read then goes through RLS
or be listed in EXEMPT with the reason. Baseline 0.

USAGE:      python tools/validate_client_hive_is_proven.py
Self-test:  python tools/validate_client_hive_is_proven.py --self-test   (identity-only source must FAIL)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
GREEN, RED = "\033[92m", "\033[91m"
RST = "\033[0m"

TAKES_CLIENT_HIVE = [
    re.compile(r"(?:const|let)\s+\w*hive\w*\s*=[^;\n]*(?:form|params|searchParams)\.get\(\s*[\"']hive_id[\"']"),
    re.compile(r"(?:const|let)\s+\w*hive\w*\s*=[^;\n]*\b(?:body|_whBody|json|payload|input|req_body)\.hive_id\b"),
    re.compile(r"(?:const|let)\s*\{[^}]*\bhive_id\b[^}]*\}\s*=\s*(?:await\s+req\.json\(\)|body|_whBody|payload|json|input)"),
]
MEMBERSHIP = [
    re.compile(r"\bresolveTenancy\("),
    re.compile(r"\brequireServiceRole\("),
    re.compile(r"from\(\s*[\"'](?:v_worker_truth|hive_members)[\"']\s*\)[\s\S]{0,240}?[\"']auth_uid[\"']"),
    re.compile(r"\b(?:user_hive_ids|is_hive_member)\b"),
    re.compile(r"createClient\([^)]*ANON_KEY[\s\S]{0,300}?Authorization"),
]
EXEMPT: dict[str, str] = {}


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"'])//.*$", r"\1", src)


def check_source(src: str) -> tuple[bool, bool]:
    """(takes a client hive, proves membership)"""
    s = _strip_comments(src)
    takes = any(p.search(s) for p in TAKES_CLIENT_HIVE)
    proves = any(p.search(s) for p in MEMBERSHIP)
    return takes, proves


def main() -> int:
    print("client-hive-is-proven: a hive the caller names must be proven (membership, not identity)")
    takers, bad = [], []
    for f in sorted(FUNCS.glob("*/index.ts")):
        fn = f.parent.name
        if fn.startswith("_"):
            continue
        takes, proves = check_source(f.read_text(encoding="utf-8", errors="replace"))
        if not takes:
            continue
        takers.append(fn)
        if not proves and fn not in EXEMPT:
            bad.append(fn)
    if bad:
        for fn in bad:
            print(f"  {RED}UNPROVEN{RST} {fn}: takes hive_id from the request and never proves the caller's membership")
        print(f"{RED}FAIL client-hive-is-proven - {len(bad)} of {len(takers)} function(s) read a caller-named hive "
              f"on identity alone{RST}")
        return 1
    print(f"{GREEN}PASS client-hive-is-proven - all {len(takers)} functions that take a hive from the request prove "
          f"the caller's membership before trusting it{RST}")
    return 0


def self_test() -> int:
    identity_only = ('serve(async (req) => { const form = await req.formData();\n'
                     'const hiveId = typeof form.get("hive_id") === "string" ? form.get("hive_id") : null;\n'
                     'const _id = await resolveIdentity(db, req);\n'
                     'await db.from("asset_nodes").select("tag").eq("hive_id", hiveId); });')
    proven = identity_only.replace("const _id = await resolveIdentity(db, req);",
                                   "const _id = await resolveIdentity(db, req); const t = await resolveTenancy(db, _id.authUid, hiveId);")
    commented = identity_only.replace("const _id", "// resolveTenancy( is only mentioned here\nconst _id")
    inline = ('const { hive_id } = await req.json();\nconst { data } = await db.from("v_worker_truth")'
              '.select("hive_status").eq("hive_id", hive_id).eq("auth_uid", caller.id);')
    cases = [("identity only", identity_only, (True, False)), ("resolveTenancy", proven, (True, True)),
             ("a proof named only in a comment", commented, (True, False)), ("inline v_worker_truth", inline, (True, True)),
             ("no client hive", "serve(async () => new Response('ok'))", (False, False))]
    fails = [n for n, src, want in cases if check_source(src) != want]
    if fails:
        print(f"{RED}SELF-TEST FAIL: {fails}{RST}")
        return 1
    print(f"{GREEN}SELF-TEST PASS: {len(cases)} cases (identity alone and a commented-out proof both fail){RST}")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
