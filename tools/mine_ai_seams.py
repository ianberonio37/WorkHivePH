"""
mine_ai_seams.py — C4 Phase 1 of SELF_IMPROVING_GATE_ROADMAP.md.
==================================================================
Catalogs the **AI seams** in the codebase: the call sites where a SaaS
surface depends on an AI verdict, or where an AI function crosses into
tenant data / billing / quota. These are the surfaces where "per-domain
green ≠ system green" (roadmap §8 note 4) — a seam bug passes both
domain gates individually and breaks the composition.

This is the *catalog* layer (analogous to L-1 miners like
`mine_canonical_registry.py`). It does NOT enforce anything; it produces
the inventory that:
  (a) Phase 2a consumes to write seam contract tests,
  (b) Phase 2b consumes for the meta-gate's composition policy
      ("this PR touches the SaaS→AI seam → AI eval regression applies"),
  (c) `validate_ai_seams_inventory.py` ratchets forward-only on so a
      *new* seam can't sneak in without a contract-test owner.

Seam kinds tracked today:
  saas→ai    A SaaS-domain page / edge fn calls an AI-domain edge fn.
             (E.g. logbook.html → ai-gateway.)
  ai→ai      An AI edge fn invokes another AI edge fn.
             (E.g. agentic-rag-loop → ai-gateway.)
  ai→tenant  An AI edge fn reads/writes a per-hive table.
             (Detected via supabase.from('<hive-scoped table>') inside
             an AI fn — RLS boundary.)
  ai→quota   An AI edge fn imports/uses the rate-limit or cost-log
             helpers. (Billing/quota boundary.)

`ai_fns` is hardcoded — it's a small, stable list. Add to AI_FNS when a
new edge function whose primary purpose is AI inference ships.

Output: `ai_seams_catalog.json` (sorted by seam_id for stable diffs).
"""
from __future__ import annotations
import io, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCTIONS_DIR = ROOT / "supabase" / "functions"
CATALOG_PATH = ROOT / "ai_seams_catalog.json"

# Edge functions whose primary purpose is AI inference / orchestration.
# Anything not in this list is treated as SaaS-domain.
AI_FNS = {
    "ai-gateway",
    "ai-orchestrator",
    "ai-eval-runner",
    "agentic-rag-loop",
    "agent-memory-store",
    "amc-orchestrator",
    "analytics-orchestrator",
    "asset-brain-query",
    "engineering-bom-sow",
    "engineering-calc-agent",
    "failure-signature-scan",
    "fmea-populator",
    "hierarchical-summarizer",
    "intelligence-report",
    "project-orchestrator",
    "semantic-fact-extractor",
    "shift-planner-orchestrator",
    "temporal-rag-orchestrator",
    "voice-action-router",
    "voice-embeddings",
    "voice-journal-agent",
    "voice-logbook-entry",
    "voice-report-intent",
    "voice-semantic-rag",
    "walkthrough-analyzer",
    "visual-defect-capture",
    "equipment-label-ocr",
    "cold-archive-query",
    "pdf-ingest",
    "data-fabric-normalizer",
    "embed-entry",
    "batch-risk-scoring",
    "scheduled-agents",
}

# Files to skip (test runs, generated reports, etc.)
SKIP_PARTS = {
    ".tmp", ".playwright-mcp", "node_modules", ".venv", "test-runs",
    "tests", "playwright-report",
}


_FN_CALL_RE = re.compile(r"/functions/v1/([a-z0-9][a-z0-9-]*)")


def is_skipped(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def edge_fn_name(p: Path) -> str | None:
    """Return the edge-fn directory name if p is inside supabase/functions/<fn>/, else None."""
    try:
        rel = p.relative_to(FUNCTIONS_DIR)
    except ValueError:
        return None
    parts = rel.parts
    if not parts or parts[0].startswith("_"):
        return None  # _shared etc.
    return parts[0]


def scan_invoke_seams() -> list[dict]:
    """Walk HTML/JS/TS files; record every /functions/v1/<ai-fn> call site."""
    seams: list[dict] = []
    seen: set[tuple] = set()
    for path in ROOT.rglob("*"):
        if not path.is_file() or is_skipped(path):
            continue
        if path.suffix.lower() not in {".html", ".js", ".ts", ".tsx", ".mjs"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for ln, line in enumerate(text.splitlines(), 1):
            for m in _FN_CALL_RE.finditer(line):
                callee = m.group(1)
                if callee not in AI_FNS:
                    continue
                caller_fn = edge_fn_name(path)
                if caller_fn is None:
                    kind = "saas→ai"
                    caller = str(path.relative_to(ROOT).as_posix())
                elif caller_fn == callee:
                    continue  # self-reference; skip
                elif caller_fn in AI_FNS:
                    kind = "ai→ai"
                    caller = caller_fn
                else:
                    kind = "saas→ai"
                    caller = caller_fn
                key = (kind, caller, callee)
                if key in seen:
                    continue
                seen.add(key)
                seams.append({
                    "id":       f"{kind}/{caller}→{callee}",
                    "kind":     kind,
                    "caller":   caller,
                    "callee":   callee,
                    "file":     str(path.relative_to(ROOT).as_posix()),
                    "line":     ln,
                    "evidence": line.strip()[:140],
                })
    return seams


_RATE_LIMIT_IMPORT_RE = re.compile(r"from\s+['\"][^'\"]*_shared/rate-limit\.ts['\"]")
_COST_LOG_IMPORT_RE   = re.compile(r"from\s+['\"][^'\"]*_shared/cost-log\.ts['\"]")
_SUPABASE_FROM_RE     = re.compile(r"\.from\(\s*['\"]([a-z_][a-z0-9_]*)['\"]\s*\)")
# Tables/views likely to be per-hive (heuristic — tightened against the
# actual AI-fn surface: see `.from()` audit. Patterns:
#   v_*_truth                       - canonical truth views (all hive-scoped via RLS)
#   voice_*                         - voice-companion per-hive tables
#   canonical_*                     - canonical period summaries / sources
#   agentic_rag_*                   - RAG trace tables
#   agent_*                         - episodic/conversational memory
#   <explicit list of known tables>
_HIVE_SCOPED_RE = re.compile(
    r"^("
    r"v_[a-z0-9_]+_truth|"
    r"voice_[a-z0-9_]+|"
    r"canonical_[a-z0-9_]+|"
    r"agentic_rag_[a-z0-9_]+|"
    r"agent_[a-z0-9_]+|"
    r"logbook_entries|asset_brain|assets?|pm_orders?|inventory|"
    r"hive_members?|alerts?|production_logs?|maintenance_logs?|"
    r"shift_handovers?|work_orders?|technician_actions?"
    r")$"
)


def scan_boundary_seams() -> list[dict]:
    """Walk AI edge-fn source; record quota/cost-log + tenant-data boundary touches."""
    seams: list[dict] = []
    for fn in sorted(AI_FNS):
        fn_dir = FUNCTIONS_DIR / fn
        if not fn_dir.is_dir():
            continue
        for path in fn_dir.rglob("*.ts"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            rel = str(path.relative_to(ROOT).as_posix())

            if _RATE_LIMIT_IMPORT_RE.search(text):
                seams.append({
                    "id":       f"ai→quota/{fn}→rate-limit",
                    "kind":     "ai→quota",
                    "caller":   fn,
                    "callee":   "_shared/rate-limit.ts",
                    "file":     rel,
                    "line":     0,
                    "evidence": "imports rate-limit helper",
                })
            if _COST_LOG_IMPORT_RE.search(text):
                seams.append({
                    "id":       f"ai→quota/{fn}→cost-log",
                    "kind":     "ai→quota",
                    "caller":   fn,
                    "callee":   "_shared/cost-log.ts",
                    "file":     rel,
                    "line":     0,
                    "evidence": "imports cost-log helper",
                })

            tables_seen: set[str] = set()
            for ln, line in enumerate(text.splitlines(), 1):
                for m in _SUPABASE_FROM_RE.finditer(line):
                    table = m.group(1)
                    if not _HIVE_SCOPED_RE.match(table) or table in tables_seen:
                        continue
                    tables_seen.add(table)
                    seams.append({
                        "id":       f"ai→tenant/{fn}→{table}",
                        "kind":     "ai→tenant",
                        "caller":   fn,
                        "callee":   table,
                        "file":     rel,
                        "line":     ln,
                        "evidence": line.strip()[:140],
                    })
    return seams


def main() -> int:
    invoke = scan_invoke_seams()
    boundary = scan_boundary_seams()
    seams = sorted(invoke + boundary, key=lambda s: s["id"])

    catalog = {
        "_meta": {
            "format_version": "1.0",
            "description": "C4 Phase 1 — AI seams catalog. SaaS→AI / AI→AI / AI→tenant / AI→quota call sites. Consumed by Phase 2a (seam contract tests), Phase 2b (meta-gate composition), and `validate_ai_seams_inventory.py` (forward-only ratchet).",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "seam_count":   len(seams),
            "by_kind": {
                k: sum(1 for s in seams if s["kind"] == k)
                for k in ("saas→ai", "ai→ai", "ai→tenant", "ai→quota")
            },
            "ai_fn_count": len(AI_FNS),
        },
        "ai_fns": sorted(AI_FNS),
        "seams":  seams,
    }
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    print(f"AI seams catalog written → {CATALOG_PATH.name}")
    print(f"  total seams       : {len(seams)}")
    for k in ("saas→ai", "ai→ai", "ai→tenant", "ai→quota"):
        c = catalog["_meta"]["by_kind"][k]
        print(f"  {k:<10}        : {c}")
    print(f"  ai_fns tracked    : {len(AI_FNS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
