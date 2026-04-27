"""
XSS / escHtml Coverage Validator — WorkHive Platform
=====================================================
Cross-Site Scripting (XSS) is the #1 web vulnerability for platforms
that render user-supplied data into the DOM. WorkHive renders logbook
entries, inventory item names, asset IDs, PM task descriptions, and
worker names directly into HTML cards and lists.

The platform uses escHtml() as its single XSS defence. It is defined
in utils.js and used in every innerHTML template that renders user data.
This validator ensures that defence can never be accidentally removed.

Four things checked:

  1. escHtml available on every innerHTML page
     — Every page that assigns innerHTML with template literals (${...})
       must have escHtml in scope: either defined locally or via utils.js.
       A page without escHtml available is one refactor away from XSS.

  2. innerHTML template literal coverage ratio
     — For each page, count interpolations (${...}) inside innerHTML
       assignments. If more than THRESHOLD% are raw (no escHtml wrapper),
       the page likely has unescaped user data somewhere in its rendering.
       Reported as WARN — some interpolations are legitimately safe
       (numbers, boolean flags, internal enum strings).

  3. insertAdjacentHTML with raw interpolation
     — insertAdjacentHTML() is equivalent to innerHTML but easier to
       miss in reviews. Every call with ${...} must use escHtml on any
       variable that could contain user-supplied content.

  4. No high-risk injection vectors
     — eval(), new Function(), and document.write() are banned in live
       pages. These bypass all escaping and allow arbitrary code execution.
       This is a regression guard — the platform currently has none.

Usage:  python validate_xss.py
Output: xss_report.json
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
    "nav-hub.html",
    "index.html",
    "floating-ai.js",
    "nav-hub.js",
]

# Pages that define escHtml themselves (don't need utils.js)
SELF_DEFINES_ESC = {"engineering-design.html"}

# Known safe interpolation patterns (numbers, enums, internal flags)
# These don't need escHtml because they cannot contain HTML
SAFE_PATTERNS = [
    r"^\s*\d+",                    # pure number
    r"\.length\b",                 # array length
    r"\bcount\b", r"\blen\b",      # count variables
    r"\bi\b", r"\bj\b", r"\bn\b",  # loop counters
    r"\?\s*'[^'<>]+'\s*:\s*'[^'<>]+'",  # ternary with static strings
    r"new Date\(",                  # date object
    r"\.toFixed\(", r"\.toLocaleString\(",  # number formatting
    r"Math\.", r"Number\(",         # math expressions
    r"parseFloat\(", r"parseInt\(",  # numeric conversions
]

# High-risk injection vectors — none of these should exist in live pages
INJECTION_VECTORS = ["eval(", "new Function(", "document.write("]

# Threshold: if more than this fraction of innerHTML interpolations are raw, warn
RAW_THRESHOLD = 0.40


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def loads_utils_js(content):
    """Returns True if the file loads utils.js."""
    return bool(re.search(r'src=["\'][^"\']*utils\.js["\']', content))


def has_esc_html(content):
    """Returns True if escHtml is defined or available in this file."""
    return bool(re.search(
        r"function\s+escHtml\s*\(|const\s+escHtml\s*=|var\s+escHtml\s*=|let\s+escHtml\s*=",
        content
    ))


def is_safe_interpolation(expr):
    """Returns True if the interpolated expression is known-safe (number/enum/flag)."""
    return any(re.search(p, expr) for p in SAFE_PATTERNS)


# ── Check 1: escHtml available on every innerHTML page ───────────────────────

def check_esc_html_availability(pages):
    """
    Every page that uses innerHTML / insertAdjacentHTML with template literal
    interpolation must have escHtml in scope. Without it, there is zero XSS
    protection for any string that gets rendered into the DOM.

    A page without escHtml available is one developer mistake away from
    introducing a stored XSS vulnerability that persists in the database.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        # Does the page use innerHTML / insertAdjacentHTML with interpolation?
        uses_inner = bool(re.search(
            r'(innerHTML|insertAdjacentHTML)\s*[=+(]\s*[^;]*\$\{',
            content, re.DOTALL
        ))
        if not uses_inner:
            continue

        # Does escHtml exist in scope?
        esc_available = (
            page in SELF_DEFINES_ESC or
            has_esc_html(content) or
            loads_utils_js(content)
        )
        if not esc_available:
            issues.append({
                "page": page,
                "reason": (
                    f"{page} uses innerHTML/insertAdjacentHTML with template "
                    f"literal interpolation but has no escHtml function available "
                    f"(not defined locally and utils.js not loaded) — "
                    f"any future user-data interpolation will be an XSS vulnerability"
                ),
            })
    return issues


# ── Check 2: innerHTML interpolation coverage ratio ───────────────────────────

def check_interpolation_coverage(pages):
    """
    For pages that have escHtml available, count the ratio of raw (unescaped)
    interpolations vs escaped ones in innerHTML assignments.

    Safe interpolations (numbers, .length, Math operations) are excluded
    from both counts — they don't need escaping.

    A high raw ratio means the page likely renders some user data without
    escaping. Reported as WARN because not all interpolations are user data.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        # Only check pages where escHtml is available
        esc_available = (
            page in SELF_DEFINES_ESC or
            has_esc_html(content) or
            loads_utils_js(content)
        )
        if not esc_available:
            continue

        # Find all innerHTML/insertAdjacentHTML template literals
        raw_count     = 0
        escaped_count = 0

        for m in re.finditer(
            r'(?:innerHTML|insertAdjacentHTML\s*\([^,]+,)\s*`([^`]+)`',
            content
        ):
            template = m.group(1)
            # Extract all ${...} interpolations
            for interp_m in re.finditer(r'\$\{([^}]+)\}', template):
                expr = interp_m.group(1).strip()
                if is_safe_interpolation(expr):
                    continue
                if "escHtml" in expr:
                    escaped_count += 1
                else:
                    raw_count += 1

        total = raw_count + escaped_count
        if total == 0:
            continue
        raw_ratio = raw_count / total
        if raw_ratio > RAW_THRESHOLD:
            issues.append({
                "page":         page,
                "raw":          raw_count,
                "escaped":      escaped_count,
                "ratio":        round(raw_ratio, 2),
                "reason": (
                    f"{page} has {raw_count}/{total} innerHTML interpolations "
                    f"without escHtml ({raw_ratio:.0%}) — "
                    f"review raw interpolations to confirm none are user-supplied data"
                ),
            })
    return issues


# ── Check 3: insertAdjacentHTML with raw string interpolation ─────────────────

def check_insert_adjacent_html(pages):
    """
    insertAdjacentHTML() is as dangerous as innerHTML but often missed in
    security reviews because it looks like a method call rather than an
    assignment. Every call with ${...} that isn't clearly a safe value
    (number, enum, static string) must use escHtml.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "insertAdjacentHTML" not in line:
                continue
            if "${" not in line:
                continue
            # Extract interpolations from this line
            for interp_m in re.finditer(r'\$\{([^}]+)\}', line):
                expr = interp_m.group(1).strip()
                if is_safe_interpolation(expr):
                    continue
                if "escHtml" not in expr:
                    issues.append({
                        "page": page,
                        "line": i + 1,
                        "expr": expr[:60],
                        "reason": (
                            f"{page}:{i + 1} — insertAdjacentHTML with raw "
                            f"interpolation '${{  {expr[:40]}  }}' — "
                            f"wrap user-data variables with escHtml()"
                        ),
                    })
                    break  # one report per line
    return issues


# ── Check 4: No high-risk injection vectors ───────────────────────────────────

def check_injection_vectors(pages):
    """
    eval(), new Function(), and document.write() bypass all escaping and
    allow arbitrary code execution. None of these should exist in live pages.
    This is a regression guard — the platform currently passes clean.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for vector in INJECTION_VECTORS:
                # Skip win.document.write( — safe print-popup pattern (not page injection)
                if vector == "document.write(" and re.search(r'\w+\.document\.write\s*\(', line):
                    continue
                if vector in line:
                    issues.append({
                        "page":   page,
                        "line":   i + 1,
                        "vector": vector,
                        "reason": (
                            f"{page}:{i + 1} — high-risk injection vector "
                            f"'{vector}' found — this bypasses all XSS escaping "
                            f"and allows arbitrary code execution"
                        ),
                    })
                    break
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("XSS / escHtml Coverage Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] escHtml available on every page that writes innerHTML",
        check_esc_html_availability(LIVE_PAGES),
        "FAIL",
    ),
    (
        f"[2] innerHTML interpolation coverage ratio (raw <= {RAW_THRESHOLD:.0%})",
        check_interpolation_coverage(LIVE_PAGES),
        "WARN",
    ),
    (
        "[3] insertAdjacentHTML calls use escHtml on variable content",
        check_insert_adjacent_html(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[4] No eval() / new Function() / document.write() in live pages",
        check_injection_vectors(LIVE_PAGES),
        "FAIL",
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

with open("xss_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved xss_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll XSS checks PASS.")
