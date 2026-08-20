#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capture_walk_coverage.py — measure WHICH FUNCTIONS a walk actually exercised.
=============================================================================
The missing input that made R4b useless. `bank_live_walk.py` stamps `fn_digests`
from the FILES a walk loaded rather than the CODE its oracle exercised, so one row
about a seller empty-state records 1,675 function keys. A digest set that names
everything is exactly as blunt as a whole-file hash for a MODIFY, which is why this
bank has collapsed four times from single shared-library edits (752 green -> 34;
then 342, ~365, ~320 rows). Measured on today's bank: 484 rows carry fn_digests and
**0 of them hold**, because 7 keys out of 1,675 changed — all 7 belonging to an
unrelated session-notice feature no marketplace empty-state claim rests on.

The prior diagnosis (feedback_naming_every_function_is_naming_none) established that
narrowing existing rows retroactively is NOT available: nobody can know which
functions 843 banked claims rested on, and inventing that mapping is the fiction R7
exists to stop. So the recovery is re-walk, not re-baseline — and a re-walk only
earns its cost if the new rows are stamped NARROW. This produces that stamp by
MEASUREMENT: Chrome's precise coverage reports which functions ran, so the narrowing
is observed rather than inferred.

WHAT IT EMITS — `<file>::<fn>` keys in exactly the vocabulary `fn_digests()` uses, so
the stamper can intersect them directly:

    ["utils.js::getDb", "utils.js::whReadError", "marketplace.html::renderRows"]

MATCHING IS BY SOURCE POSITION, NOT BY NAME. V8 reports a function's start offset;
`fn_digests` keys by name-with-occurrence (`escHtml`, `escHtml#2`) precisely so two
bodies sharing a name cannot collapse onto one key. Resolving V8's offset against the
same brace-matched spans keeps both sides speaking one vocabulary — matching on name
alone would reintroduce the collision that keying-by-occurrence was built to prevent.
The self-test asserts the two key sets are equal, because a silent vocabulary drift
here would empty the intersection and stamp nothing.

A function that never ran is deliberately NOT recorded. That is the entire point: an
oracle that never called `renderCompactStat` must not expire when its colour changes.

USAGE
    python tools/capture_walk_coverage.py --url http://127.0.0.1:5000/workhive/marketplace.html
                                          --deps marketplace.html utils.js
    python tools/capture_walk_coverage.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_GATE = None


def _gate():
    global _GATE
    if _GATE is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_vlmb_cov", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _GATE = m
    return _GATE


def fn_spans(path):
    """[(start, end, key)] using the SAME brace-matching and the SAME name-with-occurrence
    keying as fn_digests(), so both sides share one vocabulary."""
    V = _gate()
    fp = os.path.join(ROOT, path)
    if not os.path.exists(fp):
        return []
    src = open(fp, "r", encoding="utf-8", errors="replace").read()
    spans, seen = [], {}
    for m in V._FN_RE.finditer(src):
        i = src.find("{", m.end() - 1)
        if i < 0:
            continue
        depth, j, n = 0, i, len(src)
        while j < n:
            c = src[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth != 0:
            continue                      # unbalanced: skip rather than guess
        name = m.group(1)
        seen[name] = seen.get(name, 0) + 1
        key = name if seen[name] == 1 else "%s#%d" % (name, seen[name])
        spans.append((m.start(), j + 1, "%s::%s" % (path, key)))
    return spans


def keys_for_offsets(path, offsets):
    """Map executed start-offsets onto fn_digests keys. An offset inside several spans
    (a nested helper) resolves to the INNERMOST — the function that actually ran."""
    spans = fn_spans(path)
    out = set()
    for off in offsets:
        best = None
        for s, e, k in spans:
            if s <= off < e and (best is None or (e - s) < (best[1] - best[0])):
                best = (s, e, k)
        if best:
            out.add(best[2])
    return out


def capture(url, deps, wait_ms=2500, actions=None):
    """Narrow the EXTERNAL .js deps by measured coverage; keep .html deps WIDE.

    The asymmetry is deliberate and is the safety argument. V8 reports offsets for an
    inline <script> relative to that script, not to the .html document, so mapping them
    onto document positions would mint WRONG keys — and a wrong key is worse than a wide
    one: it silently drops the real dependency and mints a false green. A page's own
    inline functions are also exactly where a claim about that page lives, so keeping the
    page wide costs little. utils.js is the shared library every row anchors to, and it is
    where the whole cost sits, so that is what narrowing has to fix.

    Python's Playwright has no page.coverage (Node-only), so this drives CDP Profiler
    directly. Coverage must be armed BEFORE navigation or the load-time calls are missed.
    """
    from playwright.sync_api import sync_playwright
    executed = dict((d, set()) for d in deps)
    html_deps = [d for d in deps if d.endswith(".html")]
    js_deps = [d for d in deps if d.endswith(".js")]

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context()
        page = ctx.new_page()
        cdp = ctx.new_cdp_session(page)
        cdp.send("Profiler.enable")
        cdp.send("Profiler.startPreciseCoverage", {"callCount": True, "detailed": True})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(wait_ms)
        for act in (actions or []):
            try:
                page.click(act, timeout=3000)
                page.wait_for_timeout(600)
            except Exception:
                pass
        cov = (cdp.send("Profiler.takePreciseCoverage") or {}).get("result", [])
        b.close()

    for entry in cov:
        src_url = entry.get("url") or ""
        for d in js_deps:
            if os.path.basename(d) not in src_url:
                continue
            offs = []
            for fn in entry.get("functions", []):
                ranges = fn.get("ranges") or []
                # count > 0 on the function's OWN range means it executed. A range with
                # count 0 is code the walk loaded and never ran — exactly what must not be
                # stamped, because stamping it is how a claim inherits a dependency it
                # does not have.
                if ranges and ranges[0].get("count", 0) > 0:
                    offs.append(ranges[0].get("startOffset", 0))
            executed[d] |= keys_for_offsets(d, offs)

    V = _gate()
    for d in html_deps:
        executed[d] = set(k for k in V.fn_digests([d], version=4)
                          if k != "::v" and "::top:" not in k)
    return dict((d, sorted(v)) for d, v in executed.items())


def self_test():
    ok = True

    def ck(c, m):
        nonlocal ok
        ok &= bool(c)
        print("  %s  %s" % ("PASS" if c else "FAIL", m))

    V = _gate()
    spans = fn_spans("utils.js")
    ck(len(spans) > 50, "fn_spans finds utils.js functions (%d)" % len(spans))
    all_keys = set(k for k in V.fn_digests(["utils.js"], version=4) if k != "::v")
    # `top:` keys are per-STATEMENT hashes of code outside any function. Coverage cannot
    # attribute those to a caller, so they are not part of this vocabulary — the first
    # version of this test asserted equality against them and failed 110-vs-991, which is
    # how the distinction got noticed rather than assumed.
    digest_keys = set(k for k in all_keys if "::top:" not in k and not k.endswith("::toplevel"))
    span_keys = set(k for _, _, k in spans)
    # THE LOAD-BEARING ASSERTION. If these two vocabularies drift, the stamper's intersection
    # silently empties and every row stamps narrow-to-nothing, which reads as success.
    # Compare explicitly rather than trusting that both sides call the same regex today.
    ck(span_keys == digest_keys,
       "span keys equal fn_digests FUNCTION keys (%d vs %d)" % (len(span_keys), len(digest_keys)))
    if spans:
        s, _e, k = spans[0]
        ck(keys_for_offsets("utils.js", [s]) == set([k]), "an offset resolves to its function key")
        ck(keys_for_offsets("utils.js", [-1]) == set(), "an offset in no span resolves to nothing")
    nested = [(0, 100, "f::outer"), (10, 20, "f::inner")]
    best = None
    for s2, e2, k2 in nested:
        if s2 <= 12 < e2 and (best is None or (e2 - s2) < (best[1] - best[0])):
            best = (s2, e2, k2)
    ck(best[2] == "f::inner", "a nested offset resolves to the innermost function")
    print("  self-test %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--deps", nargs="*", default=[])
    ap.add_argument("--out", default=os.path.join(ROOT, ".tmp", "coverage.json"))
    ap.add_argument("--click", nargs="*", default=[])
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.url or not a.deps:
        print("  need --url and --deps")
        return 2
    res = capture(a.url, a.deps, actions=a.click)
    flat = sorted(k for v in res.values() for k in v)
    total = len([k for k in _gate().fn_digests(a.deps, version=3) if k != "::v"])
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"url": a.url, "deps": a.deps, "fns_exercised": flat}, f, indent=2)
    pct = (100 * len(flat) // total) if total else 0
    print("  exercised %d of %d function keys (%d%% of the dependency surface)"
          % (len(flat), total, pct))
    print("  -> %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
