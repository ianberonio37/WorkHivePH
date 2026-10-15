#!/usr/bin/env python3
"""validate_offline_is_not_no.py - a check that could not reach the server is never read as "no" (SL CA4, 2026-10-16).

Walked offline (SL CA4, the copy kept on the device):
  * Shift Brain sent a signed-in supervisor to the sign-in page: getUser() asks the SERVER, and offline it answers no
    user plus an AuthRetryableFetchError (status 0) - read as "the session is gone".
  * Every admin page told a platform admin "Founder access only" / "Platform Admins Only" after ~10 s of blank page:
    isPlatformAdmin() answered FALSE when its reads failed, and every gate read false as "not an admin".

Both are AU1's class ("a lapsed session is not a missing grant") on the network axis. This gate holds:
  1. utils.js keeps three answers - whPlatformAdminAnswer() returns 'yes' / 'no' / 'unreachable', and
     isPlatformAdmin() is `=== 'yes'` (every caller stays fail-closed)
  2. each admin GATE page asks whPlatformAdminAnswer and handles 'unreachable' (the page stays closed and says why)
  3. no page walls on a getUser()-only uid without telling AuthRetryableFetchError apart

    python tools/validate_offline_is_not_no.py              # the gate
    python tools/validate_offline_is_not_no.py --self-test  # fixtures + teeth on the pages as committed in 6c943351
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADMIN_GATES = ["founder-console.html", "marketplace-admin.html", "llm-observability.html",
               "agentic-rag-observability.html", "platform-actions.html"]

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

_BLOCK = re.compile(r"/\*.*?\*/|<!--.*?-->", re.S)
_LINE = re.compile(r"(?m)(?<![:\"'`\\/])//[^\n]*$")
_GETUSER_UID = re.compile(r"(\w+)\s*=\s*(?:\(await\s+db\.auth\.getUser\(\)\)\?\.data\?\.user\?\.id|_gu\?\.data\?\.user\?\.id)")


def _code(src: str) -> str:
    return _LINE.sub("", _BLOCK.sub(" ", src))


def utils_problems(utils: str) -> list[str]:
    u = _code(utils)
    out = []
    m = re.search(r"async function whPlatformAdminAnswer\(db\)\s*\{(.*?)\n\}", u, re.S)
    if not m or "'unreachable'" not in m.group(1):
        out.append("utils.js: no whPlatformAdminAnswer() that can answer 'unreachable'")
    if not re.search(r"async function isPlatformAdmin\(db\)\s*\{\s*return\s*\(await whPlatformAdminAnswer\(db\)\)\s*===\s*'yes';", u):
        out.append("utils.js: isPlatformAdmin() is not `(await whPlatformAdminAnswer(db)) === 'yes'` - a gate could read "
                   "'could not ask' as an answer")
    return out


def gate_problems(name: str, html: str) -> list[str]:
    c = _code(html)
    if "whPlatformAdminAnswer" not in c or "'unreachable'" not in c:
        return [f"{name}: its admin gate does not ask whPlatformAdminAnswer() and handle 'unreachable' - offline, an "
                f"admin is told the page is not for them"]
    return []


def getuser_problems(name: str, html: str) -> list[str]:
    c = _code(html)
    out = []
    for m in _GETUSER_UID.finditer(c):
        var = m.group(1)
        window = c[m.start(): m.start() + 1500]
        walls = re.search(r"if\s*\(\s*!" + re.escape(var) + r"\s*\)\s*\{\s*whSignInWall\(\)", window)
        if walls and "AuthRetryableFetchError" not in window:
            out.append(f"{name}: walls on a getUser()-only uid ({var}) without telling AuthRetryableFetchError apart - "
                       f"offline, a signed-in person is sent to sign in")
    return out


def check() -> int:
    problems = utils_problems((ROOT / "utils.js").read_text(encoding="utf-8", errors="replace"))
    for g in ADMIN_GATES:
        problems += gate_problems(g, (ROOT / g).read_text(encoding="utf-8", errors="replace"))
    pages = sorted(p for p in ROOT.glob("*.html"))
    for p in pages:
        problems += getuser_problems(p.name, p.read_text(encoding="utf-8", errors="replace"))
    for p in problems:
        print(f"FAIL offline-is-not-no: {p}")
    if problems:
        return 1
    print(f"PASS offline-is-not-no - the admin check keeps 'unreachable' apart and isPlatformAdmin stays fail-closed; "
          f"{len(ADMIN_GATES)} admin gates say why they are closed offline; no page walls on a server-only getUser() "
          f"answer ({len(pages)} pages read)")
    return 0


def self_test() -> int:
    ok = True

    def t(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(("ok  " if cond else "XX  ") + name)

    good_u = ("async function whPlatformAdminAnswer(db) {\n  if (x) return 'unreachable';\n  return 'no';\n}\n"
              "async function isPlatformAdmin(db) {\n  return (await whPlatformAdminAnswer(db)) === 'yes';\n}\n")
    t("the three-answer utils pass", utils_problems(good_u) == [])
    t("an isPlatformAdmin that reads its own failures as false fails",
      len(utils_problems(good_u.replace("return (await whPlatformAdminAnswer(db)) === 'yes';", "return false;"))) == 1)
    t("a gate that only asks isPlatformAdmin fails", gate_problems("x.html", "isPlatformAdmin(db).then(ok => ok ? a() : deny())"))
    t("a gate that handles 'unreachable' passes",
      gate_problems("x.html", "whPlatformAdminAnswer(db).then(a => a === 'unreachable' ? c() : d())") == [])
    wall = "let _authUid = null;\n try { _authUid = (await db.auth.getUser())?.data?.user?.id || null; } catch (_) {}\n if (!_authUid) { whSignInWall(); return; }"
    t("a page walling on a server-only getUser uid fails", len(getuser_problems("x.html", wall)) == 1)
    t("the same page telling AuthRetryableFetchError apart passes",
      getuser_problems("x.html", wall.replace("catch (_) {}", "catch (_) {}\n if (_authErr.name === 'AuthRetryableFetchError') {}")) == [])
    # teeth against the real files as committed in 6c943351 (before this fix)
    def at(ref, path):
        r = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True)
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""
    t("teeth: utils.js at 6c943351 has no three-answer check", len(utils_problems(at("6c943351", "utils.js"))) == 2)
    t("teeth: all five admin gates at 6c943351 fail",
      all(gate_problems(g, at("6c943351", g)) for g in ADMIN_GATES))
    t("teeth: shift-brain.html at 6c943351 walls on a server-only getUser uid",
      len(getuser_problems("shift-brain.html", at("6c943351", "shift-brain.html"))) == 1)
    print("self-test " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else check())
