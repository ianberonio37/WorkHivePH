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

# ── Drain-path coverage (the amc-orchestrator finding, 2026-09-01) ───────────────────────────────────
# The GUARD regex above only proves a guard marker EXISTS somewhere in the file. It does NOT prove the
# marker covers the ALL-HIVES DRAIN path. amc-orchestrator / benchmark-compute / scheduled-agents /
# failure-signature-scan each carried an identity guard (resolveTenancy/resolveIdentity) nested INSIDE
# `if (hive_id) { ... }` — so a single-hive caller was checked, but the no-hive DRAIN branch (which
# enumerates the whole hive roster on a service-role client and writes/fans-out for EVERY hive) reached
# the write with NO auth at all. All four were live-confirmed anon-drainable (`POST {}` → all-hives run)
# and are deployed --no-verify-jwt, so the door was fully public (BFLA + unbounded LLM cost). The fix on
# each: a service-role gate on the `!hive_id` drain path (`requireServiceRole`), leaving the pg_cron
# service-role caller unbroken. This detector locks that: a roster-enumerating service-role writer whose
# ONLY service/cron/signature guard sits inside an `if (hive_id)` POSITIVE branch fails here.
#
# Identity/membership guards (resolveTenancy/checkSupervisor/auth.getUser) gate a NAMED hive; only a
# SERVICE-ROLE/CRON/SIGNATURE guard can gate the no-hive drain (there is no hive_id to check membership
# against). So the drain path must carry one of THOSE, reachable when hive_id is absent (top-level, an
# `else`, or inside `if (!hive_id)`) — never solely inside `if (hive_id) { ... }`.
ALL_HIVES_ROSTER = re.compile(r"""\.from\(\s*["'](?:v_hives_truth|hives)["']\s*\)""")
# Literal single-hive-selector identifiers. The single-hive branch is `if (<selector>)`; a guard nested
# inside it covers only the single-hive path, never the no-hive DRAIN path.
_HIVE_SELECTOR_LITERALS = ("hive_id", "hiveId", "targetHive", "reqHiveId")
SERVICE_CRON_SIG_GUARD = re.compile(
    r"requireServiceRole|isServiceRole|CRON_SECRET|x-cron|"
    r"bearer\s*===|===\s*[_A-Za-z]*SERVICE_KEY|===\s*_WH_SERVICE|includes\(\s*[\"']?SERVICE|"
    r"verifySignature|createHmac|\bhmac\b|x-signature|stripe-signature", re.I)


def _hive_selector_vars(nc: str) -> list[str]:
    """The single-hive-selector variable names in this fn: the literals PLUS any local var assigned from
    `body.hive_id` (e.g. `const single_hive = body.hive_id ? … : null`). shift-planner-orchestrator renamed
    the selector to `single_hive`, and a detector hardcoded to `hive_id|targetHive` missed its drain hole —
    so the branch identifier must be discovered, not assumed."""
    vs = set(_HIVE_SELECTOR_LITERALS)
    for m in re.finditer(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*[^;\n]*\bbody\.hive_id\b", nc):
        vs.add(m.group(1))
    return sorted(vs, key=len, reverse=True)   # longest first so alternation is greedy-correct


def _hive_branch_re(nc: str) -> "re.Pattern[str]":
    alt = "|".join(re.escape(v) for v in _hive_selector_vars(nc))
    return re.compile(r"if\s*\(\s*(?:body\.)?(?:" + alt + r")\b")


def _positive_hive_spans(nc: str) -> list[tuple[int, int]]:
    """Char spans of `if (<hive-selector>) { ... }` POSITIVE branches (never `if (!<selector>)`, whose `!`
    blocks the match). A service/cron guard whose position falls inside one of these gates only the
    single-hive path. The selector set is discovered per-file so a renamed selector cannot hide a branch."""
    spans: list[tuple[int, int]] = []
    for m in _hive_branch_re(nc).finditer(nc):
        paren = nc.find("(", m.start())
        if paren == -1:
            continue
        depth, j, cond_end = 0, paren, -1
        while j < len(nc):
            if nc[j] == "(":
                depth += 1
            elif nc[j] == ")":
                depth -= 1
                if depth == 0:
                    cond_end = j; break
            j += 1
        if cond_end == -1:
            continue
        k = cond_end + 1
        while k < len(nc) and nc[k] in " \t\r\n":
            k += 1
        if k >= len(nc) or nc[k] != "{":      # single-statement `if (hive_id) return …` — no nested block
            continue
        depth, j, end = 0, k, -1
        while j < len(nc):
            if nc[j] == "{":
                depth += 1
            elif nc[j] == "}":
                depth -= 1
                if depth == 0:
                    end = j; break
            j += 1
        if end != -1:
            spans.append((m.start(), end))
    return spans


def drain_unguarded(src: str) -> bool:
    """True if this is a roster-enumerating service-role writer whose drain (no-hive) path has NO
    service/cron/signature guard reachable outside the `if (hive_id)` positive branches."""
    nc = strip_comments(src)
    if not ALL_HIVES_ROSTER.search(nc):        # not an all-hives roster drainer → different shape, skip
        return False
    if not _hive_branch_re(nc).search(nc):     # no single-hive branch → no split drain path to mis-cover
        return False
    spans = _positive_hive_spans(nc)
    for m in SERVICE_CRON_SIG_GUARD.finditer(nc):
        if not any(s <= m.start() <= e for s, e in spans):
            return False                       # a service/cron guard reachable on the drain path → covered
    return True                                # every service/cron guard is nested in if(hive_id) (or none)


# ── DB-webhook auto-detect injection (the embed-entry finding, 2026-09-01) ───────────────────────────
# A fn that auto-detects a Supabase DB webhook by shape (`if (body.type === "INSERT" && body.record)`) then
# writes a tenant row keyed on the CALLER-SUPPLIED `record.hive_id` is a cross-tenant injection surface: on a
# --no-verify-jwt fn, an anon POST of that exact shape reaches the write and injects into ANY hive (embed-entry
# poisoned any hive's RAG index — a maintenance-safety concern). Shape-detection is NOT authentication; the
# webhook branch must itself carry a service-role/signature gate. Live-confirmed reachable pre-fix.
WEBHOOK_BRANCH = re.compile(r"""if\s*\(\s*body\.type\s*===\s*["']INSERT["']""")


def _braced_span_after(nc: str, at: int) -> tuple[int, int] | None:
    """(start,end) of the `{ … }` block whose `if (…)` condition begins at/after `at`. None if no block."""
    paren = nc.find("(", at)
    if paren == -1:
        return None
    depth, j, cond_end = 0, paren, -1
    while j < len(nc):
        if nc[j] == "(":
            depth += 1
        elif nc[j] == ")":
            depth -= 1
            if depth == 0:
                cond_end = j; break
        j += 1
    if cond_end == -1:
        return None
    k = cond_end + 1
    while k < len(nc) and nc[k] in " \t\r\n":
        k += 1
    if k >= len(nc) or nc[k] != "{":
        return None
    depth, j = 0, k
    while j < len(nc):
        if nc[j] == "{":
            depth += 1
        elif nc[j] == "}":
            depth -= 1
            if depth == 0:
                return (at, j)
        j += 1
    return None


def webhook_record_ungated(src: str) -> bool:
    """True if a DB-webhook auto-detect branch (`if body.type==="INSERT" && body.record`) writes tenant data
    but carries NO service-role/signature gate INSIDE that branch (shape-detection ≠ authentication)."""
    nc = strip_comments(src)
    m = WEBHOOK_BRANCH.search(nc)
    if not m:
        return False
    if not DB_WRITE.search(nc):
        return False
    span = _braced_span_after(nc, m.start())
    if span is None:
        return False
    s, e = span
    return not SERVICE_CRON_SIG_GUARD.search(nc[s:e])


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

    # ── drain-path coverage teeth (the amc-orchestrator class, 2026-09-01) ──
    _roster = 'const {data:hives}=await db.from("v_hives_truth").select("id"); for(const h of hives){ await db.from("x").insert({hive_id:h.id}); }'
    # (a) VULNERABLE: the only guard is nested inside `if (targetHive) {...}` — the no-hive drain is open.
    vuln = ('if (targetHive) { const {isServiceRole}=await resolveIdentity(db,req);'
            'if(!isServiceRole){ const t=await resolveTenancy(db,a,targetHive); } }' + _roster)
    if not drain_unguarded(vuln):
        print(f"{R}self-test FAIL: did not flag a roster-drainer guarded ONLY inside if(hive_id).{X}"); ok = False
    # (b) FIXED: a requireServiceRole gate on the `!targetHive` drain path covers it.
    fixed = ('if (!targetHive) { const g=await requireServiceRole(db,req); if(!g.ok) return f; }'
             'if (targetHive) { const {isServiceRole}=await resolveIdentity(db,req); }' + _roster)
    if drain_unguarded(fixed):
        print(f"{R}self-test FAIL: flagged a drainer whose !hive_id path has requireServiceRole.{X}"); ok = False
    # (c) SAFE via a TOP-LEVEL service gate (batch-risk-scoring style) — outside the if(reqHiveId) span.
    toplevel = ('const isService = bearer === SERVICE_KEY;'
                'if (reqHiveId) { if(!isService){ /* member check */ const t=1; } }' + _roster)
    if drain_unguarded(toplevel):
        print(f"{R}self-test FAIL: flagged a drainer with a top-level bearer===SERVICE_KEY gate.{X}"); ok = False
    # (d) SAFE via an ELSE-branch service gate (cmms-sync / send-report-email style) — after the if-block.
    elsebr = ('if (hive_id) { const {isServiceRole}=await resolveIdentity(db,req);'
              'if(!isServiceRole){ const t=await resolveTenancy(db,a,hive_id); } }'
              'else { const {isServiceRole}=await resolveIdentity(db,req); if(!isServiceRole) return forbid(); }' + _roster)
    if drain_unguarded(elsebr):
        print(f"{R}self-test FAIL: flagged a drainer whose else branch has a service-role gate.{X}"); ok = False
    # (e) NON-drainer (single write, no all-hives roster read) is OUT of the drain check's scope.
    nondrain = 'if (hive_id) { const {isServiceRole}=await resolveIdentity(db,req); } await db.from("x").insert({});'
    if drain_unguarded(nondrain):
        print(f"{R}self-test FAIL: applied the drain check to a non-roster single-writer.{X}"); ok = False
    # (j) RENAMED selector (single_hive = body.hive_id) with a nested guard must STILL flag — the
    #     shift-planner-orchestrator blind spot: a detector hardcoded to hive_id|targetHive missed it.
    renamed = ('const single_hive = body.hive_id ? String(body.hive_id) : null;'
               'if (single_hive) { const {isServiceRole}=await resolveIdentity(db,req);'
               'if(!isServiceRole){ const t=await resolveTenancy(db,a,single_hive); } }' + _roster)
    if not drain_unguarded(renamed):
        print(f"{R}self-test FAIL: renamed hive-selector (single_hive) drainer not flagged.{X}"); ok = False
    # (k) renamed selector WITH a `!single_hive` service gate → covered.
    renamed_fix = ('const single_hive = body.hive_id ? String(body.hive_id) : null;'
                   'if (!single_hive) { const g=await requireServiceRole(db,req); if(!g.ok) return f; }'
                   'if (single_hive) { const {isServiceRole}=await resolveIdentity(db,req); }' + _roster)
    if drain_unguarded(renamed_fix):
        print(f"{R}self-test FAIL: renamed selector with a !single_hive requireServiceRole gate flagged.{X}"); ok = False

    # ── DB-webhook auto-detect injection teeth (the embed-entry class, 2026-09-01) ──
    # (f) VULNERABLE: a webhook-record branch writes with NO service gate inside it.
    wh_vuln = ('if (body.type === "INSERT" && body.record) { const r = body.record;'
               'await db.from("fault_knowledge").insert({ hive_id: r.hive_id }); }')
    if not webhook_record_ungated(wh_vuln):
        print(f"{R}self-test FAIL: did not flag a webhook-record writer with no gate inside the branch.{X}"); ok = False
    # (g) FIXED: a requireServiceRole gate INSIDE the webhook branch covers it.
    wh_fixed = ('if (body.type === "INSERT" && body.record) { const g = await requireServiceRole(db, req);'
                'if (!g.ok) return f; const r = body.record;'
                'await db.from("fault_knowledge").insert({ hive_id: r.hive_id }); }')
    if webhook_record_ungated(wh_fixed):
        print(f"{R}self-test FAIL: flagged a webhook branch that DOES gate with requireServiceRole.{X}"); ok = False
    # (h) NOT the webhook shape → out of scope.
    if webhook_record_ungated('await db.from("x").insert({ hive_id: body.hive_id });'):
        print(f"{R}self-test FAIL: applied the webhook check to a non-webhook writer.{X}"); ok = False
    # (i) COVERAGE, not presence: a gate present but OUTSIDE the webhook branch must still FLAG.
    wh_wrongbranch = ('if (body.hive_id) { const g = await requireServiceRole(db, req); if(!g.ok) return f; }'
                      'if (body.type === "INSERT" && body.record) { const r = body.record;'
                      'await db.from("fault_knowledge").insert({ hive_id: r.hive_id }); }')
    if not webhook_record_ungated(wh_wrongbranch):
        print(f"{R}self-test FAIL: a gate OUTSIDE the webhook branch should not count as covering it.{X}"); ok = False

    print((G + "self-test PASS - write-authZ detector has teeth (presence + drain-path + webhook-inject coverage)." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--self-test" in sys.argv:
        return 0 if self_test() else 1

    fns = verify_jwt_false_fns()
    unguarded, guarded, exempt, drain_open, webhook_open = [], [], [], [], []
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
        if guard:
            guarded.append(fn)
            # A guard marker EXISTS — but does it cover EVERY anon-reachable write path, or only the
            # single-hive branch? Two coverage holes a presence-check misses:
            #  • the all-hives DRAIN path (no hive_id) — the amc-orchestrator class;
            #  • the DB-webhook auto-detect branch keyed on caller-supplied record.hive_id — the embed-entry class.
            if drain_unguarded(src):
                drain_open.append(fn)
            if webhook_record_ungated(src):
                webhook_open.append(fn)
        else:
            unguarded.append(fn)

    print(f"{B}Public-fn WRITE authZ gate (Arc R / Z-lens, OWASP A01 / BFLA){X}")
    print(f"  verify_jwt=false fns: {len(fns)}  ·  service-role writers+exporters guarded: {len(guarded)}  ·  "
          f"exempt: {len(exempt)}  ·  drain-path open: {len(drain_open)}  ·  webhook-inject open: {len(webhook_open)}")
    for fn in exempt:
        print(f"  {Y}exempt{X} {fn} — {EXEMPT[fn]}")
    for fn in unguarded:
        print(f"  {R}FAIL{X} {fn}: verify_jwt=false + service-role client + DB write or bulk-export RPC + "
              f"NO auth/cron/signature gate (anonymously-triggerable privileged data movement — BFLA / export IDOR)")
    for fn in drain_open:
        print(f"  {R}FAIL{X} {fn}: roster-enumerating service-role writer whose auth guard sits ONLY inside "
              f"`if (hive_id)` — the no-hive DRAIN path fans out over ALL hives with NO service-role gate "
              f"(anon-drainable BFLA — the amc-orchestrator class). Add a service-role gate on the !hive_id path.")
    for fn in webhook_open:
        print(f"  {R}FAIL{X} {fn}: a DB-webhook auto-detect branch (`body.type===\"INSERT\" && body.record`) "
              f"writes tenant data keyed on caller-supplied record.hive_id with NO service-role/signature gate "
              f"INSIDE that branch (anon cross-tenant injection — the embed-entry class). Shape ≠ auth.")
    if unguarded or drain_open or webhook_open:
        print(f"{R}FAIL: {len(unguarded)} unguarded + {len(drain_open)} drain-path-open + {len(webhook_open)} "
              f"webhook-inject-open public service-role writer(s).{X}")
        return 1
    print(f"{G}PASS - every verify_jwt=false service-role writer enforces an auth/cron/signature gate, drain + webhook paths included.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
