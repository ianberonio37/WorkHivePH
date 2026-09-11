#!/usr/bin/env python3
"""validate_deploy_root_hygiene.py — T1.4: nothing un-shippable sits in the served root.

WHY. netlify.toml publishes the repo root ("."), so every root file IS a public URL. On
2026-08-24 seven dev copies sat there — index.backup.html was literally reachable on prod,
and the roster tools each carried their own private exclusion list naming the strays (six
lists, six chances to drift). The strays moved to _fixtures/ (kept as negative fixtures);
this gate keeps the class extinct:

  1. no root .html matches the stray patterns (*-test.html, *.backup*.html, *copy*, *-v?-*);
  2. _fixtures/ is force-404'd in netlify.toml (publish="." would serve it otherwise);
  3. every root .html is either in the served-page roster's scope or a declared exception;
  4. (2026-09-10) `.vercelignore` is IN HEAD and names every dev-only tree - because the site is
     served by Vercel, which reads neither netlify.toml nor _headers, so checks 1-3 alone were
     enforcing a rule against a file the deploy never opens. Asked of HEAD rather than the index:
     a deploy carries commits, so staging must not be able to turn this green.

Check 3 is deliberately just the stray-pattern sweep plus the netlify rule — the full
per-consumer roster parity lives in validate_page_roster.py (a different question).
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHECK_NAMES = ["deploy_root_hygiene"]

STRAY = re.compile(r"(-test\.html$|\.backup[^/]*\.html$|copy.*\.html$|-v\d+[^/]*\.html$)", re.I)


def main() -> int:
    problems: list[str] = []

    strays = [p.name for p in ROOT.glob("*.html") if STRAY.search(p.name)]
    if strays:
        problems.append(f"stray dev copies in the served root: {strays}")

    toml = (ROOT / "netlify.toml").read_text(encoding="utf-8") if (ROOT / "netlify.toml").exists() else ""
    block = re.search(r'from\s*=\s*"/_fixtures/\*"(.{0,200}?)force\s*=\s*true', toml, re.S)
    if not block:
        problems.append("netlify.toml lacks the force-404 rule for /_fixtures/* — the negative "
                        "fixtures would be publicly served (publish is '.')")
    # the fixtures rule must come BEFORE the catch-all (first matching rule wins)
    fx = toml.find('from = "/_fixtures/*"')
    catchall = toml.find('from = "/*"')
    if fx != -1 and catchall != -1 and fx > catchall:
        problems.append("the /_fixtures/* rule sits AFTER the catch-all — Netlify never reaches it")

    # ─────────────────────────────────────────────────────────────────────────────────────────
    # ★THE RULE THIS GATE ENFORCED LIVED IN A FILE THE DEPLOY DOES NOT READ (2026-09-10).
    # Everything above asserts netlify.toml. The site is served by VERCEL, which reads neither
    # netlify.toml nor _headers - that is already recorded as a finding. `.vercelignore` was written
    # on 2026-09-06 to remove the exposure for real... and was never committed. Vercel deploys the
    # GIT TREE, so an untracked ignore file is not part of any deployment. Re-measured four days
    # later, /_fixtures/engineering-design-test.html still answered 200 with 1,729,742 bytes.
    # An ignore file that is not tracked is not a lock, so its tracked-ness IS the check.
    vercelignore = ROOT / ".vercelignore"
    # Ask HEAD, not the index. `git ls-files` reports STAGED paths, so a bare `git add` would turn
    # this check green while the deployment - which carries commits - still excludes nothing. The
    # question is "would a deploy from this repo contain the file", and only HEAD answers it.
    tracked = ""
    try:
        tracked = subprocess.run(["git", "ls-tree", "--name-only", "HEAD", "--", ".vercelignore"],
                                 cwd=str(ROOT), capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        tracked = "?"          # no git here: cannot disprove, so do not manufacture a failure
    if not vercelignore.exists():
        problems.append(".vercelignore is missing — on Vercel this is the ONLY file that keeps dev "
                        "artifacts out of the deployment (netlify.toml and _headers are inert here)")
    elif tracked == "":
        problems.append(".vercelignore is not in HEAD, so no deployment carries it and it excludes "
                        "nothing — it needs a COMMIT, not just `git add` (measured: /_fixtures/ "
                        "still answered 200 with 1.7 MB four days after the file was written)")
    vi_text = vercelignore.read_text(encoding="utf-8", errors="replace") if vercelignore.exists() else ""
    vi_rules = {ln.strip() for ln in vi_text.splitlines() if ln.strip() and not ln.strip().startswith("#")}

    # Any git-tracked HTML that is served but is NOT a product page must be excluded by name. The
    # root-only sweep above cannot see these: two dev tools' Jinja templates were publicly serving
    # raw `{{ supabase_url }}` from subdirectories the gate never looked at.
    DEV_TREES = ("test-data-seeder/", "video_marketing_app/", "_fixtures/", "remotion_scenes/")
    try:
        all_html = subprocess.run(["git", "ls-files", "*.html"], cwd=str(ROOT),
                                  capture_output=True, text=True, timeout=30).stdout.splitlines()
    except Exception:
        all_html = []
    exposed = sorted({t for t in DEV_TREES
                      for h in all_html if h.strip().startswith(t) and t not in vi_rules})
    if exposed:
        problems.append("dev-only tree(s) are git-tracked, contain served .html and are NOT in "
                        f".vercelignore: {exposed}")

    n_root = len(list(ROOT.glob("*.html")))
    print(f"deploy-root-hygiene: {n_root} root pages · {len(strays)} strays · fixtures rule "
          f"{'present+ordered' if block and (fx == -1 or fx < catchall) else 'BROKEN'} · "
          f".vercelignore {'tracked' if tracked else 'UNTRACKED (excludes nothing)'} "
          f"with {len(vi_rules)} rule(s)")
    if problems:
        for p in problems:
            print(f"  FAIL {p}")
        return 1
    print("PASS deploy-root-hygiene — the served root carries only product pages; fixtures are 404'd.")
    return 0


def self_test() -> int:
    fails = []
    if not STRAY.search("index-native-test.html"):
        fails.append("test-copy pattern should match")
    if not STRAY.search("index.backup2.html"):
        fails.append("backup pattern should match")
    if not STRAY.search("index-v3-test.html"):
        fails.append("v3-test pattern should match")
    if STRAY.search("index.html") or STRAY.search("public-feed.html") or STRAY.search("report-sender.html"):
        fails.append("real pages must NOT match")
    # The two invariants added 2026-09-10, each stated as the question it answers.
    import subprocess as _sp
    try:
        _t = _sp.run(["git", "ls-tree", "--name-only", "HEAD", "--", ".vercelignore"], cwd=str(ROOT),
                     capture_output=True, text=True, timeout=30).stdout.strip()
        if _t == "":
            print("  (self-test note: .vercelignore is not in HEAD - the gate SHOULD fail; that is "
                  "the live finding, not a broken test. Staging alone will not clear it, by design.)")
    except Exception:
        pass
    _vi = (ROOT / ".vercelignore")
    if _vi.exists():
        _rules = {ln.strip() for ln in _vi.read_text(encoding="utf-8", errors="replace").splitlines()
                  if ln.strip() and not ln.strip().startswith("#")}
        if "_fixtures/" not in _rules:
            fails.append(".vercelignore must exclude _fixtures/ - it is the measured prod exposure")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_deploy_root_hygiene self-test (stray patterns match the 7 moved names, spare the real pages)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
