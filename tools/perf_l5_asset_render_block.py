#!/usr/bin/env python3
"""perf_l5_asset_render_block.py — Arc L · L5-ASSET: the S (Speed) lens for shared
client assets — does loading the asset BLOCK first paint?

The L0 miner scores asset E (weight) but leaves asset S `pending` (only cdn-tailwind's
render-block was scored). This merges a real, static, per-asset S verdict into the
asset:: cells of perf_scale_results.json by scanning every top-level page for HOW the
asset is loaded:

  · A `<script src=...>` WITHOUT defer/async, placed in <head> (before </head>), BLOCKS
    HTML parsing → delays first paint = render-blocking (S fix). The SAME script with
    `defer`/`async`, or placed at end-of-<body> (after the visible content is parsed),
    does not block first paint (S pass).
  · A `<link rel=stylesheet>` is render-blocking BY NATURE (browsers block paint on
    CSS to avoid an unstyled flash) — that is CORRECT for the design system, so a small
    (<= a generous KB budget) necessary stylesheet PASSES (blocking is intended, tiny).
  · A heavy page bundle (engineering-design.js, 2.2 MB) is the L1-hot weight phase's
    concern (E lens), not render-block — left as the miner set it.

Verdict per asset = PASS iff it never blocks first paint on any page; FIX iff a JS asset
loads sync-in-<head> on >=1 page (the offending pages are named — a real S fix).

USAGE: python tools/perf_l5_asset_render_block.py            # score + merge
       python tools/perf_l5_asset_render_block.py --dry      # score + report, no write
"""
from __future__ import annotations
import json, os, re, sys, glob

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "perf_scale_results.json")
DRY = "--dry" in sys.argv
CSS_BLOCK_OK_KB = 50   # a necessary stylesheet under this is acceptable head-blocking (intended, tiny)

# heavy page bundles are the WEIGHT phase's concern (E), not render-block — skip their S here.
SKIP_S = {"engineering-design.js"}


def pages():
    return [p for p in glob.glob(os.path.join(ROOT, "*.html"))
            if not re.search(r"-(test|backup)\.html$|\.backup", os.path.basename(p))]


def head_end(html: str) -> int:
    m = re.search(r"</head>", html, re.IGNORECASE)
    return m.start() if m else len(html)


def asset_size_kb(name: str) -> float:
    p = os.path.join(ROOT, name)
    return (os.path.getsize(p) / 1024.0) if os.path.isfile(p) else 0.0


def scan_js(asset: str):
    """Return (used_pages, blocking_pages) for a JS asset across all pages.
    blocking = a <script src=asset> WITHOUT defer/async located before </head>."""
    used, blocking = [], []
    # match a script tag referencing the asset, capture its full tag + position
    tag_re = re.compile(r"<script\b[^>]*\bsrc\s*=\s*[\"']([^\"']*?)" + re.escape(asset) + r"[\"'][^>]*>", re.IGNORECASE)
    for pg in pages():
        try:
            html = open(pg, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        he = head_end(html)
        page_used = False
        page_block = False
        for m in tag_re.finditer(html):
            # only treat as THIS asset if the captured prefix is empty or a path sep (avoid foo-utils.js matching utils.js)
            prefix = m.group(1)
            if prefix and not prefix.endswith("/"):
                continue
            page_used = True
            tag = m.group(0)
            deferred = bool(re.search(r"\b(defer|async)\b", tag, re.IGNORECASE))
            if not deferred and m.start() < he:
                page_block = True
        if page_used:
            used.append(os.path.basename(pg))
            if page_block:
                blocking.append(os.path.basename(pg))
    return used, blocking


def main():
    results = json.load(open(RESULTS, encoding="utf-8"))
    surf = results["surfaces"]

    rows = []
    for k, s in surf.items():
        if not k.startswith("asset::"):
            continue
        S = s.get("lenses", {}).get("S")
        if not S or not S.get("applicable"):
            continue
        name = k.split("::", 1)[1]
        if name in SKIP_S:
            continue
        if name == "cdn-tailwind":
            continue   # the miner already scored this render-block surface (sync CDN <head> script)
        is_css = name.endswith(".css")
        if is_css:
            kb = asset_size_kb(name)
            if kb <= CSS_BLOCK_OK_KB:
                S["status"] = "pass"
                S["measured"] = f"{kb:.0f}KB stylesheet — render-blocking BY NATURE (correct: blocks paint to avoid FOUC), under {CSS_BLOCK_OK_KB}KB"
                S["why"] = "a small necessary design-system stylesheet is intended to block first paint (prevents unstyled flash) — not a Speed defect"
                rows.append((name, "pass", "css-ok", []))
            else:
                S["status"] = "fix"
                S["measured"] = f"{kb:.0f}KB stylesheet — over {CSS_BLOCK_OK_KB}KB render-blocking; split critical CSS"
                S["why"] = "a large render-blocking stylesheet delays first paint beyond the necessary-CSS budget"
                rows.append((name, "fix", "css-heavy", []))
            continue
        # JS asset
        used, blocking = scan_js(name)
        if not used:
            rows.append((name, S.get("status", "pending"), "not-found", []))
            continue
        if blocking:
            S["status"] = "fix"
            S["measured"] = f"render-blocking (sync <head>, no defer) on {len(blocking)}/{len(used)} pages: {', '.join(blocking[:6])}{'…' if len(blocking) > 6 else ''}"
            S["why"] = "a sync <script> in <head> without defer/async blocks HTML parsing → delays first paint on the named pages; FIX = move to end-of-<body> or add defer (verify load-order deps first)"
            rows.append((name, "fix", f"{len(blocking)}/{len(used)} blocking", blocking))
        else:
            S["status"] = "pass"
            S["measured"] = f"non-render-blocking on all {len(used)} pages (defer/async or end-of-<body>)"
            S["why"] = "loaded after first paint everywhere (deferred or end-of-body) → does not block render (S Speed met for the shared asset)"
            rows.append((name, "pass", f"{len(used)} pages clean", []))

    # recompute aggregates
    for lens in ("S", "E", "R", "B"):
        p = d = pend = 0
        for s in surf.values():
            c = s.get("lenses", {}).get(lens)
            if not c or not c.get("applicable"):
                continue
            d += 1
            if c["status"] == "pass":
                p += 1
            elif c["status"] == "pending":
                pend += 1
        results["lens_pass"][lens] = p
        results["lens_pending"][lens] = pend
        results["lens_pct"][lens] = round(1000 * p / d) / 10 if d else 0

    if not DRY:
        json.dump(results, open(RESULTS, "w", encoding="utf-8"), indent=2)

    print("=" * 64)
    print("ARC L — L5-ASSET render-block (S lens, static per-asset)")
    print("=" * 64)
    for name, st, note, blk in rows:
        flag = "PASS" if st == "pass" else ("FIX " if st == "fix" else "----")
        print(f"  [{flag}] {name:26} {note}")
    print(f"\n  -> lens_pass now: S={results['lens_pass']['S']} E={results['lens_pass']['E']} R={results['lens_pass']['R']} B={results['lens_pass']['B']}")
    print(f"  -> S = {results['lens_pass']['S']}/{sum(1 for s in surf.values() if s['lenses'].get('S',{}).get('applicable'))} = {results['lens_pct']['S']}% (floor 90)")
    print(f"  -> {'(dry, not written)' if DRY else 'merged asset:: S cells into perf_scale_results.json'}")


if __name__ == "__main__":
    sys.exit(main() or 0)
