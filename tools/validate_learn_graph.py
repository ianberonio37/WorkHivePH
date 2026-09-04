#!/usr/bin/env python3
"""learn-graph — T152: the teaching cluster is navigable in both directions (2026-08-26).

53 articles only teach as a cluster if a reader can move through them. Two
different failures break that, and they are invisible to each other:

  AN ORPHAN   — an article no hub link reaches. It exists, it is indexed, a
                searcher can land on it, and nobody browsing the library will
                ever find it. Writing it was work that reaches nobody.
  A DEAD END  — an article that links onward to nothing. A reader who finishes it
                has to go back and start again, which is where a session ends.

Measured 2026-08-26: 53 articles, 53 reachable from the hub, ZERO orphans, ZERO
dead ends, and the hub links to nothing that does not exist. The graph is
complete in both directions; this gate is what keeps it that way, because adding
an article and forgetting the hub entry is a one-line omission nobody notices.

★A HUB LINK TO A MISSING ARTICLE IS ALSO CHECKED, because the reverse of an
orphan is a promise: a library index offering a guide that 404s is worse than not
listing it, and this cluster has been renamed before.

★ONWARD LINKS MUST GO TO OTHER LEARN ARTICLES, not merely somewhere. A page whose
only outbound link is a signup CTA is a dead end for a reader who came to learn,
however many links it technically has.

Usage: python tools/validate_learn_graph.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SLUG = re.compile(r"/learn/([a-z0-9\-]+)/|href=\"([a-z0-9\-]+)/\"|href=\"\.\./([a-z0-9\-]+)/\"")


def slugs_in(src: str) -> set:
    out = set()
    for m in SLUG.finditer(src):
        out.add(next(g for g in m.groups() if g))
    return out


def main() -> int:
    files = sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html")))
    articles = {Path(f).parent.name for f in files}
    hub_path = ROOT / "learn" / "index.html"
    if not articles or not hub_path.exists():
        print("SKIP learn-graph — learn cluster or its hub not found")
        return 0

    hub = io.open(hub_path, encoding="utf-8", errors="replace").read()
    hub_links = slugs_in(hub)

    orphans = sorted(articles - hub_links)
    ghosts = sorted(hub_links - articles - {"index"})

    dead_ends = []
    for f in files:
        name = Path(f).parent.name
        onward = slugs_in(io.open(f, encoding="utf-8", errors="replace").read()) - {name, "index"}
        if not (onward & articles):
            dead_ends.append(name)

    print(f"  articles {len(articles)} | reachable from hub {len(articles) - len(orphans)} | "
          f"with onward links {len(articles) - len(dead_ends)}")

    fails = []
    if orphans:
        fails.append(f"{len(orphans)} ORPHAN(S) - no hub link reaches them, so nobody browsing the "
                     f"library will find them: {', '.join(orphans[:6])}")
    if ghosts:
        fails.append(f"{len(ghosts)} hub link(s) to an article that does not exist - a library index "
                     f"offering a guide that 404s: {', '.join(ghosts[:6])}")
    if dead_ends:
        fails.append(f"{len(dead_ends)} DEAD END(S) - they link onward to no other learn article, so a "
                     f"reader who finishes has to go back and start again: {', '.join(dead_ends[:6])}")

    if fails:
        print("FAIL learn-graph:")
        for x in fails:
            print("    - " + x)
        return 1
    print(f"PASS learn-graph — all {len(articles)} articles are reachable from the hub, all link onward "
          f"to another article, and the hub promises nothing that is missing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
