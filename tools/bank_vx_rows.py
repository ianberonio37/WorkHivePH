#!/usr/bin/env python3
"""bank_vx_rows.py - close Wave VX's static search rows (VX-S, VX-A, VX-G, VX-X) on evidence read from the served files.

A VX search row asks one check of one public page (or one engine of one page cluster). Most of those checks are facts of
the files that ship: robots.txt, sitemap.xml, llms.txt, the page's head, its markdown twin. They are read here, after
the gate that owns the same fact passes, and a row is banked (locking, 60) only when its own check holds. A check that
needs a live measurement (cwv-390: Lighthouse at 390) is never banked here; it waits for its walk.

    python tools/bank_vx_rows.py --dry          # what would bank, and why each other row stays open
    python tools/bank_vx_rows.py                # bank them (writes through registry_io)
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bank_sl_walk as bsw  # noqa: E402
import freshness_trip as ft  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SITE = "https://workhiveph.com/"
# the gate that owns each family's facts; a row is never banked on a red gate
GATES = {
    "VX-S": [("tools/validate_calc_pages.py",), ("tools/freshness_trip.py", "--check")],
    "VX-A": [("tools/extractability_gate.py",), ("tools/validate_calc_pages.py",)],
    "VX-G": [("tools/validate_md_twins.py",), ("tools/content_grounding_gate.py",)],
    "VX-X": [("tools/freshness_trip.py", "--check")],
}


def _rd(p: Path) -> str:
    try:
        return io.open(p, encoding="utf-8").read()
    except OSError:
        return ""


def _url(page: str) -> str:
    return SITE + page.replace("index.html", "")


def _linked_from_elsewhere(page: str, pages: list[str]) -> bool:
    href = "/" + page.replace("index.html", "")
    for other in pages:
        if other != page and href in _rd(ROOT / other):
            return True
    return False


def check(fam: str, cell: dict, pub: list[str], ctx: dict) -> tuple[bool, str]:
    """(holds, what was read) for one cell."""
    if fam == "VX-X":
        cl_pages = cell["pages"]
        blocked = [b for b in cell["crawlers"] if ctx["robots_blocks"](b)]
        if blocked:
            return False, f"robots.txt disallows / for {', '.join(blocked)}"
        if ctx["parity"]:
            return False, f"robots.txt groups drop '*' rules: {ctx['parity']}"
        not_in_map = [p for p in cl_pages if _url(p) not in ctx["sitemap"]]
        if not_in_map:
            return False, f"{len(not_in_map)} page(s) of {cell['cluster']} not in sitemap.xml"
        return True, (f"robots.txt lets {', '.join(cell['crawlers'])} read all {len(cl_pages)} pages of {cell['cluster']} "
                      f"(every named group repeats the '*' rules), and sitemap.xml lists them")
    page = cell["page"]
    src = _rd(ROOT / page)
    chk = cell["check"]
    if chk == "title-meta":
        ok = bool(re.search(r"<title>[^<]{10,}", src) and re.search(r'<meta name="description" content="[^"]{50,}', src))
        return ok, "a title and a meta description of 50+ characters in the served head"
    if chk == "canonical":
        m = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', src)
        ok = bool(m) and m.group(1).rstrip("/") == _url(page).rstrip("/")
        return ok, f"canonical {m.group(1) if m else 'missing'} against {_url(page)}"
    if chk == "structured-data":
        ok = "application/ld+json" in src
        return ok, "a JSON-LD block in the served page"
    if chk == "internal-links":
        ok = _url(page) in ctx["sitemap"] and _linked_from_elsewhere(page, ctx["all_pages"])
        return ok, "listed in sitemap.xml and linked from another served page"
    if chk == "cwv-390":
        return False, "needs a Lighthouse run at 390 (walked, never read from the file)"
    if chk == "answer-first":
        ok = ("answer-first" in src) or (page.startswith("learn/") and ctx["extractability_ok"])
        return ok, "an answer-first block (class answer-first, or extractability_gate on a learn article)"
    if chk == "extractable-figure":
        ok = page.startswith(("learn/", "tools/")) and (ctx["extractability_ok"] if page.startswith("learn/") else ctx["calc_ok"])
        return ok, "a statistic an engine can lift (extractability_gate / validate_calc_pages)"
    if chk == "cited-source":
        ok = bool(re.search(r'<a[^>]+href="https?://(?!workhiveph\.com)[^"]+"', src)) or "citation" in src
        return ok, "an outbound cited source or a citation field in the page"
    if chk == "markdown-twin":
        ok = (ROOT / (page + ".md")).exists() and ctx["twins_ok"]
        return ok, f"{page}.md exists and validate_md_twins passes"
    if chk == "llms-txt-listed":
        ok = _url(page) in ctx["llms"] or page.replace("index.html", "") in ctx["llms"]
        return ok, "the page's URL is listed in llms.txt"
    return False, f"unknown check {chk}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    from registry_io import load_doc, save_doc
    import sublayer_inventory as si
    gate_ok = {}
    for fam, gates in GATES.items():
        res = [bsw._run_gate(str(ROOT / g[0]), *g[1:]) for g in gates]
        gate_ok[fam] = all(ok for ok, _ in res)
        print(f"  {fam} gates: " + " · ".join(f"{Path(g[0]).name} {'PASS' if ok else 'FAIL'}" for g, (ok, _) in zip(gates, res)))
    robots = _rd(ROOT / "robots.txt")

    groups, agents, rules = [], [], set()
    for line in robots.splitlines():
        line = line.split("#", 1)[0].strip()
        k, _, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            if rules:
                groups.append(([x.lower() for x in agents], rules))
                agents, rules = [], set()
            agents.append(v)
        elif k in ("allow", "disallow"):
            rules.add((k, v))
    if agents:
        groups.append(([x.lower() for x in agents], rules))

    def robots_blocks(bot: str) -> bool:
        """RFC 9309: the bot obeys its own named group, else '*'; blocked when that group disallows the root."""
        g = next((r for a_, r in groups if bot.lower() in a_), None) or next((r for a_, r in groups if "*" in a_), set())
        return ("disallow", "/") in g

    ctx = {"sitemap": _rd(ROOT / "sitemap.xml"), "llms": _rd(ROOT / "llms.txt"), "robots_blocks": robots_blocks,
           "parity": "; ".join(t["unit"] for t in ft.parity_trips()),
           "extractability_ok": gate_ok["VX-A"], "calc_ok": gate_ok["VX-S"], "twins_ok": gate_ok["VX-G"]}
    classes = si.page_classes()
    pub = classes["public"]
    ctx["all_pages"] = sorted({p for ps in classes.values() for p in ps})
    doc = load_doc()
    rows = [t for t in doc["trajectories"] if (t.get("vx") or {}).get("family") in GATES and t.get("status") == "specced"]
    banked, left = 0, []
    for t in rows:
        fam = t["vx"]["family"]
        if not gate_ok[fam]:
            left.append(f"{t['id']}: {fam} gate is red")
            continue
        ok, what = check(fam, t["vx"]["cell"], pub, ctx)
        if not ok:
            left.append(f"{t['id']} {t['title'][:70]}: {what}")
            continue
        basis = (f"[{date.today().isoformat()}] pct -> {{pct}}. Read from the files that ship (bank_vx_rows.py): {what}. "
                 f"Gates {', '.join(Path(g[0]).name for g in GATES[fam])} PASS.")
        if not a.dry:
            bsw._bank(doc, t["id"], basis, [Path(g[0]).stem for g in GATES[fam]])
        banked += 1
    if not a.dry and banked:
        save_doc(doc)
    for line in left[:40]:
        print("  left open: " + line)
    if len(left) > 40:
        print(f"  ... and {len(left) - 40} more left open")
    print(f"{'would bank' if a.dry else 'banked'} {banked} VX search row(s); {len(left)} left open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
