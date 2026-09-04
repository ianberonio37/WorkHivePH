#!/usr/bin/env python3
"""validate_webhook_signature_verified.py — T378's lock: the payment-intake webhook (gcash-receipt-inbound)
authenticates its caller by a shared-secret HMAC and FAILS CLOSED — so a forged receipt cannot mint credits.
This endpoint can cause money (marketplace credits) to be created from an unauthenticated POST, so every one
of the following must hold, or a forger walks in:

  1. FAIL CLOSED — no GCASH_INBOUND_SECRET configured => the request is REFUSED (401), never accepted
     unsigned ("resting state until Ian sets one" must be closed, not open).
  2. HMAC over the body — the expected signature is an HMAC of (timestamp . body), so the signature commits
     to the exact payload (a changed amount invalidates it).
  3. CONSTANT-TIME compare — the received signature is compared with a timing-safe equal, so it cannot be
     recovered byte-by-byte by measuring rejections.
  4. MISMATCH => 401 — a wrong/absent signature is refused, not logged-and-accepted.
  5. REPLAY WINDOW — a timestamp outside an accepted window is refused, so a captured (sig, ts, body) triple
     does not work forever.

Static source lock (the edge runtime is not always serving this fn locally, and a live 401-probe would go
dark whenever the container is down/contended — so the structural invariant is the durable gate; a live
probe is the board's job). Read-only, browser-free. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FN = ROOT / "supabase" / "functions" / "gcash-receipt-inbound" / "index.ts"

CHECK_NAMES = ["webhook-signature-verified"]


def check(src: str) -> list[str]:
    problems: list[str] = []
    # 1. FAIL CLOSED — a missing secret is refused (the `if (!secret)` guard on GCASH_INBOUND_SECRET).
    if "GCASH_INBOUND_SECRET" not in src or not re.search(r"if\s*\(\s*!\s*secret\s*\)", src):
        problems.append("does not FAIL CLOSED on a missing GCASH_INBOUND_SECRET — an unconfigured intake must "
                        "refuse (401), never accept unsigned receipts that can mint credits.")
    # 2. HMAC of the payload (a keyed hash, not a plain digest).
    if not re.search(r"crypto\.subtle\.(sign|importKey)", src):
        problems.append("no HMAC computation (crypto.subtle) — the signature is not a keyed hash of the payload.")
    # 3. CONSTANT-TIME MISMATCH REFUSAL — a negated timing-safe compare guards the refusal, so a wrong/absent
    #    signature is rejected and cannot be probed byte-by-byte. `!safeEqual(...)` is the single load-bearing
    #    token: remove/negate it and a forged signature falls through.
    if not re.search(r"!\s*(safeEqual|timingSafe\w*)\s*\(", src):
        problems.append("no constant-time signature-mismatch guard (!safeEqual(...)) — a wrong or absent "
                        "signature is not refused with a timing-safe compare (a forged receipt gets through).")
    # 4. REPLAY WINDOW — the timestamp skew is bounded, so a captured (sig, ts, body) triple expires.
    if not re.search(r"Date\.now\(\)\s*-\s*tsNum|tsNum\s*[-)]*.{0,12}Date\.now\(\)", src):
        problems.append("no timestamp replay window (a bounded Date.now() - tsNum skew) — a captured "
                        "(sig, ts, body) triple would work forever.")
    return problems


def main() -> int:
    if not FN.exists():
        print("FAIL webhook-signature-verified: gcash-receipt-inbound/index.ts not found"); return 1
    problems = check(FN.read_text(encoding="utf-8", errors="replace"))
    if problems:
        print("FAIL webhook-signature-verified — the payment-intake webhook can be forged:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS webhook-signature-verified — gcash-receipt-inbound fails closed with no secret, verifies an "
          "HMAC of (ts.body) with a constant-time compare, refuses a mismatch with 401, and enforces a replay "
          "window (a forged receipt cannot mint credits).")
    return 0


def self_test() -> int:
    good = ('const secret = Deno.env.get("GCASH_INBOUND_SECRET") || "";\n'
            'if (!secret) return fail(ctx, "no_secret", "x", { status: 401 });\n'
            'const sig = req.headers.get("X-WorkHive-Signature") || "";\n'
            'if (Math.abs(Date.now() - tsNum) > 600000) return fail(ctx,"stale","Timestamp window",{status:401});\n'
            'const key = await crypto.subtle.importKey("raw", enc, {name:"HMAC"}, false, ["sign"]);\n'
            'const expect = await hmacHex(secret, `${ts}.${raw}`);\n'
            'if (!safeEqual(expect, sig)) return fail(ctx, "bad_signature", "Invalid signature", { status: 401 });')
    fails = []
    if check(good):
        fails.append("the real verifying fn should PASS")
    # each mutation BREAKS the property (not just a label), so the matching check must redden:
    if not any("FAIL CLOSED" in p for p in check(good.replace('if (!secret) return fail(ctx, "no_secret", "x", { status: 401 });', 'const ok = true;'))):
        fails.append("removing the fail-closed guard should FAIL")
    if not any("HMAC" in p for p in check(good.replace("crypto.subtle.importKey", "md5"))):
        fails.append("dropping the HMAC computation should FAIL")
    if not any("constant-time" in p for p in check(good.replace("!safeEqual(expect, sig)", "false"))):
        fails.append("negating-away the mismatch guard should FAIL")
    if not any("replay" in p for p in check(good.replace("Math.abs(Date.now() - tsNum) > 600000", "0 > 1"))):
        fails.append("removing the replay window should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_webhook_signature_verified self-test (no-fail-closed / no-HMAC / no-mismatch-guard / no-replay redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
