"""
fix_learn_fab_path.py — Grounded Sweep (learn articles, prod-path leak).
========================================================================
The static learn/*/index.html pages load the feedback FAB with a hardcoded
TESTER-absolute path:  <script src="/workhive/wh-feedback-fab.js">.

That works in the local Flask tester (which serves JS only under /workhive/)
but 404s in PRODUCTION (workhiveph.com serves at root, with NO /workhive/
prefix). The "Local dev URL bridge" rewriter on these pages only rewrites
<a href> links — it does NOT touch <script src>/<link href> — so this leak
ships broken to prod (the FAB never loads).

Neither absolute path works in both environments (tester: /workhive/... = 200,
/... = 404; prod: the reverse). The robust fix is a DEPTH-AWARE RELATIVE path
to the site-root asset:

  learn/index.html            (hub, depth 1)  ->  ../wh-feedback-fab.js
  learn/<slug>/index.html     (article, d.2)  ->  ../../wh-feedback-fab.js

Relative resolves correctly in BOTH: /workhive/learn/.. + ../.. = /workhive/..
(tester 200) and /learn/.. + ../.. = /.. (prod 200).

Idempotent + re-runnable. Guarded forward by validate_prod_path_leak.py.

Usage:  python tools/fix_learn_fab_path.py [--check]
"""
from __future__ import annotations
import io, re, sys, glob, os
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LEAK = '/workhive/wh-feedback-fab.js'


def rel_prefix(rel_path: str) -> str:
    # depth = number of dir levels under repo root for this file's directory
    # learn/index.html -> ['learn','index.html'] -> dir depth 1 -> '../'
    # learn/slug/index.html -> dir depth 2 -> '../../'
    parts = Path(rel_path).parts
    depth = len(parts) - 1  # exclude the filename
    return '../' * depth


def main() -> int:
    check = "--check" in sys.argv
    # Repo-wide: the same leak shipped on learn/* AND about/, feedback/,
    # privacy-policy/, terms-of-service/ (any subdir index.html).
    targets = sorted(glob.glob(str(ROOT / "**" / "index.html"), recursive=True))
    changed = []
    for fp in targets:
        if "node_modules" in fp or "test-data-seeder" in fp:
            continue
        p = Path(fp)
        rel = os.path.relpath(fp, ROOT).replace("\\", "/")
        text = p.read_text(encoding="utf-8", errors="replace")
        if LEAK not in text:
            continue
        new_src = rel_prefix(rel) + 'wh-feedback-fab.js'
        new = text.replace(LEAK, new_src)
        if new != text:
            changed.append((rel, new_src))
            if not check:
                p.write_text(new, encoding="utf-8")

    verb = "WOULD fix" if check else "fixed"
    print(f"learn fab prod-path: {verb} {len(changed)} file(s).")
    for rel, src in changed:
        print(f"  {rel:<58s} -> {src}")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
