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
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"


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
    ok = missing_fails and present_passes
    print(f"  self-test: missing→FAIL={missing_fails}  present→clean={present_passes}  {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return _self_test()
    if not FRONT_DOOR.exists():
        print(f"{RED}index.html not found{RST}")
        return 1
    findings = audit(FRONT_DOOR.read_text(encoding="utf-8", errors="replace"))
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
        return 1
    print(f"  {GREEN}PASS{RST} — Turnstile in-page wiring intact; live bot-block = dashboard enrollment (attributed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
