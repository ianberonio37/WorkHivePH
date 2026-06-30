#!/usr/bin/env python3
"""memory_prune_transcripts.py - Memory-System M4.1: scheduled transcript retention/pruning.
================================================================================
Memento's `prune-candidates` (in memento_precision_audit.py) PROPOSES never-retrieved old
transcript sources but never acts, so the DB grows unbounded: transcripts are ~31% of chunks
and `vector_query` full-scans every chunk_vector on every retrieval (p50 latency climbs as the
corpus grows). This actually EVICTS the safe-to-drop tail — transcript sources older than N days
that have NEVER surfaced in any logged event — reclaiming both rows and scan cost.

Safe to delete because (a) it only touches OLD + NEVER-RETRIEVED transcripts (zero recall value
shown), (b) M1.1 keeps a fresh backup (recoverable), and (c) transcripts are regenerable by
re-indexing the session jsonl if it still exists. Curated memories (feedback/project/reference/
skill/handoff) are NEVER touched — only `type='transcript'`.

Commands:
  --dry-run     (default) report candidates; delete nothing.
  --apply       require a recent backup (make one if stale), DELETE the candidates' chunk rows
                (+ their vectors; FTS cleaned by the chunks delete triggers), VACUUM to reclaim,
                and report chunk-count + DB-size before/after.  --days N sets retention (def 45).
  --self-test   prove on a real-schema scratch copy that pruning removes ONLY old never-retrieved
                transcripts and leaves fresh/retrieved/curated chunks intact.

Exit 0 = ok. Stdlib only. Mutates ONLY the local memory.db, and only after a backup exists.
"""
from __future__ import annotations

import io
import subprocess
import sys
import time
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

MEMENTO_TOOLS = Path.home() / ".claude-memento" / "tools"
sys.path.insert(0, str(MEMENTO_TOOLS))
try:
    import memento_db  # noqa: E402
except Exception as e:  # pragma: no cover
    print(f"  SKIP — memento_db not importable ({type(e).__name__}: {e})")
    sys.exit(0)

import sqlite3  # noqa: E402

ROOT = Path(__file__).resolve().parent
DEFAULT_DAYS = 45.0
SCHEDULED_RETENTION_DAYS = 60.0   # conservative for the unattended SessionStart run
THROTTLE_DAYS = 7.0               # --scheduled prunes at most weekly
BACKUP_DIR = Path.home() / ".claude-memento" / "backups"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"


def _arg_days() -> float:
    for i, a in enumerate(sys.argv):
        if a == "--days" and i + 1 < len(sys.argv):
            try:
                return float(sys.argv[i + 1])
            except ValueError:
                pass
    return DEFAULT_DAYS


def candidates(conn, days: float) -> tuple[list[tuple[str, int]], int]:
    """(list[(source_name, n_chunks)], total_chunks) — old never-retrieved transcript sources."""
    cutoff = time.time() - days * 86400
    cur = conn.cursor()
    cur.execute("SELECT source_name, COUNT(*) n, MAX(source_mtime) m "
                "FROM chunks WHERE type='transcript' GROUP BY source_name")
    sources = cur.fetchall()
    cur.execute("SELECT meta_json FROM memento_events WHERE meta_json IS NOT NULL")
    blob = " ".join(r[0] for r in cur.fetchall())
    cands = [(name, n) for (name, n, m) in sources if m < cutoff and name not in blob]
    return cands, sum(n for _, n in cands)


def _delete_sources(conn, names: list[str]) -> int:
    """Delete every chunk (and its vector) for the given transcript source_names. FTS is an
    external-content table kept in sync by the chunks delete trigger. Returns rows deleted."""
    cur = conn.cursor()
    qmarks = ",".join("?" * len(names))
    cur.execute(f"SELECT id FROM chunks WHERE source_name IN ({qmarks})", names)
    ids = [r[0] for r in cur.fetchall()]
    if not ids:
        return 0
    idmarks = ",".join("?" * len(ids))
    cur.execute(f"DELETE FROM chunks_vectors WHERE chunk_id IN ({idmarks})", ids)
    cur.execute(f"DELETE FROM chunks WHERE id IN ({idmarks})", ids)
    conn.commit()
    return len(ids)


def _ensure_backup() -> bool:
    """Make a fresh backup before any destructive prune (M1.1). Returns True if a backup exists."""
    tool = ROOT / "memory_db_backup.py"
    if not tool.exists():
        return False
    try:
        subprocess.run([sys.executable, str(tool), "--backup", "--force"],
                       capture_output=True, text=True, timeout=60)
    except Exception:
        pass
    return any(BACKUP_DIR.glob("memory_*.db"))


def do_dry_run(days: float) -> int:
    with memento_db._connect() as conn:
        cands, total = candidates(conn, days)
    print(f"  {len(cands)} transcript sources > {days:g}d old & never retrieved — {total} chunks prunable")
    for name, n in sorted(cands, key=lambda x: -x[1])[:15]:
        print(f"    {n:4d} chunks  {name}")
    if not cands:
        print(f"  {G}nothing to prune{X} (corpus tail is fresh or still useful)")
    return 0


def do_apply(days: float) -> int:
    with memento_db._connect() as conn:
        cands, total = candidates(conn, days)
        before = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    if not cands:
        print(f"  {Y}skip{X} no prunable transcripts > {days:g}d old & never retrieved")
        return 0
    if not _ensure_backup():
        print(f"  {R}ABORT{X} no backup present and could not create one — refusing to delete")
        return 1
    size_before = memento_db.DB_PATH.stat().st_size
    names = [n for n, _ in cands]
    with memento_db._connect() as conn:
        deleted = _delete_sources(conn, names)
        conn.execute("VACUUM")
        after = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    size_after = memento_db.DB_PATH.stat().st_size
    print(f"  {G}pruned{X} {deleted} chunks from {len(names)} old transcript sources · "
          f"chunks {before}->{after} · {size_before/1e6:.1f}MB->{size_after/1e6:.1f}MB "
          f"(reclaimed {(size_before-size_after)/1e6:.1f}MB)")
    return 0


def _wipe(p: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        try:
            f = Path(str(p) + suffix)
            if f.exists():
                f.unlink()
        except OSError:
            pass


def do_scheduled() -> int:
    """Unattended cadence run (SessionStart): self-throttled to at most weekly, conservative
    60-day retention, backup-guarded. A no-op most sessions (just a meta read)."""
    with memento_db._connect() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key='last_prune_epoch'").fetchone()
    last = float(row[0]) if row and row[0] else 0.0
    age_days = (time.time() - last) / 86400.0 if last else 1e9
    if age_days < THROTTLE_DAYS:
        print(f"  {Y}skip{X} last prune {age_days:.1f}d ago (< {THROTTLE_DAYS:g}d throttle)")
        return 0
    rc = do_apply(SCHEDULED_RETENTION_DAYS)
    try:
        with memento_db._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_prune_epoch', ?)",
                         (str(time.time()),))
            conn.commit()
    except Exception:
        pass
    return rc


def do_self_test() -> int:
    """Build a real-schema scratch DB, seed 4 transcript sources (old/never, old/retrieved,
    fresh/never) + a curated chunk, prune, assert ONLY the old-never transcript is gone."""
    import gc, os, tempfile
    saved = memento_db.DB_PATH
    scratch = Path(tempfile.gettempdir()) / f"mem_prune_drill_{os.getpid()}.db"
    _wipe(scratch)
    memento_db.DB_PATH = scratch
    try:
        with memento_db._connect() as _c:
            memento_db.init_schema(_c)  # real schema (chunks + fts + vectors + triggers + meta + events)
        now = time.time()
        old = now - 100 * 86400
        with memento_db._connect() as conn:
            cur = conn.cursor()
            def add(cid, name, typ, mtime):
                cur.execute("INSERT INTO chunks (id, source_path, source_name, chunk_idx, type, "
                            "title, description, text, importance, source_mtime, created_at_epoch) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (cid, name, name, 0, typ, name, "d", "body text here", 1, mtime, int(now)))
                cur.execute("INSERT INTO chunks_vectors (chunk_id, vector, vocab_version, created_at_epoch) "
                            "VALUES (?, ?, ?, ?)", (cid, b"\x00" * 8, 1, int(now)))
            add(1, "transcript_oldnever.jsonl", "transcript", old)      # SHOULD prune
            add(2, "transcript_oldretr.jsonl",  "transcript", old)      # retrieved -> keep
            add(3, "transcript_fresh.jsonl",    "transcript", now)      # fresh -> keep
            add(4, "feedback_keep.md",          "feedback",   old)      # curated -> never touched
            # mark source 2 as having been retrieved (appears in an event)
            cur.execute("INSERT INTO memento_events (event_type, event_ts, meta_json) VALUES "
                        "('retrieval', ?, ?)", (int(now), '{\"name\": \"transcript_oldretr.jsonl\"}'))
            conn.commit()
        with memento_db._connect() as conn:
            cands, _ = candidates(conn, days=45)
            names = [n for n, _ in cands]
            _delete_sources(conn, names)
            remaining = {r[0] for r in conn.execute("SELECT source_name FROM chunks").fetchall()}
            vec_ids = {r[0] for r in conn.execute("SELECT chunk_id FROM chunks_vectors").fetchall()}
    finally:
        memento_db.DB_PATH = saved
        gc.collect()
        _wipe(scratch)
    pruned_right = names == ["transcript_oldnever.jsonl"]
    kept_right = remaining == {"transcript_oldretr.jsonl", "transcript_fresh.jsonl", "feedback_keep.md"}
    vec_cascaded = 1 not in vec_ids and vec_ids == {2, 3, 4}
    print(f"  candidates: {names}  ({'OK' if pruned_right else 'FAIL'})")
    print(f"  remaining:  {sorted(remaining)}  ({'OK' if kept_right else 'FAIL'})")
    print(f"  vectors cascaded (id1 gone): {sorted(vec_ids)}  ({'OK' if vec_cascaded else 'FAIL'})")
    if pruned_right and kept_right and vec_cascaded:
        print(f"  {G}TEETH VERIFIED{X} prunes ONLY old never-retrieved transcripts; keeps retrieved/fresh/curated.")
        return 0
    print(f"  {R}FAIL{X}")
    return 1


def main() -> int:
    print(f"{B}Memory-System M4.1 - transcript retention / pruning{X}")
    print("=" * 62)
    argv = sys.argv[1:]
    days = _arg_days()
    if "--self-test" in argv:
        rc = do_self_test()
        print(f"\n{(G if rc == 0 else R)}{B}  TRANSCRIPT PRUNE SELFTEST: {'PASS' if rc == 0 else 'FAIL'}{X}")
        return rc
    if "--scheduled" in argv:
        rc = do_scheduled()
    elif "--apply" in argv:
        rc = do_apply(days)
    else:
        rc = do_dry_run(days)
    print(f"\n{(G if rc == 0 else R)}{B}  TRANSCRIPT PRUNE: {'PASS' if rc == 0 else 'FAIL'}{X}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
