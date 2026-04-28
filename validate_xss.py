"""
XSS / escHtml Coverage Validator — WorkHive Platform
======================================================
Cross-Site Scripting (XSS) is the #1 web vulnerability for platforms that
render user-supplied data into the DOM. WorkHive renders logbook entries,
inventory item names, asset IDs, PM task descriptions, and worker names
directly into HTML cards.

The platform uses escHtml() as its single XSS defence. This validator
ensures that defence is present everywhere it is needed.

  Layer 1 — Presence checks
    1.  escHtml available             — every innerHTML page has escHtml in scope
    2.  outerHTML not raw             — outerHTML with interpolation uses escHtml

  Layer 2 — Coverage checks
    3.  Raw interpolation ratio       — no page exceeds 40% raw (unescaped) interpolations
    4.  insertAdjacentHTML safe       — every insertAdjacentHTML with ${...} uses escHtml

  Layer 3 — High-risk patterns
    5.  No injection vectors          — no eval / new Function / document.write in live pages
    6.  No setAttribute event handler — no setAttribute('onclick', ...) with user data

  Layer 4 — Scope completeness
    7.  All live pages in scope       — analytics.html and all new pages included in checks

Usage:  python validate_xss.py
Output: xss_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

LIVE_PAGES = [
    "logbook.html",
    "inventory.html",
    "pm-scheduler.html",
    "hive.html",
    "assistant.html",
    "skillmatrix.html",
    "dayplanner.html",
    "engineering-design.html",
    "analytics.html",
    "platform-health.html",
    "nav-hub.html",
    "index.html",
    "floating-ai.js",
    "nav-hub.js",
]

# Pages that define escHtml themselves (don't load utils.js)
SELF_DEFINES_ESC = {"engineering-design.html"}

# Known-safe interpolation patterns: numbers, enums, internal counters
SAFE_PATTERNS = [
    r"^\s*\d+", r"\.length\b", r"\bcount\b", r"\blen\b",
    r"\bi\b", r"\bj\b", r"\bn\b",
    r"\?\s*'[^'<>]+'\s*:\s*'[^'<>]+'",
    r"new Date\(", r"\.toFixed\(", r"\.toLocaleString\(",
    r"Math\.", r"Number\(", r"parseFloat\(", r"parseInt\(",
]

INJECTION_VECTORS = ["eval(", "new Function(", "document.write("]
RAW_THRESHOLD     = 0.40


# ── Helpers ───────────────────────────────────────────────────────────────────

def loads_utils_js(content):
    return bool(re.search(r'src=["\'][^"\']*utils\.js["\']', content))

def has_esc_html(content):
    return bool(re.search(
        r"function\s+escHtml\s*\(|const\s+escHtml\s*=|var\s+escHtml\s*=|let\s+escHtml\s*=",
        content
    ))

def esc_available(page, content):
    return page in SELF_DEFINES_ESC or has_esc_html(content) or loads_utils_js(content)

def is_safe_interpolation(expr):
    return any(re.search(p, expr) for p in SAFE_PATTERNS)


# ── Layer 1: Presence checks ──────────────────────────────────────────────────

def check_esc_html_available():
    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if content is None:
            continue
        uses_inner = bool(re.search(
            r'(innerHTML|insertAdjacentHTML|outerHTML)\s*[=+(]\s*[^;]*\$\{',
            content, re.DOTALL
        ))
        if not uses_inner:
            continue
        if not esc_available(page, content):
            issues.append({"check": "esc_html_available", "page": page,
                           "reason": f"{page} uses innerHTML/outerHTML with interpolation but escHtml is not in scope — any user data rendered is an XSS vulnerability"})
    return issues


def check_outer_html_raw():
    """
    outerHTML = `...${expr}...` carries the same XSS risk as innerHTML.
    The existing innerHTML scan misses outerHTML entirely.
    """
    # Helper functions that internally escape their output — false-positive suppression
    SAFE_HELPER_CALLS = {
        "statusBadge(",   # uses hard-coded enum label map
        "freqBadge(",     # uses hard-coded frequency abbreviations
        "stockStatus(",   # returns internal status enum
        "catBadge(",      # uses CATEGORY_COLORS lookup (no raw user string rendered)
        "catPill(",       # internally calls escHtml(cat)
        "critBadge(",     # internally calls escHtml(crit)
    }

    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if content is None or not esc_available(page, content):
            continue
        for m in re.finditer(r'outerHTML\s*=\s*`([^`]+)`', content):
            template = m.group(1)
            for im in re.finditer(r'\$\{([^}]+)\}', template):
                expr = im.group(1).strip()
                if is_safe_interpolation(expr):
                    continue
                if "escHtml" in expr:
                    continue
                if any(expr.startswith(fn) for fn in SAFE_HELPER_CALLS):
                    continue
                line = content[:m.start()].count('\n') + 1
                issues.append({"check": "outer_html_raw", "page": page, "line": line,
                               "reason": f"{page}:{line} outerHTML interpolation '${{  {expr[:40]}  }}' without escHtml"})
                break
    return issues


# ── Layer 2: Coverage checks ──────────────────────────────────────────────────

def check_raw_interpolation_ratio():
    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if content is None or not esc_available(page, content):
            continue
        raw = 0; esc = 0
        for m in re.finditer(
            r'(?:innerHTML|outerHTML|insertAdjacentHTML\s*\([^,]+,)\s*`([^`]+)`',
            content
        ):
            for im in re.finditer(r'\$\{([^}]+)\}', m.group(1)):
                expr = im.group(1).strip()
                if is_safe_interpolation(expr):
                    continue
                if "escHtml" in expr:
                    esc += 1
                else:
                    raw += 1
        total = raw + esc
        if total == 0:
            continue
        ratio = raw / total
        if ratio > RAW_THRESHOLD:
            issues.append({"check": "raw_interpolation_ratio", "page": page,
                           "raw": raw, "escaped": esc, "ratio": round(ratio, 2),
                           "skip": True,   # WARN not FAIL — some raw interpolations are safe
                           "reason": f"{page}: {raw}/{total} innerHTML interpolations without escHtml ({ratio:.0%}) — review raw ones to confirm none are user-supplied data"})
    return issues


def check_insert_adjacent_html():
    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "insertAdjacentHTML" not in line or "${" not in line:
                continue
            for im in re.finditer(r'\$\{([^}]+)\}', line):
                expr = im.group(1).strip()
                if is_safe_interpolation(expr) or "escHtml" in expr:
                    continue
                issues.append({"check": "insert_adjacent_html", "page": page, "line": i + 1,
                               "reason": f"{page}:{i+1} insertAdjacentHTML with raw '${{  {expr[:40]}  }}' — wrap user-data with escHtml()"})
                break
    return issues


# ── Layer 3: High-risk patterns ───────────────────────────────────────────────

def check_injection_vectors():
    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for vector in INJECTION_VECTORS:
                if vector == "document.write(" and re.search(r'\w+\.document\.write\s*\(', line):
                    continue
                if vector in line:
                    issues.append({"check": "injection_vectors", "page": page,
                                   "line": i + 1, "vector": vector,
                                   "reason": f"{page}:{i+1} high-risk vector '{vector}' bypasses all XSS escaping — remove or wrap in code review comment"})
                    break
    return issues


def check_set_attribute_event_handlers():
    """
    setAttribute('onclick', userInput) dynamically adds event handlers from
    user-supplied strings. escHtml does not protect this because the value is
    evaluated as JavaScript, not HTML.
    Pattern: setAttribute('on...', expr) where expr is not a static string.
    """
    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            m = re.search(r'setAttribute\s*\(\s*[\'"]on\w+[\'"]\s*,\s*([^)]+)\)', line)
            if not m:
                continue
            expr = m.group(1).strip()
            # Static string literals are safe
            if re.match(r'^[\'"][^\'\"]*[\'"]$', expr):
                continue
            # Template literals without interpolation are safe
            if re.match(r'^`[^$`]*`$', expr):
                continue
            issues.append({"check": "set_attribute_event_handler", "page": page, "line": i + 1,
                           "reason": f"{page}:{i+1} setAttribute('on...', {expr[:40]}) with dynamic value — use data-attributes + addEventListener instead"})
    return issues


# ── Layer 4: Scope completeness ───────────────────────────────────────────────

def check_all_html_pages_in_scope():
    """
    Every .html file that renders user data must be in LIVE_PAGES.
    Check that no html/js file that uses innerHTML with interpolation is silently excluded.
    """
    import glob
    issues = []
    live_set = set(LIVE_PAGES)
    for path in glob.glob("*.html") + glob.glob("*.js"):
        fname = os.path.basename(path)
        if fname in live_set:
            continue
        # Skip backup/test/platform-internal/retired files
        if any(s in fname for s in ["-test", ".backup", "platform-health", "guardian",
                                     "parts-tracker", "symbol-gallery", "architecture"]):
            continue
        content = read_file(fname)
        if not content:
            continue
        uses_inner = bool(re.search(r'innerHTML\s*[=+]\s*[^;]*\$\{', content))
        if uses_inner:
            issues.append({"check": "all_pages_in_scope", "page": fname,
                           "reason": f"{fname} uses innerHTML with interpolation but is not in validate_xss.py LIVE_PAGES — XSS checks never run on it"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1
    "esc_html_available", "outer_html_raw",
    # L2
    "raw_interpolation_ratio", "insert_adjacent_html",
    # L3
    "injection_vectors", "set_attribute_event_handler",
    # L4
    "all_pages_in_scope",
]

CHECK_LABELS = {
    # L1
    "esc_html_available":          "L1  escHtml in scope on every innerHTML/outerHTML page",
    "outer_html_raw":              "L1  outerHTML interpolations use escHtml",
    # L2
    "raw_interpolation_ratio":     "L2  Raw interpolation ratio <= 40% per page  [WARN]",
    "insert_adjacent_html":        "L2  insertAdjacentHTML interpolations use escHtml",
    # L3
    "injection_vectors":           "L3  No eval / new Function / document.write",
    "set_attribute_event_handler": "L3  No setAttribute('on...', dynamic) patterns",
    # L4
    "all_pages_in_scope":          "L4  All innerHTML pages included in LIVE_PAGES",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nXSS / escHtml Coverage Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_esc_html_available()
    all_issues += check_outer_html_raw()
    all_issues += check_raw_interpolation_ratio()
    all_issues += check_insert_adjacent_html()
    all_issues += check_injection_vectors()
    all_issues += check_set_attribute_event_handlers()
    all_issues += check_all_html_pages_in_scope()

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_skip == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_skip} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "xss",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_skip,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("xss_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
