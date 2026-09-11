#!/usr/bin/env python3
"""check_credential_pointers.py — no page tells a reader where a secret lives.

★THE FIX THAT NEVER REACHED ITS TARGET, FOUND AGAIN THREE WEEKS LATER. On 2026-08-25 the line
`Grafana login: admin · password in infra/mcp/.env.mcp` was removed from `marketplace-admin.html`, with the
reason written into the file: *"this overlay renders for ANY signed-in visitor to the URL, not only the
founder, and a credentials location baked into page copy is a screen-share/shoulder hazard."* Three pages
carried the identical paragraph and were never touched — and they were **worse than the one that was fixed,
because none of them is auth-gated at all**, so it rendered for anyone who opened the URL.

It leaks no password. It names the account and points at the file that holds one, which is most of the work,
and it does it on a page anybody can read.

This gate exists because the class recurs by COPY: a paragraph written once gets pasted onto sibling pages,
and a fix applied to the page somebody happened to be looking at leaves the copies behind. Only a sweep of
every page can see that.

What counts: a password stated or located, a login named beside a password, a credentials path, an inline
API key. What does not: the word "password" in a label, a sign-in form, or a comment — a comment ships to the
browser but is not shown to a reader, and this gate is about what a reader SEES. (A comment holding a real
secret is a different gate's job, and `tools/scan_secrets.py` owns it.)

  python tools/check_credential_pointers.py
  python tools/check_credential_pointers.py --self-test
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMENT = re.compile(r"<!--.*?-->", re.S)

PATTERNS = [
    (re.compile(r"password\s+(?:is|in)\s+[^<\"\n]{3,44}", re.I), "a password stated or located"),
    (re.compile(r"login:\s*\w+\s*[·:|-]\s*password", re.I), "a login named beside its password"),
    (re.compile(r"credential[s]?\s+(?:are\s+)?in\s+[^<\"\n]{3,40}", re.I), "a credentials path"),
    (re.compile(r"\.env[a-z.]*\b[^<\"\n]{0,24}password", re.I), "an env file named as holding a password"),
    (re.compile(r"api[_ ]?key\s*[:=]\s*[A-Za-z0-9_\-]{12,}", re.I), "an inline API key"),
]

GLOBS = ["*.html", "learn/*/index.html", "tools/*/index.html", "seo_assets/calc_pages_staging/*/index.html"]


def visible(path: Path) -> str:
    """What a reader sees: comments removed, because a comment ships but is never rendered."""
    return COMMENT.sub(" ", path.read_text(encoding="utf-8", errors="replace"))


def main() -> int:
    if "--self-test" in sys.argv:
        fails = []
        s = "Grafana login: admin · password in infra/mcp/.env.mcp"
        if not any(p.search(s) for p, _ in PATTERNS):
            fails.append("the exact line this gate exists for is not caught")
        if any(p.search("<label>Password</label><input type=password>") for p, _ in PATTERNS):
            fails.append("a sign-in form is being flagged")
        if any(p.search("Forgot your password? Reset it") for p, _ in PATTERNS):
            fails.append("ordinary password copy is being flagged")
        if COMMENT.sub(" ", "<!-- password in .env -->").strip():
            fails.append("comments are not being stripped before the read")
        if not any(p.search("credentials are in infra/.env.local") for p, _ in PATTERNS):
            fails.append("a credentials path is not caught")
        print("FAIL credential-pointers self-test - " + "; ".join(fails) if fails
              else "self-test OK: 5 mutations, each caught - the real line is found, a sign-in form is not")
        return 1 if fails else 0

    files, hits = [], []
    for g in GLOBS:
        files.extend(glob.glob(str(ROOT / g)))
    for f in sorted(set(files)):
        p = Path(f)
        try:
            txt = visible(p)
        except OSError:
            continue
        for pat, why in PATTERNS:
            for m in pat.finditer(txt):
                hits.append((p.relative_to(ROOT).as_posix(), why, re.sub(r"\s+", " ", m.group(0))[:60]))

    print(f"pages read: {len(set(files))}")
    print(f"pages telling a reader where a secret lives: {len({h[0] for h in hits})}")
    for f, why, txt in hits[:12]:
        print(f"  {f[:40]:42} {why}: {txt!r}")
    if not hits:
        print("  none - no page names an account beside a password or points at a credentials file")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
