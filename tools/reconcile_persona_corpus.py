#!/usr/bin/env python3
"""reconcile_persona_corpus.py — persona-knowledge FRESHNESS engine (companion wiring W12).

The ingest tool does ADD + UPDATE (hash-supersede) but NOT DELETE — so a retired learn
article or a deleted drop-folder file leaves GHOST chunks the persona can still cite.
This reconciles persona_knowledge against its manifests and SWEEPS orphans (O17, the
missing DELETE):

  manifested channel        manifest (source of truth)            orphan -> SWEEP
  ─────────────────────────────────────────────────────────────────────────────────
  platform_doc  learn/<slug>   platform_catalog.json articles      slug gone   -> delete
  platform_doc  platform/feat* platform_catalog.json features      scope gone  -> delete
  drop-folder   corpus/<f>/<n>  files under persona_corpus/         file gone   -> delete
  external      external/<std>  EXTERNAL_SHARED (in ingest tool)    std gone    -> delete
  skill_md      <slug>/SKILL.md CURATE map (in ingest tool)         slug gone   -> delete

AD-HOC channels (source_type 'pdf' via --pdf, 'url' via --url) have NO manifest, so they
are NEVER swept — they're intentional one-offs.

Usage:
  python tools/reconcile_persona_corpus.py --dry-run   # report adds/sweeps, no writes
  python tools/reconcile_persona_corpus.py             # SWEEP orphans
  python tools/reconcile_persona_corpus.py --ingest    # sweep + ingest missing (--source all)
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]


def _load_ingest_module():
    spec = importlib.util.spec_from_file_location("ipk", ROOT / "tools" / "ingest_persona_knowledge.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def live_sources(ipk) -> set[str]:
    """The union of every manifested channel's CURRENT valid sources."""
    live: set[str] = set()
    # skill_md (CURATE map)
    for slug in ipk.CURATE:
        live.add(f"{slug}/SKILL.md")
    # external (in-code EXTERNAL_SHARED)
    for std, _sec, _con in ipk.EXTERNAL_SHARED:
        live.add(f"external/{std}")
    # drop-folder (files present under persona_corpus/)
    if ipk.CORPUS_DIR.exists():
        for folder in ipk.FOLDER_SCOPE:
            d = ipk.CORPUS_DIR / folder
            if d.exists():
                for p in d.iterdir():
                    if p.is_file() and p.suffix.lower() in ipk.TEXT_EXTS:
                        live.add(f"corpus/{folder}/{p.name}")
    # platform_doc (platform_catalog.json articles + feature-scope buckets)
    if ipk.CATALOG.exists():
        cat = json.loads(ipk.CATALOG.read_text(encoding="utf-8", errors="ignore"))
        for a in cat.get("articles", []):
            if a.get("slug"):
                live.add(f"learn/{a['slug']}")
        scopes = set()
        for f in cat.get("features", []):
            if (f.get("capability") or "").strip():
                scopes.add(ipk.classify_scope(f"{f.get('name','')} {f.get('capability','')} {f.get('nav_section','')}"))
        for sc in scopes:
            live.add(f"platform/features-{sc}")
    return live


# only sweep sources that belong to a MANIFESTED channel (prefix-scoped); ad-hoc
# pdf/url sources have no manifest and must be left alone.
def _is_manifested(source: str, source_type: str) -> bool:
    if source_type in ("pdf", "url"):
        return False
    return (source.startswith("learn/") or source.startswith("platform/features-")
            or source.startswith("corpus/") or source.startswith("external/")
            or source.endswith("/SKILL.md"))


def main() -> int:
    ap = argparse.ArgumentParser(description="persona-knowledge freshness reconcile (W12, O17 sweep)")
    ap.add_argument("--dry-run", action="store_true", help="report adds/sweeps, no DB writes")
    ap.add_argument("--ingest", action="store_true", help="after sweeping, ingest missing (--source all)")
    args = ap.parse_args()

    ipk = _load_ingest_module()
    live = live_sources(ipk)

    conn = psycopg2.connect(ipk.DB_DSN)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("select source, source_type, count(*) from persona_knowledge group by 1,2 order by 1")
    rows = cur.fetchall()

    present = {src for src, _st, _n in rows}
    orphans = [(src, st, n) for src, st, n in rows if _is_manifested(src, st) and src not in live]
    missing = sorted(s for s in live if s not in present)

    print("=" * 72)
    print(f"PERSONA-CORPUS RECONCILE  ({'DRY-RUN' if args.dry_run else 'APPLY'})")
    print("=" * 72)
    print(f"  manifested live sources: {len(live)} | in corpus: {len(present)}")
    print(f"  ORPHANS to sweep (in corpus, not in any manifest): {len(orphans)}")
    swept_chunks = 0
    for src, st, n in orphans:
        print(f"    - SWEEP {src} [{st}] ({n} chunks)")
        swept_chunks += n
        if not args.dry_run:
            cur.execute("delete from persona_knowledge where source = %s", (src,))
    print(f"  MISSING (in manifest, not yet ingested): {len(missing)}")
    for s in missing[:20]:
        print(f"    - MISSING {s}")
    if len(missing) > 20:
        print(f"    ... +{len(missing) - 20} more")

    if not args.dry_run:
        conn.commit()
        print(f"  committed: swept {swept_chunks} chunks from {len(orphans)} orphan source(s)")
    cur.close()
    conn.close()

    if args.ingest and missing and not args.dry_run:
        print("\n--- ingesting missing (--source all) ---")
        import subprocess
        subprocess.call([sys.executable, str(ROOT / "tools" / "ingest_persona_knowledge.py"),
                         "--source", "all", "--embed-model", "gemini"], cwd=str(ROOT))

    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
