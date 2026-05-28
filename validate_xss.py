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

  Layer 5 — Script load order
    8.  utils.js before main script   — escHtml undefined at runtime if utils.js loads after

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
    "companion-launcher.js",
    "nav-hub.js",
    "report-sender.html",
    "community.html",
    "marketplace.html",
    "marketplace-admin.html",
    "marketplace-seller.html",
    "marketplace-seller-profile.html",
    "public-feed.html",
    "project-manager.html",
    "integrations.html",
    "ph-intelligence.html",
    "project-report.html",
    "predictive.html",
    "achievements.html",
    "asset-hub.html",
    "shift-brain.html",
    "alert-hub.html",
    # Phase B.3: cross-page voice handler. Lazy-loaded by nav-hub.js so it
    # ends up on every page; needs the same XSS coverage as the HTML files.
    "voice-handler.js",
    # Universal feedback widget (2026-05-19): renders on every page via
    # nav-hub.js. Uses innerHTML with interpolation for the form HTML, so
    # needs XSS coverage like other shared helpers.
    "wh-feedback-fab.js",
    # Shared helper that uses innerHTML with interpolation (PRODUCTION_FIXES #15)
    "worker-drawer.js",
    # Founder Console — admin-only platform-wide dashboard (Phase 1+)
    "founder-console.html",
    # P1 roadmap 2026-05-27 — admin-only observability dashboards. Both define
    # escHtml inline within their inline scripts and only render from trusted
    # admin-readable data sources.
    "llm-observability.html",
    "validator-catalog.html",
]

# Pages that define escHtml themselves (don't load utils.js)
SELF_DEFINES_ESC = {"engineering-design.html", "llm-observability.html", "validator-catalog.html"}

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
    # Word-boundary regex per vector. Plain substring match misfires on
    # benign identifiers (e.g. _rewriteQueryForRetrieval( contains "eval(",
    # _newFunction() / _newFunctionX( contain "new Function("). Anchoring
    # at \b cuts those false positives without weakening the real check.
    vector_patterns = [
        ("eval(",            re.compile(r'\beval\s*\(')),
        ("new Function(",    re.compile(r'\bnew\s+Function\s*\(')),
        ("document.write(",  re.compile(r'(?<![\w.])document\.write\s*\(')),
    ]
    for page in LIVE_PAGES:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for vector_label, pat in vector_patterns:
                if vector_label == "document.write(" and re.search(r'\w+\.document\.write\s*\(', line):
                    continue
                if pat.search(line):
                    issues.append({"check": "injection_vectors", "page": page,
                                   "line": i + 1, "vector": vector_label,
                                   "reason": f"{page}:{i+1} high-risk vector '{vector_label}' bypasses all XSS escaping — remove or wrap in code review comment"})
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


# ── Layer 5: Script load order ────────────────────────────────────────────────

def check_utils_load_order():
    """
    utils.js must be loaded via a <script src="utils.js"> tag BEFORE the main
    inline <script> block. If it appears after, escHtml() is undefined when the
    page script executes — XSS protection silently fails for the entire page
    without any runtime error or warning.

    This was the root cause of a community.html regression where the CDN and
    utils.js were placed after the main <script> block during a refactor.
    """
    issues = []
    html_pages = [p for p in LIVE_PAGES if p.endswith(".html")]
    for page in html_pages:
        content = read_file(page)
        if content is None or "utils.js" not in content:
            continue
        utils_pos = content.find("utils.js")
        # Find the last inline <script> block (no src= attribute)
        script_pos = -1
        for m in re.finditer(r"<script(?!\s+src=)[^>]*>", content):
            script_pos = m.start()
        if utils_pos == -1 or script_pos == -1:
            continue
        if utils_pos > script_pos:
            issues.append({
                "check": "utils_load_order",
                "page": page,
                "reason": (f"{page} loads utils.js AFTER the main <script> block — "
                           f"escHtml() is undefined when page code runs; "
                           f"move utils.js <script src> above the main <script> block")
            })
    return issues


# ── Layer 6: LIKE injection guard ─────────────────────────────────────────────

def check_esc_html_shorthand_undeclared():
    r"""Catch the bug class found in the 2026-05-13 walkthrough:
    a renderer references the `e(...)` shorthand without declaring
    `const e = escHtml` in scope, producing ReferenceError at runtime.

    Heuristic: for each `${e(` / `e(\`` callsite, walk back to find the
    nearest preceding `function` keyword (function declaration OR arrow
    function block start), then scan that function body forward for a
    declaration of `e`. This handles long functions where the declaration
    is many lines above the first use.

    Acceptable declaration patterns:
      const e = escHtml      |  let e = escHtml   |  var e = escHtml
      catch (e) / catch(e)   (so we don't flag the error-variable case)

    If no declaration found in the enclosing function, flag the line. The
    fix at the call site is one line: add `const e = escHtml;` at the top.
    """
    issues = []
    # Use of `e(...)` shorthand. Match `e(` not preceded by an identifier char
    # (excludes `name(e)`, `else`, `delete`, etc.). Allow a template-literal
    # `e(\`` or a paren-style call `e(foo`.
    use_re = re.compile(r'(?<![a-zA-Z_$])e\(\s*[`a-zA-Z_$0-9.,\'\"]')
    # Accept any declaration of `e` in scope. The QA preferred form is
    # `const e = escHtml` but engineering-design uses a custom wrapper
    # `const e = s => <editable span>${escHtml(s)}</span>` which still
    # produces safe HTML. The runtime test is "is `e` defined", not "is
    # `e` specifically the escHtml shorthand".
    decl_re = re.compile(
        r'(?:(?:const|let|var)\s+e\s*=|catch\s*\(\s*e\s*\))'
    )
    # Scope boundary: the `function` keyword only. Arrow function lambdas
    # (`l => ...`) close over their parent scope's `e` declaration, so they
    # are NOT scope boundaries for this check. Looking back to the nearest
    # `function` (named or anonymous) catches the real enclosing function
    # without false-positives on every `.map(... => ...)` callsite.
    # Require `function` as a whole word followed by `(`, `*`, or whitespace
    # + identifier so `=== 'function'` (typeof guard, string literal) and
    # `db.functions.invoke(...)` (Supabase functions namespace) are NOT
    # matched. Caught 2026-05-13 after Persona Contract added both patterns
    # inside renderer bodies on asset-hub.html.
    func_open_re = re.compile(r"\bfunction\b\s*(?:\*|\(|[A-Za-z_$])")

    for page in LIVE_PAGES:
        content = read_file(page)
        if not content:
            continue
        lines = content.splitlines()
        # Pre-scan: does the file have any top-level `const e =` declaration
        # OUTSIDE every function body? If yes, accept all callsites in this
        # file because JS closures will resolve `e` from the global scope.
        # Heuristic: any `const e = ...` line whose preceding non-empty line
        # is NOT inside a function (we approximate by checking that nesting
        # depth at that line is zero via a balanced-brace counter from the
        # start of the first `<script>` block).
        has_global_e = _has_global_e_declaration(content, decl_re)

        seen_lines = set()
        for i, line in enumerate(lines):
            if not use_re.search(line):
                continue
            if i in seen_lines:
                continue
            seen_lines.add(i)
            if has_global_e:
                continue
            # Walk back to find the nearest preceding function-open line.
            scope_start = 0
            for j in range(i - 1, -1, -1):
                if func_open_re.search(lines[j]):
                    scope_start = j
                    break
            context = "\n".join(lines[scope_start:i + 1])
            if decl_re.search(context):
                continue
            issues.append({
                "check": "esc_html_shorthand_undeclared",
                "page": page,
                "line": i + 1,
                "reason": (
                    f"{page}:{i+1} uses `e(...)` shorthand for escHtml but "
                    f"no `const e = escHtml` declaration in the enclosing "
                    f"function (scope starts at line {scope_start+1}) and "
                    f"no top-level declaration in the file. ReferenceError "
                    f"at runtime. Fix: add `const e = escHtml;` at the top "
                    f"of the function OR at the top of the script block."
                )
            })
    return issues


def _has_global_e_declaration(content, decl_re):
    """Approximate scope analysis: find any `const|let|var e = ...` line whose
    brace nesting depth (relative to the first <script> tag) is zero. That is
    a script-tag-level declaration, visible to every inner function via
    closure. Returns True if at least one is found.
    """
    script_start = content.find('<script')
    if script_start < 0:
        return False
    # Skip past the opening <script ...> tag
    open_close = content.find('>', script_start)
    if open_close < 0:
        return False
    body = content[open_close + 1:]
    depth = 0
    pos = 0
    for line in body.splitlines(keepends=True):
        if depth == 0 and decl_re.search(line):
            return True
        for ch in line:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth = max(0, depth - 1)
        pos += len(line)
    return False


def check_ilike_wildcard_escape():
    """
    Supabase `.ilike()` queries that interpolate user input with %${var}%
    must escape % and _ in the variable before use. Without escaping:
      - % in user input matches everything (returns all rows)
      - _ matches any single character (over-matches results)

    This is not SQL injection but causes incorrect and over-broad results.

    Correct pattern (confirmed in logbook.html):
        const safeSV = rawSearch.replace(/%/g, '\\\\%').replace(/_/g, '\\\\_');
        query.or(`field.ilike.%${safeSV}%,...`);

    The check: any .or( or .ilike( call with %${VAR}% interpolation where
    VAR does NOT have a preceding .replace(/%/g pattern within 20 lines.
    """
    issues = []
    for page in LIVE_PAGES:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            # Find ilike.%${ or .ilike('%${  patterns
            if not re.search(r'ilike[.(%]+%\$\{(\w+)', line):
                continue
            m = re.search(r'ilike[.(%]+%\$\{(\w+)', line)
            if not m:
                continue
            var_name = m.group(1)
            # Check if var_name has .replace(/%/g applied within 20 lines above
            look_back = max(0, i - 20)
            context = "\n".join(lines[look_back:i + 1])
            safe_pattern = re.search(
                rf'{re.escape(var_name)}\s*=.*\.replace\s*\(\s*/[%]',
                context
            )
            if not safe_pattern:
                issues.append({
                    "check": "ilike_wildcard_escape",
                    "page": page,
                    "line": i + 1,
                    "reason": (
                        f"{page}:{i+1} .ilike('%${{{var_name}}}%') — "
                        f"{var_name} must have .replace(/%/g, '\\\\%').replace(/_/g, '\\\\_') "
                        f"applied before use; % in user input returns all rows"
                    )
                })
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
    # L5
    "utils_load_order",
    # L6
    "ilike_wildcard_escape",
    # L7 (walkthrough 2026-05-13)
    "esc_html_shorthand_undeclared",
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
    # L5
    "utils_load_order":            "L5  utils.js loads before main <script> block on all pages",
    # L6
    "ilike_wildcard_escape":       "L6  .ilike('%${var}%') queries escape % and _ wildcards in user input",
    # L7
    "esc_html_shorthand_undeclared": "L7  Every `e(...)` shorthand callsite has `const e = escHtml` in scope",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nXSS / escHtml Coverage Validator (6-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_esc_html_available()
    all_issues += check_outer_html_raw()
    all_issues += check_raw_interpolation_ratio()
    all_issues += check_insert_adjacent_html()
    all_issues += check_injection_vectors()
    all_issues += check_set_attribute_event_handlers()
    all_issues += check_all_html_pages_in_scope()
    all_issues += check_utils_load_order()
    all_issues += check_ilike_wildcard_escape()
    all_issues += check_esc_html_shorthand_undeclared()

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

