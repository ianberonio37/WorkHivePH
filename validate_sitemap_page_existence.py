"""
Sitemap Page Existence Validator (L0, ratcheted).
===================================================
Every <loc>...</loc> URL in sitemap.xml must resolve to a real file
on disk. Search engines get a 404, lose trust, deindex the page.

Output: sitemap_page_existence_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path
from urllib.parse import urlparse

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "sitemap_page_existence_report.json"
BASELINE_PATH = ROOT / "sitemap_page_existence_baseline.json"

LOC_RE = re.compile(r"<loc>(?P<url>[^<]+)</loc>", re.IGNORECASE)


def _resolve(url: str) -> Path | None:
    p = urlparse(url)
    path = (p.path or "/").strip()
    if path == "/" or path == "":
        return ROOT / "index.html"
    path = path.lstrip("/")
    if path.startswith("workhive/"):
        path = path[len("workhive/"):]
    if not path: return ROOT / "index.html"
    candidate = ROOT / path
    if candidate.is_dir():
        candidate = candidate / "index.html"
    # If no extension, try .html
    if "." not in candidate.name:
        candidate = candidate.with_suffix(".html")
    return candidate


def main() -> int:
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.exists():
        print("PASS — no sitemap.xml at root.")
        return 0
    body = sitemap.read_text(encoding="utf-8", errors="replace")
    urls = [m.group("url").strip() for m in LOC_RE.finditer(body)]

    broken = []
    for u in urls:
        resolved = _resolve(u)
        if resolved is None: continue
        if not resolved.exists():
            try:
                rel = resolved.relative_to(ROOT) if resolved.is_relative_to(ROOT) else resolved
            except Exception:
                rel = resolved
            broken.append({"url": u, "resolved": str(rel)})

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("broken", 0)
        except Exception: baseline = 0
    else:
        baseline = len(broken)
        BASELINE_PATH.write_text(json.dumps({"broken": baseline, "established": True}, indent=2), encoding="utf-8")
    if len(broken) < baseline:
        baseline = len(broken)
        BASELINE_PATH.write_text(json.dumps({"broken": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"total_urls": len(urls), "total_broken": len(broken), "baseline": baseline},
        "broken": broken,
    }, indent=2), encoding="utf-8")

    print(f"\nSitemap Page Existence Validator (L0)")
    print("=" * 56)
    print(f"  sitemap URLs:     {len(urls)}")
    print(f"  broken:           {len(broken)}  (baseline: {baseline})")
    if not broken:
        print("\n  PASS — every sitemap.xml URL resolves to a file.")
        return 0
    for b in broken[:20]:
        print(f"  {b['url']}  → {b['resolved']}")
    return 1 if len(broken) > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
