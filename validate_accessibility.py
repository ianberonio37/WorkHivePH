"""
Accessibility Baseline Validator — WorkHive Platform
=====================================================
Field workers use WorkHive on mobile in industrial environments: bright
sunlight, gloves, loud background noise. Accessibility is not just legal
compliance — it is direct usability for your actual users.

  Layer 1 — Image accessibility
    1.  img alt attributes       — every static <img> must have an alt attribute

  Layer 2 — Dialog accessibility
    2.  Dialog accessible names  — role="dialog" must have aria-labelledby
    3.  Dialog aria-modal flag   — role="dialog" must have aria-modal="true"  [WARN]

  Layer 3 — Form input labels
    4.  Unlabeled form inputs    — inputs with id= must have a labeling mechanism  [WARN]

  Layer 4 — Button labeling
    5.  Buttons using title      — icon buttons must use aria-label, not title=

  Layer 5 — Dynamic content announcements
    6.  Toast aria-live          — toast containers need role="alert" aria-live="polite"

  Layer 6 — Bottom-sheet keyboard accessibility (May 2026)
    7.  Focus trap present       — pages with sheet-overlay need a trapFocus helper  [WARN]
    8.  Escape closes sheets     — pages with sheet-overlay need Escape handler  [WARN]
    9.  Toggle buttons aria-pressed — buttons that toggle .active need aria-pressed  [WARN]
    10. Status regions live      — connection chip / presence area need role=status  [WARN]

Usage:  python validate_accessibility.py
Output: accessibility_report.json
"""
import re, json, sys

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
    "nav-hub.html",
    "community.html",
    "marketplace.html",
    "marketplace-admin.html",
    "marketplace-seller.html",
    "marketplace-seller-profile.html",
    "public-feed.html",
]

LABEL_EXEMPT_TYPES = {
    "hidden", "submit", "reset", "button", "image", "file", "radio", "checkbox"
}


def _is_template_line(line):
    stripped = line.strip()
    return stripped.startswith("`") or stripped.startswith("${") or (
        stripped.startswith("<") and ("${" in stripped or "`" in stripped)
    )


# ── Layer 1: Image accessibility ─────────────────────────────────────────────

def check_img_alt(pages):
    """Every static <img> must declare alt=. Empty alt="" is fine for decorative
    images. Template-literal img tags are excluded."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "<img " not in line and "<img\t" not in line:
                continue
            if _is_template_line(line):
                continue
            if "alt=" in line:
                continue
            if re.search(r"<img\b", line) and "<!--" not in line.split("<img")[0]:
                issues.append({"check": "img_alt", "page": page, "line": i + 1,
                               "reason": (f"{page}:{i + 1} <img> missing alt attribute "
                                          f"(use alt=\"\" for decorative, alt=\"description\" for meaningful): "
                                          f"`{line.strip()[:60]}`")})
    return issues


# ── Layer 2: Dialog accessibility ────────────────────────────────────────────

def check_dialog_labels(pages):
    """role="dialog" without aria-labelledby means screen readers announce only
    "dialog" — no title, no context."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        for m in re.finditer(r'role=["\']dialog["\']', content):
            tag_start = content.rfind("<", 0, m.start())
            tag_end   = content.find(">", m.start())
            if tag_end == -1:
                continue
            tag_text  = content[tag_start:tag_end + 1]
            if "aria-labelledby" not in tag_text and "aria-label" not in tag_text:
                line_no   = content[:m.start()].count("\n") + 1
                id_m      = re.search(r'id=["\']([^"\']+)["\']', tag_text)
                dialog_id = id_m.group(1) if id_m else "unknown"
                issues.append({"check": "dialog_labels", "page": page, "line": line_no,
                               "reason": (f"{page}:{line_no} dialog '{dialog_id}' has role=\"dialog\" "
                                          f"but no aria-labelledby — screen readers announce only "
                                          f"\"dialog\" with no title when this modal opens")})
    return issues


def check_dialog_aria_modal(pages):
    """
    role="dialog" without aria-modal="true" means background content is still
    accessible to screen reader cursor. Workers using VoiceOver/TalkBack can
    tab or swipe behind the open modal, reading content they shouldn't interact
    with. aria-modal="true" tells the screen reader the dialog is the only
    active region.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        for m in re.finditer(r'role=["\']dialog["\']', content):
            tag_start = content.rfind("<", 0, m.start())
            tag_end   = content.find(">", m.start())
            if tag_end == -1:
                continue
            tag_text  = content[tag_start:tag_end + 1]
            if 'aria-modal' not in tag_text:
                line_no   = content[:m.start()].count("\n") + 1
                id_m      = re.search(r'id=["\']([^"\']+)["\']', tag_text)
                dialog_id = id_m.group(1) if id_m else "unknown"
                issues.append({"check": "dialog_aria_modal", "page": page, "line": line_no,
                               "skip": True,
                               "reason": (f"{page}:{line_no} dialog '{dialog_id}' missing aria-modal=\"true\" "
                                          f"— screen reader cursor can navigate behind the open modal; "
                                          f"add aria-modal=\"true\" to lock focus to the dialog")})
    return issues


# ── Layer 3: Form input labels (WARN) ────────────────────────────────────────

def check_unlabeled_inputs(pages):
    """Inputs/selects with id= but no <label for=>, no aria-label, and no
    placeholder are completely inaccessible to screen readers."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        labeled_ids = set(re.findall(r'<label[^>]+for=["\']([^"\']+)["\']', content))
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "<input" not in line and "<select" not in line:
                continue
            if _is_template_line(line):
                continue
            type_m = re.search(r'type=["\'](\w+)["\']', line)
            if type_m and type_m.group(1).lower() in LABEL_EXEMPT_TYPES:
                continue
            id_m = re.search(r'\bid=["\']([^"\']+)["\']', line)
            if not id_m:
                continue
            input_id = id_m.group(1)
            if (input_id not in labeled_ids
                    and "aria-label" not in line
                    and "placeholder=" not in line
                    and "title=" not in line):
                issues.append({"check": "unlabeled_inputs", "page": page,
                               "line": i + 1, "skip": True,
                               "reason": (f"{page}:{i + 1} input/select id=\"{input_id}\" has no "
                                          f"<label for=\"{input_id}\">, aria-label, or placeholder — "
                                          f"completely inaccessible to screen readers")})
    return issues


# ── Layer 4: Button labeling ──────────────────────────────────────────────────

def check_button_title_only(pages):
    """title= is not announced on touch devices. Icon-only buttons must use
    aria-label instead of title for their accessible name."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "<button" not in line or "title=" not in line:
                continue
            if "aria-label" in line or "aria-labelledby" in line:
                continue
            title_m   = re.search(r'title=["\']([^"\']+)["\']', line)
            title_val = title_m.group(1) if title_m else "?"
            stripped  = line.strip()
            if stripped.endswith(">") or stripped.endswith("/>"):
                issues.append({"check": "button_title_only", "page": page, "line": i + 1,
                               "reason": (f"{page}:{i + 1} button uses title=\"{title_val}\" as "
                                          f"its only accessible name — title is not announced on touch "
                                          f"devices; use aria-label=\"{title_val}\" instead")})
    return issues


# ── Layer 5: Dynamic content announcements ────────────────────────────────────

def check_toast_aria_live(pages):
    """
    Toast containers must have role="alert" and aria-live="polite" so screen
    readers announce the message when it appears. showToast() fires status
    updates, error messages, and confirmations — without aria-live, blind and
    low-vision workers get no feedback when they save an entry, hit an error,
    or receive an approval notification.

    Correct pattern:  <div id="toast" role="alert" aria-live="polite">
    Missing pattern:  <div id="toast">  ← silent to screen readers
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        # Find toast container elements (id="toast" or id ends with "-toast")
        for m in re.finditer(r'<div[^>]+id=["\']([^"\']*toast[^"\']*)["\'][^>]*>', content, re.IGNORECASE):
            tag_text  = m.group(0)
            toast_id  = m.group(1)
            line_no   = content[:m.start()].count("\n") + 1
            has_live  = "aria-live" in tag_text
            has_alert = 'role="alert"' in tag_text or "role='alert'" in tag_text
            if not has_live and not has_alert:
                issues.append({"check": "toast_aria_live", "page": page, "line": line_no,
                               "reason": (f"{page}:{line_no} #{toast_id} has no role=\"alert\" or aria-live — "
                                          f"showToast() messages are silent to screen readers; "
                                          f"add role=\"alert\" aria-live=\"polite\" to the toast container")})
    return issues


# ── Layer 6: Bottom-sheet keyboard accessibility (May 2026) ────────────────────

def check_focus_trap(pages):
    """Pages that have bottom-sheet UI (sheet-overlay class) need a focus-trap
    helper. Otherwise Tab from inside the sheet escapes to background nav,
    which is a WCAG 2.4.3 Focus Order failure."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if "sheet-overlay" not in content and "modal-overlay" not in content:
            continue
        has_trap = ("trapFocus" in content) or ("function trapFocus" in content)
        if not has_trap:
            issues.append({"check": "focus_trap", "skip": True,
                           "reason": (f"{page} has bottom-sheet UI but no trapFocus helper — "
                                      f"Tab from inside the sheet escapes to background nav (WCAG 2.4.3)")})
    return issues


def check_escape_closes(pages):
    """Pages with bottom-sheet UI need a document-level keydown listener that
    handles Escape so users can close the sheet without reaching for a mouse."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if "sheet-overlay" not in content and "modal-overlay" not in content:
            continue
        has_escape = bool(re.search(
            r"addEventListener\(\s*['\"]keydown['\"][^)]*\).*?Escape",
            content, re.DOTALL
        )) or "e.key === 'Escape'" in content or 'e.key === "Escape"' in content
        if not has_escape:
            issues.append({"check": "escape_closes", "skip": True,
                           "reason": (f"{page} has bottom-sheet UI but no document-level "
                                      f"Escape handler — keyboard users can't close the sheet")})
    return issues


def check_toggle_aria_pressed(pages):
    """Buttons that toggle an .active class via classList should also expose
    aria-pressed so screen readers announce the toggle state. Match: a button
    that has classList.toggle('active' or classList.add('active') near it."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        # Only flag if the page has BOTH a toggle pattern AND any button class
        # used for a toggleable widget (reaction-btn, filter-chip, tab-btn etc.)
        toggles_active = bool(re.search(r"classList\.(toggle|add)\(\s*['\"]active['\"]", content))
        if not toggles_active:
            continue
        # Look at the button class definitions used as toggleables
        toggleable_classes = ["reaction-btn", "filter-chip", "tab-btn"]
        for cls in toggleable_classes:
            if cls not in content:
                continue
            # If buttons of this class exist, at least one of them should carry aria-pressed
            cls_buttons = re.findall(
                r'<button[^>]*class="[^"]*' + re.escape(cls) + r'[^"]*"[^>]*>',
                content
            )
            cls_buttons += re.findall(
                r'class="[^"]*' + re.escape(cls) + r'[^"]*"[^>]*aria-pressed',
                content
            )
            # Heuristic: at least 50% of buttons of this class should have aria-pressed
            with_pressed = sum(1 for b in cls_buttons if "aria-pressed" in b)
            if cls_buttons and with_pressed == 0:
                issues.append({"check": "toggle_aria_pressed", "skip": True,
                               "reason": (f"{page} has toggleable .{cls} buttons that flip "
                                          f"an .active class but none declare aria-pressed — "
                                          f"screen readers don't announce the toggle state")})
                break  # one report per page is enough
    return issues


def check_status_live_region(pages):
    """Connection status indicators (conn-dot / conn-label) should sit inside a
    role="status" + aria-live region so screen readers announce online/offline
    transitions."""
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        has_conn_dot = ("conn-dot" in content) or ("conn-label" in content)
        if not has_conn_dot:
            continue
        # Find the wrapper element that contains conn-dot — does it have role=status?
        # Match within a small window (~250 chars) around the conn-dot id
        wrapper_re = re.compile(
            r'<(?:div|span)[^>]*role\s*=\s*"status"[^>]*aria-live[^>]*>[\s\S]{0,250}?conn-dot|'
            r'conn-dot[\s\S]{0,250}?role\s*=\s*"status"',
            re.DOTALL
        )
        if not wrapper_re.search(content):
            issues.append({"check": "status_live_region", "skip": True,
                           "reason": (f"{page} has a connection-status indicator (conn-dot) but "
                                      f"the surrounding container is not a role=\"status\" "
                                      f"aria-live region — connect/disconnect transitions are "
                                      f"silent to screen readers")})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "img_alt",
    "dialog_labels",
    "dialog_aria_modal",
    "unlabeled_inputs",
    "button_title_only",
    "toast_aria_live",
    "focus_trap",
    "escape_closes",
    "toggle_aria_pressed",
    "status_live_region",
]

CHECK_LABELS = {
    "img_alt":            "L1  Static <img> tags have alt attribute",
    "dialog_labels":      "L2  Dialogs (role=dialog) have aria-labelledby",
    "dialog_aria_modal":  "L2  Dialogs (role=dialog) have aria-modal=\"true\"  [WARN]",
    "unlabeled_inputs":   "L3  Form inputs with id= have a labeling mechanism  [WARN]",
    "button_title_only":  "L4  Icon buttons use aria-label, not title=",
    "toast_aria_live":    "L5  Toast containers have role=\"alert\" aria-live=\"polite\"",
    "focus_trap":         "L6  Pages with sheet-overlay have a trapFocus helper  [WARN]",
    "escape_closes":      "L6  Pages with sheet-overlay have a document Escape handler  [WARN]",
    "toggle_aria_pressed":"L6  Toggleable .active buttons declare aria-pressed  [WARN]",
    "status_live_region": "L6  Connection-status conn-dot lives in role=status aria-live  [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nAccessibility Baseline Validator (6-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_img_alt(LIVE_PAGES)
    all_issues += check_dialog_labels(LIVE_PAGES)
    all_issues += check_dialog_aria_modal(LIVE_PAGES)
    all_issues += check_unlabeled_inputs(LIVE_PAGES)
    all_issues += check_button_title_only(LIVE_PAGES)
    all_issues += check_toast_aria_live(LIVE_PAGES)
    all_issues += check_focus_trap(LIVE_PAGES)
    all_issues += check_escape_closes(LIVE_PAGES)
    all_issues += check_toggle_aria_pressed(LIVE_PAGES)
    all_issues += check_status_live_region(LIVE_PAGES)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "accessibility",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("accessibility_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
