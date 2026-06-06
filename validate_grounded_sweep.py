"""
Grounded MCP Sweep — Self-Coverage Validator (Standing Rule D for the sweep).
============================================================================
The Grounded MCP Sweep (workflows/grounded_mcp_sweep.md) drives each page LIVE,
fixes root-cause bugs, and CRYSTALLIZES each fix into a live regression lock (a
journey-*.spec.ts assertion). The risk after the fact is silent erosion: a page
is marked done in the roadmap, but its crystallized lock gets renamed, deleted,
or never actually existed — so the gate quietly stops guarding what the sweep
fixed.

This meta-validator closes that loop. It is the sweep's analogue of
validate_c_track_self_coverage.py — Standing Rule D ("a guard must justify its
existence or be retired") applied to the sweep itself:

  1. The sweep's own stack is intact (SOP + worksheet template + roadmap +
     critique queue + this manifest all present).
  2. EVERY page marked done in GROUNDED_SWEEP_ROADMAP.md has a lock entry in
     grounded_sweep_locks.json.
  3. EACH lock's spec file exists AND still contains its marker string (the
     freshness anchor — a rename/delete of the crystallized assertion wakes
     this check before the regression guard can silently vanish).

Why this makes the sweep a first-class part of the self-improving mega gate:
the sweep stops being a one-off ritual whose guards can rot, and becomes a
ratchet the gate self-polices every run.

Exit codes:
  0  sweep stack intact + every done page has a live lock that still asserts it.
  1  a done page has no lock, a lock's spec is missing, or its marker vanished.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

ROADMAP   = ROOT / "GROUNDED_SWEEP_ROADMAP.md"
MANIFEST  = ROOT / "grounded_sweep_locks.json"

# The sweep's own load-bearing stack — if any of these vanish, the method itself
# has eroded.
STACK = [
    ("sop",            "workflows/grounded_mcp_sweep.md"),
    ("worksheet",      "workflows/grounded_mcp_sweep_page_template.md"),
    ("roadmap",        "GROUNDED_SWEEP_ROADMAP.md"),
    ("critique_queue", "SWEEP_CRITIQUE_QUEUE.md"),
    ("locks_manifest", "grounded_sweep_locks.json"),
]

DONE_MARK = "☑"  # ☑


def _done_pages(roadmap_text: str) -> list[str]:
    """Every page marked done in the roadmap progress table. A 'done' row carries
    the ☑ glyph AND a backticked `<page>.html`; the first such page on the line is
    the primary swept page (sub-pages are swept with their parent). The status
    legend line carries ☑ but no backticked page, so it is naturally excluded."""
    pages: list[str] = []
    for line in roadmap_text.splitlines():
        if DONE_MARK not in line:
            continue
        m = re.search(r"`([a-z0-9][a-z0-9\-]*\.html)`", line)
        if m:
            pages.append(m.group(1))
    # de-dup preserving order
    seen, out = set(), []
    for p in pages:
        if p not in seen:
            seen.add(p); out.append(p)
    return out


def main() -> int:
    errors: list[tuple[str, str]] = []
    ok: list[str] = []

    # 1. Sweep stack intact.
    for key, rel in STACK:
        if (ROOT / rel).exists():
            ok.append(f"stack:{key}")
        else:
            errors.append((f"stack:{key}", f"missing {rel}"))

    # Load manifest (fatal if absent/malformed — the whole check rides on it).
    locks: dict = {}
    if MANIFEST.exists():
        try:
            locks = (json.loads(MANIFEST.read_text(encoding="utf-8")) or {}).get("locks", {})
        except Exception as e:
            errors.append(("manifest", f"parse error: {e}"))
    # (a missing manifest is already reported by the STACK loop)

    # 2 + 3. Every done page has a lock whose spec exists + still asserts it.
    if ROADMAP.exists():
        done = _done_pages(ROADMAP.read_text(encoding="utf-8"))
        if not done:
            errors.append(("roadmap", "no done (☑) pages parsed — roadmap table format may have changed"))
        for page in done:
            lock = locks.get(page)
            if not lock:
                errors.append((f"lock:{page}", "page is marked done in the roadmap but has NO entry in "
                                               "grounded_sweep_locks.json — its crystallized guard is untracked"))
                continue
            spec_rel = lock.get("spec", "")
            marker   = lock.get("marker", "")
            spec_path = ROOT / spec_rel
            if not spec_path.exists():
                errors.append((f"lock:{page}", f"lock spec missing: {spec_rel}"))
                continue
            spec_text = spec_path.read_text(encoding="utf-8")
            if marker and marker not in spec_text:
                errors.append((f"lock:{page}", f"marker '{marker}' no longer in {spec_rel} — the "
                                               f"crystallized assertion was renamed/removed"))
                continue
            ok.append(f"lock:{page} ({spec_rel})")
    else:
        errors.append(("roadmap", "GROUNDED_SWEEP_ROADMAP.md missing"))

    bar = "=" * 70
    print(bar)
    if errors:
        print(f"\033[91mFAIL\033[0m  Grounded-sweep self-coverage: {len(errors)} problem(s)")
        for item, why in errors:
            print(f"  - {item:<26s}  {why}")
        print(bar)
        print("  Fix: add/repair the page's lock in grounded_sweep_locks.json, or restore")
        print("       the crystallized assertion (its marker) in the named journey spec.")
        return 1
    print(f"\033[92mOK\033[0m  Grounded-sweep self-coverage: {len(ok)} items intact.")
    print(f"  {len(STACK)} stack files | {len(locks)} page locks | every done page guarded.")
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
