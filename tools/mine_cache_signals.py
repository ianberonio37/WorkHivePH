"""
Cache / CDN Substrate Miner (Maturity Phase 2, 2026-06-16).
============================================================
Closes the (CA, G-1.5) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4.

The Caching & CDN layer spans three cache tiers (study §2): CDN edge
(`_headers`), the LLM response cache (`ai_cache` via `cached()`), and the PWA
service-worker shell (`sw.js`). This miner surfaces the SHAPE of all three so
the (CA, GH) hit-rate ratchet and (CA, GS) invalidation sentinel have a
substrate to measure:

  - CDN: _headers Cache-Control coverage (does static get a cache policy?)
  - LLM cache: count of edge fns calling cached() / importing _shared/cache.ts
  - SW shell: CACHE_NAME + SHELL_FILES count (the precache set)

Inputs:  _headers, sw.js, supabase/functions/*/index.ts
Output:  cache_signals_report.json
Exit code: 0 (informational miner)
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
HEADERS = ROOT / "_headers"
SW = ROOT / "sw.js"
FN_DIR = ROOT / "supabase" / "functions"
REPORT = ROOT / "cache_signals_report.json"

CHECK_NAMES = ["cache_signals"]

CACHE_NAME_RE = re.compile(r"const\s+CACHE_NAME\s*=\s*['\"]([^'\"]+)['\"]")
SHELL_FILES_RE = re.compile(r"const\s+SHELL_FILES\s*=\s*\[([\s\S]*?)\];")


def main() -> int:
    # --- CDN edge: _headers Cache-Control coverage ---
    cdn_rules = 0
    cdn_present = HEADERS.exists()
    if cdn_present:
        htext = HEADERS.read_text(encoding="utf-8", errors="replace")
        cdn_rules = len(re.findall(r"(?i)Cache-Control\s*:", htext))

    # --- SW shell ---
    cache_name, shell_count = None, 0
    if SW.exists():
        stext = SW.read_text(encoding="utf-8", errors="replace")
        m = CACHE_NAME_RE.search(stext)
        cache_name = m.group(1) if m else None
        ms = SHELL_FILES_RE.search(stext)
        if ms:
            shell_count = len(re.findall(r"['\"][./][^'\"\n]+['\"]", ms.group(1)))

    # --- LLM response cache adopters ---
    cache_adopters: list[str] = []
    if FN_DIR.exists():
        for entry in sorted(FN_DIR.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            idx = entry / "index.ts"
            if not idx.exists():
                continue
            t = idx.read_text(encoding="utf-8", errors="replace")
            if re.search(r"\bcached\s*\(", t) or "_shared/cache.ts" in t:
                cache_adopters.append(entry.name)

    out = {
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cdn": {"headers_present": cdn_present, "cache_control_rules": cdn_rules},
        "sw_shell": {"cache_name": cache_name, "shell_files": shell_count},
        "llm_cache": {"adopters": sorted(cache_adopters), "adopter_count": len(cache_adopters)},
    }
    REPORT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"Cache-signals miner:")
    print(f"  CDN _headers: {'present' if cdn_present else 'MISSING'}, {cdn_rules} Cache-Control rule(s)")
    print(f"  SW shell: CACHE_NAME={cache_name}, {shell_count} precached files")
    print(f"  LLM cache adopters: {len(cache_adopters)} ({', '.join(cache_adopters) or 'none'})")
    print(f"  See: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
