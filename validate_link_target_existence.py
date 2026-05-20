"""
Link Target Existence Validator (L0, ratcheted).
=================================================
Catches the class where a page links (button, anchor, redirect) to a
.html file that no longer exists — user clicks, lands on a 404. The
worst kind of UX bug because it's invisible until someone tests it.

Detection
  Scan each of the 30 canonical pages for outgoing link targets:
    1. <a href="X.html">           — anchor tags
    2. href="X.html"               — generic href attribute
    3. location.href = 'X.html'    — JS redirect
    4. window.location.href = ...  — same
    5. window.open('X.html', ...)  — popups
    6. href: 'X.html'              — JS objects (tile config arrays)
  For each target, resolve to an absolute path inside the project root
  (relative-link resolution = same-dir).

  Filter:
    - Skip external URLs (http://, https://, mailto:, tel:)
    - Skip in-page anchors (#X)
    - Skip dynamic refs (templates, variables — we only check literal
      string ".html" suffixes)

  Flag any target whose file doesn't exist.

Allow markers
  Inline `<!-- link-allow: <reason> -->` or `// link-allow: <reason>`
  within ±200 chars of the href call. Use for legitimate "coming soon"
  placeholders (rare).

Output
  link_target_existence_report.json
  Exit 1 when broken_links > baseline; 0 otherwise.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "link_target_existence_report.json"
BASELINE_PATH = ROOT / "link_target_existence_baseline.json"


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


# Match any string literal ending in `.html` that's referenced as a link target.
# We capture the WHOLE string content; resolution happens after.
LINK_PATTERNS = [
    # <a href="X.html"> / href="X.html"
    re.compile(r"""\bhref\s*=\s*['"`](?P<target>[^'"`\s#?]+\.html(?:[?#][^'"`]*)?)['"`]"""),
    # location.href / window.location.href = 'X.html'
    re.compile(r"""(?:location|window\.location)\.href\s*=\s*['"`](?P<target>[^'"`\s#?]+\.html(?:[?#][^'"`]*)?)['"`]"""),
    # window.open('X.html', ...)
    re.compile(r"""window\.open\s*\(\s*['"`](?P<target>[^'"`\s#?]+\.html(?:[?#][^'"`]*)?)['"`]"""),
    # JS object literal: `href: 'X.html'` — common in tile config arrays
    re.compile(r"""\bhref\s*:\s*['"`](?P<target>[^'"`\s#?]+\.html(?:[?#][^'"`]*)?)['"`]"""),
]

# Allow markers — within ±200 chars of the link match
ALLOW_RE = re.compile(r"link-allow", re.IGNORECASE)


def _strip_target_query(t: str) -> str:
    """Strip ?query / #fragment so we resolve only the .html path."""
    for ch in ("?", "#"):
        if ch in t:
            t = t.split(ch, 1)[0]
    return t


def _resolve(source_page: Path, target: str) -> Path | None:
    """Resolve `target` relative to `source_page`'s directory. Returns None
    for external/protocol-relative URLs."""
    t = _strip_target_query(target).strip()
    if not t:
        return None
    if t.startswith(("http://", "https://", "//", "mailto:", "tel:", "javascript:")):
        return None
    # Absolute (starts with /) — resolve relative to project root.
    if t.startswith("/"):
        # WorkHive prod prefix `/workhive/...` resolves to project root
        if t.startswith("/workhive/"):
            t = t[len("/workhive/"):]
        else:
            t = t.lstrip("/")
        return ROOT / t
    # Relative — resolve to source page's directory.
    return source_page.parent / t


def _bold(s):   return f"\033[1m{s}\033[0m"
def _red(s):    return f"\033[91m{s}\033[0m"
def _green(s):  return f"\033[92m{s}\033[0m"
def _yellow(s): return f"\033[93m{s}\033[0m"


def main() -> int:
    per_page: list[dict] = []
    total_broken = 0
    total_links  = 0
    seen_broken: set[tuple[str, str]] = set()  # (page, target)

    for name in PAGES:
        page = ROOT / name
        if not page.exists():
            continue
        try:
            body = page.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        broken: list[dict] = []
        page_link_count = 0

        for pat in LINK_PATTERNS:
            for m in pat.finditer(body):
                target = m.group("target")
                page_link_count += 1

                # Allow window
                win = body[max(0, m.start() - 200):m.end() + 200]
                if ALLOW_RE.search(win):
                    continue

                resolved = _resolve(page, target)
                if resolved is None:
                    continue
                if not resolved.exists():
                    key = (name, target)
                    if key in seen_broken:
                        continue
                    seen_broken.add(key)
                    broken.append({
                        "target":   target,
                        "resolved": str(resolved.relative_to(ROOT)) if resolved.is_absolute() and resolved.is_relative_to(ROOT) else str(resolved),
                        "offset":   m.start(),
                    })

        per_page.append({
            "page":        name,
            "link_count":  page_link_count,
            "broken":      broken,
        })
        total_broken += len(broken)
        total_links  += page_link_count

    # Baseline ratchet
    baseline = 0
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("broken", 0)
        except Exception:
            baseline = 0
    else:
        baseline = total_broken
        BASELINE_PATH.write_text(
            json.dumps({"broken": baseline, "established": True}, indent=2),
            encoding="utf-8",
        )

    if total_broken < baseline:
        baseline = total_broken
        BASELINE_PATH.write_text(
            json.dumps({"broken": baseline, "tightened": True}, indent=2),
            encoding="utf-8",
        )

    report = {
        "summary": {
            "pages_scanned":  len(per_page),
            "total_links":    total_links,
            "total_broken":   total_broken,
            "baseline":       baseline,
        },
        "per_page": per_page,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(_bold("Link Target Existence Validator (L0)"))
    print("=" * 56)
    print(f"  pages scanned:    {len(per_page)}")
    print(f"  total .html links: {total_links}")
    print(f"  broken:           {total_broken}  (baseline: {baseline})")

    if total_broken == 0:
        print()
        print(_green("PASS — every link target exists on disk."))
        return 0

    print()
    print("Broken link targets:")
    for entry in per_page:
        if not entry["broken"]:
            continue
        print(f"  {entry['page']} ({entry['link_count']} links)")
        for b in entry["broken"]:
            print(f"    → {b['target']}  (resolves to: {b['resolved']})")

    if total_broken > baseline:
        print()
        print(_red(f"FAIL — broken {total_broken} > baseline {baseline} (new broken link introduced)"))
        print("Fix options:")
        print("  1. Update the href to the new file name.")
        print("  2. Restore the missing file or remove the link.")
        print("  3. Add `<!-- link-allow: <reason> -->` if the link is intentionally pre-launch.")
        return 1

    print()
    print(_yellow(f"At baseline ({baseline}) — punch list above; tighten by fixing one."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
