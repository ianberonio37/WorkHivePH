#!/usr/bin/env python3
"""
memory_cache.py — PKS Phase 3: the memory retrieval cache (consumption layer).
==============================================================================
PLATFORM_KNOWLEDGE_SUBSTRATE_ROADMAP L3. `MEMORY.md` is loaded WHOLE into context every session and has
a hard load cap (~24.4KB); past it, older entries silently truncate. It climbed to 23.5KB this session
(each real finding adds a line) and the compactor is down to retiring 1/run — the budget discipline is
at its ceiling.

The SQLite FTS5+TF-IDF retrieval engine ALREADY EXISTS — Memento's memory.db (`chunks_fts` FTS5 +
`chunks_vectors` TF-IDF), used by the per-prompt UserPromptSubmit hook. So P3 is NOT a new cache; it is
the CONSUMPTION change that leverages it: keep MEMORY.md a slim DOCTRINE-CORE (the always-on feedback
lessons) and let REFERENCE/PROJECT pointers live RETRIEVAL-ONLY (already indexed in chunks_fts, surfaced
on-demand). That makes the index-size cap MOOT — the corpus can grow unbounded in SQLite; the session
load stays small.

Commands:
  --retrieve "<query>" [--k N]   on-demand FTS5 memory retrieval (the slice, ~500 tokens, not the 24KB
                                 whole index). Proves references are reachable without the pointer.
  --check                        GATE: every reference/project memory file on disk is INDEXED in
                                 memory.db (so it's safe for MEMORY.md to be pointer-light), AND
                                 MEMORY.md <= budget. Exit 1 on a coverage gap or over-budget.
  --slim [--apply]               proactively partition MEMORY.md: keep ALL feedback (doctrine) + the N
                                 most-recent references; move older (verified-retrievable) references to
                                 retrieval-only. Backs up first; reversible.

Stdlib only (sqlite3).
"""
from __future__ import annotations
import argparse, io, re, sqlite3, sys, time
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

MEMENTO_DB = Path.home() / ".claude-memento" / "memory.db"
# The project memory dir (this repo's). Resolve from the known project path pattern.
MEM_DIR = (Path.home() / ".claude" / "projects" /
           "c--Users-ILBeronio-Desktop-Industry-4-0-AI-Maintenance-Engineer-Self-learning-Road-Map-Build---Sell-with-Claude-Code-Website-simple-1st" / "memory")
MEMORY_MD = MEM_DIR / "MEMORY.md"
MEM_TYPES = ("feedback", "reference", "project")
BUDGET_BYTES = 18000          # comfortable session-load target (~6KB headroom under the 24.4KB hard cap)
KEEP_RECENT_REFS = 24         # references kept in the session-start index; older = retrieval-only
ENTRY_RE = re.compile(r"^- \[.*?\]\((?P<file>[\w./-]+\.md)\).*$")


def _conn():
    if not MEMENTO_DB.exists():
        return None
    try:
        return sqlite3.connect(f"file:{MEMENTO_DB}?mode=ro", uri=True)
    except Exception:
        return None


def _fts_query(terms: str) -> str:
    # Quote each token so FTS5 doesn't choke on punctuation / operators.
    toks = re.findall(r"[A-Za-z0-9_]+", terms)
    return " OR ".join(f'"{t}"' for t in toks) or '""'


def retrieve(query: str, k: int) -> int:
    c = _conn()
    if c is None:
        print("  (memory.db unavailable)"); return 0
    try:
        rows = c.execute(
            "SELECT c.type, c.source_name, substr(replace(c.text,char(10),' '),1,140), bm25(chunks_fts) rank "
            "FROM chunks_fts f JOIN chunks c ON c.rowid=f.rowid "
            f"WHERE chunks_fts MATCH ? AND c.type IN ({','.join('?'*len(MEM_TYPES))}) "
            "ORDER BY rank LIMIT ?",
            (_fts_query(query), *MEM_TYPES, k)).fetchall()
    except Exception as e:
        print(f"  FTS query error: {e}"); return 1
    print(f"\nmemory_cache · retrieve '{query}' → {len(rows)} chunk(s) (~{sum(len(r[2]) for r in rows)//4} tokens):")
    seen = set()
    for t, src, snip, rank in rows:
        if src in seen:
            continue
        seen.add(src)
        print(f"  [{t}] {src}\n    {snip.strip()}")
    return 0


def _indexed_sources(any_type: bool = False) -> set:
    """Distinct source_names indexed in memory.db. any_type=True → ANY chunk type (for the coverage
    check: a file is retrievable if it's indexed under any type, e.g. a cached-web page as 'cached_web')."""
    c = _conn()
    if c is None:
        return set()
    try:
        if any_type:
            return {r[0] for r in c.execute("SELECT DISTINCT source_name FROM chunks").fetchall()}
        return {r[0] for r in c.execute(
            f"SELECT DISTINCT source_name FROM chunks WHERE type IN ({','.join('?'*len(MEM_TYPES))})", MEM_TYPES).fetchall()}
    except Exception:
        return set()


def check() -> int:
    print("\n" + "=" * 72)
    print("  PKS P3 — memory retrieval cache gate (coverage + budget)")
    print("=" * 72)
    if not MEMORY_MD.exists():
        print("  SKIP: MEMORY.md not found."); return 0
    size = MEMORY_MD.stat().st_size
    # coverage: every reference/project topic file on disk must be indexed (FTS5-retrievable),
    # else moving its pointer out of MEMORY.md would lose it.
    # durable reference/project memories (exclude reference_url_* — those are cached-web WebFetch
    # artifacts, indexed as 'cached_web', not durable memories).
    disk = {p.name for p in MEM_DIR.glob("*.md")
            if p.name != "MEMORY.md" and p.name.startswith(("reference_", "project_"))
            and not p.name.startswith("reference_url_")}
    indexed = _indexed_sources(any_type=True)
    missing = sorted(disk - indexed)
    fails = 0
    if _conn() is None:
        print("  SKIP: memory.db unavailable — coverage not checkable.")
    elif missing:
        fails += 1
        print(f"  FAIL: {len(missing)} reference/project memory file(s) NOT indexed (not retrievable): {missing[:8]}")
        print("        FIX: re-run the Memento indexer so they're FTS5-retrievable before they can go pointer-light.")
    else:
        print(f"  PASS: all {len(disk)} reference/project memory files are indexed (FTS5-retrievable).")
    if size > 24400:
        fails += 1
        print(f"  FAIL: MEMORY.md {size} bytes OVER the 24.4KB hard load cap — entries are truncating. Run --slim --apply.")
    elif size > BUDGET_BYTES:
        print(f"  WARN: MEMORY.md {size} bytes over the {BUDGET_BYTES}B P3 target (still loads). Run --slim to trim references.")
    else:
        print(f"  PASS: MEMORY.md {size} bytes <= {BUDGET_BYTES}B target.")
    print()
    return 1 if fails else 0


def slim(apply: bool) -> int:
    if not MEMORY_MD.exists():
        print("MEMORY.md not found"); return 0
    text = MEMORY_MD.read_text(encoding="utf-8")
    lines = text.splitlines()
    indexed = _indexed_sources()
    header, entries = [], []
    for ln in lines:
        m = ENTRY_RE.match(ln)
        if m:
            entries.append((ln, m.group("file")))
        elif not entries:
            header.append(ln)
    # partition: feedback = doctrine (ALWAYS keep). reference/project = candidates for retrieval-only.
    kept, moved = [], []
    ref_seen = 0
    # keep entries in file order; feedback always kept; references kept only for the most-recent KEEP_RECENT_REFS
    # (recency = position from the END of the list, where new entries are appended).
    ref_entries = [e for e in entries if not e[1].startswith("feedback_")]
    recent_refs = set(id(e) for e in ref_entries[-KEEP_RECENT_REFS:])
    for ln, f in entries:
        if f.startswith("feedback_"):
            kept.append(ln); continue
        if id((ln, f)) in recent_refs or any(id(e) in recent_refs and e[0] == ln for e in ref_entries):
            kept.append(ln); continue
        # older reference: move to retrieval-only ONLY if it's FTS5-retrievable (safety).
        if f in indexed:
            moved.append((ln, f))
        else:
            kept.append(ln)  # not retrievable → must stay in the index
    note = (f"- _({len(moved)} older reference pointers are RETRIEVAL-ONLY — surfaced on-demand from "
            f"memory.db FTS5 via Memento / `python tools/memory_cache.py --retrieve \"<topic>\"`; the topic "
            f"files remain on disk. PKS P3.)_")
    new = "\n".join(header + [ln for ln in kept] + ["", note]) + "\n"
    print(f"slim: {len(entries)} entries → keep {len(kept)} (all feedback + {KEEP_RECENT_REFS} recent refs), "
          f"move {len(moved)} refs to retrieval-only. {MEMORY_MD.stat().st_size}B → {len(new.encode('utf-8'))}B")
    if not apply:
        print("  (dry run — pass --apply to write; a backup is made)")
        return 0
    bak = MEM_DIR / f"MEMORY.md.p3bak-{time.strftime('%Y%m%d-%H%M%S')}"
    bak.write_text(text, encoding="utf-8")
    MEMORY_MD.write_text(new, encoding="utf-8")
    print(f"  APPLIED. backup: {bak.name} (restore to undo).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrieve", metavar="QUERY")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--slim", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.retrieve:
        return retrieve(a.retrieve, a.k)
    if a.check:
        return check()
    if a.slim:
        return slim(a.apply)
    return check()


if __name__ == "__main__":
    sys.exit(main())
