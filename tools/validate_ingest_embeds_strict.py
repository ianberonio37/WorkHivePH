#!/usr/bin/env python3
"""ingest-embeds-strict - a vector WRITTEN to a row comes from the corpus's own embedder, or the row gets none (2026-10-26).

embedding-chain.ts states the rule (STRICT = INGEST): failover is safe for a read and poison for a write - a degraded answer
lasts one response, a persisted vector in a foreign space is permanent, well-formed and never found again (the corpus was
poisoned twice that way). embed-entry followed it. Walked live with the local embedder stopped, pdf-ingest walked the whole
chain - Voyage, Gemini, Jina, three other spaces - and wrote nothing only because every key was dead or spent. Four more
writers embedded the same way, and the gateway filed the turn's QUERY vector (which may come from a fallback) into the
journal row.

W1 every writer below embeds with { strict: true } and no plain generateEmbedding( call remains in it.
W2 journal recall reports whether its query vector is the pinned embedder's, and the gateway reuses it for the row only then.

Teeth: the tree at 1045f447 fails W1 and W2.
    python tools/validate_ingest_embeds_strict.py [--ref <git-ref>]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRITERS = [
    "supabase/functions/embed-entry/index.ts",
    "supabase/functions/pdf-ingest/index.ts",
    "supabase/functions/semantic-fact-extractor/index.ts",
    "supabase/functions/visual-defect-capture/index.ts",
    "supabase/functions/_shared/episodic-memory.ts",
]


def _read(path: str, ref: str | None) -> str:
    if ref:
        try:
            return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT, text=True, encoding="utf-8",
                                           errors="replace", stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            return ""
    p = ROOT / path
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def check(ref: str | None = None) -> list[str]:
    bad = []
    for path in WRITERS:
        src = _read(path, ref)
        name = path.split("functions/")[1]
        if re.search(r"\bgenerateEmbedding\(", src):
            bad.append(f"W1 {name}: writes a vector from the full chain (generateEmbedding) - a fallback's foreign space lands in the row")
        if "strict: true" not in src:
            bad.append(f"W1 {name}: no strict embed")
    jr = _read("supabase/functions/_shared/journal-recall.ts", ref)
    m = re.search(r"export async function persistJournalEntry[\s\S]*?\n}\n", jr)
    if not m or "strict: true" not in m.group(0):
        bad.append("W1 _shared/journal-recall.ts: persistJournalEntry embeds a row from the full chain")
    if "query_embedding_pinned" not in jr or "pinnedEmbedderName()" not in jr:
        bad.append("W2 _shared/journal-recall.ts: recall does not say whether its query vector is the pinned embedder's")
    gw = _read("supabase/functions/ai-gateway/index.ts", ref)
    if "recallEmbeddingPinned ? recallEmbedding : undefined" not in gw:
        bad.append("W2 ai-gateway: the turn's query vector is filed into the journal row whatever embedder produced it")
    return bad


def main() -> int:
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else None
    bad = check(ref)
    print(f"ingest-embeds-strict{' @ ' + ref if ref else ''}: {len(WRITERS) + 1} writers, {len(bad)} finding(s)")
    for b in bad:
        print("  - " + b)
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
