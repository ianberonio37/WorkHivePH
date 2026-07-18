"""Post-seed step: populate the RAG index so a fresh reseed lands SEARCHABLE.

ARC DI §10.5 seeder co-land (2026-07-08): the seeder bulk-INSERTs `fault_knowledge`
(and other *_knowledge) rows but skips the live `embed-entry` write path, so after a
clean reseed the corpus has 0 embeddings — semantic search / RAG grounding returns
NOTHING until a backfill runs. This step closes that co-land: if the self-hosted
bge-small embed server (:8901, quota-free) is up, it re-embeds the fault corpus into
ONE deterministic vector space (via tools/reembed_fault_knowledge.py). It SKIPS
gracefully (never fails the seed) if the embed server is down — the manual tool is
always available as the fallback.
"""
import subprocess
import sys
import urllib.request
from pathlib import Path

EMBED_HEALTH = "http://127.0.0.1:8901/health"
REEMBED_TOOL = Path(__file__).resolve().parent.parent.parent / "tools" / "reembed_fault_knowledge.py"


def _embed_server_up() -> bool:
    try:
        with urllib.request.urlopen(EMBED_HEALTH, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def run_post_seed_embed(client, log, ctx: dict) -> dict:
    """Re-embed the fault corpus if the local bge embed server is reachable."""
    if not REEMBED_TOOL.exists():
        log("  embed corpus: reembed tool not found — skipped")
        return {"embed_corpus": "skipped_no_tool"}
    if not _embed_server_up():
        log("  embed corpus: bge embed server :8901 down — skipped (run tools/reembed_fault_knowledge.py "
            "after starting embed_server.py to populate the RAG index)")
        return {"embed_corpus": "skipped_server_down"}
    log("  embed corpus: bge server up — re-embedding fault_knowledge into bge-small-en-v1.5 space...")
    try:
        r = subprocess.run([sys.executable, str(REEMBED_TOOL)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600)
        tail = (r.stdout or "").strip().splitlines()[-1:] or [(r.stderr or "").strip()[:120]]
        log(f"  embed corpus: {tail[0] if tail else 'done'}")
        return {"embed_corpus": "ok" if r.returncode == 0 else "failed"}
    except Exception as e:
        log(f"  embed corpus: skipped ({e})")
        return {"embed_corpus": f"error:{type(e).__name__}"}
