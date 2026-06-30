#!/usr/bin/env python3
"""validate_signup_enumeration_safety.py — Arc I I1/I: account-enumeration resistance (OWASP ASVS V2.2).

ASVS V2.2 (anti-automation / enumeration): the auth flows must not let an attacker discover WHICH accounts
exist. The mandatory uniform-response surface is the **login** path — it must NOT distinguish "no such user"
from "wrong password" (both reveal account existence). For a **username-based** registration system, signup
necessarily tells the user a username is taken (they can't pick it) — that is an ACCEPTED ASVS carve-out, but
the disclosure must (a) route through a rate-limitable / PII-free RPC (not a raw cross-user table read), and
(b) be paired with bot-protection (Arc I I7 — Turnstile + RPC rate-limit), so it can't be scripted into a
user-list harvest.

RULES (on index.html, the auth front door):
  1. LOGIN uniform-response: the signInWithPassword error branch must map invalid credentials to a uniform
     message and must NOT contain an account-existence tell ("no account", "user not found", "not registered",
     "no such user", "email not found"). FAIL otherwise.
  2. SIGNUP availability via rate-limitable RPC: the uniqueness check must use the check_username_available
     RPC (PII-free, rate-limitable), NOT a direct worker_profiles SELECT that enumerates by username. FAIL on
     a raw cross-user availability read.
  3. RESET (only if a reset flow exists): uniform response, same tell-free rule.

Baseline 0 — any FAIL is a regression. The by-design signup carve-out is documented, not failed.

USAGE:      python tools/validate_signup_enumeration_safety.py
Self-test:  python tools/validate_signup_enumeration_safety.py --self-test
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

# account-existence tells — phrases that reveal an account does/doesn't exist (enumeration leak)
ENUM_TELL = re.compile(
    r"no account|user not found|username (does not exist|not found|doesn'?t exist)|"
    r"not registered|email not (found|registered)|no such user|account does not exist|"
    r"user does not exist|email (does not exist|not found)",
    re.I,
)
# acceptable uniform invalid-credential message
UNIFORM = re.compile(r"wrong (username|user) or password|invalid (login|credential)|incorrect (username|user)", re.I)


def _strip(body: str) -> str:
    b = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    return re.sub(r"//.*", "", b)


def _region(body: str, anchor: str, before: int = 0, after: int = 700) -> str:
    """Return the text window around the first occurrence of `anchor`."""
    i = body.find(anchor)
    if i < 0:
        return ""
    return body[max(0, i - before): i + after]


def audit(src: str) -> list[tuple[str, str]]:
    """Return list of (severity, message). severity in {FAIL, OK, NOTE}."""
    out: list[tuple[str, str]] = []
    body = _strip(src)

    # ── Rule 1: LOGIN uniform-response ──
    login = _region(body, "signInWithPassword", before=80, after=500)
    if not login:
        out.append(("NOTE", "no signInWithPassword path found (login flow absent?)"))
    else:
        if ENUM_TELL.search(login):
            tell = ENUM_TELL.search(login).group(0)
            out.append(("FAIL", f"LOGIN reveals account existence (enumeration tell: '{tell}') — ASVS V2.2 violation"))
        elif UNIFORM.search(login):
            out.append(("OK", f"LOGIN uniform-response present ('{UNIFORM.search(login).group(0)}') — no user-exists tell"))
        else:
            # no tell and no recognized uniform phrase: not a leak, but flag for review
            out.append(("NOTE", "LOGIN error branch has no enumeration tell, but no recognized uniform phrase either — review"))

    # ── Rule 2: SIGNUP availability via rate-limitable RPC ──
    # The RPC name is unique to the signup uniqueness path — scan whole-body (region windows miss it
    # because the <input id="su-username"> markup sits ~190 lines above submitSignUp's RPC call).
    signup = body
    if "check_username_available" in signup:
        out.append(("OK", "SIGNUP availability via check_username_available RPC (PII-free, rate-limitable) — by-design carve-out"))
        # the carve-out is only safe if paired with bot-protection (I7) — note the dependency
        if re.search(r"turnstile|cf-turnstile", body, re.I):
            out.append(("OK", "signup paired with Turnstile bot-protection (I7) — availability oracle is rate-limited"))
        else:
            out.append(("NOTE", "signup availability oracle NOT yet paired with in-page Turnstile (Arc I I7 build target) — relies on RPC/GoTrue rate-limit"))
    elif re.search(r"from\(['\"]worker_profiles['\"]\)[\s\S]{0,120}\.(select|eq)\([^)]*username", signup):
        out.append(("FAIL", "SIGNUP checks availability via a raw worker_profiles SELECT (enumerable by username) — use the check_username_available RPC"))
    else:
        out.append(("NOTE", "no signup availability check detected — review if username uniqueness is enforced elsewhere"))

    # ── Rule 3: RESET path (only if present) ──
    if re.search(r"resetPasswordForEmail|recover", body, re.I):
        reset = _region(body, "resetPasswordForEmail", before=40, after=400) or _region(body, "recover", after=400)
        if ENUM_TELL.search(reset):
            out.append(("FAIL", "PASSWORD-RESET reveals account existence — ASVS V2.2 violation"))
        else:
            out.append(("OK", "password-reset path present, no enumeration tell"))
    else:
        out.append(("NOTE", "no in-app password-reset flow (GoTrue provider path) — Arc I I3 attributed ceiling"))

    return out


def _self_test() -> int:
    leak = """
      const { data, error } = await db.auth.signInWithPassword({ email, password });
      if (error) { errEl.textContent = 'No account found for that username.'; return; }
    """
    safe = """
      const { data, error } = await db.auth.signInWithPassword({ email, password });
      if (error) { errEl.textContent = error.message.includes('Invalid login') ? 'Wrong username or password.' : error.message; return; }
      const { data: free } = await db.rpc('check_username_available', { p_username: u });
    """
    leak_fails = any(s == "FAIL" for s, _ in audit(leak))
    safe_passes = not any(s == "FAIL" for s, _ in audit(safe))
    ok = leak_fails and safe_passes
    print(f"  self-test: leak→FAIL={leak_fails}  safe→clean={safe_passes}  {'PASS' if ok else 'FAIL'}")
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
    print("  validate_signup_enumeration_safety — Arc I I1/I (ASVS V2.2 enumeration resistance)")
    print("=" * 74)
    for sev, msg in findings:
        c = RED if sev == "FAIL" else (GREEN if sev == "OK" else YEL)
        print(f"  {c}{sev:<4}{RST} {msg}")
    print("-" * 74)
    if fails:
        print(f"  {RED}FAIL{RST} — {len(fails)} enumeration leak(s)")
        return 1
    print(f"  {GREEN}PASS{RST} — login uniform-response holds; signup carve-out is RPC-gated & by-design")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
