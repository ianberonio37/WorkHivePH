"""
Mobile UX Compliance Validator — WorkHive Platform
===================================================
WorkHive targets field workers on mobile phones in industrial environments:
bright sunlight, gloves, noisy floors. Mobile UX failures are invisible
on desktop during development but break the experience for every field worker.

Four things checked:

  1. viewport-fit=cover on all pages
     — Every page must include viewport-fit=cover in its <meta name="viewport">
       tag. Without it, content is hidden behind the iOS home bar indicator
       on iPhone X and later (the notch area). Workers lose the bottom ~34px
       of the screen — buttons, inputs, and nav items are cut off.

  2. Input font-size >= 16px (iOS auto-zoom guard)
     — The .wh-input CSS class must declare font-size >= 1rem (16px). Below
       16px, iOS Safari automatically zooms in when the worker taps the input
       field, breaking the layout and requiring a double-tap to zoom out. This
       is one of the most common mobile UX issues on industrial apps.

  3. Pages with fixed bottom elements have safe-area-inset-bottom
     — Any page that uses position:fixed with bottom:0 in its own CSS must
       also reference env(safe-area-inset-bottom) somewhere. Without it, fixed
       bottom navs, chat inputs, and action sheets are partially obscured by
       the iOS home indicator bar on notched devices.

  4. No inline touch target below 44px
     — Interactive elements (<button>, <a>) with an explicit inline height or
       min-height below 44px (2.75rem) are too small for gloved or sweat-covered
       fingers. The Mobile Maestro skill sets 44x44px as the hard minimum.
       This check scans inline styles only — CSS-class-defined sizes are handled
       by the design system and assumed correct.

Usage:  python validate_mobile.py
Output: mobile_report.json
"""
import re, json, sys

LIVE_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "assistant.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
    "platform-health.html",
    "index.html",
]

# Minimum touch target in px from the Mobile Maestro skill
MIN_TOUCH_PX = 44

# Safe CSS values for font-size on inputs (>=16px)
# These all resolve to 16px or higher at default browser settings
SAFE_FONT_SIZES = {
    "1rem", "1.0rem", "1.1rem", "1.2rem", "1.25rem", "1.5rem", "2rem",
    "16px", "17px", "18px", "20px", "24px",
}


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ── Check 1: viewport-fit=cover on all live pages ────────────────────────────

def check_viewport_fit(pages):
    """
    Every live page must declare viewport-fit=cover in its viewport meta tag.
    Missing it on iPhone X+ causes the safe area at the bottom (home bar) and
    top (notch) to be left blank — content stops at those boundaries, making
    the page look broken on modern iPhones.

    Correct:   <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    Missing:   <meta name="viewport" content="width=device-width, initial-scale=1.0">
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        m = re.search(r'<meta[^>]+name=["\']viewport["\'][^>]*content=["\']([^"\']+)["\']', content, re.IGNORECASE)
        if not m:
            issues.append({
                "page": page,
                "reason": f"{page} has no <meta name='viewport'> tag",
            })
            continue
        if "viewport-fit=cover" not in m.group(1):
            issues.append({
                "page":    page,
                "current": m.group(1),
                "reason": (
                    f"{page} viewport is missing viewport-fit=cover: "
                    f"'{m.group(1)}' — content is hidden behind iOS notch/home bar "
                    f"on iPhone X and later"
                ),
            })
    return issues


# ── Check 2: .wh-input font-size >= 16px ─────────────────────────────────────

def check_input_font_size(pages):
    """
    The .wh-input class must declare font-size >= 1rem (16px). This is the
    iOS Safari auto-zoom threshold — any input with a smaller font-size causes
    the viewport to zoom in when the worker taps the field.

    After zoom, the worker must double-tap or pinch to restore the layout.
    In a noisy plant with gloves, this is a significant usability failure.

    This check scans the .wh-input CSS definition in each page's <style> block.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        # Does this page even use .wh-input?
        if ".wh-input" not in content:
            continue

        # Find the font-size declaration inside the .wh-input rule block
        m = re.search(r"\.wh-input\s*\{([^}]+)\}", content, re.DOTALL)
        if not m:
            continue

        rule_block = m.group(1)
        fs_m = re.search(r"font-size\s*:\s*([^;]+);", rule_block)
        if not fs_m:
            issues.append({
                "page": page,
                "reason": (
                    f"{page} .wh-input CSS rule has no font-size declaration — "
                    f"browser default may be below 16px on some devices, "
                    f"triggering iOS Safari auto-zoom on input tap"
                ),
            })
            continue

        font_size = fs_m.group(1).strip().lower()
        if font_size not in SAFE_FONT_SIZES:
            # Try to parse numeric value
            num_m = re.search(r"([\d.]+)(rem|px|em)", font_size)
            if num_m:
                val  = float(num_m.group(1))
                unit = num_m.group(2)
                px_val = val * 16 if unit == "rem" else val
                if px_val < 16:
                    issues.append({
                        "page":       page,
                        "font_size":  font_size,
                        "px_equiv":   px_val,
                        "reason": (
                            f"{page} .wh-input font-size is {font_size} "
                            f"(~{px_val:.0f}px, below 16px threshold) — "
                            f"iOS Safari will auto-zoom when workers tap input fields"
                        ),
                    })
    return issues


# ── Check 3: Pages with fixed bottom elements have safe-area-inset-bottom ────

def check_safe_area(pages):
    """
    If a page has its own fixed bottom CSS (not from floating-ai.js), it must
    also reference env(safe-area-inset-bottom) to avoid the iOS home indicator
    overlapping the UI.

    A fixed bottom nav at bottom:0 without safe-area-inset-bottom puts the
    nav buttons right where the home indicator bar appears — workers
    accidentally trigger the home gesture instead of tapping nav buttons.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        # Find CSS position:fixed with bottom:0 patterns (own CSS)
        has_fixed_bottom = bool(re.search(
            r"position\s*:\s*fixed[^}]*bottom\s*:\s*0\b"
            r"|bottom\s*:\s*0[^}]*position\s*:\s*fixed",
            content, re.DOTALL
        ))
        if not has_fixed_bottom:
            continue

        has_safe_area = "env(safe-area-inset-bottom)" in content
        if not has_safe_area:
            issues.append({
                "page": page,
                "reason": (
                    f"{page} has position:fixed bottom:0 CSS but no "
                    f"env(safe-area-inset-bottom) — fixed bottom UI will be "
                    f"partially hidden behind the iOS home indicator bar on "
                    f"iPhone X and later devices"
                ),
            })
    return issues


# ── Check 4: No inline touch target below 44px ───────────────────────────────

def check_touch_targets(pages):
    """
    Interactive elements (<button>, <a>) with inline height or min-height
    styles below 44px are too small for reliable touch on mobile.

    The Mobile Maestro skill specifies 44x44px as the absolute minimum for
    any tappable element. Workers in gloves or with wet hands need the extra
    target area — a 32px button that works on desktop will frustrate a
    field worker trying to confirm a PM completion.

    Only inline styles are checked here — CSS-class sizes are assumed
    to comply with the design system's 44px standard.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "<button" not in line and "<a " not in line:
                continue
            # Look for inline height or min-height
            for attr in ("height:", "min-height:"):
                m = re.search(
                    rf'style="[^"]*{re.escape(attr)}\s*([\d.]+)(px|rem)[^"]*"',
                    line
                )
                if not m:
                    continue
                val  = float(m.group(1))
                unit = m.group(2)
                px_val = val * 16 if unit == "rem" else val
                if px_val < MIN_TOUCH_PX:
                    issues.append({
                        "page":   page,
                        "line":   i + 1,
                        "size":   f"{val}{unit} (~{px_val:.0f}px)",
                        "reason": (
                            f"{page}:{i + 1} — interactive element has inline "
                            f"{attr}{val}{unit} ({px_val:.0f}px) below "
                            f"the {MIN_TOUCH_PX}px minimum touch target — "
                            f"too small for gloved or field worker hands"
                        ),
                    })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Mobile UX Compliance Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] viewport-fit=cover on all live pages",
        check_viewport_fit(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[2] .wh-input font-size >= 16px (iOS auto-zoom guard)",
        check_input_font_size(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[3] Pages with fixed bottom elements have safe-area-inset-bottom",
        check_safe_area(LIVE_PAGES),
        "WARN",
    ),
    (
        f"[4] No inline touch target below {MIN_TOUCH_PX}px on interactive elements",
        check_touch_targets(LIVE_PAGES),
        "WARN",
    ),
]

for label, issues, severity in checks:
    print(f"\n{label}\n")
    if not issues:
        print("  PASS")
    else:
        for iss in issues:
            print(f"  {severity}  {iss.get('page', '?')}")
            print(f"        {iss['reason']}")
        if severity == "FAIL":
            fail_count += len(issues)
        else:
            warn_count += len(issues)
    report[label] = issues

print(f"\n{'=' * 70}")
print(f"Result: {fail_count} FAIL  {warn_count} WARN")

with open("mobile_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved mobile_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll mobile UX checks PASS.")
