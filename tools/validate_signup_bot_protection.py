#!/usr/bin/env python3
"""validate_signup_bot_protection.py — Arc I I7/I: signup bot-protection wiring (OWASP ASVS V2 anti-automation).

ASVS V2.1 anti-automation: account creation must resist scripted/bot signup. WorkHive wires Cloudflare
Turnstile on the signup form with a CONFIGURE-TO-ENABLE pattern (mirrors Arc F's python-api auth key):
the in-page integration is present and asserted here (the DEVELOPER half); the live bot-block needs the
Turnstile sitekey + the Supabase Auth > Bot Protection dashboard toggle (the PROVIDER half = attributed,
out of local scope). This gate proves the in-page half stays intact — a refactor that rips out the widget,
the script loader, or the captchaToken hand-off FAILs.

RULE (on index.html, the signup front door):
  1. a Turnstile container (#su-turnstile) exists in the signup form
  2. mountTurnstile() loads the challenges.cloudflare.com Turnstile script and renders the widget,
     gated on window.WH_TURNSTILE_SITEKEY (so it's inert/non-breaking when unconfigured)
  3. submitSignUp() attaches the captchaToken to signUp() ONLY when a token exists (GoTrue rejects a
     token when captcha is disabled — an unconfigured signup must send none)

★THE CSP HALF, ADDED 2026-08-28 (T169) — AND A CORRECTION TO THIS FILE'S OWN SCOPE CLAIM. The
docstring above used to say the remaining work was "the sitekey + the Supabase dashboard toggle
(the PROVIDER half = attributed, out of local scope)". That was wrong in a way that mattered:
there was a THIRD requirement, and it was entirely local — in `_headers`, a tracked file in this
repo. script-src did not permit challenges.cloudflare.com and NO frame-src was declared at all,
so it fell back to default-src 'self' and would have blocked Turnstile's challenge iframe.

The consequence was not a degraded widget but an OUTAGE ON THE FRONT DOOR. Enabling bot defense
would go: script blocked => window.turnstile never defined => mountTurnstile()'s render() returns
early => _turnstileToken() returns null => signUp() sends no captchaToken — while step two of the
very same switch tells Supabase to reject exactly that. Signup dies platform-wide, the feature
meant to protect it is the cause, the only evidence is a console CSP violation, and `_headers` is
PROD-ONLY so nothing local reproduces it. A switch documented as two steps had a silent third in a
file nobody flipping it would open, which is why this now belongs to a gate and not to memory.

RULE (on _headers, the prod edge):
  4. script-src permits https://challenges.cloudflare.com
  5. frame-src permits it too — an ABSENT frame-src is a FAILURE here, not a neutral omission,
     because it silently inherits default-src 'self' and blocks the iframe

Baseline 0 — any missing piece is a regression. The "unconfigured = inert" property is REQUIRED, not a gap.

USAGE:      python tools/validate_signup_bot_protection.py
Self-test:  python tools/validate_signup_bot_protection.py --self-test
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FRONT_DOOR = ROOT / "index.html"
EDGE_HEADERS = ROOT / "_headers"
TURNSTILE_ORIGIN = "https://challenges.cloudflare.com"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"


def audit_csp(headers: str) -> list[tuple[str, str]]:
    """The edge half: the CSP must permit Turnstile's script AND its iframe.

    ★AN ABSENT frame-src IS A FAILURE, NOT A NEUTRAL OMISSION. CSP falls back to default-src,
    which is 'self' here, so saying nothing about frames says "no third-party frames" just as
    loudly as declaring it — and Turnstile renders its challenge in an iframe. The omission and
    the denial are the same header to a browser; only one of them looks deliberate in review.
    """
    m = re.search(r"Content-Security-Policy:\s*([^\n]+)", headers)
    if not m:
        return [("FAIL", "no Content-Security-Policy found in _headers — cannot judge the edge half")]

    directives: dict[str, str] = {}
    for part in m.group(1).split(";"):
        part = part.strip()
        if part:
            directives[part.split()[0].lower()] = part

    script_ok = TURNSTILE_ORIGIN in directives.get("script-src", "")
    frame_declared = "frame-src" in directives          # frame-ancestors is a DIFFERENT directive
    frame_ok = frame_declared and TURNSTILE_ORIGIN in directives["frame-src"]

    out = [("OK" if script_ok else "FAIL",
            f"CSP script-src permits {TURNSTILE_ORIGIN} (else api.js is blocked and "
            f"window.turnstile never exists)")]
    if not frame_declared:
        out.append(("FAIL", "CSP declares NO frame-src — it inherits default-src and blocks the "
                            "Turnstile challenge iframe; an omission here is a denial"))
    else:
        out.append(("OK" if frame_ok else "FAIL",
                    f"CSP frame-src permits {TURNSTILE_ORIGIN} (the challenge renders in an iframe)"))
        # ★THE REGRESSION THIS CLAUSE EXISTS FOR, CAUGHT IN THE ACT. Declaring frame-src at all
        # REPLACES the default-src fallback rather than adding to it, so the moment the directive
        # was introduced for Turnstile it silently revoked same-origin framing — and assistant.html
        # lazily loads voice-journal.html into an iframe for its Journal tab (:498,
        # frame.src = 'voice-journal.html?embedded=1'). The fix for one prod-only CSP bug was
        # therefore one keystroke from shipping another, invisible the same way: _headers has no
        # local equivalent, and a blocked frame throws nothing a page can see.
        if "'self'" not in directives["frame-src"]:
            out.append(("FAIL", "CSP declares frame-src WITHOUT 'self' — declaring the directive "
                                "REPLACES the default-src fallback, so this revokes same-origin "
                                "framing; assistant.html embeds voice-journal.html and would break"))
        else:
            out.append(("OK", "CSP frame-src keeps 'self' (assistant.html embeds voice-journal.html; "
                              "declaring frame-src replaces the default-src fallback, it does not add "
                              "to it)"))
    return out


def audit(src: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    b = re.sub(r"<!--.*?-->", "", src, flags=re.S)  # drop HTML comments

    has_container = bool(re.search(r"id=['\"]su-turnstile['\"]", b))
    has_mount = bool(re.search(r"function mountTurnstile", b))
    has_script = bool(re.search(r"challenges\.cloudflare\.com/turnstile", b))
    sitekey_gated = bool(re.search(r"WH_TURNSTILE_SITEKEY", b))
    token_conditional = bool(re.search(r"captchaToken\s*\?\s*\{\s*options", b) or
                             re.search(r"\.\.\.\(\s*captchaToken", b))
    token_helper = bool(re.search(r"_turnstileToken\s*\(", b))

    checks = [
        (has_container, "container #su-turnstile present in signup form"),
        (has_mount, "mountTurnstile() loader present"),
        (has_script, "Cloudflare Turnstile script source wired"),
        (sitekey_gated, "gated on window.WH_TURNSTILE_SITEKEY (inert when unconfigured = non-breaking)"),
        (token_helper, "_turnstileToken() reader present"),
        (token_conditional, "captchaToken attached to signUp() ONLY when present (no token sent when disabled)"),
    ]
    for ok, msg in checks:
        out.append(("OK" if ok else "FAIL", msg))
    return out


def _self_test() -> int:
    missing = "<form id='panel-signup'><input id='su-username'></form>"  # no turnstile wiring
    present = """
      <div id="su-turnstile"></div>
      function mountTurnstile(){ const k=window.WH_TURNSTILE_SITEKEY; s.src='https://challenges.cloudflare.com/turnstile/v0/api.js'; }
      function _turnstileToken(){ return window.turnstile.getResponse(id); }
      const captchaToken=_turnstileToken();
      await db.auth.signUp({ email, password, ...(captchaToken ? { options:{captchaToken} } : {}) });
    """
    missing_fails = any(s == "FAIL" for s, _ in audit(missing))
    present_passes = not any(s == "FAIL" for s, _ in audit(present))

    # the edge half — the three CSP shapes that matter, including the one that shipped
    good_csp = ("  Content-Security-Policy: default-src 'self'; script-src 'self' "
                "https://challenges.cloudflare.com; frame-src 'self' "
                "https://challenges.cloudflare.com; frame-ancestors 'none'")
    # the near-miss: Turnstile permitted, but declaring frame-src dropped same-origin framing
    selfless_csp = ("  Content-Security-Policy: default-src 'self'; script-src 'self' "
                    "https://challenges.cloudflare.com; frame-src "
                    "https://challenges.cloudflare.com; frame-ancestors 'none'")
    # ★THE EXACT PRE-FIX HEADER: script-src without Turnstile and NO frame-src at all. Both halves
    # must be indicted, or the self-test would bless the configuration that caused the finding.
    shipped_csp = ("  Content-Security-Policy: default-src 'self'; script-src 'self' "
                   "https://cdn.tailwindcss.com; frame-ancestors 'none'")
    # frame-ancestors must not be mistaken for frame-src — different directive, opposite question
    decoy_csp = ("  Content-Security-Policy: default-src 'self'; script-src 'self' "
                 "https://challenges.cloudflare.com; frame-ancestors 'none'")

    good_passes = not any(s == "FAIL" for s, _ in audit_csp(good_csp))
    shipped_fails = len([1 for s, _ in audit_csp(shipped_csp) if s == "FAIL"]) == 2
    decoy_fails = any(s == "FAIL" for s, _ in audit_csp(decoy_csp))
    none_fails = any(s == "FAIL" for s, _ in audit_csp("no policy here"))
    selfless_fails = any("revokes same-origin framing" in m
                         for s, m in audit_csp(selfless_csp) if s == "FAIL")

    ok = all([missing_fails, present_passes, good_passes, shipped_fails, decoy_fails,
              none_fails, selfless_fails])
    print(f"  page half : missing→FAIL={missing_fails}  present→clean={present_passes}")
    print(f"  edge half : good→clean={good_passes}  pre-fix→2 FAILs={shipped_fails}  "
          f"frame-ancestors-decoy→FAIL={decoy_fails}  no-CSP→FAIL={none_fails}  "
          f"frame-src-without-self→FAIL={selfless_fails}")
    print(f"  self-test: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return _self_test()
    if not FRONT_DOOR.exists():
        print(f"{RED}index.html not found{RST}")
        return 1
    if not EDGE_HEADERS.exists():
        print(f"{RED}_headers not found — the edge half of the switch cannot be judged{RST}")
        return 1
    findings = audit(FRONT_DOOR.read_text(encoding="utf-8", errors="replace"))
    findings += audit_csp(EDGE_HEADERS.read_text(encoding="utf-8", errors="replace"))
    fails = [m for s, m in findings if s == "FAIL"]
    print("=" * 74)
    print("  validate_signup_bot_protection — Arc I I7/I (Turnstile wiring, configure-to-enable)")
    print("=" * 74)
    for sev, msg in findings:
        c = GREEN if sev == "OK" else RED
        print(f"  {c}{sev:<4}{RST} {msg}")
    print("-" * 74)
    if fails:
        print(f"  {RED}FAIL{RST} — {len(fails)} bot-protection wiring piece(s) missing")
        print("    A switch that cannot be thrown is not a feature behind a flag; it is an outage")
        print("    waiting for whoever throws it. Both halves must hold while the feature is OFF.")
        return 1
    print(f"  {GREEN}PASS{RST} — in-page wiring intact AND the edge permits Turnstile, so the "
          f"documented switch is true; the remaining step is the Supabase dashboard toggle (attributed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
