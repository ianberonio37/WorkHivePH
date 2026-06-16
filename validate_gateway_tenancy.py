"""
Gateway Tenancy Verification -- WorkHive Platform (Pillar I)
============================================================
The Full-Stack SaaS Gateway's Pillar I invariant:

  Any edge function that reads a CLIENT-SUPPLIED hive_id and uses it to scope
  data / rate-limit / forward MUST verify, server-side, that the caller is an
  active member of that hive -- never trust body.hive_id.

This catches the bug class found 2026-06-15: platform-gateway authenticated the
user (auth_uid) but trusted body.hive_id for rate-limit + audit + downstream
forwarding, so a signed-in worker could act against ANY hive. The canonical fix
is _shared/tenant-context.ts `resolveTenancy()` (or the equivalent inline
v_worker_truth active-member check used by analytics-orchestrator /
export-hive-data).

A function is SAFE when it either:
  (a) calls resolveTenancy() / resolveContext() from tenant-context.ts, OR
  (b) contains the canonical inline check
      (v_worker_truth ... auth_uid ... hive_status ... 'active'), OR
  (c) is listed in TENANCY_VERIFY_EXEMPT with a one-line justification
      (service-role-only / cron / webhook / solo-only / forwarded by a
       gateway that already verified).

This is COMPLEMENTARY to validate_gateway_coverage.py: that one ratchets *route
adoption*; this one ratchets *tenancy verification*. Different axis.

Ratchet: the count of unverified client-hive readers is baseline-locked in
gateway_tenancy_baseline.json and may only move DOWN (study Rule B). Closing it
is the Pillar I rollout (FULLSTACK_SAAS_GATEWAY_ROADMAP.md Phase 1).

Run:
  python validate_gateway_tenancy.py            # gate (exit 1 on regression)
  python validate_gateway_tenancy.py --self-test # prove the detector ($0, offline)

Skills consulted: security (tenant boundary / auth bind), multitenant-engineer
(hive isolation), architect (single verification source of truth).
"""
from __future__ import annotations

import re
import os
import sys
import json
import glob

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

FUNCTIONS_DIR = os.path.join("supabase", "functions")
BASELINE_FILE = "gateway_tenancy_baseline.json"
REPORT_FILE   = "gateway_tenancy_report.json"

# Fns that legitimately read a client hive_id without their OWN membership check.
# Each needs a one-line justification (mirrors GATEWAY_BYPASS_OK in spirit).
# Code-verified 2026-06-15 — NOT a blanket "looks internal" pass.
TENANCY_VERIFY_EXEMPT = {
    "marketplace-checkout":
        "Cross-hive BY DESIGN (a buyer purchases another hive's listing). "
        "Client hive_id is buyer-context metadata written to the order row only "
        "(index.ts:163); price/listing/seller fetched server-side from canonical "
        "views by listing_id — hive_id never scopes a protected read.",
    # NOTE: resume-extract + resume-polish were here ("hive_id rate-limit only").
    # Pillar P (2026-06-15) moved them OFF the client hive_id entirely — they now
    # rate-limit per-IDENTITY (checkSoloRateLimit), read no client hive_id at all,
    # and so are no longer detected as client-hive readers. Exemption removed so a
    # future unguarded body.hive_id read would FAIL rather than be silently exempt.
    "voice-journal-agent":
        "Conversational companion that reads NO hive-scoped data on the voice "
        "surface (explicitly defers KPIs to the Work Assistant, index.ts:544). "
        "Client hive_id is a cost-log tag only (index.ts:553), never a scoping "
        "read — a membership check would be over-gating (false positive).",
    # NOTE: data-fabric-normalizer + sensor-readings-ingest were here as
    # "exempt — machine ingest, needs an ingest key". They now carry a REAL
    # control (requireServiceRole rejects browser/anon callers), so they are
    # detected as verified and no longer need an exemption.
}

# ── Detection ────────────────────────────────────────────────────────────────

# Strip comments BEFORE scanning — the `[\s\S]*?` destructure regexes can span from
# a `{` in a header comment (e.g. one that merely MENTIONS `hive_id`/`auth_uid`)
# through to a real `} = await req.json()` in code, manufacturing a false positive.
# (Same "comments trip regex detectors" class the QA skill flags.) Stripping can
# only REMOVE false positives — it never masks a real code-level read.
def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)   # block comments
    src = re.sub(r"//[^\n]*", "", src)          # line comments
    return src

# A function reads a CLIENT hive_id when the parsed request body yields one.
# NOTE: destructure patterns use [\s\S]*? (not [^}]*) so a nested default like
# `context = {}` in the SAME destructure can't truncate the match — that bug
# hid ai-gateway's `const { agent, context = {}, hive_id = null } = body;`.
# Optional const/let/var (ai-gateway uses a bare `body = await req.json()` after
# a typed `let body: GatewayRequest;` declaration) and an optional type annotation.
_BODY_VAR_RE   = re.compile(r"(?:(?:const|let|var)\s+)?(\w+)\s*(?::[^=\n]+)?=\s*await\s+req\.json\(\)")
_DESTRUCTURE_AT_PARSE_RE = re.compile(
    r"\{[\s\S]*?\bhive_id\b[\s\S]*?\}\s*=\s*await\s+req\.json\(\)")
# Direct property access on a common body identifier.
_BODY_PROP_RE  = re.compile(r"\b(?:body|payload|reqBody|req_body|_body|reqJson|json|data)\s*\.\s*hive_id\b")

# Verification tokens (the canonical safe patterns). resolveTenancy/resolveContext
# = membership-verify a USER. requireServiceRole = a MACHINE-ingest endpoint that
# rejects browser/anon callers (only trusted service-role may write; the device-
# facing per-hive ingest key is the tracked follow-up).
_HELPER_RE     = re.compile(r"\b(?:resolve(?:Tenancy|Context)|requireServiceRole)\s*\(")
_INLINE_CANON  = re.compile(
    r"v_worker_truth[\s\S]{0,500}?auth_uid[\s\S]{0,500}?hive_status[\s\S]{0,300}?active",
    re.IGNORECASE)


def reads_client_hive(src: str) -> bool:
    if _DESTRUCTURE_AT_PARSE_RE.search(src):
        return True
    if _BODY_PROP_RE.search(src):
        return True
    # Body var assigned from req.json() then `<var>.hive_id` or destructured later.
    for m in _BODY_VAR_RE.finditer(src):
        v = re.escape(m.group(1))
        if re.search(rf"\b{v}\s*\.\s*hive_id\b", src):
            return True
        if re.search(rf"\{{[\s\S]*?\bhive_id\b[\s\S]*?\}}\s*=\s*{v}\b", src):
            return True
    return False


def has_verification(src: str) -> bool:
    return bool(_HELPER_RE.search(src) or _INLINE_CANON.search(src))


# ── Identity-key variant (auth_uid / user_id) — SAME IDOR class as hive_id ──────
# Pillar R triage (2026-06-15) found voice-semantic-rag + agentic-rag-loop scoping
# a PERSONAL read by a CLIENT-supplied `auth_uid` on a service-role (RLS-bypassed)
# client → cross-user IDOR. Generalize Pillar I: ANY client-supplied IDENTITY key
# used to SCOPE a service-role read must be server-verified. The dangerous shape is
# "reads a client auth_uid/user_id AND uses it in a .eq()/match_ scope" WITHOUT a
# server-side identity derivation (getUser / resolveIdentity / resolveTenancy) or a
# requireServiceRole gate.
_BODY_IDENTITY_PROP_RE = re.compile(
    r"\b(?:body|payload|reqBody|req_body|_body|reqJson|json|data)\s*\.\s*(?:auth_uid|user_id)\b")
_DESTRUCTURE_IDENTITY_RE = re.compile(
    r"\{[\s\S]*?\b(?:auth_uid|user_id)\b[\s\S]*?\}\s*=\s*await\s+req\.json\(\)")
_SCOPE_BY_IDENTITY_RE = re.compile(
    r"""\.eq\(\s*["'](?:auth_uid|user_id)["']|match_(?:auth_uid|user_id)\s*:""")
# Identity verification = derive/verify the caller server-side (NOT trust the body).
_IDENTITY_VERIFY_RE = re.compile(
    r"\.auth\.getUser\s*\(|\bresolve(?:Identity|Tenancy|Context)\s*\(|\brequireServiceRole\s*\(")


def reads_client_identity(src: str) -> bool:
    if _BODY_IDENTITY_PROP_RE.search(src) or _DESTRUCTURE_IDENTITY_RE.search(src):
        return True
    for m in _BODY_VAR_RE.finditer(src):
        v = re.escape(m.group(1))
        if re.search(rf"\b{v}\s*\.\s*(?:auth_uid|user_id)\b", src):
            return True
        if re.search(rf"\{{[\s\S]*?\b(?:auth_uid|user_id)\b[\s\S]*?\}}\s*=\s*{v}\b", src):
            return True
    return False


def scopes_by_identity(src: str) -> bool:
    return bool(_SCOPE_BY_IDENTITY_RE.search(src))


def has_identity_verification(src: str) -> bool:
    return bool(_IDENTITY_VERIFY_RE.search(src))


def list_edge_fns() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            if d.startswith("_"):
                continue
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((d, idx))
    return out


def scan() -> dict:
    safe, unsafe, exempt, irrelevant = [], [], [], []
    for name, path in list_edge_fns():
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                src = _strip_comments(f.read())
        except Exception:
            continue
        hive_relevant  = reads_client_hive(src)
        ident_relevant = reads_client_identity(src) and scopes_by_identity(src)
        if not hive_relevant and not ident_relevant:
            irrelevant.append(name)
            continue
        # SAFE only when EVERY relevant identity dimension is verified server-side.
        hive_ok  = (not hive_relevant)  or has_verification(src)
        ident_ok = (not ident_relevant) or has_identity_verification(src)
        if hive_ok and ident_ok:
            safe.append(name)
        elif name in TENANCY_VERIFY_EXEMPT:
            exempt.append(name)
        else:
            unsafe.append(name)
    return {
        "safe":       sorted(safe),
        "unsafe":     sorted(unsafe),
        "exempt":     sorted(exempt),
        "irrelevant": sorted(irrelevant),
    }


# ── Self-test ────────────────────────────────────────────────────────────────

_T_UNSAFE = """
serve(async (req) => {
  const body = await req.json();
  const rl = await checkRouteRateLimit(db, body.hive_id || "", route);
});
"""
_T_SAFE_HELPER = """
import { resolveTenancy } from "../_shared/tenant-context.ts";
serve(async (req) => {
  const body = await req.json();
  const t = await resolveTenancy(db, authUid, body.hive_id || null);
  if (!t.ok) return fail();
});
"""
_T_SAFE_INLINE = """
serve(async (req) => {
  const { hive_id } = await req.json();
  const { data: m } = await db.from("v_worker_truth")
    .select("role").eq("auth_uid", uid).eq("hive_id", hive_id).eq("hive_status", "active").maybeSingle();
  if (!m) return forbidden();
});
"""
_T_IRRELEVANT = """
serve(async (req) => {
  const { worker_name } = await req.json();
  return ok(worker_name);
});
"""
# Regression guard: nested default `context = {}` in the SAME destructure must
# not truncate detection (this exact shape hid ai-gateway from the first scan).
_T_UNSAFE_NESTED = """
serve(async (req) => {
  const body = await req.json();
  const { agent, message, context = {}, hive_id = null } = body;
  const data = await fetchHive(hive_id);
});
"""
# Machine-ingest endpoint: reads client hive_id but gates on requireServiceRole.
_T_SAFE_INGEST = """
import { requireServiceRole } from "../_shared/tenant-context.ts";
serve(async (req) => {
  const body = await req.json();
  const g = await requireServiceRole(db, req);
  if (!g.ok) return fail();
  await db.from("sensor_readings").insert({ hive_id: body.hive_id });
});
"""
# Identity-key variant (auth_uid IDOR). UNSAFE: reads a client auth_uid AND scopes
# a read by it with NO server-side identity verification.
_T_IDENT_UNSAFE = """
serve(async (req) => {
  const { auth_uid, query_text } = await req.json();
  const { data } = await db.from("voice_journal_entries").select("*").eq("auth_uid", auth_uid);
});
"""
# SAFE: the scoped uid is JWT-derived via getUser (client body value ignored).
_T_IDENT_SAFE = """
serve(async (req) => {
  const { auth_uid: _body } = await req.json();
  const authed = createClient(URL, ANON, { global: { headers: { Authorization: bearer } } });
  const { data: { user } } = await authed.auth.getUser();
  const { data } = await db.from("voice_journal_entries").select("*").eq("auth_uid", user.id);
});
"""


def self_test() -> bool:
    cases = [
        ("unsafe reader flagged",     _T_UNSAFE,       True,  False),
        ("safe via helper",           _T_SAFE_HELPER,  True,  True),
        ("safe via inline canonical", _T_SAFE_INLINE,  True,  True),
        ("no client hive_id",         _T_IRRELEVANT,   False, False),
        ("nested-default destructure", _T_UNSAFE_NESTED, True, False),
        ("safe via machine-ingest gate", _T_SAFE_INGEST, True, True),
    ]
    ident_cases = [
        ("identity UNSAFE (client auth_uid scope, no getUser)", _T_IDENT_UNSAFE, True,  False),
        ("identity safe (getUser-derived uid)",                 _T_IDENT_SAFE,   True,  True),
    ]
    passed = 0
    for label, src, want_reads, want_verified in cases:
        got_reads = reads_client_hive(src)
        got_verified = has_verification(src)
        ok = (got_reads == want_reads) and (got_verified == want_verified)
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}: reads={got_reads} verified={got_verified}")
        passed += ok
    for label, src, want_scope, want_verified in ident_cases:
        got_scope = reads_client_identity(src) and scopes_by_identity(src)
        got_verified = has_identity_verification(src)
        ok = (got_scope == want_scope) and (got_verified == want_verified)
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}: ident_scope={got_scope} ident_verified={got_verified}")
        passed += ok
    cases = cases + ident_cases  # for the count below
    print(f"\n  self-test: {passed}/{len(cases)} passed")
    return passed == len(cases)


# ── Main ─────────────────────────────────────────────────────────────────────

def load_baseline() -> int | None:
    if os.path.isfile(BASELINE_FILE):
        try:
            with open(BASELINE_FILE, "r", encoding="utf-8") as f:
                return int(json.load(f).get("unsafe_count", 0))
        except Exception:
            return None
    return None


def main() -> None:
    if "--self-test" in sys.argv:
        sys.exit(0 if self_test() else 1)

    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nGateway Tenancy Verification (Pillar I)"))
    print("=" * 60)

    res = scan()
    n_unsafe = len(res["unsafe"])
    baseline = load_baseline()

    print(f"  client-hive readers: {len(res['safe']) + n_unsafe + len(res['exempt'])}"
          f"  (safe {len(res['safe'])}, exempt {len(res['exempt'])}, UNVERIFIED {n_unsafe})")
    if res["unsafe"]:
        print(f"\n  {bold('UNVERIFIED client-hive readers:')}")
        for n in res["unsafe"]:
            print(f"    - {n}: reads client hive_id with no membership check "
                  f"(add resolveTenancy() or list in TENANCY_VERIFY_EXEMPT)")

    if "--write-baseline" in sys.argv:
        with open(BASELINE_FILE, "w", encoding="utf-8") as f:
            json.dump({"unsafe_count": n_unsafe, "unsafe": res["unsafe"]}, f, indent=2)
        print(f"\n  baseline written: unsafe_count={n_unsafe}")

    failed = baseline is not None and n_unsafe > baseline
    try:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump({"validator": "gateway_tenancy", "baseline": baseline,
                       "unsafe_count": n_unsafe, **res}, f, indent=2)
    except Exception:
        pass

    if baseline is None:
        print(f"\n\033[93m  No baseline yet. Run with --write-baseline to lock {n_unsafe}.\033[0m")
        sys.exit(0)
    if failed:
        print(f"\n\033[91m  FAIL: {n_unsafe} unverified > baseline {baseline} (Rule B: only down).\033[0m")
        sys.exit(1)
    print(f"\n\033[92m  PASS: {n_unsafe} unverified <= baseline {baseline}.\033[0m")
    sys.exit(0)


if __name__ == "__main__":
    main()
