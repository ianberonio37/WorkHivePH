#!/usr/bin/env python3
"""prove_regression_cover.py — W3-AR layer CI: does anything catch this page's regressions before a person does?

Eighteen pages carry a row asking exactly that, and it is the one question in the wave that needs no browser
and no database: **a page is covered when some registered gate or test names it.** The evidence lives in
files — `run_platform_checks.py`, the Playwright specs, the prover scripts — so it can be read directly.

★NAMING A PAGE IS NOT THE SAME AS EXERCISING IT, and this gate is careful about the difference. A page
mentioned only in a comment, or only in a roster the gate iterates without asserting anything about it, is
not covered. So a mention counts only when it appears in a **registered** gate's script or in a test file,
and every mention is reported with the file that carries it — a claim of cover a person can go and check
rather than take on faith.

  python tools/prove_regression_cover.py
  python tools/prove_regression_cover.py --json .tmp/regression_cover.json
  python tools/prove_regression_cover.py --self-test
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"
MARK = "catch this page's regressions"

# where a page can be exercised: the gate registry, the provers it runs, and the test suites
SEARCH_GLOBS = [
    "run_platform_checks.py",
    "tools/*.py", "tools/*.mjs", "tools/*.js",
    "tests/**/*.spec.*", "tests/**/*.test.*", "e2e/**/*.*", "playwright/**/*.*",
]
SKIP = ("node_modules", ".tmp", ".emoji_bak", "seo_assets")


def rows() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [t for t in reg["trajectories"] if t.get("wave") == "W3-AR" and MARK in (t.get("title") or "")]


def corpus() -> dict:
    """Every file that could exercise a page, read once."""
    out = {}
    for pat in SEARCH_GLOBS:
        for f in glob.glob(str(ROOT / pat), recursive=True):
            p = Path(f)
            if any(s in p.as_posix() for s in SKIP) or not p.is_file():
                continue
            try:
                out[p.relative_to(ROOT).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return out


def registered_gate_scripts() -> set:
    """Only the scripts run_platform_checks actually runs - an unregistered prover catches nothing."""
    src = (ROOT / "run_platform_checks.py").read_text(encoding="utf-8", errors="replace")
    out = set()
    for m in re.finditer(r'"script":\s*os\.path\.join\(([^)]*)\)', src):
        parts = [p.strip().strip('"').strip("'") for p in m.group(1).split(",")]
        out.add(os.path.join(*parts).replace("\\", "/"))
    return out


def strip_comments(s: str, py: bool) -> str:
    """A page named only in a comment is not exercised by anything."""
    if py:
        return re.sub(r"(?m)^\s*#.*$", " ", re.sub(r'"""(?:.|\n)*?"""', " ", s))
    return re.sub(r"(?m)^\s*//.*$", " ", re.sub(r"/\*(?:.|\n)*?\*/", " ", s))


def main() -> int:
    if "--self-test" in sys.argv:
        fails = []
        if strip_comments("# page.html\nx = 'a.html'", True).count("page.html"):
            fails.append("a python comment is not being stripped")
        if strip_comments("// page.html\nconst x = 'a.html'", False).count("page.html"):
            fails.append("a js comment is not being stripped")
        if not registered_gate_scripts():
            fails.append("no registered gate scripts could be read")
        if not rows():
            fails.append("no W3-AR regression-cover rows found")
        print("FAIL regression-cover self-test - " + "; ".join(fails) if fails
              else f"self-test OK: comments stripped both ways, {len(registered_gate_scripts())} registered "
                   f"gate script(s), {len(rows())} row(s) to answer")
        return 1 if fails else 0

    files = corpus()
    gates = registered_gate_scripts()
    out, covered, bare = [], 0, []
    for t in rows():
        page = (t.get("pages") or [""])[0]
        if not page:
            continue
        hits = []
        for rel, body in files.items():
            if page not in body:
                continue
            clean = strip_comments(body, rel.endswith(".py"))
            if page not in clean:
                continue                                   # named only in a comment
            hits.append(rel)
        gated = [h for h in hits if h in gates or h == "run_platform_checks.py"
                 or "/tests/" in h or h.startswith("tests/")]
        rec = {"id": t["id"], "page": page, "named_in": hits[:6],
               "exercised_by": gated[:4],
               "verdict": "ok" if gated else "BAD",
               "line": (f"exercised by {len(gated)} registered gate/test file(s): {', '.join(gated[:3])}"
                        if gated else
                        (f"named in {len(hits)} file(s) but none is a registered gate or a test - "
                         f"{', '.join(hits[:3])}" if hits else
                         "no registered gate, prover or test names this page at all"))}
        out.append(rec)
        covered += 1 if gated else 0
        if not gated:
            bare.append(page)

    print(f"pages asked whether anything catches their regressions: {len(out)}")
    print(f"  exercised by a registered gate or test: {covered}")
    print(f"  named by nothing that runs:             {len(out) - covered}")
    for r in out:
        print(f"  {'ok ' if r['verdict'] == 'ok' else 'BAD'} {r['page'][:36]:38} {r['line'][:96]}")

    if "--json" in sys.argv:
        dest = sys.argv[sys.argv.index("--json") + 1]
        Path(dest).parent.mkdir(exist_ok=True)
        Path(dest).write_text(json.dumps({"results": out}, indent=1), encoding="utf-8")
        print(f"\n  {dest}")
    return 1 if bare else 0


if __name__ == "__main__":
    raise SystemExit(main())
