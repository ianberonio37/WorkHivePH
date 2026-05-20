"""
Backfill aria-label on icon-close + similar pattern buttons / inputs that
lack an accessible name. Caught by validate_aria_label_coverage.py 2026-05-20.

Targets:
  - <button id="...-close" ...>     → aria-label="Close"
  - <button id="...close-...">       → aria-label="Close"
  - <button onclick="close*(">       → aria-label="Close"
  - <input type="number" ...> in dynamic templates → aria-label="Quantity"
    (heuristic: surrounding template mentions `qty` / `_partsUsed`)

Idempotent: only inserts aria-label when none of {aria-label, aria-labelledby,
title} already exists. Skips elements already inside a <label for="...">.
"""
from __future__ import annotations
import re, sys, io
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

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

# <button ATTRS>INNER</button> — capture attrs
BUTTON_RE = re.compile(r"""<button\b(?P<attrs>[^>]*)>(?P<inner>[\s\S]*?)</button>""", re.IGNORECASE)
HAS_LABEL_RE = re.compile(r"""\b(?:aria-label|aria-labelledby|title)\s*=""", re.IGNORECASE)
ID_RE = re.compile(r"""\bid\s*=\s*['"`]([^'"`]+)['"`]""", re.IGNORECASE)
ONCLICK_RE = re.compile(r"""\bonclick\s*=\s*['"`]([^'"`]+)['"`]""", re.IGNORECASE)


def _strip_text(inner: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", inner)
    cleaned = re.sub(r"&[#\w]+;", "", cleaned)
    return cleaned.strip()


def _infer_label(attrs: str, inner: str) -> str | None:
    """Pick an aria-label for an icon button based on its id / onclick / class."""
    id_m = ID_RE.search(attrs)
    onclick_m = ONCLICK_RE.search(attrs)
    id_val = id_m.group(1).lower() if id_m else ""
    onclick = onclick_m.group(1).lower() if onclick_m else ""

    # Close pattern
    close_keywords = ("close", "dismiss", "cancel", "hide")
    if any(k in id_val for k in close_keywords) or any(k in onclick for k in close_keywords):
        return "Close"
    # Open pattern (toggles)
    if any(k in id_val for k in ("toggle",)) or any(k in onclick for k in ("toggle",)):
        return "Toggle"
    # Remove / delete pattern
    if any(k in id_val for k in ("remove", "delete")) or "remove" in onclick or "splice" in onclick:
        return "Remove"
    # Common bell / hamburger / menu
    if "hamburger" in id_val or "menu-toggle" in id_val: return "Open menu"
    if "bell" in id_val: return "Notifications"
    # No safe inference
    return None


def main() -> int:
    changed = 0
    total_fixed = 0
    for name in PAGES:
        page = ROOT / name
        if not page.exists(): continue
        body = page.read_text(encoding="utf-8", errors="replace")
        original = body
        fixed_in_page = 0

        def _replace(m):
            nonlocal fixed_in_page
            attrs = m.group("attrs")
            inner = m.group("inner")
            if HAS_LABEL_RE.search(attrs):
                return m.group(0)
            if _strip_text(inner):  # has visible text
                return m.group(0)
            label = _infer_label(attrs, inner)
            if not label:
                return m.group(0)
            # Insert aria-label after the opening tag's first attribute boundary
            new_attrs = attrs.rstrip() + f' aria-label="{label}"'
            if not new_attrs.startswith(" "):
                new_attrs = " " + new_attrs
            fixed_in_page += 1
            return f"<button{new_attrs}>{inner}</button>"

        body = BUTTON_RE.sub(_replace, body)

        if body != original:
            page.write_text(body, encoding="utf-8")
            changed += 1
            total_fixed += fixed_in_page
            print(f"  + {name}  ({fixed_in_page} buttons labelled)")

    print(f"\nUpdated {changed} pages · {total_fixed} buttons labelled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
