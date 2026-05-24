"""
RAG Flywheel Processor (post-walk gap-closer)
==============================================
Reads the latest .tmp/rag_observations_turn_<N>.jsonl, diffs observations
against the canonical_sources registry, and:

  - AUTO-APPLIES   canonical_sources INSERTs for tiles with no existing
                   anchor (per the user's locked decision 2026-05-21).
  - AUTO-GENERATES new L0 ratchets in validate_rag_flywheel_locks.py for
                   tiles that observed a passing checker (locks the win).
  - QUEUES        proposed Layer 2 spec deltas to
                   .tmp/flywheel_turn_<N>_l2_review.md  for human review
                   before they land in the test suite.

Writes a per-turn markdown report to flywheel_turn_<N>_report.md and
extends MEMORY.md via the standard project entry pattern.

Usage:
  python tools/rag_flywheel_processor.py            # dry: classify gaps, no writes
  python tools/rag_flywheel_processor.py --commit   # auto-apply seeds + L0 ratchets

Env (only when --commit):
  SUPABASE_URL                 = http://127.0.0.1:54321  (local default)
  SUPABASE_SERVICE_ROLE_KEY    = sb_secret_*             (local secret key)
"""

from __future__ import annotations
import os
import sys
import json
import argparse
import glob
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional


TMP_DIR        = Path(".tmp")
LOCKS_FILE     = Path("validate_rag_flywheel_locks.py")
MEMORY_DIR     = Path(
    os.path.expanduser("~/.claude/projects/c--Users-ILBeronio-Desktop-Industry-4-0-AI-Maintenance-Engineer-Self-learning-Road-Map-Build---Sell-with-Claude-Code-Website-simple-1st/memory")
)


def lazy_imports():
    try:
        import requests  # noqa: F401
    except ImportError:
        print("FAIL: install requests (pip install requests)")
        sys.exit(2)


def find_latest_turn() -> Optional[int]:
    files = list(TMP_DIR.glob("rag_observations_turn_*.jsonl"))
    nums = []
    for f in files:
        m = re.match(r"rag_observations_turn_(\d+)\.jsonl", f.name)
        if m: nums.append(int(m.group(1)))
    return max(nums) if nums else None


def load_observations(turn: int) -> List[Dict[str, Any]]:
    p = TMP_DIR / f"rag_observations_turn_{turn}.jsonl"
    if not p.exists(): return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def fetch_canonical_sources(url: str, key: str) -> Dict[str, Dict[str, Any]]:
    """Return {domain: row} for existing canonical_sources rag-tile rows.
    Key by domain because canonical_sources PRIMARY KEY = domain.
    Per-tile uniqueness: domain = 'ui_kpi_tile:rag_tile:<page>:<tile_key>'.
    Schema: domain, source_kind, source_name, owner_skill, freshness, contract, description, notes."""
    import requests
    try:
        r = requests.get(
            f"{url}/rest/v1/canonical_sources?select=*&domain=like.ui_kpi_tile:*&limit=1000",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=20,
        )
        if r.status_code != 200:
            print(f"WARN: canonical_sources fetch failed HTTP {r.status_code} body={r.text[:120]}")
            return {}
        return {row["domain"]: row for row in r.json() if row.get("domain")}
    except Exception as err:
        print(f"WARN: canonical_sources fetch threw {err}")
        return {}


def infer_source_from_ai(ai_answer: str) -> Optional[str]:
    """Best-effort: scan the AI's answer for a v_*_truth or table name."""
    if not ai_answer: return None
    m = re.search(r"\b(v_[a-z_]+_truth)\b", ai_answer)
    if m: return m.group(1)
    m = re.search(r"\b(logbook|pm_completions|asset_nodes|inventory_items|amc_briefings|asset_risk_scores)\b", ai_answer)
    if m: return m.group(1)
    return None


def seed_canonical(url: str, key: str, source_name: str, source_table: Optional[str], notes: str) -> bool:
    """INSERT a new canonical_sources row for a discovered rag-tile.
    Schema: domain, source_kind, source_name, owner_skill, freshness, contract, description, notes.
    source_kind CHECK = view|table|rpc|column.
    PK is `domain` — must be unique per tile, so encode tile identity in domain:
        domain = 'ui_kpi_tile:rag_tile:<page>:<tile_key>'
    Older runs used domain='ui_kpi_tile' which collided on every subsequent insert,
    silently dropping the row under resolution=ignore-duplicates (turn 24 bug fix)."""
    import requests
    # Only seed when we actually know the source (AI inferred it). Without a
    # source, registering an UI-tile alias adds noise without value.
    if not source_table:
        return False
    kind = "view" if source_table.startswith("v_") else "table"
    payload = {
        "domain":       f"ui_kpi_tile:{source_name}",          # unique-per-tile to satisfy PK
        "source_kind":  kind,
        "source_name":  source_table,                          # the actual data source, not the tile alias
        "owner_skill":  "frontend",
        "freshness":    "live",
        "contract":     f"surfaced via {source_name}",         # which UI tile binds to it
        "description":  notes[:500],
        "notes":        "auto-seeded by RAG flywheel processor",
    }
    try:
        r = requests.post(
            f"{url}/rest/v1/canonical_sources",
            headers={
                "apikey":        key,
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json",
                "Prefer":        "return=minimal,resolution=ignore-duplicates",
            },
            data=json.dumps(payload),
            timeout=20,
        )
        if r.status_code in (200, 201, 204):
            return True
        print(f"WARN: seed {source_name} -> HTTP {r.status_code}: {r.text[:120]}")
        return False
    except Exception as err:
        print(f"WARN: seed {source_name} threw {err}")
        return False


def write_l0_locks(turn: int, observed: List[Dict[str, Any]], existing_locks: set) -> int:
    """Append per-tile invariants to validate_rag_flywheel_locks.py. Each
    tile that observed a checker-passing answer gets a 'must-pass' lock."""
    new_locks: List[Dict[str, str]] = []
    for obs in observed:
        if obs.get("mode") != "real": continue
        key = obs.get("tile_key", "")
        if not key or key in existing_locks: continue
        # Lock the win: this tile must keep returning a checker-passing answer on subsequent walks.
        new_locks.append({
            "tile_key":   key,
            "page":       obs.get("page", ""),
            "label":      obs.get("tile_label", ""),
            "ai_route":   obs.get("ai_route", "?"),
            "first_seen": f"turn {turn}",
        })

    if not new_locks: return 0

    # If locks file doesn't exist yet, scaffold it.
    if not LOCKS_FILE.exists():
        LOCKS_FILE.write_text(_scaffold_locks_file(), encoding="utf-8")

    # Splice new lock entries into TILE_LOCKS dict.
    # Must insert BEFORE the dict's CLOSING brace, not before the first
    # inner `{` (which would land inside the first entry's value).
    # Use regex anchored on the next-line-only "}" that terminates the dict literal.
    src = LOCKS_FILE.read_text(encoding="utf-8")
    marker_re = re.compile(r"TILE_LOCKS\s*:\s*dict\s*=\s*\{(.*?)\n\}", re.DOTALL)
    m = marker_re.search(src)
    if not m:
        print("WARN: TILE_LOCKS marker not found in locks file; skipping write")
        return 0
    block = ""
    for lk in new_locks:
        block += f'    "{lk["tile_key"]}": {{"page": "{lk["page"]}", "label": "{lk["label"]}", "first_seen": "{lk["first_seen"]}", "route": "{lk["ai_route"]}"}},\n'
    # Re-render the whole TILE_LOCKS body: existing inner content + new block
    inner = m.group(1)
    if inner and not inner.endswith("\n"):
        inner = inner + "\n"
    new_body = f"TILE_LOCKS: dict = {{{inner}{block}}}"
    new_src = src[:m.start()] + new_body + src[m.end():]
    LOCKS_FILE.write_text(new_src, encoding="utf-8")
    return len(new_locks)


def _scaffold_locks_file() -> str:
    return '''"""
RAG Flywheel — per-tile L0 locks (auto-generated by rag_flywheel_processor.py)
============================================================================
Each entry is a tile that the walk has observed answering a grounding-probe
question with checker_passed=true at least once. The validator REQUIRES the
locked tile attribute to still be present on its page (regression catches
deletions). It does NOT re-run the AI question on every CI run — the walk
spec does that on its own cadence.

Generated entries: do not hand-edit. Append via tools/rag_flywheel_processor.py.
"""

from __future__ import annotations
import os, sys, re

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


# {tile_key: {"page": "...", "label": "...", "first_seen": "turn N", "route": "..."}}
TILE_LOCKS: dict = {
}


def check_locked_tiles_present() -> list[dict]:
    issues = []
    for tile_key, meta in TILE_LOCKS.items():
        page_file = meta.get("page", "") + ".html"
        if not os.path.isfile(page_file):
            issues.append({"check": "page_exists", "reason": f"locked page missing: {page_file} (tile {tile_key})"})
            continue
        src = read_file(page_file) or ""
        needle = f'data-rag-tile="{tile_key}"'
        if needle not in src:
            issues.append({"check": "tile_present", "reason": f"locked tile attribute missing: {needle} in {page_file}"})
    return issues


CHECKS = [
    ("tile_present", "RAG flywheel tile-lock invariants (auto-generated)", check_locked_tiles_present),
]


def main() -> int:
    print("\\033[1m\\nRAG Flywheel L0 Locks Validator\\033[0m")
    print("=" * 60)
    print(f"  Locked tiles: {len(TILE_LOCKS)}")
    all_issues = []
    keys = [c[0] for c in CHECKS]
    labels = {c[0]: c[1] for c in CHECKS}
    for key, _label, fn in CHECKS:
        for issue in fn():
            issue.setdefault("check", key)
            all_issues.append(issue)
    n_pass, n_skip, n_fail = format_result(keys, labels, all_issues)
    print()
    if n_fail == 0:
        print(f"  \\033[92mAll {n_pass} checks passed.\\033[0m")
    else:
        print(f"  \\033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
'''


def existing_locked_tiles() -> set:
    if not LOCKS_FILE.exists(): return set()
    src = LOCKS_FILE.read_text(encoding="utf-8")
    # Match keys like "analytics:oee": { ... — return just the key string, not the prefix tuple.
    keys = re.findall(r'"([a-z0-9_-]+:[a-z0-9_]+)"\s*:\s*\{', src)
    return set(keys)


def write_l2_review_queue(turn: int, observed: List[Dict[str, Any]]) -> Path:
    """Build a markdown queue of proposed L2 spec assertions for human review.
    Per [[feedback-local-first-never-push-prod]] AND the user's locked decision,
    canonicals + L0 are auto-applied but L2 spec changes go through human review."""
    out = TMP_DIR / f"flywheel_turn_{turn}_l2_review.md"
    lines = [
        f"# RAG Flywheel Turn {turn} — Proposed Layer 2 spec deltas",
        "",
        "Each block below is a candidate assertion to add to a Playwright journey",
        "spec. The walk has CONFIRMED checker_passed=true for these tiles — locking",
        "them with an L2 assertion ratchets the win so a future regression fails CI.",
        "",
        "Review, edit, copy into the relevant tests/journey-*.spec.ts file, then",
        "delete this queue file. Skip any that don't make sense to lock.",
        "",
        "---",
        "",
    ]
    by_page: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for obs in observed:
        if obs.get("mode") != "real": continue
        if obs.get("ai_checker_passed") is True:
            by_page[obs["page"]].append(obs)

    if not any(by_page.values()):
        lines.append("_No checker-passing tiles this turn — nothing to lock at L2._\n")
    else:
        for page, items in sorted(by_page.items()):
            lines.append(f"## `{page}` ({len(items)} candidate locks)\n")
            for obs in items:
                lines.append(f"### `{obs['tile_key']}` — {obs['tile_label']}")
                lines.append(f"- **Probe question**: {obs.get('question', '')}")
                lines.append(f"- **Observed value**: `{obs.get('displayed_value', '')}`")
                lines.append(f"- **AI route**: `{obs.get('ai_route', '?')}` | retries={obs.get('ai_retries', '?')} | tokens={obs.get('ai_total_tokens', '?')} | latency={obs.get('ai_latency_ms', '?')}ms")
                lines.append(f"- **AI answer** (first 200 chars): {obs.get('ai_answer', '')[:200]}")
                cites = obs.get('ai_citations', []) or []
                lines.append(f"- **AI citations**: {len(cites)} — " + ", ".join(c.get('chunk_id', '?') for c in cites[:3]))
                lines.append("")
                lines.append("**Suggested L2 assertion** (paste into journey-flywheel-locks.spec.ts):")
                lines.append("```ts")
                lines.append(f"test('{obs['page']} :: {obs['tile_key']} answers with checker pass', async ({{ whPage }}) => {{")
                lines.append(f"  await whPage.goto('/workhive/{obs['page']}.html'); await waitForPageReady(whPage);")
                lines.append(f"  const tile = whPage.locator('[data-rag-tile=\"{obs['tile_key']}\"]');")
                lines.append(f"  await expect(tile).toBeVisible();")
                lines.append(f"  // Optionally probe agentic-rag-loop and assert grader_passed/checker_passed.")
                lines.append(f"}});")
                lines.append("```")
                lines.append("")
            lines.append("---\n")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def build_report(turn: int, observed: List[Dict[str, Any]], gaps: Dict[str, Any], commits: Dict[str, int]) -> Path:
    out = Path(f"flywheel_turn_{turn}_report.md")
    total = len(observed)
    real = [o for o in observed if o.get("mode") == "real"]
    dry  = [o for o in observed if o.get("mode") == "dry"]
    checker_pass = [o for o in real if o.get("ai_checker_passed") is True]
    grader_pass  = [o for o in real if o.get("ai_grader_passed") is True]
    cited        = [o for o in real if (o.get("ai_citation_count") or 0) > 0]
    avg_latency  = round(sum(o.get("ai_latency_ms", 0) or 0 for o in real) / max(len(real), 1), 1)
    avg_tokens   = round(sum(o.get("ai_total_tokens", 0) or 0 for o in real) / max(len(real), 1), 1)
    by_page      = Counter(o["page"] for o in observed)
    by_route     = Counter((o.get("ai_route") or "n/a") for o in real)

    lines = [
        f"# RAG Flywheel — Turn {turn} report",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Walk metrics",
        f"- Tiles observed   : **{total}** ({len(real)} real / {len(dry)} dry)",
        f"- Pages walked     : {len(by_page)} ({', '.join(f'{k}={v}' for k,v in sorted(by_page.items()))})",
        f"- Routes used      : {dict(by_route) if by_route else 'n/a (dry run)'}",
        f"- Avg latency      : {avg_latency} ms",
        f"- Avg tokens       : {avg_tokens}",
        "",
        "## Convergence metrics",
        f"- Grader pass rate    : **{round(len(grader_pass) / max(len(real), 1) * 100, 1)}%** ({len(grader_pass)}/{len(real)})",
        f"- Checker pass rate   : **{round(len(checker_pass) / max(len(real), 1) * 100, 1)}%** ({len(checker_pass)}/{len(real)})",
        f"- Citation coverage   : {round(len(cited) / max(len(real), 1) * 100, 1)}% ({len(cited)}/{len(real)} tiles had ≥1 citation)",
        "",
        "## Gaps found",
        f"- Tiles missing canonical anchor      : **{len(gaps.get('missing_anchor', []))}**",
        f"- Tiles with checker FAIL (need work) : **{len(gaps.get('checker_failed', []))}**",
        f"- Tiles with zero citations           : **{len(gaps.get('no_citations', []))}**",
        "",
        "## Auto-actions taken",
        f"- canonical_sources INSERTed : **{commits.get('canonicals_seeded', 0)}**",
        f"- New L0 tile locks added    : **{commits.get('l0_locks_added', 0)}**",
        f"- L2 review queue            : `.tmp/flywheel_turn_{turn}_l2_review.md` (manual review per locked decision)",
        "",
    ]
    if gaps.get("checker_failed"):
        lines += ["## Tiles needing work (checker failed)", ""]
        for g in gaps["checker_failed"]:
            lines.append(f"- `{g['page']}::{g['tile_key']}` — value={g.get('displayed_value','?')} — AI answer: _{g.get('ai_answer','')[:120]}_")
        lines.append("")
    if gaps.get("missing_anchor"):
        lines += ["## Tiles missing canonical anchor (auto-seeded above if --commit)", ""]
        for g in gaps["missing_anchor"]:
            lines.append(f"- `rag_tile:{g['page']}:{g['tile_key'].split(':',1)[-1]}` — inferred source: `{g.get('inferred_source','TBD')}`")
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Process the latest RAG flywheel walk observations")
    ap.add_argument("--turn", type=int, help="Process a specific turn (default: latest)")
    ap.add_argument("--commit", action="store_true", help="Apply auto-seeds + L0 locks (default: dry-run report only)")
    args = ap.parse_args()

    turn = args.turn or find_latest_turn()
    if not turn:
        print("FAIL: no rag_observations_turn_*.jsonl found in .tmp/")
        return 1
    print(f"\033[1mRAG Flywheel Processor — turn {turn}\033[0m")

    observed = load_observations(turn)
    if not observed:
        print(f"FAIL: empty observations file for turn {turn}")
        return 1
    print(f"  Loaded {len(observed)} observations")

    url = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    # Identify gaps
    gaps: Dict[str, List[Dict[str, Any]]] = {"missing_anchor": [], "checker_failed": [], "no_citations": []}
    existing: Dict[str, Any] = {}
    if args.commit:
        lazy_imports()
        if not key:
            print("FAIL: SUPABASE_SERVICE_ROLE_KEY required for --commit")
            return 2
        existing = fetch_canonical_sources(url, key)
        print(f"  Existing canonical_sources rag_tile rows: {len(existing)}")

    for obs in observed:
        source_name = f"rag_tile:{obs.get('tile_key', '')}"
        domain_key  = f"ui_kpi_tile:{source_name}"   # matches seed_canonical's domain encoding
        if domain_key not in existing:
            obs["inferred_source"] = infer_source_from_ai(obs.get("ai_answer", ""))
            gaps["missing_anchor"].append({**obs, "scope_key": source_name})
        if obs.get("mode") == "real":
            # Treat non-200 AI responses (rate-limit, timeout, server-side fail) as checker_failed.
            # An AI that couldn't even respond is the strongest signal of a gap.
            if obs.get("ai_checker_passed") is False or (obs.get("ai_status") not in (None, 200)):
                gaps["checker_failed"].append(obs)
            if (obs.get("ai_citation_count") or 0) == 0 and obs.get("ai_status") == 200:
                gaps["no_citations"].append(obs)

    commits = {"canonicals_seeded": 0, "l0_locks_added": 0}

    if args.commit:
        # Auto-seed canonical anchors
        for g in gaps["missing_anchor"]:
            ok = seed_canonical(
                url, key,
                source_name  = g["scope_key"],
                source_table = g.get("inferred_source"),
                notes        = f"Auto-seeded by RAG flywheel turn {turn} from page={g['page']} label={g.get('tile_label','')}",
            )
            if ok: commits["canonicals_seeded"] += 1

        # Auto-generate L0 tile locks for tiles that passed checker
        existing_keys = existing_locked_tiles()
        commits["l0_locks_added"] = write_l0_locks(turn, observed, existing_keys)

    # L2 review queue (always written — humans gate it)
    l2_path = write_l2_review_queue(turn, observed)
    report_path = build_report(turn, observed, gaps, commits)

    print()
    print(f"  REPORT  : {report_path}")
    print(f"  L2 QUEUE: {l2_path}")
    print(f"  Canonicals seeded: {commits['canonicals_seeded']}  L0 locks added: {commits['l0_locks_added']}")
    print(f"  Gaps — missing-anchor: {len(gaps['missing_anchor'])}  checker-fail: {len(gaps['checker_failed'])}  no-citations: {len(gaps['no_citations'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
