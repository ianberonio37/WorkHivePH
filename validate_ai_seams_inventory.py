"""
AI Seams Inventory Validator (C4 Phase 1 of SELF_IMPROVING_GATE_ROADMAP.md).
=============================================================================
Forward-only ratchet on the AI seams catalog produced by
`tools/mine_ai_seams.py`. The catalog is the source of truth for the
boundaries where "per-domain green ≠ system green":
  - saas→ai : a SaaS surface depends on an AI verdict.
  - ai→ai   : cross-AI orchestration call.
  - ai→tenant : an AI fn reads/writes hive-scoped data (RLS boundary).
  - ai→quota  : an AI fn imports rate-limit / cost-log helpers.

This validator re-mines on every run and compares the FRESH catalog to
the committed baseline. The policy mirrors `migration_hashes.json`:

  - new seam appeared (catalog count exceeds baseline) -> FAIL: the
    committer must `python tools/mine_ai_seams.py` and commit the
    updated catalog, owning the new boundary explicitly.
  - seam disappeared (catalog count below baseline)    -> INFO: a
    surface was decommissioned; baseline lowers on the next mine.
  - counts match                                       -> PASS.

That's all the discipline Phase 1 needs. Phase 2a will add per-seam
contract-test wiring (a `contract_test:` field on each seam, ratcheted
toward 100% coverage). Phase 2b's meta-gate consumes the catalog to
decide blast radius (e.g. an AI-eval-regression blocks a deploy only if
the PR touches a `saas→ai` seam).

Exit codes:
  0  catalog matches baseline (counts equal per kind), or baseline absent
     (first run records it silently).
  1  new seams appeared without a catalog commit.
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
MINER = ROOT / "tools" / "mine_ai_seams.py"
CATALOG = ROOT / "ai_seams_catalog.json"
BASELINE = ROOT / "ai_seams_baseline.json"

CHECK_NAMES = ["ai_seams_inventory"]

# P3 freshness anchors — wake this validator if the miner or its catalog
# fields move, so the validator can't quietly drift from the source.
FRESHNESS_ANCHORS = [
    ("tools/mine_ai_seams.py", r"AI_FNS\s*=\s*\{", "AI_FNS list moved; rewire."),
    ("tools/mine_ai_seams.py", r"by_kind",         "Catalog schema field moved; rewire baseline read."),
]


def main() -> int:
    if not MINER.exists():
        print(f"\033[91mFAIL: {MINER} missing — cannot mine AI seams\033[0m")
        return 2
    proc = subprocess.run(
        [sys.executable, "-u", str(MINER)],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        print(f"\033[91mFAIL: miner exited {proc.returncode}\033[0m")
        return proc.returncode
    if not CATALOG.exists():
        print(f"\033[91mFAIL: catalog {CATALOG.name} not written by miner\033[0m")
        return 2
    try:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"\033[91mFAIL: catalog parse error: {e}\033[0m")
        return 2
    by_kind = catalog.get("_meta", {}).get("by_kind", {})
    total = catalog.get("_meta", {}).get("seam_count", 0)

    if not BASELINE.exists():
        baseline = {
            "_meta": {
                "description": "C4 Phase 1 — frozen seam counts per kind. Forward-only ratchet (new seams require catalog commit).",
            },
            "seam_count": total,
            "by_kind":    dict(by_kind),
        }
        BASELINE.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\033[96mFIRST RUN\033[0m — baselined seam_count={total} per kind: {dict(by_kind)}")
        return 0

    try:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"\033[91mFAIL: baseline parse error: {e}\033[0m")
        return 2

    base_by_kind = baseline.get("by_kind", {})
    base_total = baseline.get("seam_count", 0)

    new_seams: list[str] = []
    fewer_seams: list[str] = []
    for k in ("saas→ai", "ai→ai", "ai→tenant", "ai→quota"):
        cur = int(by_kind.get(k, 0))
        prev = int(base_by_kind.get(k, 0))
        if cur > prev:
            new_seams.append(f"{k}: +{cur-prev} ({prev} -> {cur})")
        elif cur < prev:
            fewer_seams.append(f"{k}: -{prev-cur} ({prev} -> {cur})")

    if new_seams:
        print(f"\033[91mFAIL\033[0m  AI seams inventory grew without baseline update:")
        for n in new_seams:
            print(f"  + {n}")
        print(f"\n  Fix: review the new seam(s) in {CATALOG.name}, then commit both the catalog")
        print(f"        and an updated baseline by deleting {BASELINE.name} and re-running.")
        print(f"        (A new seam is a new contract surface that needs a test owner.)")
        return 1

    if fewer_seams:
        print(f"\033[96mINFO\033[0m  AI seams inventory shrank (surface decommissioned?):")
        for f in fewer_seams:
            print(f"  - {f}")
        print(f"        Baseline auto-lowers on the next clean run if this is intended.")

    print(f"\033[92mOK\033[0m  AI seams inventory: {total} seams (baseline {base_total}) — per-kind {dict(by_kind)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
