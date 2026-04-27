"""
Accessibility Baseline Validator — WorkHive Platform
=====================================================
Field workers use WorkHive on mobile in industrial environments: bright
sunlight, gloves, loud background noise. Accessibility is not just legal
compliance — it is direct usability for your actual users.

Four things checked:

  1. img alt attributes      — every static <img> tag must have an alt
                               attribute. Missing alt means screen readers
                               announce "image" with no context, and broken
                               image links show nothing. Empty alt="" is
                               acceptable for decorative images — it must
                               be explicit.

  2. Dialog accessible names — every element with role="dialog" must have
                               aria-labelledby pointing to its title element.
                               Without it, screen readers announce only
                               "dialog" when the modal opens — the worker
                               has no idea what it's for.

  3. Unlabeled form inputs   — <input> and <select> elements with an id=
                               but no matching <label for=...>, no aria-label,
                               and no placeholder have zero labeling mechanism.
                               Screen readers cannot identify the field at all.
                               Reported as WARN (placeholder is partial credit).

  4. Buttons using title     — the title= attribute is NOT accessible on touch
                               devices and is unreliable on screen readers.
                               Buttons that rely on title for their accessible
                               name must use aria-label instead.

Usage:  python validate_accessibility.py
Output: accessibility_report.json
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
    "nav-hub.html",
]

# Input types that don't need visible labels
LABEL_EXEMPT_TYPES = {
    "hidden", "submit", "reset", "button", "image", "file", "radio", "checkbox"
}


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def is_template_literal_line(line):
    """Heuristic: lines inside JS template literals start with backtick context."""
    stripped = line.strip()
    return stripped.startswith("`") or stripped.startswith("${") or (
        stripped.startswith("<") and (
            "${" in stripped or "`" in stripped
        )
    )


# ── Check 1: img tags missing alt attribute ───────────────────────────────────

def check_img_alt(pages):
    """
    Every static <img> tag must have an alt attribute.
    - alt="" is fine for decorative images (explicitly empty)
    - alt="description" is required for meaningful images
    - No alt at all = screen reader announces "image" with filename or nothing

    Template literal img tags (inside JS strings) are excluded — those are
    dynamically generated and harder to validate statically.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "<img " not in line and "<img\t" not in line:
                continue
            if is_template_literal_line(line):
                continue
            if "alt=" in line:
                continue
            # Confirm it's actually an img tag opening (not a comment)
            if re.search(r"<img\b", line) and "<!--" not in line.split("<img")[0]:
                issues.append({
                    "page": page,
                    "line": i + 1,
                    "code": line.strip()[:80],
                    "reason": (
                        f"{page}:{i + 1} — <img> missing alt attribute "
                        f"(use alt=\"\" for decorative, alt=\"description\" for meaningful): "
                        f"`{line.strip()[:60]}`"
                    ),
                })
    return issues


# ── Check 2: role="dialog" missing aria-labelledby ───────────────────────────

def check_dialog_labels(pages):
    """
    Modal dialogs must announce their title when they open.
    role="dialog" with aria-modal="true" is correct, but without
    aria-labelledby the screen reader just says "dialog" — no name,
    no context. aria-labelledby should point to the modal's title element.

    Fix:
      <div role="dialog" aria-modal="true" aria-labelledby="my-modal-title">
        <h2 id="my-modal-title">Modal Title Here</h2>
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        for m in re.finditer(r'role=["\']dialog["\']', content):
            # Get the full opening tag (within 200 chars)
            tag_start = content.rfind("<", 0, m.start())
            tag_end   = content.find(">", m.start())
            if tag_end == -1:
                continue
            tag_text = content[tag_start:tag_end + 1]
            if "aria-labelledby" not in tag_text and "aria-label" not in tag_text:
                line_no = content[:m.start()].count("\n") + 1
                # Extract the dialog id if present
                id_m = re.search(r'id=["\']([^"\']+)["\']', tag_text)
                dialog_id = id_m.group(1) if id_m else "unknown"
                issues.append({
                    "page":      page,
                    "dialog_id": dialog_id,
                    "line":      line_no,
                    "reason": (
                        f"{page}:{line_no} — dialog '{dialog_id}' has role=\"dialog\" "
                        f"but no aria-labelledby — screen readers announce only "
                        f"\"dialog\" with no title when this modal opens"
                    ),
                })
    return issues


# ── Check 3: Form inputs with no labeling mechanism (WARN) ───────────────────

def check_unlabeled_inputs(pages):
    """
    Inputs and selects with an id= should have a matching <label for=...>.
    If there's no label, aria-label, aria-labelledby, or placeholder, the
    field is completely inaccessible to screen readers.

    This checks for inputs/selects that have an id= but NO corresponding
    <label for="that-id"> anywhere in the file. Placeholder-only inputs
    are imperfect (placeholder disappears on focus) but acceptable for now.

    Reported as WARN because placeholder provides partial accessibility.
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        # Collect all label for= values in the file
        labeled_ids = set(re.findall(r'<label[^>]+for=["\']([^"\']+)["\']', content))

        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "<input" not in line and "<select" not in line:
                continue
            if is_template_literal_line(line):
                continue

            # Skip exempt types
            type_m = re.search(r'type=["\'](\w+)["\']', line)
            if type_m and type_m.group(1).lower() in LABEL_EXEMPT_TYPES:
                continue

            # Get the input's id
            id_m = re.search(r'\bid=["\']([^"\']+)["\']', line)
            if not id_m:
                continue   # no id — can't check label pairing
            input_id = id_m.group(1)

            # Check labeling mechanisms
            has_label       = input_id in labeled_ids
            has_aria_label  = "aria-label" in line
            has_placeholder = "placeholder=" in line
            has_title       = "title=" in line

            if not has_label and not has_aria_label and not has_placeholder and not has_title:
                issues.append({
                    "page":     page,
                    "input_id": input_id,
                    "line":     i + 1,
                    "reason": (
                        f"{page}:{i + 1} — input/select id=\"{input_id}\" has no "
                        f"<label for=\"{input_id}\">, aria-label, or placeholder — "
                        f"completely inaccessible to screen readers"
                    ),
                })
    return issues


# ── Check 4: Buttons using title instead of aria-label ───────────────────────

def check_button_title_only(pages):
    """
    The title= attribute is NOT accessible on touch screens (no hover) and
    is inconsistently supported across screen readers. Buttons that use title=
    as their only accessible name must switch to aria-label=.

    This matters most for icon-only buttons (SVG icons, symbol buttons) where
    title= is often added as a "tooltip" but doesn't actually help screen reader
    or mobile users.

    Safe pattern:   <button aria-label="Notifications">...</button>
    Unsafe pattern: <button title="Notifications">...</button>
    """
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "<button" not in line:
                continue
            if 'title=' not in line:
                continue
            # Only flag if there's no aria-label on this line AND no visible text
            if "aria-label" in line or "aria-labelledby" in line:
                continue
            # Extract the title value for the report
            title_m = re.search(r'title=["\']([^"\']+)["\']', line)
            title_val = title_m.group(1) if title_m else "?"
            # Only flag if it looks like an icon button (no obvious text content)
            # Simple heuristic: line ends with > and title is the only label
            stripped = line.strip()
            if stripped.endswith(">") or stripped.endswith("/>"):
                issues.append({
                    "page":  page,
                    "line":  i + 1,
                    "title": title_val,
                    "reason": (
                        f"{page}:{i + 1} — button uses title=\"{title_val}\" as "
                        f"its only accessible name — title is not announced on touch "
                        f"devices or reliably by screen readers: "
                        f"use aria-label=\"{title_val}\" instead"
                    ),
                })
    return issues


# ── Main ──────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("\n" + "=" * 70)
print("Accessibility Baseline Validator")
print("=" * 70)

fail_count = 0
warn_count = 0
report     = {}

checks = [
    (
        "[1] Static <img> tags have alt attribute",
        check_img_alt(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[2] Dialogs (role=dialog) have aria-labelledby",
        check_dialog_labels(LIVE_PAGES),
        "FAIL",
    ),
    (
        "[3] Form inputs with id= have a labeling mechanism",
        check_unlabeled_inputs(LIVE_PAGES),
        "WARN",
    ),
    (
        "[4] Buttons use aria-label instead of title for accessible name",
        check_button_title_only(LIVE_PAGES),
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

with open("accessibility_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("Saved accessibility_report.json")

if fail_count:
    print("\nFIX REQUIRED.")
    sys.exit(1)
print("\nAll accessibility checks PASS.")
