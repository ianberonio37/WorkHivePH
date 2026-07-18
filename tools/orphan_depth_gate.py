#!/usr/bin/env python3
"""
orphan_depth_gate.py — SEO/AEO/GEO Arc, Phase P1/P3 (the Crawl/index "0 orphans +
<=3 clicks" cell of the SEO scoreboard).

The sitemap validators prove every public URL EXISTS + is listed; this gate proves
every public surface is REACHABLE by a crawler from the homepage in <=3 clicks and
that none is ORPHANED (no crawlable inbound link). Google discovers pages by
following <a href> from page to page; a page with no inbound anchor, or one buried
>3 hops deep, is crawled rarely or not at all — so it can't rank or be cited.

It reads the SCRIPT-STRIPPED DOM of each surface (exactly what GPTBot/ClaudeBot see,
and the initial-state DOM Googlebot indexes) — reusing landing_extractability_gate's
crawler-view model: in-DOM display:none links DO count; links injected by JS on a
click do NOT. The public surface list is catalog-derived (seo_technical_gate.indexable_pages)
so a new /learn article is covered automatically.

Checks (forward-only ratcheted, same convention as seo_technical_gate.py):
  orphans       a public surface with ZERO crawlable inbound <a href> from any other
                public surface (nothing links to it → effectively undiscoverable)
  click_depth   a LINKED public surface (inbound>=1) that is still NOT reachable from
                index.html within 3 clicks (unreachable, or depth 4+) — fails "<=3 clicks"

CLI:
    python tools/orphan_depth_gate.py            # ratcheted run (exit 1 on NEW drift)
    python tools/orphan_depth_gate.py --strict   # fail on ANY issue > 0
    python tools/orphan_depth_gate.py --update-baseline
    python tools/orphan_depth_gate.py --self-test
"""
from __future__ import annotations

import re
import sys
import json
import posixpath
from collections import deque
from pathlib import Path
from datetime import datetime, timezone

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from seo_technical_gate import indexable_pages  # noqa: E402  (canonical public-surface list)

BASELINE_PATH = ROOT / "orphan_depth_baseline.json"
REPORT_PATH = ROOT / "orphan_depth_report.json"
ROOT_SURFACE = "index.html"
MAX_DEPTH = 3

CHECK_ORDER = ["orphans", "click_depth"]

_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
_HREF_RE = re.compile(r'<a\b[^>]*\bhref\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def _read(rel: str) -> str:
    try:
        return (ROOT / rel).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _strip_scripts(html: str) -> str:
    """The HTML a non-JS crawler sees: <script> bodies removed, display:none kept."""
    return _SCRIPT_RE.sub("", html)


def _alias_map(surfaces: list[str]) -> dict[str, str]:
    """Map every URL form a link might use → its canonical surface path.

    "index.html"            → "", "index.html"
    "learn/index.html"      → "learn", "learn/index.html"
    "learn/<slug>/index.html" → "learn/<slug>", "learn/<slug>/index.html"
    "about/index.html"      → "about", "about/index.html"
    """
    m: dict[str, str] = {}
    for s in surfaces:
        if s == "index.html":
            keys = {"", "index.html"}
        elif s.endswith("/index.html"):
            base = s[: -len("/index.html")]
            keys = {base, base + "/index.html", s}
        else:
            keys = {s}
        for k in keys:
            m[k] = s
    return m


def _norm_href(href: str, source_surface: str) -> str | None:
    """Normalize an <a href> (relative to source_surface) to the alias space
    ('' | 'learn' | 'learn/<slug>' | 'about' | ...). Returns None for non-page or
    off-site links."""
    href = href.split("#")[0].split("?")[0].strip()
    if not href or href.lower().startswith(("mailto:", "tel:", "javascript:", "data:")):
        return None
    # absolute URL → keep only our own domain
    if re.match(r"^https?://", href, re.IGNORECASE):
        m = re.match(r"^https?://[^/]*workhiveph\.com(/.*)?$", href, re.IGNORECASE)
        if not m:
            return None
        href = m.group(1) or "/"
    # strip the LOCAL serving prefix so /workhive/learn/x and /learn/x both normalize
    href = re.sub(r"^/+", "/", href)
    href = re.sub(r"^/?workhive/", "/", href, flags=re.IGNORECASE)
    if href.startswith("/"):
        path = href.lstrip("/")
    else:
        src_dir = source_surface.rsplit("/", 1)[0] if "/" in source_surface else ""
        joined = posixpath.join(src_dir, href) if src_dir else href
        path = posixpath.normpath(joined)
        if path in (".", ""):
            path = ""
    return path.strip("/")


def build_graph(surfaces: list[str], pages_html: dict[str, str] | None = None):
    """Directed crawl graph over the public surfaces (script-stripped DOM)."""
    amap = _alias_map(surfaces)
    graph: dict[str, set[str]] = {s: set() for s in surfaces}
    inbound: dict[str, int] = {s: 0 for s in surfaces}
    for s in surfaces:
        html = pages_html[s] if pages_html is not None else _read(s)
        dom = _strip_scripts(html)
        for href in _HREF_RE.findall(dom):
            norm = _norm_href(href, s)
            if norm is None:
                continue
            tgt = amap.get(norm)
            if tgt and tgt != s:
                graph[s].add(tgt)
    for s in surfaces:
        for t in graph[s]:
            inbound[t] += 1
    return graph, inbound


def bfs_depths(graph: dict[str, set[str]], root: str = ROOT_SURFACE) -> dict[str, int]:
    depth = {root: 0}
    q = deque([root])
    while q:
        u = q.popleft()
        for v in graph.get(u, ()):
            if v not in depth:
                depth[v] = depth[u] + 1
                q.append(v)
    return depth


def run_checks(surfaces: list[str] | None = None, pages_html: dict[str, str] | None = None) -> dict:
    if surfaces is None:
        surfaces = indexable_pages()
    checks = {k: {"count": 0, "issues": []} for k in CHECK_ORDER}

    graph, inbound = build_graph(surfaces, pages_html)
    depth = bfs_depths(graph, ROOT_SURFACE)

    for s in surfaces:
        if s == ROOT_SURFACE:
            continue
        if inbound[s] == 0:
            checks["orphans"]["issues"].append(
                {"page": s, "reason": f"{s} has ZERO crawlable inbound <a href> from any public page (orphan)"}
            )
        else:
            d = depth.get(s)
            if d is None:
                checks["click_depth"]["issues"].append(
                    {"page": s, "reason": f"{s} is linked but UNREACHABLE from {ROOT_SURFACE} (disconnected from the homepage crawl)"}
                )
            elif d > MAX_DEPTH:
                checks["click_depth"]["issues"].append(
                    {"page": s, "reason": f"{s} is {d} clicks from {ROOT_SURFACE} (> {MAX_DEPTH})"}
                )

    for k in CHECK_ORDER:
        checks[k]["count"] = len(checks[k]["issues"])
    return checks


def _load_baseline() -> dict:
    if BASELINE_PATH.exists():
        try:
            return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def evaluate(strict: bool = False, update_baseline: bool = False) -> tuple[int, dict]:
    checks = run_checks()
    prior = _load_baseline().get("checks", {})
    rows, fails, new_base = [], [], {}
    for name in CHECK_ORDER:
        cur = checks[name]["count"]
        base = prior.get(name, cur)
        ratcheted = min(base, cur)
        new_base[name] = ratcheted
        failing = (cur > 0) if strict else (cur > ratcheted)
        if failing:
            fails.append(name)
        rows.append({"check": name, "current": cur, "baseline": 0 if strict else ratcheted,
                     "status": "FAIL" if failing else ("OK" if cur == 0 else "HELD"),
                     "issues": checks[name]["issues"]})
    total = sum(checks[n]["count"] for n in CHECK_ORDER)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "mode": "strict" if strict else "ratchet", "total_issues": total,
              "max_depth": MAX_DEPTH, "failed_checks": fails, "checks": rows}
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if not strict:
        est = _load_baseline().get("established")
        BASELINE_PATH.write_text(json.dumps({
            "checks": new_base,
            "established": est or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2), encoding="utf-8")
    elif update_baseline:
        BASELINE_PATH.write_text(json.dumps({
            "checks": {n: checks[n]["count"] for n in CHECK_ORDER},
            "established": _load_baseline().get("established")
                or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2), encoding="utf-8")
    return (1 if fails else 0), report


def _print(report: dict) -> None:
    def c(code, s):
        return f"\033[{code}m{s}\033[0m"

    print(c("96", "\n  ORPHAN / CLICK-DEPTH GATE (P1) · " + report["mode"]))
    print("  " + "=" * 62)
    print(c("90", f"    root={ROOT_SURFACE} · max click-depth={report.get('max_depth')}"))
    print("  " + "-" * 62)
    for r in report["checks"]:
        col = "91" if r["status"] == "FAIL" else ("92" if r["status"] == "OK" else "93")
        print(f"    {c(col, r['status'].ljust(4))} {r['check']:<12} current={r['current']}  baseline={r['baseline']}")
        for i in r["issues"][:6]:
            print(c("90", f"          - {i['reason']}"))
        if len(r["issues"]) > 6:
            print(c("90", f"          … +{len(r['issues']) - 6} more"))
    n = len(report["failed_checks"])
    print(c("92", "\n  PASS — no check over baseline.\n") if n == 0
          else c("91", f"\n  FAIL — {n} check(s) over baseline: {', '.join(report['failed_checks'])}\n"))


def self_test() -> int:
    fails = 0

    def ck(cond, msg):
        nonlocal fails
        print(("  \033[92mPASS\033[0m  " if cond else "  \033[91mFAIL\033[0m  ") + msg)
        if not cond:
            fails += 1

    print("\n\033[1morphan_depth_gate.py --self-test\033[0m")
    print("=" * 60)

    # href normalization (live-state-independent)
    ck(_norm_href("/learn/oee/", "index.html") == "learn/oee", "absolute /learn/oee/ → learn/oee")
    ck(_norm_href("../oee/", "learn/mtbf/index.html") == "learn/oee", "relative ../oee/ from an article → learn/oee")
    ck(_norm_href("/workhive/learn/oee/", "index.html") == "learn/oee", "local /workhive/ prefix stripped")
    ck(_norm_href("https://workhiveph.com/about/", "index.html") == "about", "own-domain absolute URL → about")
    ck(_norm_href("https://reddit.com/x", "index.html") is None, "off-site URL → None")
    ck(_norm_href("mailto:a@b.com", "index.html") is None, "mailto → None")
    ck(_norm_href("/", "learn/oee/index.html") == "", "root / → '' (home)")

    surfaces = ["index.html", "learn/index.html",
                "learn/a/index.html", "learn/b/index.html", "learn/c/index.html",
                "about/index.html"]

    # GOOD graph: home → hub + about; hub → a,b,c. All reachable depth<=2, all have inbound.
    good = {
        "index.html": '<a href="/learn/">Guides</a> <a href="/about/">About</a>',
        "learn/index.html": '<a href="/learn/a/">A</a> <a href="/learn/b/">B</a> <a href="/learn/c/">C</a>',
        "learn/a/index.html": '<a href="../b/">B</a>',
        "learn/b/index.html": '<a href="../a/">A</a>',
        "learn/c/index.html": '<a href="/learn/">back</a>',
        "about/index.html": '<a href="/">home</a>',
    }
    g = run_checks(surfaces, good)
    ck(g["orphans"]["count"] == 0, "all-linked graph → orphans 0")
    ck(g["click_depth"]["count"] == 0, "all reachable <=3 clicks → click_depth 0")

    # BAD graph: 'c' has no inbound (orphan); 'b' reachable only via a 4-hop chain from home.
    # home → a (1) → x? build a depth-4 chain: home→learn hub(1)→a(2)→b(3) is depth3 (ok).
    # Make a long chain: home→about(1)→ (about links a) a(2)→ a links b → b(3). still <=3.
    # Force depth 4: home→about(1)→a(2)→? Need 4. Use: home→about(1); about→a(2); a→b(3); b→? .
    # Instead: 'b' linked ONLY by 'c-chain' that itself sits at depth 3 → b at depth 4.
    bad = {
        "index.html": '<a href="/about/">About</a>',          # home → about (depth1)
        "learn/index.html": '<a href="/learn/a/">A</a>',       # hub unreachable (home doesn't link hub)
        "about/index.html": '<a href="/learn/a/">A</a>',       # about → a (depth2)
        "learn/a/index.html": '<a href="/learn/index.html">hub</a>',  # a → hub (depth3)
        "learn/b/index.html": '<a href="/learn/a/">A</a>',     # b → a ; b linked? who links b?
        "learn/c/index.html": '<a href="/learn/b/">B</a>',     # c → b (gives b inbound, but c is orphan)
    }
    b = run_checks(surfaces, bad)
    # c: inbound 0 (nobody links c) → orphan. b: inbound 1 (from c) but c unreachable → b unreachable.
    ck("learn/c/index.html" in [i["page"] for i in b["orphans"]["issues"]], "page with no inbound → flagged orphan")
    ck(b["orphans"]["count"] == 1, "exactly one orphan (c)")
    ck(any(i["page"] == "learn/b/index.html" for i in b["click_depth"]["issues"]),
       "linked-but-unreachable page → flagged click_depth")
    ck("index.html" not in [i["page"] for i in b["orphans"]["issues"]], "root never flagged as orphan")

    # Live surface list is catalog-derived
    try:
        live = indexable_pages()
        ck(len(live) >= 30 and "index.html" in live, f"surface list catalog-derived ({len(live)} pages)")
    except Exception as e:
        ck(False, f"indexable_pages() callable — {e}")

    print("=" * 60)
    print("\033[92m  self-test PASS\033[0m\n" if not fails else f"\033[91m  self-test FAIL — {fails}\033[0m\n")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    rc, report = evaluate(strict="--strict" in argv, update_baseline="--update-baseline" in argv)
    _print(report)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
