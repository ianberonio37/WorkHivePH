"""
ufai_ingest.py  —  route UFAI-battery CRITIC candidates into the sweep queue
============================================================================
The reusable battery (ufai_battery.js, run in the Playwright MCP) returns, per
page, a `critic.candidates` array of opinionated "should-be" records in the
sweep_critiques.json schema. This tool MERGES those candidates into
sweep_critiques.json so they flow through the SAME engine + disposition path as
every other sweep finding:

    sweep_critiques.json  →  flywheel_orchestrator → promotion_queue.md
                          →  you dispose via promotion_dispositions.json

Doctrine (workflows/grounded_mcp_sweep.md Phase 4.6/4.7): the engine PROPOSES,
you DISPOSE. So this tool:
  - ADDS new candidate keys only; it NEVER overwrites an existing critique
    (a key already in the file may have been hand-edited or already disposed).
  - Is idempotent: re-ingesting the same battery dump is a no-op.
  - Only routes CRITIC candidates (TASTE/CONTENT). DEFECTs are fixed INLINE by
    the agent and are deliberately NOT queued here.

Input forms (any of):
  - a full battery run() dump            → reads .critic.candidates
  - a bare critic() dump                 → reads .candidates
  - a raw list of candidate records      → used as-is

Usage:
  python ufai_ingest.py <battery_dump.json>            # merge from a file
  python ufai_ingest.py --stdin < dump.json            # merge from stdin
  python ufai_ingest.py <dump.json> --dry-run          # show what WOULD merge
"""
from __future__ import annotations
import io, sys, json, argparse, datetime
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SWEEP = ROOT / "sweep_critiques.json"
REQUIRED = ("key", "page", "title", "pillar", "severity", "flag", "should_be")


def _extract_candidates(payload) -> list[dict]:
    """Accept a run() dump, a critic() dump, or a raw list."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("critic"), dict) and "candidates" in payload["critic"]:
            return payload["critic"]["candidates"]
        if "candidates" in payload:
            return payload["candidates"]
    raise SystemExit("ERROR: could not find critic candidates in the input "
                     "(expected .critic.candidates, .candidates, or a list).")


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge UFAI-battery critic candidates into sweep_critiques.json")
    ap.add_argument("dump", nargs="?", help="battery run()/critic() JSON dump file")
    ap.add_argument("--stdin", action="store_true", help="read the dump from stdin")
    ap.add_argument("--dry-run", action="store_true", help="print the merge plan; write nothing")
    args = ap.parse_args()

    if args.stdin:
        payload = json.load(sys.stdin)
    elif args.dump:
        payload = json.loads(Path(args.dump).read_text(encoding="utf-8"))
    else:
        ap.error("provide a dump file or --stdin")

    candidates = _extract_candidates(payload)

    sweep = json.loads(SWEEP.read_text(encoding="utf-8"))
    existing = {c.get("key") for c in sweep.get("critiques", [])}

    added, skipped, invalid = [], [], []
    for c in candidates:
        if not isinstance(c, dict) or not all(k in c for k in REQUIRED):
            invalid.append(c.get("key", "<no-key>") if isinstance(c, dict) else str(c)[:40])
            continue
        if c["key"] in existing:
            skipped.append(c["key"])
            continue
        # normalize the optional fields the schema carries
        c.setdefault("wave", 0)
        c.setdefault("effort", "M")
        added.append(c)
        existing.add(c["key"])

    print(f"UFAI ingest: {len(candidates)} candidate(s) → "
          f"{len(added)} NEW · {len(skipped)} already-present · {len(invalid)} invalid")
    for k in added:
        print(f"  + {k['key']}  [{k['pillar']}/{k['severity']}/{k['flag']}]  {k['title']}")
    if invalid:
        print(f"  ! invalid (missing required fields {REQUIRED}): {invalid}")

    if args.dry_run:
        print("(--dry-run: nothing written)")
        return 0
    if not added:
        print("Nothing new to merge; sweep_critiques.json unchanged.")
        return 0

    sweep.setdefault("critiques", []).extend(added)
    sweep["generated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    SWEEP.write_text(json.dumps(sweep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(added)} new critique(s) → {SWEEP.name}. "
          f"Dispose via promotion_dispositions.json (engine proposes, you dispose).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
