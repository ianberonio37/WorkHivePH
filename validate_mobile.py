"""
Mobile UX Compliance Validator — WorkHive Platform
===================================================
WorkHive targets field workers on mobile phones in industrial environments:
bright sunlight, gloves, noisy floors. Mobile UX failures are invisible
on desktop during development but break the experience for every field worker.

  Layer 1 — Screen fit
    1.  viewport-fit=cover           — content must reach iOS notch/home bar edges
    2.  Input font-size >= 16px       — prevents iOS Safari auto-zoom on field tap

  Layer 2 — Touch geometry
    3.  safe-area-inset-bottom        — fixed bottom elements clear the iOS home bar
    4.  Touch targets >= 44px         — gloved hands need a minimum tap area

  Layer 3 — GPU / animation safety
    5.  will-change:filter override   — iOS GPU crash guard on animated elements
    6.  body animation reduced-motion — blank page guard when Reduce Motion is on

  Layer 4 — Scroll containment
    7.  Overscroll behavior on modals — prevents pull-to-refresh leaking out of drawers  [WARN]

  Layer 5 — Scope completeness
    8.  All live pages in scope        — analytics.html and nav-hub.html were missing

Usage:  python validate_mobile.py
Output: mobile_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

LIVE_PAGES = [
    "index.html",
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "assistant.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
    "analytics.html",
    "nav-hub.html",
    "platform-health.html",
]

MIN_TOUCH_PX = 44

SAFE_FONT_SIZES = {
    "1rem", "1.0rem", "1.1rem", "1.2rem", "1.25rem", "1.5rem", "2rem",
    "16px", "17px", "18px", "20px", "24px",
}

# Pages with scrollable CSS containers that must have overscroll-behavior: contain
# Checked by scanning <style> blocks for overflow-y without overscroll-behavior
SCROLL_PAGES = [
    "skillmatrix.html",   # .modal-body { overflow-y: auto }
    "hive.html",          # modal panel overflow-y: auto
    "logbook.html",       # multiple modal containers overflow-y: auto
    "assistant.html",     # chat message area overflow-y: auto
    "inventory.html",
    "pm-scheduler.html",
    "engineering-design.html",
]


# ── Layer 1: Screen fit ───────────────────────────────────────────────────────

def check_viewport_fit(pages):
    """viewport-fit=cover must be in every page's viewport meta tag — without it,
    content is clipped by the iOS notch and home bar on iPhone X+."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        m = re.search(r'<meta[^>]+name=["\']viewport["\'][^>]*content=["\']([^"\']+)["\']', content, re.IGNORECASE)
        if not m:
            issues.append({"check": "viewport_fit", "page": page,
                           "reason": f"{page} has no <meta name='viewport'> tag"})
            continue
        if "viewport-fit=cover" not in m.group(1):
            issues.append({"check": "viewport_fit", "page": page,
                           "reason": (f"{page} viewport missing viewport-fit=cover: "
                                      f"'{m.group(1)}' — content hidden behind iOS notch/home bar")})
    return issues


def check_input_font_size(pages):
    """The .wh-input CSS class must declare font-size >= 1rem (16px). Below 16px,
    iOS Safari auto-zooms on input tap — workers must double-tap to restore layout."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if ".wh-input" not in content:
            continue
        m = re.search(r"\.wh-input\s*\{([^}]+)\}", content, re.DOTALL)
        if not m:
            continue
        rule_block = m.group(1)
        fs_m = re.search(r"font-size\s*:\s*([^;]+);", rule_block)
        if not fs_m:
            issues.append({"check": "input_font_size", "page": page,
                           "reason": (f"{page} .wh-input has no font-size — browser default "
                                      f"may trigger iOS Safari auto-zoom on input tap")})
            continue
        font_size = fs_m.group(1).strip().lower()
        if font_size not in SAFE_FONT_SIZES:
            num_m = re.search(r"([\d.]+)(rem|px|em)", font_size)
            if num_m:
                val, unit = float(num_m.group(1)), num_m.group(2)
                px_val = val * 16 if unit == "rem" else val
                if px_val < 16:
                    issues.append({"check": "input_font_size", "page": page,
                                   "reason": (f"{page} .wh-input font-size is {font_size} "
                                              f"(~{px_val:.0f}px, below 16px) — iOS Safari "
                                              f"will auto-zoom when workers tap input fields")})
    return issues


# ── Layer 2: Touch geometry ───────────────────────────────────────────────────

def check_safe_area(pages):
    """Pages with position:fixed bottom:0 CSS must reference env(safe-area-inset-bottom)
    — otherwise fixed bottom UI is partially hidden behind the iOS home indicator."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        has_fixed_bottom = bool(re.search(
            r"position\s*:\s*fixed[^}]*bottom\s*:\s*0\b"
            r"|bottom\s*:\s*0[^}]*position\s*:\s*fixed",
            content, re.DOTALL
        ))
        if not has_fixed_bottom:
            continue
        if "env(safe-area-inset-bottom)" not in content:
            issues.append({"check": "safe_area", "page": page,
                           "reason": (f"{page} has position:fixed bottom:0 but no "
                                      f"env(safe-area-inset-bottom) — fixed bottom UI overlaps "
                                      f"the iOS home indicator bar on iPhone X+")})
    return issues


def check_touch_targets(pages):
    """Interactive elements with inline height or min-height below 44px are too
    small for gloved or field worker hands."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        # engineering-design.html uses compact 28px row-delete icons in a
        # desktop-only calculator form — exempted from inline touch target checks
        if page == "engineering-design.html":
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "<button" not in line and "<a " not in line:
                continue
            # Use \b to avoid matching "height:" inside "min-height:" twice
            for attr in (r"\bheight:", r"\bmin-height:"):
                m = re.search(rf'style="[^"]*{attr}\s*([\d.]+)(px|rem)[^"]*"', line)
                if not m:
                    continue
                val, unit = float(m.group(1)), m.group(2)
                px_val = val * 16 if unit == "rem" else val
                if px_val < MIN_TOUCH_PX:
                    issues.append({"check": "touch_targets", "page": page, "line": i + 1,
                                   "reason": (f"{page}:{i + 1} interactive element has inline "
                                              f"{attr}{val}{unit} ({px_val:.0f}px) below "
                                              f"{MIN_TOUCH_PX}px minimum for gloved field workers")})
    return issues


# ── Layer 3: GPU / animation safety ──────────────────────────────────────────

def check_will_change_filter(pages):
    """will-change:filter without a mobile @media override exhausts iOS Safari GPU
    memory on animated elements and crashes the browser tab."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        # Only scan CSS <style> blocks — avoid matching text descriptions in HTML
        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", content, re.DOTALL | re.IGNORECASE)
        css = "\n".join(style_blocks)
        if not re.search(r"will-change\s*:\s*filter", css):
            continue
        has_override = bool(re.search(
            r"@media\s*\([^)]*max-width[^)]*\)[^{]*\{.*?will-change\s*:\s*auto",
            css, re.DOTALL
        ))
        if not has_override:
            issues.append({"check": "will_change_filter", "page": page,
                           "reason": (f"{page} uses will-change:filter with no mobile override "
                                      f"(will-change:auto at max-width:767px) — exhausts iOS GPU "
                                      f"memory and crashes the tab")})
    return issues


def check_body_animation_reduced_motion(pages):
    """Pages with body { animation } must have a prefers-reduced-motion override
    or body stays opacity:0 permanently on iOS with Reduce Motion enabled."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if not re.search(r"body\s*\{[^}]*\banimation\s*:", content, re.DOTALL):
            continue
        has_override = bool(re.search(
            r"prefers-reduced-motion[^)]*\)[^{]*\{[^}]*body[^}]*animation\s*:\s*none",
            content, re.DOTALL
        ))
        if not has_override:
            issues.append({"check": "body_animation_motion", "page": page,
                           "reason": (f"{page} body has animation but no prefers-reduced-motion "
                                      f"override — page stays blank on iOS with Reduce Motion on")})
    return issues


# ── Layer 4: Scroll containment ───────────────────────────────────────────────

def check_overscroll_behavior(pages):
    """
    Scrollable modal and drawer containers must include overscroll-behavior: contain
    (or the Tailwind class overscroll-contain). Without it, when a worker scrolls
    to the top or bottom of a modal on Android Chrome, the scroll event propagates
    to the page behind — triggering the pull-to-refresh gesture and closing or
    refreshing the page mid-task.

    Applies to CSS-defined scrollable containers: overflow-y: auto/scroll inside
    a <style> block that does not already declare overscroll-behavior: contain.
    Reported as WARN — functional but causes confusing UX on Android devices.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        # Extract <style> blocks only (CSS-defined, not Tailwind utility classes)
        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", content, re.DOTALL | re.IGNORECASE)
        if not style_blocks:
            continue
        combined_css = "\n".join(style_blocks)
        # Check if any CSS rule has overflow-y: auto/scroll without overscroll-behavior
        has_scroll = bool(re.search(r"overflow-y\s*:\s*(auto|scroll)", combined_css))
        if not has_scroll:
            continue
        has_overscroll = bool(re.search(r"overscroll-behavior", combined_css))
        if not has_overscroll:
            issues.append({"check": "overscroll_behavior", "page": page, "skip": True,
                           "reason": (f"{page} has overflow-y:auto/scroll in CSS but no "
                                      f"overscroll-behavior:contain — scrolling to the edge of "
                                      f"a modal triggers Android pull-to-refresh behind the dialog; "
                                      f"add overscroll-behavior:contain to scrollable modal containers")})
    return issues


# ── Layer 5: Scope completeness ───────────────────────────────────────────────

def check_all_pages_in_scope(live_pages):
    """
    All known live HTML pages must be included in LIVE_PAGES so every page is
    checked for mobile compliance. analytics.html and nav-hub.html were previously
    missing — their viewport tags, animations, and touch targets were invisible
    to this validator.
    """
    KNOWN_LIVE = {
        "index.html", "logbook.html", "inventory.html", "pm-scheduler.html",
        "hive.html", "assistant.html", "skillmatrix.html", "dayplanner.html",
        "engineering-design.html", "analytics.html", "nav-hub.html",
        "platform-health.html",
    }
    in_scope = set(live_pages)
    missing  = [p for p in sorted(KNOWN_LIVE) if p not in in_scope and os.path.exists(p)]
    issues   = []
    for page in missing:
        issues.append({"check": "pages_in_scope", "page": page,
                       "reason": (f"{page} exists but is not in LIVE_PAGES — "
                                  f"its viewport tags, animations, and touch targets "
                                  f"are not checked for mobile compliance")})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "viewport_fit",
    "input_font_size",
    "safe_area",
    "touch_targets",
    "will_change_filter",
    "body_animation_motion",
    "overscroll_behavior",
    "pages_in_scope",
]

CHECK_LABELS = {
    "viewport_fit":          "L1  viewport-fit=cover on all live pages",
    "input_font_size":       "L1  .wh-input font-size >= 16px (iOS auto-zoom guard)",
    "safe_area":             "L2  Fixed bottom elements have safe-area-inset-bottom",
    "touch_targets":         "L2  No inline touch target below 44px",
    "will_change_filter":    "L3  will-change:filter has mobile override (iOS GPU crash guard)",
    "body_animation_motion": "L3  body animation has prefers-reduced-motion override",
    "overscroll_behavior":   "L4  Scrollable modal containers have overscroll-behavior:contain  [WARN]",
    "pages_in_scope":        "L5  All live pages included in mobile validation scope",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nMobile UX Compliance Validator (5-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_viewport_fit(LIVE_PAGES)
    all_issues += check_input_font_size(LIVE_PAGES)
    all_issues += check_safe_area(LIVE_PAGES)
    all_issues += check_touch_targets(LIVE_PAGES)
    all_issues += check_will_change_filter(LIVE_PAGES)
    all_issues += check_body_animation_reduced_motion(LIVE_PAGES)
    all_issues += check_overscroll_behavior(SCROLL_PAGES)
    all_issues += check_all_pages_in_scope(LIVE_PAGES)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "mobile",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("mobile_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
