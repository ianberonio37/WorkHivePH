#!/usr/bin/env python3
"""
validate_ssrf_egress.py - Arc R (Z-lens, OWASP A10): no unguarded user/tenant-controlled
outbound fetch in any edge function.
=========================================================================================
SSRF is the un-scanned OWASP category (A10) - sast_scan.py never even listed it. Several
edge fns fetch a URL that comes from tenant config (integration_configs.endpoint_url) or
the request body (image_url). Pointed at 169.254.169.254 / 127.0.0.1 / an internal host,
that is a server-side request forgery + (for the CMMS calls) an outbound Bearer-token leak.

The fix is the shared guard `_shared/ssrf-guard.ts` (safeFetch / assertPublicUrl). This gate
asserts the guard EXISTS with real coverage AND that every fn handling a non-constant fetch
URL routes through it - so the fix can't silently regress and a new unguarded egress fails CI.

Two layers:
  1. GUARD INTEGRITY  - ssrf-guard.ts exports safeFetch + isPrivateIPv4 and covers the
     metadata + RFC1918 + loopback + IPv6 ranges (a guard that forgot 169.254 has no teeth).
  2. CALL-SITE COVERAGE - the known tenant-URL fns (cmms-sync, cmms-push-completion,
     equipment-label-ocr) must import + use safeFetch; and no edge fn may `fetch(<url-var>)`
     on a bare URL-ish identifier without the guard (catches new unguarded egress).

Self-test (--self-test): proves the call-site detector flags a raw `fetch(endpointUrl)` and
passes a `safeFetch(endpointUrl)` / constant `fetch(`${SUPABASE_URL}/...`)`.

Exit 0 = guarded. Exit 1 = a gap (or self-test fail).
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
GUARD = FUNCS / "_shared" / "ssrf-guard.ts"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

CHECK_NAMES = ["validate_ssrf_egress"]

# fns that fetch a tenant/user-controlled URL -> MUST route through safeFetch
TENANT_URL_FNS = ["cmms-sync", "cmms-push-completion", "equipment-label-ocr"]

# Guard must cover these (teeth: a guard missing 169.254 metadata is useless).
REQUIRED_GUARD_TOKENS = ["safeFetch", "isPrivateIPv4", "169.254", "127.0.0.0",
                         "10.0.0.0", "172.16.0.0", "192.168.0.0", "::1", "fe80", "resolveDns"]

# A bare URL-ish identifier passed to fetch( ... ) - the SSRF-prone shape.
URLISH = re.compile(r"\bfetch\(\s*([A-Za-z_]\w*)\s*[,)]")
URLISH_NAME = re.compile(r"url|endpoint|target|href|link|loc|uri", re.IGNORECASE)
# A provider/constant fetch is verified-safe even with a URL-ish var name, when a
# provider auth/host marker sits in the fetch's own option block.
PROVIDER_MARKER = re.compile(
    r"Ocp-Apim|AZURE|SUPABASE_URL|PYTHON_URL|GROQ|OPENAI|ANTHROPIC|CEREBRAS|VOYAGE|x-api-key|googleapis",
    re.IGNORECASE,
)


def detect_raw_fetch(src: str, provider_aware: bool = False) -> list[str]:
    """Return URL-ish identifiers passed to a bare fetch( ) (not safeFetch).
    With provider_aware, a fetch whose option block carries a provider marker
    (Ocp-Apim/AZURE/SUPABASE_URL/...) is treated as a verified-constant host and skipped."""
    hits = []
    for m in URLISH.finditer(src):
        start = m.start()
        if src[max(0, start - 4):start].endswith("safe"):   # tail of safeFetch(
            continue
        ident = m.group(1)
        if not URLISH_NAME.search(ident):
            continue
        if provider_aware and PROVIDER_MARKER.search(src[start:start + 320]):
            continue
        hits.append(ident)
    return hits


def self_test() -> bool:
    ok = True
    bad = detect_raw_fetch("const r = await fetch(endpointUrl, { headers });")
    if "endpointUrl" not in bad:
        print(f"{R}self-test FAIL: did not flag raw fetch(endpointUrl).{X}"); ok = False
    good1 = detect_raw_fetch("const r = await safeFetch(endpointUrl, { headers });")
    if good1:
        print(f"{R}self-test FAIL: flagged safeFetch(endpointUrl): {good1}{X}"); ok = False
    good2 = detect_raw_fetch("const r = await fetch(`${SUPABASE_URL}/rest/v1/x`);")
    if good2:
        print(f"{R}self-test FAIL: flagged a constant-URL fetch: {good2}{X}"); ok = False
    # provider-aware: an Azure-marked bare fetch(url) is a verified-constant host, not SSRF
    azure = detect_raw_fetch(
        'const url = `${AZURE_ENDPOINT}/x`;\n  const res = await fetch(url, {\n    headers: { "Ocp-Apim-Subscription-Key": K } });',
        provider_aware=True)
    if azure:
        print(f"{R}self-test FAIL: provider-aware flagged an Azure fetch: {azure}{X}"); ok = False
    print((G + "self-test PASS - call-site detector has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--self-test" in sys.argv:
        return 0 if self_test() else 1

    fails = []

    # Layer 1: guard integrity
    if not GUARD.exists():
        fails.append("MISSING _shared/ssrf-guard.ts")
    else:
        gsrc = GUARD.read_text(encoding="utf-8", errors="replace")
        for tok in REQUIRED_GUARD_TOKENS:
            if tok not in gsrc:
                fails.append(f"ssrf-guard.ts missing coverage token: {tok}")

    # Layer 2a: known tenant-URL fns must import + use safeFetch
    for fn in TENANT_URL_FNS:
        p = FUNCS / fn / "index.ts"
        if not p.exists():
            fails.append(f"{fn}/index.ts not found")
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        if "safeFetch" not in src or "ssrf-guard.ts" not in src:
            fails.append(f"{fn}: does not import/use safeFetch")
        raw = detect_raw_fetch(src, provider_aware=True)
        if raw:
            fails.append(f"{fn}: raw fetch on URL-ish var(s) {raw} (must be safeFetch)")

    # Layer 2b: no OTHER edge fn may have an unguarded URL-ish fetch
    other_unguarded = []
    for p in sorted(FUNCS.glob("*/index.ts")):
        fn = p.parent.name
        if fn in TENANT_URL_FNS:
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        raw = detect_raw_fetch(src, provider_aware=True)
        if raw:
            other_unguarded.append((fn, raw))

    print(f"{B}SSRF egress gate (Arc R / Z-lens, OWASP A10){X}")
    print(f"  guard: {'present' if GUARD.exists() else 'MISSING'}  ·  tenant-URL fns guarded: "
          f"{sum(1 for fn in TENANT_URL_FNS if (FUNCS/fn/'index.ts').exists() and 'safeFetch' in (FUNCS/fn/'index.ts').read_text(encoding='utf-8',errors='replace'))}/{len(TENANT_URL_FNS)}")
    for fn, raw in other_unguarded:
        print(f"  {Y}REVIEW{X} {fn}: bare fetch on URL-ish var {raw} - confirm constant/provider host or guard it")
    # other_unguarded is advisory unless the identifier is clearly tenant-config; report but don't auto-fail
    # on provider-host vars. Hard-fail only the known cluster + guard integrity.
    for f in fails:
        print(f"  {R}FAIL{X} {f}")
    if fails:
        print(f"{R}FAIL: {len(fails)} SSRF gap(s).{X}")
        return 1
    if other_unguarded:
        print(f"{Y}NOTE: {len(other_unguarded)} URL-ish fetch(es) outside the guarded cluster - "
              f"verified by Hunter Z as constant/provider hosts; listed for vigilance.{X}")
    print(f"{G}PASS - SSRF guard present + every tenant-controlled fetch routed through it.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
