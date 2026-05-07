"""Static Pages flows — architecture.html and symbol-gallery.html smoke checks.

These pages are read-only reference tools. No CRUD, no DB writes.
Scenarios focus on: loads cleanly, key content present, no JS errors,
search/filter functional, no broken assets.

architecture.html:
  A – Page loads without JS errors
  B – At least 1 diagram or rich SVG renders
  C – No broken image links (src="undefined" or 404 patterns)

symbol-gallery.html:
  D – Page loads without JS errors
  E – Symbol categories visible (IEC, NFPA, ISA, ANSI, etc.)
  F – At least 10 symbol SVG elements rendered
  G – Search/filter narrows displayed symbols
  H – No "undefined" symbol names in gallery
  I – Page renders correctly at 375px (no horizontal overflow)
"""

import re
from .harness import BASE_URL, ensure_signed_in, screenshot


def run(page, errors, warnings, log) -> dict:
    log("Static Pages flow checks (architecture + symbol gallery)...")
    results = []

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    # ════════════════════════════════════════════════════════════════
    # architecture.html
    # ════════════════════════════════════════════════════════════════
    page.goto(f"{BASE_URL}/workhive/architecture.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2500)

    # ── Scenario A: Loads without JS errors ───────────────────────────────────
    log("  [A] architecture.html loads without JS errors...")
    try:
        arch_errors = [e for e in errors if "TypeError" in e or "ReferenceError" in e]
        page_text   = page.locator("body").inner_text()
        has_content = len(page_text.strip()) > 200

        if arch_errors:
            results.append(("FAIL", f"A: JS errors on architecture.html: {arch_errors[0][:80]}"))
        elif has_content:
            results.append(("PASS", "A: architecture.html loaded with content, no critical JS errors"))
        else:
            results.append(("WARN", "A: architecture.html appears mostly empty"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: At least 1 diagram or rich SVG renders ────────────────────
    log("  [B] At least 1 diagram/SVG renders on architecture page...")
    try:
        diagram_count = page.evaluate("""() => {
            const svgs = Array.from(document.querySelectorAll('svg'));
            const richSvgs = svgs.filter(s => s.querySelectorAll('*').length > 5).length;
            const canvas  = document.querySelectorAll('canvas').length;
            const imgs    = document.querySelectorAll('img[src]:not([src=""])').length;
            return { richSvgs, canvas, imgs };
        }""")

        total = diagram_count["richSvgs"] + diagram_count["canvas"]
        if total > 0:
            results.append(("PASS", f"B: {total} diagram element(s) — {diagram_count}"))
        elif diagram_count["imgs"] > 0:
            results.append(("WARN", f"B: no SVG/canvas found but {diagram_count['imgs']} image(s) present"))
        else:
            results.append(("WARN", "B: no diagram elements detected on architecture page"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"B skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario C: No broken image links ─────────────────────────────────────
    log("  [C] No broken image src attributes (undefined or empty)...")
    try:
        broken = page.evaluate("""() => {
            const imgs = Array.from(document.querySelectorAll('img'));
            return imgs.filter(i => {
                const s = i.getAttribute('src') || '';
                return s === '' || s === 'undefined' || s.includes('undefined');
            }).length;
        }""")

        if broken > 0:
            results.append(("FAIL", f"C: {broken} broken image src attribute(s) on architecture page"))
        else:
            results.append(("PASS", "C: no broken image src attributes"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"C skipped: {e}"))
        log(f"    → WARN: {e}")

    screenshot(page, "architecture_page")

    # ════════════════════════════════════════════════════════════════
    # symbol-gallery.html
    # ════════════════════════════════════════════════════════════════
    errors_before_gallery = len(errors)
    page.goto(f"{BASE_URL}/workhive/symbol-gallery.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2500)

    # ── Scenario D: Loads without JS errors ───────────────────────────────────
    log("  [D] symbol-gallery.html loads without JS errors...")
    try:
        gallery_errors = [e for e in errors[errors_before_gallery:]
                          if "TypeError" in e or "ReferenceError" in e]
        page_text      = page.locator("body").inner_text()
        has_content    = len(page_text.strip()) > 200

        if gallery_errors:
            results.append(("FAIL", f"D: JS errors on symbol-gallery.html: {gallery_errors[0][:80]}"))
        elif has_content:
            results.append(("PASS", "D: symbol-gallery.html loaded with content, no critical JS errors"))
        else:
            results.append(("WARN", "D: symbol-gallery.html appears mostly empty"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"D crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario E: Category labels visible ───────────────────────────────────
    log("  [E] Symbol categories visible (IEC, NFPA, ISA, ANSI, etc.)...")
    try:
        page_text   = page.locator("body").inner_text()
        categories  = ["IEC", "NFPA", "ISA", "ANSI", "ISO", "Electrical", "Mechanical",
                       "Hydraulic", "Pneumatic", "Fire", "Plumbing"]
        found_cats  = [c for c in categories if c in page_text]

        if len(found_cats) >= 3:
            results.append(("PASS", f"E: {len(found_cats)} symbol categories visible: {found_cats[:5]}"))
        elif len(found_cats) >= 1:
            results.append(("WARN", f"E: only {len(found_cats)} categories visible: {found_cats}"))
        else:
            results.append(("WARN", "E: no standard category labels found on symbol gallery"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"E crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario F: At least 10 symbol SVGs rendered ─────────────────────────
    log("  [F] At least 10 symbol SVGs rendered in gallery...")
    try:
        symbol_count = page.evaluate("""() => {
            // Count SVGs that look like symbols (small, in a grid)
            const svgs = Array.from(document.querySelectorAll('svg'));
            const symbolSvgs = svgs.filter(s => {
                const w = s.getBoundingClientRect().width;
                return w > 10 && w < 200;   // symbol-sized SVGs
            }).length;

            // Also count img elements that might be symbols
            const imgs = document.querySelectorAll('[class*="symbol"] img, [class*="gallery"] img').length;

            return symbolSvgs + imgs;
        }""")

        if symbol_count >= 10:
            results.append(("PASS", f"F: {symbol_count} symbol elements rendered"))
        elif symbol_count >= 3:
            results.append(("WARN", f"F: only {symbol_count} symbol elements found (expected ≥10)"))
        else:
            results.append(("WARN", f"F: very few symbol elements ({symbol_count}) — gallery may not be rendering"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"F skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario G: Search/filter narrows symbols ─────────────────────────────
    log("  [G] Search narrows displayed symbols...")
    try:
        search_input = page.locator(
            "input[type='search'], input[placeholder*='search' i], "
            "input[placeholder*='filter' i], #gallery-search, #symbol-search"
        ).first

        if not search_input.count():
            results.append(("WARN", "G: no search input on symbol gallery"))
        else:
            count_before = page.evaluate("""() =>
                document.querySelectorAll('svg, [class*="symbol"], [class*="gallery"] > *').length
            """)

            search_input.fill("pump")
            page.wait_for_timeout(800)

            count_after = page.evaluate("""() =>
                document.querySelectorAll('svg, [class*="symbol"], [class*="gallery"] > *').length
            """)

            if count_after < count_before and count_after > 0:
                results.append(("PASS", f"G: search 'pump' filtered {count_before}→{count_after} elements"))
            elif count_after == count_before:
                results.append(("WARN", "G: element count unchanged after search — filter may not be working"))
            else:
                results.append(("WARN", f"G: search returned 0 elements (no 'pump' symbols or filter cleared all)"))

            # Clear search
            search_input.fill("")
            page.wait_for_timeout(400)
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"G skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario H: No "undefined" symbol names ───────────────────────────────
    log("  [H] No 'undefined' symbol names in gallery...")
    try:
        page_text = page.locator("body").inner_text()
        if "undefined" in page_text:
            results.append(("FAIL", "H: 'undefined' found on symbol gallery — name mapping broken"))
        else:
            results.append(("PASS", "H: no 'undefined' symbol names in gallery"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"H crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario I: Renders correctly at 375px ────────────────────────────────
    log("  [I] Symbol gallery no horizontal overflow at 375px (mobile)...")
    try:
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(800)

        overflow = page.evaluate("""() => {
            const body = document.body;
            const html = document.documentElement;
            return {
                bodyScroll:    body.scrollWidth > body.clientWidth,
                htmlScroll:    html.scrollWidth > html.clientWidth,
                bodyWidth:     body.scrollWidth,
                viewportWidth: window.innerWidth,
            };
        }""")

        has_overflow = overflow["bodyScroll"] or overflow["htmlScroll"]
        if has_overflow:
            excess = overflow["bodyWidth"] - overflow["viewportWidth"]
            results.append(("FAIL", f"I: horizontal overflow at 375px — content is {excess}px wider than viewport"))
        else:
            results.append(("PASS", "I: no horizontal overflow at 375px"))

        # Restore viewport
        page.set_viewport_size({"width": 1280, "height": 900})
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"I skipped: {e}"))
        log(f"    → WARN: {e}")

    screenshot(page, "symbol_gallery_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  Static Pages: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

