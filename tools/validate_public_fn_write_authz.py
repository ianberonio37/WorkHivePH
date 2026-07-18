#!/usr/bin/env python3
# DEEPWALK-CELL: * D9
"""
validate_public_fn_write_authz.py - Arc R (Z-lens, OWASP A01/BFLA): a verify_jwt=false edge fn that
WRITES on the service-role client must enforce an auth / cron / signature gate.
====================================================================================================
Sibling of validate_public_fn_authz (which covers the open-LLM-PROXY subset). This closes the R2
CORE for the WRITE surface: an edge fn that runs `verify_jwt = false` AND builds a SERVICE-ROLE client
(RLS bypassed) AND performs a DB write is, without an authorization gate, an anonymously-triggerable
privileged mutation — Broken Function-Level Authorization (BFLA).

REAL finding that motivated this gate (Arc R R2, 2026-07-01): `pdf-ingest` ran verify_jwt=false with a
service-role client and NO auth check — an anon `POST {}` (drain mode) force-processed every pending
pdf_job across ALL hives (unauthorized, unbounded all-hives compute + cross-table inserts). Its sibling
batch drainers (batch-risk-scoring / parts-staging-recommender / trigger-ml-retrain) all enforce a
service-role bearer gate; pdf-ingest was missing it. FIX: `if (bearer !== SERVICE_KEY) return 403`.

RULE: a verify_jwt=false fn that (service-role client) AND (writes) must carry >=1 GUARD marker:
  - identity/membership : resolveTenancy / resolveIdentity / user_can_access_hive / user_hive_ids /
                          checkSupervisor / auth.getUser / getUser( / authenticate( / api_keys
  - service-role / cron : isService / requireServiceRole / `bearer === SERVICE_KEY` / CRON_SECRET /
                          x-cron / authHeader.includes(SERVICE_ROLE)
  - request signature   : verifySignature / createHmac / hmac / x-signature
  - identity rate-limit : checkSoloRateLimit (writes only the caller's own identity-scoped row)
Fns with none = BFLA finding. Self-authenticating / evidence-exempt fns are allow-listed with a reason.

Self-test (--self-test): a service-role writer with no guard FAILs; one with an isService gate passes;
a non-writer / non-service fn is ignored.
Exit 0 = every public service-role writer is guarded. Exit 1 = an unguarded writer (or self-test fail).
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
CONFIG = ROOT / "supabase" / "config.toml"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

CHECK_NAMES = ["validate_public_fn_write_authz"]

# Self-authenticating / public-by-design writers (verify their own signature or are the auth entry).
EXEMPT = {
    "login": "auth entrypoint — establishes identity, no pre-auth tenant write",
    "cmms-webhook-receiver": "HMAC/token signature-verified inbound webhook",
}

SERVICE_CLIENT = re.compile(r"SUPABASE_SERVICE_ROLE_KEY")
DB_WRITE = re.compile(r"\.(insert|upsert|update|delete)\s*\(")
GUARD = re.compile(
    # identity / membership
    r"resolveTenancy|resolveIdentity|user_can_access_hive|user_hive_ids|checkSupervisor|"
    r"\.auth\.getUser|getUser\s*\(|authenticate\s*\(|api_keys|"
    # service-role / cron gate
    r"isService|requireServiceRole|CRON_SECRET|x-cron|"
    r"bearer\s*===|===\s*SERVICE_KEY|===\s*_WH_SERVICE|includes\(\s*[\"']?SERVICE|"
    # request signature
    r"verifySignature|createHmac|\bhmac\b|x-signature|stripe-signature|"
    # identity-scoped rate-limit (writes only the caller's own bucket row)
    r"checkSoloRateLimit",
    re.I,
)

# Privileged bulk-export DEFINER RPCs. A verify_jwt=false service-role fn that INVOKES one of these is a
# cross-tenant data-export surface exactly as dangerous as a direct write, so it must carry the SAME authZ
# guard — even if it performs no DB write of its own. This makes export-hive-data's authZ ratchet
# FIRST-CLASS instead of depending on its incidental best-effort audit-log insert (drop that insert and the
# write-arm would silently stop covering it). export_hive_data dumps an ENTIRE hive to JSON (roadmap §0b:
# "the most likely place to find a real cross-tenant export"). Add future bulk-export DEFINER RPCs here.
PRIVILEGED_READ_RPCS = {"export_hive_data"}
PRIV_READ_RPC = re.compile(r"""\.rpc\(\s*["'](?:%s)["']""" % "|".join(re.escape(n) for n in sorted(PRIVILEGED_READ_RPCS)))


def strip_comments(src: str) -> str:
    return re.sub(r"//.*", "", re.sub(r"/\*.*?\*/", "", src, flags=re.S))


def calls_privileged_read_rpc(src: str) -> bool:
    """True if the fn invokes an export_hive_data-class bulk-export DEFINER RPC (comments stripped)."""
    return bool(PRIV_READ_RPC.search(strip_comments(src)))


def verify_jwt_false_fns() -> list[str]:
    if not CONFIG.exists():
        return []
    out, current = [], None
    for line in CONFIG.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\[functions\.([A-Za-z0-9_-]+)\]", line.strip())
        if m:
            current = m.group(1)
        elif current and re.search(r"verify_jwt\s*=\s*false", line):
            out.append(current); current = None
        elif current and re.search(r"verify_jwt\s*=\s*true", line):
            current = None
    return out


def classify(src: str) -> tuple[bool, bool, bool]:
    nc = strip_comments(src)
    return (bool(SERVICE_CLIENT.search(nc)), bool(DB_WRITE.search(nc)), bool(GUARD.search(nc)))


def self_test() -> bool:
    ok = True
    unguarded = 'const db = createClient(url, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")); await db.from("t").insert(row);'
    svc, wr, guard = classify(unguarded)
    if not (svc and wr and not guard):
        print(f"{R}self-test FAIL: did not flag an unguarded service-role writer.{X}"); ok = False
    guarded = ('const isService = bearer === SERVICE_KEY; if(!isService) return f;'
               'const db = createClient(url, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")); await db.from("t").insert(row);')
    svc2, wr2, guard2 = classify(guarded)
    if not (svc2 and wr2 and guard2):
        print(f"{R}self-test FAIL: did not see the isService gate.{X}"); ok = False
    reader = 'const db = createClient(url, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")); const {data}=await db.from("t").select("*");'
    _s, wr3, _g = classify(reader)
    if wr3:
        print(f"{R}self-test FAIL: flagged a read-only fn as a writer.{X}"); ok = False
    # privileged bulk-export reader (invokes the export_hive_data RPC) with NO guard must be IN SCOPE + unguarded
    exp_unguarded = ('const db = createClient(url, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY"));'
                     'const {data} = await db.rpc("export_hive_data", { p_hive_id: h });')
    s4, w4, g4 = classify(exp_unguarded)
    if not (s4 and calls_privileged_read_rpc(exp_unguarded) and not w4 and not g4):
        print(f"{R}self-test FAIL: did not treat an unguarded export_hive_data-RPC reader as an in-scope, unguarded surface.{X}"); ok = False
    # the SAME reader WITH a checkSupervisor guard must be recognized as guarded
    exp_guarded = ('const a = await checkSupervisor(db, jwt, h); if (!a.ok) return forbid();'
                   'const db = createClient(url, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY"));'
                   'const {data} = await db.rpc("export_hive_data", { p_hive_id: h });')
    if not (calls_privileged_read_rpc(exp_guarded) and classify(exp_guarded)[2]):
        print(f"{R}self-test FAIL: did not see the checkSupervisor guard on the export reader.{X}"); ok = False
    # a benign reader calling a NON-privileged RPC must stay OUT of scope
    if calls_privileged_read_rpc('const {data}=await db.rpc("get_public_stats",{});'):
        print(f"{R}self-test FAIL: flagged a non-privileged RPC as a bulk-export surface.{X}"); ok = False
    print((G + "self-test PASS - write-authZ detector has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--self-test" in sys.argv:
        return 0 if self_test() else 1

    fns = verify_jwt_false_fns()
    unguarded, guarded, exempt = [], [], []
    for fn in fns:
        p = FUNCS / fn / "index.ts"
        if not p.exists():
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        svc, wr, guard = classify(src)
        priv_read = calls_privileged_read_rpc(src)
        # In scope: a service-role fn that WRITES, OR one that invokes a privileged bulk-export DEFINER RPC
        # (export_hive_data-class). Both are anonymously-triggerable privileged data movements that, without
        # a guard, are BFLA (write) / cross-tenant export IDOR (read). The reader arm makes export-hive-data
        # first-class ratcheted rather than covered only via its incidental audit-log write.
        if not (svc and (wr or priv_read)):
            continue  # not a service-role writer or privileged-export reader — out of scope for THIS gate
        if fn in EXEMPT:
            exempt.append(fn); continue
        (guarded if guard else unguarded).append(fn)

    print(f"{B}Public-fn WRITE authZ gate (Arc R / Z-lens, OWASP A01 / BFLA){X}")
    print(f"  verify_jwt=false fns: {len(fns)}  ·  service-role writers+exporters guarded: {len(guarded)}  ·  exempt: {len(exempt)}")
    for fn in exempt:
        print(f"  {Y}exempt{X} {fn} — {EXEMPT[fn]}")
    for fn in unguarded:
        print(f"  {R}FAIL{X} {fn}: verify_jwt=false + service-role client + DB write or bulk-export RPC + "
              f"NO auth/cron/signature gate (anonymously-triggerable privileged data movement — BFLA / export IDOR)")
    if unguarded:
        print(f"{R}FAIL: {len(unguarded)} unguarded public service-role writer(s).{X}")
        return 1
    print(f"{G}PASS - every verify_jwt=false service-role writer enforces an auth/cron/signature gate.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
