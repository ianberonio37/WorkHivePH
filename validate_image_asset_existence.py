"""
Image / Asset Existence Validator (L0, ratcheted).
===================================================
Every `<img src="X.png">`, `<link href="X.css">`, `<script src="X.js">`,
and CSS `url('X.svg')` pointing at a LOCAL file (relative or /workhive/...)
must exist on disk. Catches dead asset references that render as broken-
image icons or 404s.

Output: image_asset_existence_report.json. Exit 1 on regression.
Allow with `<!-- asset-allow: <reason> -->` near the tag.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "image_asset_existence_report.json"
BASELINE_PATH = ROOT / "image_asset_existence_baseline.json"

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

# <img src="X">, <link href="X">, <script src="X">
ATTR_RE = re.compile(
    r"""<(?:img|link|script|source|video|audio|iframe)\b[^>]*\b(?:src|href)\s*=\s*['"`](?P<target>[^'"`\s]+)['"`]""",
    re.IGNORECASE,
)
# CSS url('X')
URL_RE = re.compile(r"""url\(\s*['"`]?(?P<target>[^'"`)\s]+)['"`]?\s*\)""", re.IGNORECASE)

ASSET_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
              ".css", ".js", ".mp4", ".webm", ".woff", ".woff2", ".ttf", ".otf"}

ALLOW_RE = re.compile(r"asset-allow", re.IGNORECASE)


def _resolve(source_page: Path, target: str) -> Path | None:
    """Resolve target relative to source. Returns None for external/dynamic."""
    t = target.strip()
    if not t: return None
    # External / protocol-relative / data URIs / hash anchors
    if t.startswith(("http://", "https://", "//", "data:", "mailto:", "tel:", "javascript:", "#", "?")):
        return None
    # Strip query/fragment
    for ch in ("?", "#"):
        if ch in t: t = t.split(ch, 1)[0]
    if not t: return None
    # Only care about local file extensions we care about
    ext = "." + t.rsplit(".", 1)[-1].lower() if "." in t else ""
    if ext not in ASSET_EXTS: return None
    # Absolute /workhive/X or /X
    if t.startswith("/workhive/"):
        return ROOT / t[len("/workhive/"):]
    if t.startswith("/"):
        return ROOT / t.lstrip("/")
    return source_page.parent / t


def main() -> int:
    per_page = []
    total_broken = 0
    total_refs = 0
    seen: set = set()

    for name in PAGES:
        page = ROOT / name
        if not page.exists(): continue
        body = page.read_text(encoding="utf-8", errors="replace")
        broken = []
        for pat in (ATTR_RE, URL_RE):
            for m in pat.finditer(body):
                target = m.group("target")
                total_refs += 1
                win = body[max(0, m.start() - 200):m.end() + 200]
                if ALLOW_RE.search(win): continue
                resolved = _resolve(page, target)
                if resolved is None: continue
                if not resolved.exists():
                    key = (name, target)
                    if key in seen: continue
                    seen.add(key)
                    try:
                        rel = resolved.relative_to(ROOT) if resolved.is_relative_to(ROOT) else resolved
                    except Exception:
                        rel = resolved
                    broken.append({"target": target, "resolved": str(rel), "offset": m.start()})
        per_page.append({"page": name, "broken": broken})
        total_broken += len(broken)

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("broken", 0)
        except Exception: baseline = 0
    else:
        baseline = total_broken
        BASELINE_PATH.write_text(json.dumps({"broken": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_broken < baseline:
        baseline = total_broken
        BASELINE_PATH.write_text(json.dumps({"broken": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"pages_scanned": len(per_page), "total_refs": total_refs,
                    "total_broken": total_broken, "baseline": baseline},
        "per_page": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nImage / Asset Existence Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(per_page)}")
    print(f"  asset refs:       {total_refs}")
    print(f"  broken:           {total_broken}  (baseline: {baseline})")
    if total_broken == 0:
        print("\n  PASS — every local asset reference resolves to a file.")
        return 0
    shown = 0
    for entry in per_page:
        if not entry["broken"]: continue
        print(f"  {entry['page']}")
        for b in entry["broken"]:
            print(f"    → {b['target']}  (resolves to: {b['resolved']})")
            shown += 1
            if shown >= 30:
                print("    ... (more in report)")
                break
        if shown >= 30: break
    return 1 if total_broken > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
