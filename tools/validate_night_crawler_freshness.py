#!/usr/bin/env python3
"""
validate_night_crawler_freshness.py — Night Crawler external-substrate staleness gate.
======================================================================================
The Night Crawler (tools/night_crawler.py) distills external web sources into durable
`substrate/external/*.md` chunks. Unlike the INTERNAL substrate (page/edge-fn/table-rls),
whose source_sha can be hash-re-derived from local files, an external chunk's source lives
on the public web and DRIFTS silently — the distilled facts can go stale.

This gate reports every external chunk whose age exceeds its own `ttl_days` (default 30) so
staleness is SURFACED, then hands the fix command (`night_crawler.py --refresh-stale`).

NON-BLOCKING BY DESIGN: external staleness is expected and must never break a commit or the
platform build, so this gate ALWAYS exits 0. It reports; it never fails. (Registered
severity: warn, skip_if_fast: True.) Run it standalone to see what needs a re-crawl:
    python tools/validate_night_crawler_freshness.py
"""
from __future__ import annotations

import io
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
EXTERNAL = ROOT / "substrate" / "external"
DEFAULT_TTL_DAYS = 30


def _frontmatter(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    if not txt.startswith("---"):
        return {}
    end = txt.find("\n---", 3)
    if end == -1:
        return {}
    fm: dict = {}
    for line in txt[3:end].splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def _age_days(fm: dict) -> int | None:
    stamp = fm.get("fetched_at") or (fm.get("last_verified", "") + "T00:00:00Z")
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None


def main() -> int:
    print("\n" + "=" * 72)
    print("  Night Crawler — external-substrate freshness (non-blocking staleness report)")
    print("=" * 72)
    if not EXTERNAL.exists() or not any(EXTERNAL.glob("*.md")):
        print("  SKIP: substrate/external/ not seeded yet — the Night Crawler has crawled nothing.")
        return 0

    chunks = sorted(EXTERNAL.glob("*.md"))
    stale: list[tuple[str, int, int]] = []
    unknown: list[str] = []
    for path in chunks:
        fm = _frontmatter(path)
        ttl = int(fm.get("ttl_days", DEFAULT_TTL_DAYS) or DEFAULT_TTL_DAYS)
        age = _age_days(fm)
        if age is None:
            unknown.append(path.name)
        elif age > ttl:
            stale.append((path.name, age, ttl))

    fresh = len(chunks) - len(stale) - len(unknown)
    print(f"  {len(chunks)} external chunk(s): {fresh} fresh, {len(stale)} stale, "
          f"{len(unknown)} undated.")
    if stale:
        print("\n  STALE (age > ttl_days) — re-crawl to refresh the distilled facts:")
        for name, age, ttl in sorted(stale, key=lambda t: -t[1]):
            print(f"    • {name}  ({age}d old, ttl {ttl}d)")
        print("\n  FIX: python tools/night_crawler.py --refresh-stale")
    if unknown:
        print(f"\n  UNDATED (no parseable fetched_at): {', '.join(unknown[:10])}")
    if not stale and not unknown:
        print("  PASS: every external chunk is within its freshness window.")
    # Always non-blocking: staleness of external knowledge is expected, never a build failure.
    return 0


if __name__ == "__main__":
    sys.exit(main())
