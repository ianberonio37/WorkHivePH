"""
Gateway Policy Hive-Binding -- WorkHive Platform (Pillar P)
==========================================================
The Full-Stack SaaS Gateway's Pillar P (Policy & Governance) invariant for
rate-limit / quota enforcement:

  Policy buckets (rate-limit, quota) must be keyed on a VERIFIED tenant -- never
  on a raw, unverified CLIENT hive_id. An ANON-CAPABLE edge function that passes
  the client `hive_id` straight into a hive-keyed rate-limit helper lets an
  UNAUTHENTICATED caller drain a *victim* hive's shared bucket simply by spoofing
  its id (cross-tenant denial-of-service), and lets a caller mint a fresh bucket
  by inventing an id (dodging their own cap).

This catches the bug class found 2026-06-15 (the Pillar I <-> P intersection):
  - ai-gateway authenticated the user but, on its ANON voice-journal path (which
    skips resolveTenancy), rate-limited on the client `hive_id` -> an anon POST
    `{agent:"voice-journal", hive_id:"<victim>"}` consumed the victim's bucket.
  - resume-extract / resume-polish (public, verify_jwt=false, solo features) did
    `if (hive_id) checkAIRateLimit(db, hive_id)` with NO membership check.

The canonical fix mirrors platform-gateway: resolve the VERIFIED hive
(`resolveTenancy().hive_id`) and pass THAT to the rate-limit helper for proven
members; for anon / no-verified-hive callers, bucket on the caller's own
identity via `checkSoloRateLimit(db, soloRateLimitKey(authUid, clientIp))`.

  EXPLOITABLE  = anon-capable fn that passes a raw client hive_id to a hive-keyed
                 rate-limit helper. This is the FAIL-eligible class (baseline 0).
  LATENT       = an AUTHED-only fn that passes the raw `hive_id` var (its value is
                 membership-verified earlier, so not exploitable). Reported as the
                 Pillar P naming-convention backlog (adopt a `verifiedHiveId` var),
                 NOT a failure.

Detection of "anon-capable": the fn shows it handles callers with no verified
hive -- an `ANON_OK` allowlist token, or a `soloRateLimitKey(` / per-identity
bucket (a fn only writes that code when it expects hive-less / anon callers), or
an explicit entry in ANON_CAPABLE.

This is COMPLEMENTARY to validate_gateway_tenancy.py (Pillar I): that ratchets
whether a client-hive READER verifies membership at all; this ratchets whether
POLICY ENFORCEMENT keys on the verified tenant on EVERY path (incl. anon).

Ratchet: the count of EXPLOITABLE fns is baseline-locked in
policy_hive_binding_baseline.json and may only move DOWN (study Rule B).

Run:
  python validate_policy_hive_binding.py             # gate (exit 1 on regression)
  python validate_policy_hive_binding.py --self-test # prove the detector ($0, offline)
  python validate_policy_hive_binding.py --write-baseline

Skills consulted: security (cross-tenant DoS / unauth abuse), multitenant-engineer
(per-hive bucket isolation), architect (verified-tenant binding as the single
policy key).
"""
from __future__ import annotations

import re
import os
import sys
import json

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

FUNCTIONS_DIR = os.path.join("supabase", "functions")
BASELINE_FILE = "policy_hive_binding_baseline.json"
REPORT_FILE   = "policy_hive_binding_report.json"

# Anon-capable fns that legitimately bucket hive-less callers but are PROVEN to
# never key a hive-rate-limit on a raw client hive_id (code-verified). Currently
# empty: ai-gateway, resume-extract and resume-polish all bucket on the verified
# hive (members) or identity (anon) after the 2026-06-15 Pillar P fix, so the
# detector clears them automatically -- no exemption needed.
POLICY_BINDING_EXEMPT: dict[str, str] = {}

# ── Detection ────────────────────────────────────────────────────────────────

# A hive-keyed rate-limit helper CALL (not its definition -- the def carries a
# `hiveId: string` typed param, so the `[\w.]+\s*,` first-arg shape fails on the
# `db: Type` colon; the `(?<!function )` lookbehind is belt-and-suspenders).
# Captures arg1 (db client) and arg2 (the hive argument, single segment).
_RL_CALL_RE = re.compile(
    r"(?<!function )\bcheck(?:AI|User|Classed|Route)RateLimit\s*\(\s*[\w.]+\s*,\s*([^,)\n]+)",
    re.DOTALL,
)
# A raw, unverified CLIENT hive token as the rate-limit key: `hive_id`,
# `body.hive_id` (with an optional `|| ""` / `|| null`). A verified variable
# (`verifiedHiveId`, `tenancy.hive_id`, a renamed `single_hive`/`reqHiveId`) does
# NOT match `\bhive_id\b`, so it is correctly treated as safe.
_RAW_CLIENT_HIVE_RE = re.compile(r"^(?:body\.)?hive_id\b")

# Anon-capable signals.
_ANON_OK_RE        = re.compile(r"\bANON_OK\w*")
_SOLO_BUCKET_RE    = re.compile(r"\bsoloRateLimitKey\s*\(|\bcheckSoloRateLimit\s*\(")


def passes_raw_client_hive_to_ratelimit(src: str) -> bool:
    for m in _RL_CALL_RE.finditer(src):
        arg2 = m.group(1).strip()
        if _RAW_CLIENT_HIVE_RE.match(arg2):
            return True
    return False


def is_anon_capable(name: str, src: str) -> bool:
    if name in ANON_CAPABLE:
        return True
    return bool(_ANON_OK_RE.search(src) or _SOLO_BUCKET_RE.search(src))


# Curated anon-capable set (belt-and-suspenders; the structural signals above
# already catch these). Kept so a future refactor that drops the solo helper
# does not silently un-flag a public fn.
ANON_CAPABLE = {"ai-gateway", "resume-extract", "resume-polish", "voice-journal-agent"}


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
    exploitable, latent, exempt, clean = [], [], [], []
    for name, path in list_edge_fns():
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                src = f.read()
        except Exception:
            continue
        if not passes_raw_client_hive_to_ratelimit(src):
            clean.append(name)
            continue
        # This fn keys a rate-limit on a raw client hive_id.
        if not is_anon_capable(name, src):
            latent.append(name)          # authed-only: value is verified earlier
        elif name in POLICY_BINDING_EXEMPT:
            exempt.append(name)
        else:
            exploitable.append(name)     # anon-capable + raw client hive -> FAIL
    return {
        "exploitable": sorted(exploitable),
        "latent":      sorted(latent),
        "exempt":      sorted(exempt),
        "clean_count": len(clean),
    }


# ── Self-test ────────────────────────────────────────────────────────────────

_T_EXPLOIT_ANONOK = """
const ANON_OK_AGENTS = new Set(["voice-journal"]);
serve(async (req) => {
  const { hive_id } = await req.json();
  const rl = await checkAIRateLimit(db, hive_id, RATE_LIMIT_PER_HOUR);
});
"""
_T_SAFE_VERIFIED = """
const ANON_OK_AGENTS = new Set(["voice-journal"]);
serve(async (req) => {
  let verifiedHiveId = null;
  const rl = await checkUserRateLimit(
    adminClient,
    verifiedHiveId,
    userId,
  );
});
"""
_T_SAFE_SOLO_ONLY = """
serve(async (req) => {
  const clientIp = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  const rl = await checkSoloRateLimit(db, soloRateLimitKey(auth_uid, clientIp));
});
"""
# Authed-only fn passing the raw hive var: LATENT (verified earlier), not a FAIL.
_T_LATENT_AUTHED = """
import { resolveTenancy } from "../_shared/tenant-context.ts";
serve(async (req) => {
  const { hive_id } = await req.json();
  const t = await resolveTenancy(db, authUid, hive_id);
  if (!t.ok) return fail();
  const rl = await checkAIRateLimit(db, hive_id || "");
});
"""
# Multiline anon-capable raw call (the exact ai-gateway-pre-fix shape).
_T_EXPLOIT_MULTILINE = """
const ANON_OK_AGENTS = new Set(["voice-journal"]);
serve(async (req) => {
  const rl = await checkUserRateLimit(
    adminClient,
    hive_id || "",
    userId,
    RL_OVERRIDE,
  );
});
"""
# The helper DEFINITION must NOT be detected as a call (typed `hiveId` param).
_T_DEF_NOT_CALL = """
async function checkAIRateLimit(
  db: SupabaseClient, hiveId: string, limitPerHour: number,
): Promise<{ allowed: boolean }> {
  return { allowed: true };
}
serve(async (req) => {
  const clientIp = "";
  const rl = await checkSoloRateLimit(db, soloRateLimitKey(auth_uid, clientIp));
});
"""


def self_test() -> bool:
    # (label, src, want_raw_client, want_anon_capable, want_verdict)
    # verdict: "exploitable" | "latent" | "clean"
    cases = [
        ("anon-ok + raw client hive",       _T_EXPLOIT_ANONOK,    True,  True,  "exploitable"),
        ("anon-ok + verified var",          _T_SAFE_VERIFIED,     False, True,  "clean"),
        ("solo-only bucket",                _T_SAFE_SOLO_ONLY,    False, True,  "clean"),
        ("authed-only raw hive (latent)",   _T_LATENT_AUTHED,     True,  False, "latent"),
        ("multiline anon raw call",         _T_EXPLOIT_MULTILINE, True,  True,  "exploitable"),
        ("helper def is not a call",        _T_DEF_NOT_CALL,      False, True,  "clean"),
    ]
    passed = 0
    for label, src, want_raw, want_anon, want_verdict in cases:
        got_raw  = passes_raw_client_hive_to_ratelimit(src)
        got_anon = is_anon_capable("_t_", src)
        if not got_raw:
            verdict = "clean"
        elif not got_anon:
            verdict = "latent"
        else:
            verdict = "exploitable"
        ok = (got_raw == want_raw) and (got_anon == want_anon) and (verdict == want_verdict)
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}: raw={got_raw} anon={got_anon} verdict={verdict}")
        passed += ok
    print(f"\n  self-test: {passed}/{len(cases)} passed")
    return passed == len(cases)


# ── Main ─────────────────────────────────────────────────────────────────────

def load_baseline() -> int | None:
    if os.path.isfile(BASELINE_FILE):
        try:
            with open(BASELINE_FILE, "r", encoding="utf-8") as f:
                return int(json.load(f).get("exploitable_count", 0))
        except Exception:
            return None
    return None


def main() -> None:
    if "--self-test" in sys.argv:
        sys.exit(0 if self_test() else 1)

    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nGateway Policy Hive-Binding (Pillar P)"))
    print("=" * 60)

    res = scan()
    n_exploit = len(res["exploitable"])
    baseline = load_baseline()

    print(f"  rate-limit hive-key bindings: exploitable {n_exploit}, "
          f"latent {len(res['latent'])}, exempt {len(res['exempt'])}, "
          f"clean {res['clean_count']}")
    if res["exploitable"]:
        print(f"\n  {bold('EXPLOITABLE (anon-capable fn keys rate-limit on a raw client hive_id):')}")
        for n in res["exploitable"]:
            print(f"    - {n}: an anon caller can drain a victim hive's bucket by "
                  f"spoofing hive_id (use the verified hive, or checkSoloRateLimit "
                  f"for anon; or list in POLICY_BINDING_EXEMPT)")
    if res["latent"]:
        print(f"\n  {bold('latent backlog')} (authed-only; value is membership-verified "
              f"earlier -- adopt a verifiedHiveId var for clarity, not exploitable):")
        for n in res["latent"]:
            print(f"    - {n}")

    if "--write-baseline" in sys.argv:
        with open(BASELINE_FILE, "w", encoding="utf-8") as f:
            json.dump({"exploitable_count": n_exploit, "exploitable": res["exploitable"]}, f, indent=2)
        print(f"\n  baseline written: exploitable_count={n_exploit}")

    failed = baseline is not None and n_exploit > baseline
    try:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump({"validator": "policy_hive_binding", "baseline": baseline,
                       "exploitable_count": n_exploit, **res}, f, indent=2)
    except Exception:
        pass

    if baseline is None:
        print(f"\n\033[93m  No baseline yet. Run with --write-baseline to lock {n_exploit}.\033[0m")
        sys.exit(0)
    if failed:
        print(f"\n\033[91m  FAIL: {n_exploit} exploitable > baseline {baseline} (Rule B: only down).\033[0m")
        sys.exit(1)
    print(f"\n\033[92m  PASS: {n_exploit} exploitable <= baseline {baseline}.\033[0m")
    sys.exit(0)


if __name__ == "__main__":
    main()
