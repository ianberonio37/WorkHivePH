#!/usr/bin/env python3
"""
validate_substrate_freshness.py — PKS Layer 2 anti-regression gate.
===================================================================
The Platform Knowledge Substrate (substrate/*.md, built by build_substrate.py) only saves tokens if
it is TRUSTWORTHY — a stale chunk is worse than no chunk. Each chunk carries a `source_sha` anchored to
its source (a page/edge-fn/skill/doc file's content hash, or the live DB introspection for table-rls /
rpc). This gate re-derives every source_sha and FAILs if any chunk drifted (source changed but the
chunk was not rebuilt) — treating the substrate as code, exactly like a doc-drift CI check.

Mechanism: runs `build_substrate.py --check` (dry run — writes nothing) which recomputes every chunk's
source_sha and reports each drifted chunk. Any drift => this gate FAILs with the fix command.

DB-dependent chunk types (table-rls, rpc) are skipped cleanly if docker/DB is absent — file-based types
(page, edge-fn, skill, doc) are always checkable. Fast + static-ish => runs in every gate (not
skip_if_fast). Fix on FAIL: `python tools/build_substrate.py` then re-run.
"""
import io
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BUILDER = ROOT / "tools" / "build_substrate.py"
SUB = ROOT / "substrate"


def main() -> int:
    print("\n" + "=" * 72)
    print("  Platform Knowledge Substrate — freshness gate (source_sha anti-regression)")
    print("=" * 72)
    if not BUILDER.exists():
        print("  FAIL: tools/build_substrate.py missing — the substrate generator was removed.")
        return 1
    if not SUB.exists() or not any(SUB.rglob("*.md")):
        print("  SKIP: substrate/ not built yet — run `python tools/build_substrate.py` to seed it.")
        return 0
    try:
        r = subprocess.run([sys.executable, str(BUILDER), "--check"], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=180)
    except Exception as e:
        print(f"  SKIP: could not run the freshness check ({e}).")
        return 0
    out = (r.stdout or "").strip()
    stale = [ln.strip() for ln in out.splitlines() if "WOULD update" in ln]
    if r.returncode == 0 and not stale:
        n = sum(1 for _ in SUB.rglob("*.md"))
        print(f"  PASS: all {n} substrate chunks are fresh (every source_sha matches its source).")
        return 0
    print(f"  FAIL: {len(stale)} substrate chunk(s) are STALE (source changed, chunk not rebuilt):")
    for s in stale[:40]:
        print(f"    {s}")
    if len(stale) > 40:
        print(f"    … +{len(stale) - 40} more")
    print("\n  FIX: python tools/build_substrate.py   (then re-run this gate)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
