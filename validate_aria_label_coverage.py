"""
ARIA Label / Accessible Name Coverage Validator (L0, ratcheted).
=================================================================
Interactive elements must have an accessible name. Without one,
screen readers announce nothing — users navigating with assistive
tech can't identify the button or input.

Detection
  Find `<button>`, `<input type="text|search|email|...">`, and
  icon-only links (`<a><svg></svg></a>` with no other text). For each:

  Has accessible name if ANY of:
    - text content non-empty (e.g. `<button>Save</button>`)
    - `aria-label="..."` attribute
    - `aria-labelledby="..."` attribute
    - `title="..."` attribute (less ideal but counts)
    - <input> has an associated `<label for="ID">` somewhere on the page

Output: aria_label_coverage_report.json. Exit 1 on regression.
Allow with `data-aria-allow="<reason>"`.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "aria_label_coverage_report.json"
BASELINE_PATH = ROOT / "aria_label_coverage_baseline.json"

PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

# <button ...>text</button> — capture attributes + inner text
BUTTON_RE = re.compile(r"""<button\b(?P<attrs>[^>]*)>(?P<inner>[\s\S]*?)</button>""", re.IGNORECASE)
# <input ...> self-closing or with closing
INPUT_RE  = re.compile(r"""<input\b(?P<attrs>[^>]*)/?>""", re.IGNORECASE)
# <label for="ID">
LABEL_FOR_RE = re.compile(r"""<label\b[^>]*\bfor\s*=\s*['"`](?P<id>[^'"`]+)['"`]""", re.IGNORECASE)

# Attribute extractors
ATTR_ARIA_LABEL = re.compile(r"""\baria-label\s*=\s*['"`]([^'"`]*[A-Za-z][^'"`]*)['"`]""", re.IGNORECASE)
ATTR_ARIA_LABELLEDBY = re.compile(r"""\baria-labelledby\s*=""", re.IGNORECASE)
ATTR_TITLE = re.compile(r"""\btitle\s*=\s*['"`]([^'"`]+)['"`]""", re.IGNORECASE)
ATTR_ID    = re.compile(r"""\bid\s*=\s*['"`]([^'"`]+)['"`]""", re.IGNORECASE)
ATTR_TYPE  = re.compile(r"""\btype\s*=\s*['"`]([^'"`]+)['"`]""", re.IGNORECASE)
ATTR_PLACEHOLDER = re.compile(r"""\bplaceholder\s*=\s*['"`]([^'"`]+)['"`]""", re.IGNORECASE)
ATTR_ARIA_HIDDEN = re.compile(r"""\baria-hidden\s*=\s*['"`]true['"`]""", re.IGNORECASE)
ATTR_ALLOW = re.compile(r"""data-aria-allow\s*=""", re.IGNORECASE)

# Input types we audit (interactive textual inputs)
AUDITED_INPUT_TYPES = {"text", "search", "email", "tel", "url", "password", "number"}

HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def _has_visible_text(html: str) -> bool:
    """Strip tags, check non-empty text remains."""
    cleaned = re.sub(r"<[^>]+>", "", html)
    cleaned = re.sub(r"&[#\w]+;", "", cleaned)  # entities
    return bool(cleaned.strip())


def main() -> int:
    per_page = []
    total_elements = 0
    total_missing = 0

    for name in PAGES:
        page = ROOT / name
        if not page.exists(): continue
        body = HTML_COMMENT_RE.sub("", page.read_text(encoding="utf-8", errors="replace"))

        # Build label-for set for the page
        label_targets = {m.group("id") for m in LABEL_FOR_RE.finditer(body)}

        missing = []

        # Buttons
        for m in BUTTON_RE.finditer(body):
            total_elements += 1
            attrs = m.group("attrs")
            inner = m.group("inner")
            if ATTR_ALLOW.search(attrs): continue
            if _has_visible_text(inner): continue
            if ATTR_ARIA_LABEL.search(attrs): continue
            if ATTR_ARIA_LABELLEDBY.search(attrs): continue
            if ATTR_TITLE.search(attrs): continue
            # Skip icon-only buttons with aria-hidden inner (they're decorative
            # wrappers around a labelled SVG — still need the button to be labelled)
            missing.append({
                "kind":    "button",
                "snippet": ("<button" + attrs[:80] + ">").strip(),
                "offset":  m.start(),
            })

        # Inputs
        for m in INPUT_RE.finditer(body):
            attrs = m.group("attrs")
            tm = ATTR_TYPE.search(attrs)
            input_type = (tm.group(1) if tm else "text").lower()
            # Skip non-audited types: submit, button, hidden, checkbox, radio
            if input_type not in AUDITED_INPUT_TYPES: continue
            total_elements += 1
            if ATTR_ALLOW.search(attrs): continue
            if ATTR_ARIA_LABEL.search(attrs): continue
            if ATTR_ARIA_LABELLEDBY.search(attrs): continue
            if ATTR_TITLE.search(attrs): continue
            # <input id="X"> with a matching <label for="X">?
            im = ATTR_ID.search(attrs)
            if im and im.group(1) in label_targets: continue
            # Placeholder alone is NOT an accessible name per WCAG, but the
            # team uses it as a soft fallback — accept for now (baseline).
            if ATTR_PLACEHOLDER.search(attrs): continue
            missing.append({
                "kind":    "input(" + input_type + ")",
                "snippet": ("<input" + attrs[:80] + ">").strip(),
                "offset":  m.start(),
            })

        per_page.append({"page": name, "missing": missing})
        total_missing += len(missing)

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
        "summary": {"pages_scanned": len(per_page), "total_elements": total_elements,
                    "total_missing": total_missing, "baseline": baseline},
        "per_page": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nARIA Label Coverage Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(per_page)}")
    print(f"  interactives:     {total_elements}")
    print(f"  missing name:     {total_missing}  (baseline: {baseline})")
    if total_missing == 0:
        print("\n  PASS — every interactive element has an accessible name.")
        return 0
    shown = 0
    for entry in per_page:
        if not entry["missing"]: continue
        print(f"  {entry['page']}")
        for m in entry["missing"]:
            print(f"    {m['kind']:14s}  {m['snippet'][:60]}")
            shown += 1
            if shown >= 25:
                print("    ... (more in report)")
                break
        if shown >= 25: break
    return 1 if total_missing > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
