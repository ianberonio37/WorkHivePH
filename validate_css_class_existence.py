"""
CSS Class Existence Validator (L0, ratcheted).
================================================
Every `classList.add('X')` / `classList.remove('X')` / `classList.toggle('X')`
must have a corresponding CSS rule defined somewhere (in the page's
<style> blocks or shared stylesheets). Catches the class where a CSS
rule was renamed/removed but JS still toggles the old class — JS runs
without error but UI doesn't change.

Output: css_class_existence_report.json. Exit 1 on regression.
Allow with `// css-class-allow: <reason>` near the call.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "css_class_existence_report.json"
BASELINE_PATH = ROOT / "css_class_existence_baseline.json"

PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "engineering-design.js", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

# JS classList ops. Captures the literal first-arg string. We then check
# whether the call is followed by ` + ` (concat) — if so, the literal is
# a prefix/suffix for a dynamic class and we skip (validator can't resolve
# the runtime value of the concatenated variable).
CLASSLIST_RE = re.compile(
    r"""\bclassList\.(?:add|remove|toggle|replace)\(\s*['"`](?P<cls>[\w-]+)['"`](?P<tail>\s*[+,)])""",
)
# Tailwind utility classes — never need a custom CSS rule. We accept any
# class that LOOKS like a Tailwind utility (prefix:size, with hyphens,
# common prefixes).
TAILWIND_PREFIXES = {
    "text", "bg", "border", "rounded", "p", "px", "py", "pl", "pr", "pt", "pb",
    "m", "mx", "my", "ml", "mr", "mt", "mb", "w", "h", "min", "max",
    "flex", "grid", "block", "inline", "absolute", "relative", "fixed",
    "static", "hidden", "shadow", "opacity", "transition", "transform",
    "rotate", "scale", "translate", "duration", "delay", "ease",
    "font", "leading", "tracking", "gap", "items", "justify", "content",
    "z", "top", "bottom", "left", "right", "inset", "overflow", "object",
    "ring", "outline", "cursor", "select", "pointer", "resize", "list",
    "appearance", "table", "col", "row", "self", "place", "order",
    "space", "divide", "uppercase", "lowercase", "capitalize", "truncate",
    "underline", "italic", "antialiased", "sr",
}
TAILWIND_BASIC = {"container", "group", "peer"}

# CSS rule selectors — extract `.classname` from <style> blocks AND .css files.
# Match `.X` anywhere (including compound selectors like `.simple-card.tag-green`).
# Previous lookbehind variants either missed chained class names or stopped at
# the first one. Inside CSS-only contexts (style blocks, .css files), the
# false-positive risk from things like `1.5rem` is filtered because the
# class-name char class requires the first char to be `[a-zA-Z_]`.
CSS_CLASS_REF_RE = re.compile(r"""\.([a-zA-Z_][\w-]*)""")
STYLE_BLOCK_RE = re.compile(r"""<style\b[^>]*>(?P<body>[\s\S]*?)</style>""", re.IGNORECASE)

ALLOW_RE = re.compile(r"css-class-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def _gather_known_classes() -> set[str]:
    """Classes defined in any <style> block on any page or any *.css file."""
    classes: set[str] = set()
    # CSS files in root
    for css in sorted(ROOT.glob("*.css")):
        body = css.read_text(encoding="utf-8", errors="replace")
        # Strip /* ... */ comments
        body = re.sub(r"/\*[\s\S]*?\*/", "", body)
        for m in CSS_CLASS_REF_RE.finditer(body):
            classes.add(m.group(1))
    # <style> blocks per page (also pick up classes used in same-page styles)
    for name in PAGES:
        p = ROOT / name
        if not p.exists(): continue
        raw = p.read_text(encoding="utf-8", errors="replace")
        for sm in STYLE_BLOCK_RE.finditer(raw):
            body = re.sub(r"/\*[\s\S]*?\*/", "", sm.group("body"))
            for m in CSS_CLASS_REF_RE.finditer(body):
                classes.add(m.group(1))
    return classes


def _is_tailwind(cls: str) -> bool:
    """Treat as Tailwind utility if matches common utility patterns."""
    if cls in TAILWIND_BASIC: return True
    # Modifier prefix: `hover:`, `focus:`, `md:` — not relevant here since
    # classList.add() rarely uses prefixed responsive variants. Skip.
    # Underscore-numeric (e.g. `mt-2`, `text-xl`, `border-orange-wh`)
    parts = cls.split("-")
    if not parts: return False
    if parts[0] in TAILWIND_PREFIXES: return True
    return False


# Sentinel binding: name the L2 test `test('css_class_existence: ...')` for coverage credit.
CHECK_NAMES = ["css_class_existence"]


def main() -> int:
    known = _gather_known_classes()

    per_page = []
    total_calls = 0
    total_missing = 0
    seen: set = set()

    for name in PAGES:
        page = ROOT / name
        if not page.exists(): continue
        body = HTML_COMMENT_RE.sub("", page.read_text(encoding="utf-8", errors="replace"))
        misses = []
        for m in CLASSLIST_RE.finditer(body):
            cls = m.group("cls")
            tail = m.group("tail").strip()
            total_calls += 1
            # Dynamic concat — the literal is a prefix/suffix; can't resolve
            # the runtime full class name. Skip.
            if tail == "+":
                continue
            if cls in known: continue
            if _is_tailwind(cls): continue
            # Wide window — typical "block comment above .classList call"
            # placement puts the marker ~300-400 chars upstream.
            win = body[max(0, m.start() - 500):m.end() + 200]
            if ALLOW_RE.search(win): continue
            key = (name, cls)
            if key in seen: continue
            seen.add(key)
            misses.append({"class": cls, "offset": m.start()})
        per_page.append({"page": name, "missing": misses})
        total_missing += len(misses)

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("missing", 0)
        except Exception: baseline = 0
    else:
        baseline = total_missing
        BASELINE_PATH.write_text(json.dumps({"missing": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_missing < baseline:
        baseline = total_missing
        BASELINE_PATH.write_text(json.dumps({"missing": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"pages_scanned": len(per_page), "total_calls": total_calls,
                    "total_missing": total_missing, "baseline": baseline,
                    "css_classes_known": len(known)},
        "per_page": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nCSS Class Existence Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(per_page)}")
    print(f"  classlist calls:  {total_calls}")
    print(f"  css classes:      {len(known)}")
    print(f"  missing:          {total_missing}  (baseline: {baseline})")
    if total_missing == 0:
        print("\n  PASS — every classList.add/remove/toggle class has a CSS rule.")
        return 0
    shown = 0
    for entry in per_page:
        if not entry["missing"]: continue
        print(f"  {entry['page']}")
        for m in entry["missing"]:
            print(f"    → classList.*('{m['class']}')  — no CSS rule for .{m['class']}")
            shown += 1
            if shown >= 20:
                print("    ... (more in report)")
                break
        if shown >= 20: break
    return 1 if total_missing > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
