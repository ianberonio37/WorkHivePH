#!/usr/bin/env python3
"""validate_accessor_load_order.py — the LOCK for the "accessor called before utils.js" page-killer.

THE BUG (measured live, Arc-K DAY1-4, 2026-07-22): the storage-SSOT big-bang sweep converted
dayplanner.html's `let WORKER_NAME = whWorker()` in an inline <script> block at L459 — but
`<script src="utils.js">` (which DEFINES whWorker) loads at L1710. At document-order execution the
bare `whWorker()` threw `ReferenceError`, WORKER_NAME never initialized, the init IIFE threw, and
the page stuck on "Loading day plan…" FOR EVERY USER (shipped broken). hive.html had the same call
inside try{} — not fatal, but its supervisor CLS paint-hint was silently dead every load.

THE RULE (deterministic, offline, forward-only): a utils.js-defined accessor (whWorker / whHiveId /
whWorkerName …) called in an inline script ABOVE the `<script src="utils.js">` tag must be
typeof-guarded — `(typeof whWorker === 'function' ? whWorker() : <fallback>)` — because it runs
before the definition. An unguarded early call is a latent ReferenceError.

  python tools/validate_accessor_load_order.py            # check (forward ratchet)
  python tools/validate_accessor_load_order.py --update-baseline
  python tools/validate_accessor_load_order.py --self-test
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "accessor_load_order_baseline.json"

# Accessors DEFINED in utils.js that pages call at init. A call to one of these above the utils.js
# <script> tag is the ReferenceError trap. (Add here if utils.js grows more early-called globals.)
ACCESSORS = ["whWorker", "whHiveId", "whWorkerName", "whHiveName"]
CALL_RE = re.compile(r"\b(" + "|".join(ACCESSORS) + r")\s*\(")
UTILS_TAG_RE = re.compile(r"<script[^>]*\bsrc\s*=\s*['\"][^'\"]*utils\.js", re.I)
COMMENT_LEAD = re.compile(r"^\s*(//|\*|<!--)")


def scan(repo: Path) -> list[dict]:
    """Unguarded accessor calls on code lines ABOVE the utils.js tag. [{file,line,accessor,text}]."""
    out: list[dict] = []
    for f in sorted(repo.glob("*.html")):
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        utils_line = next((i for i, ln in enumerate(lines) if UTILS_TAG_RE.search(ln)), None)
        if utils_line is None:
            continue                       # page doesn't load utils.js — different concern
        for i, ln in enumerate(lines):
            if i >= utils_line:
                break
            if COMMENT_LEAD.match(ln):
                continue
            m = CALL_RE.search(ln)
            if not m:
                continue
            # typeof-guarded on the same line = safe
            if re.search(r"typeof\s+" + re.escape(m.group(1)), ln):
                continue
            out.append({"file": f.name, "line": i + 1, "accessor": m.group(1),
                        "utils_line": utils_line + 1, "text": ln.strip()[:90]})
    return out


def self_test() -> int:
    fails = []
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / "bad.html").write_text(
            "<script>\n"
            "let W = whWorker();\n"                                     # L2 — UNGUARDED above utils
            "let H = (typeof whHiveId === 'function' ? whHiveId() : '');\n"  # guarded → safe
            "// whWorker() in a comment\n"                              # comment → skip
            "</script>\n"
            "<script src='utils.js'></script>\n"
            "<script>let late = whWorker();</script>\n",               # AFTER utils → safe
            encoding="utf-8")
        (repo / "nolib.html").write_text("<script>let W = whWorker();</script>\n", encoding="utf-8")  # no utils tag → skip
        f = scan(repo)
        accs = [x["accessor"] for x in f]
        if not any(x["file"] == "bad.html" and x["line"] == 2 for x in f):
            fails.append(f"unguarded whWorker above utils must flag: {f}")
        if any("whHiveId" == a for a in accs):
            fails.append("typeof-guarded call must NOT flag")
        if len(f) != 1:
            fails.append(f"exactly 1 finding expected (comment/after-utils/no-lib all skipped), got {len(f)}: {f}")
    if fails:
        print("FAIL validate_accessor_load_order self-test:")
        for x in fails:
            print("  - " + x)
        return 1
    print("PASS validate_accessor_load_order self-test (unguarded-above-utils · typeof-safe · comment · after-utils · no-lib)")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        return self_test()
    findings = scan(ROOT)
    print(f"accessor-load-order: {len(findings)} unguarded accessor call(s) above the utils.js tag")
    for x in findings:
        print(f"  ✗ {x['file']}:{x['line']}  {x['accessor']}() (utils.js at L{x['utils_line']}) "
              f"→ ReferenceError → guard with (typeof {x['accessor']}==='function'?…:fallback)  «{x['text']}»")
    if "--update-baseline" in argv:
        BASELINE.write_text(json.dumps({"count": len(findings),
                                        "sites": [f"{x['file']}:{x['line']}" for x in findings]}, indent=2),
                            encoding="utf-8")
        print(f"baseline banked: count={len(findings)}")
        return 0
    base = json.loads(BASELINE.read_text(encoding="utf-8")).get("count", 0) if BASELINE.exists() else 0
    if len(findings) > base:
        print(f"FAIL accessor-load-order: {len(findings)} > baseline {base} (a page will ReferenceError at init)")
        return 1
    print(f"PASS accessor-load-order: {len(findings)} <= baseline {base} (ratchet held)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
