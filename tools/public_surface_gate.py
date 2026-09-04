#!/usr/bin/env python3
"""public_surface_gate.py — T1.3: the 114 public pages join a UX denominator.

WHY. The entire top-of-funnel (learn hub + 55 guides + 60 calculator pages) sat in NO UX
denominator: the 22-page bank roster is app surfaces, the link gate scanned root pages only,
and cta_gate checked in-body CTA presence — so the funnel could (and did) route every reader
to an email waitlist while claiming "no sign-up needed" about a gated page, under a green
board. Template-DEEP coverage is the two exemplars in prove_cta_activation.mjs (clicked live,
both viewports); this gate is the instance-CHEAP static lint of every page.

Checks per page (all four born from T1's measured findings):
  1. auth-doors    — both doors present: a ?signin=1 href AND a ?signup=1 href.
  2. no-waitlist   — zero href="/#join" (the retired primary; the honest updates block
                     lives on index itself, not as a funnel destination).
  3. claim-honesty — the "no sign-up needed" claim class is banned UNLESS scoped to the
                     embedded on-page tool ("on this page" / "embedded calculator" within
                     the same sentence). The pre-fix lie: that exact claim, attached to a
                     link into engineering-design.html — a page that REQUIRES identity.
  4. links-resolve — every site-relative href resolves on disk (the root link gate's roster
                     is root pages; nothing checked these 114 pages' own links until now).
  5. tables-scroll — (T2, 2026-08-24) every <table> sits inside a data-table-scroll wrapper.
                     Bare prose tables forced 171/134px whole-page pan at 390 (WCAG 1.4.10);
                     scrollWidth is a RENDERING fact no static lint can read, but the WRAPPER
                     is static — prevention here, cure = tools/wrap_public_tables.py, the live
                     reflow reading stays with the browser probes.

Writes public_surface_registry.json (the per-page report — the registry IS the receipt).
Ratchet: violations must be 0 (no baseline file: T1.0 fixed the whole surface, and a new
public page must be born compliant — a baseline would grandfather new lies).
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "public_surface_registry.json"

CHECK_NAMES = ["public_surface"]

GATED_HINT = re.compile(r"no sign-?up (?:needed|required)", re.I)
SCOPED_OK = re.compile(r"no sign-?up needed[^.]{0,80}?(on this page|embedded)", re.I)
HREF_RE = re.compile(r"""\bhref\s*=\s*["'](?P<h>[^"']+)["']""")


def pages() -> list[Path]:
    return ([ROOT / "learn" / "index.html"]
            + sorted((ROOT / "learn").glob("*/index.html"))
            + sorted((ROOT / "tools").glob("*/index.html")))


def resolve(page: Path, href: str) -> Path | None:
    """Site-relative/relative .html or directory hrefs -> disk path; None = out of scope."""
    h = href.split("#", 1)[0].split("?", 1)[0]
    if not h or h.startswith(("http://", "https://", "//", "mailto:", "tel:", "javascript:", "data:")):
        return None
    if h.startswith("/"):
        p = ROOT / h.lstrip("/")
    else:
        p = page.parent / h
    if h.endswith("/"):
        p = p / "index.html"
    if p.suffix not in (".html", ""):
        return None            # assets are the perf lane's subject, not this gate's
    if p.suffix == "":
        p = p / "index.html"
    return p


def lint(page: Path) -> dict:
    text = page.read_text(encoding="utf-8", errors="replace")
    v: list[str] = []

    if "signin=1" not in text:
        v.append("no sign-in door (?signin=1)")
    if "signup=1" not in text:
        v.append("no sign-up door (?signup=1)")
    if 'href="/#join"' in text:
        v.append('waitlist CTA survives (href="/#join")')

    # T3 (2026-08-25): the scoped exemption must verify its FACT. The T1 lint accepted any claim
    # scoped "on this page"/"embedded" — and my own T1 rewrite then asserted an "embedded
    # calculator" on 60 pages that contain ZERO <input> elements (worked-example landings).
    # An allow-pattern that trusts the WORD re-opens the exact lie it was built to ban.
    has_inputs = "<input" in text.lower()
    for m in GATED_HINT.finditer(text):
        window = text[m.start():m.start() + 120]
        if not SCOPED_OK.search(window):
            v.append(f'unscoped "no sign-up" claim: …{window[:60]}…')
        elif not has_inputs:
            v.append(f'claim scoped to an on-page/embedded tool but the page has NO <input>: …{window[:60]}…')

    broken = []
    for m in HREF_RE.finditer(text):
        p = resolve(page, m.group("h"))
        if p is not None and not p.exists():
            broken.append(m.group("h"))
    if broken:
        v.append(f"{len(broken)} unresolvable link(s): {broken[:3]}")

    bare_tables = sum(1 for m in re.finditer(r"<table\b", text, re.I)
                      if "data-table-scroll" not in text[max(0, m.start() - 220):m.start()])
    if bare_tables:
        v.append(f"{bare_tables} bare <table>(s) without a data-table-scroll wrapper "
                 "(forces whole-page horizontal pan at 390 — run tools/wrap_public_tables.py)")

    try:
        label = str(page.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        label = page.name   # out-of-tree page (self-test fixtures, resurrection copies)
    return {"page": label,
            "family": "learn" if "learn" in page.parts else "tools",
            "violations": v}


def main() -> int:
    rows = [lint(p) for p in pages()]
    bad = [r for r in rows if r["violations"]]
    REGISTRY.write_text(json.dumps({
        "generated": True, "pages": len(rows), "violations": sum(len(r["violations"]) for r in rows),
        "note": "T1.3 instance-cheap lint; template-deep = prove_cta_activation.mjs exemplars",
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print(f"public-surface: {len(rows)} pages · {len(bad)} with violations")
    for r in bad[:12]:
        for x in r["violations"]:
            print(f"  FAIL {r['page']}: {x}")
    if bad:
        return 1
    print("PASS public-surface — every funnel page carries both doors, no waitlist CTA, "
          "claims scoped, links resolve.")
    return 0


def self_test() -> int:
    """Prove each rule can FAIL (a check that passes on the corpus proves nothing until it can fail)."""
    import tempfile
    fails = []
    cases = {
        "no sign-in door": '<a href="/?signup=1">x</a>',
        "waitlist CTA": '<a href="/?signup=1">x</a><a href="/?signin=1">y</a><a href="/#join">z</a>',
        "unscoped claim": '<a href="/?signup=1">x</a><a href="/?signin=1">y</a><p>free, no sign-up needed for the tools.</p>',
        "unresolvable link": '<a href="/?signup=1">x</a><a href="/?signin=1">y</a><a href="/nonexistent-page-xyz.html">z</a>',
        "bare table": '<a href="/?signup=1">x</a><a href="/?signin=1">y</a><table><tr><td>w</td></tr></table>',
    }
    with tempfile.TemporaryDirectory() as td:
        for name, body in cases.items():
            f = Path(td) / "t" / "index.html"
            f.parent.mkdir(exist_ok=True)
            f.write_text(body, encoding="utf-8")
            # lint() resolves relative to the page; absolute hrefs resolve against ROOT (real).
            r = lint(f)
            if not r["violations"]:
                fails.append(f"case '{name}' should FAIL, got clean")
    ok = lint(pages()[0])   # the live hub must currently be clean (post-T1.0)
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print(f"PASS public_surface_gate self-test ({len(cases)} mutation cases redden; live hub violations={len(ok['violations'])})")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
