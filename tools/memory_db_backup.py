#!/usr/bin/env python3
"""memory_db_backup.py - Memory-System M1.1: backup + restore drill for memory.db.
================================================================================
The single highest-value durability gap in the Memento memory system. `memory.db`
(~90MB, ~/.claude-memento/memory.db) is durable, hard-to-reconstruct state — the
TF-IDF vocab, transcript/event history, and the FTS5 index — and it had ZERO
backup. SQLite files corrupt on interrupted writes, and the Stop/PreToolUse hooks
write to it mid-session, so an interrupted hook can leave a torn DB with no way
back. This tool closes that gap, $0, fully LOCAL (no prod, no network).

It uses SQLite's ONLINE BACKUP API (sqlite3.Connection.backup) which produces a
transactionally-consistent snapshot even while the hooks are writing (WAL mode) —
unlike a naive file copy, which can capture a torn page.

The backup is a self-contained recovery SET per timestamp:
  - memory_<ts>.db          the SQLite snapshot (fast restore of the whole index)
  - memory_md_<ts>.zip      the curated auto-memory .md topic files — the ONLY
                            half that is NOT regenerable (transcripts rebuild from
                            session jsonl; vectors/vocab rebuild by re-indexing;
                            but a hand-written feedback/project memory, once lost,
                            is gone). Tiny (~200KB), so we bundle it every time.
  - memory_<ts>.manifest.json   the RPO evidence: chunk count, integrity verdict,
                            schema version, byte sizes, md-file count.

Commands:
  --backup        write a fresh recovery set + 5-deep rotation (throttled: skips if
                  the newest set is < THROTTLE_HOURS old, unless --force). This is
                  what the SessionStart hook calls.
  --drill         (default; the GATE) prove the full round-trip deterministically:
                  online-backup the live DB to a scratch file, reopen it, run
                  PRAGMA integrity_check, assert chunk count matches source, assert
                  schema version, and run a REAL FTS5 BM25 query against the restored
                  copy (proves the index — not just the bytes — survived). Then drop
                  the scratch. Exit 0 = a snapshot restores to a WORKING DB.
  --check-sources report the durability of the curated .md half (count + newest
                  backup age) without writing anything.

Stdlib only. Reads no secrets. Never touches prod or the network.
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

MEMENTO_DIR = Path.home() / ".claude-memento"
DB_PATH = MEMENTO_DIR / "memory.db"
BACKUP_DIR = MEMENTO_DIR / "backups"
KEEP = 5                       # 5-deep rotation
THROTTLE_HOURS = 6.0           # --backup is a no-op if newest set is younger than this
EXPECT_SCHEMA = 10             # memento_db.SCHEMA_VERSION at time of writing
CHUNK_TOLERANCE = 0.02         # restored chunk count may differ by <2% (live writes mid-backup)
VACUUM_FREE_RATIO = 0.15       # M1.2: VACUUM the live DB once free pages exceed this fraction
                               # (SQLite never reclaims delete space without VACUUM; auto_vacuum is OFF)

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _open_ro(path: Path) -> sqlite3.Connection:
    """Open a DB read-only via URI so a drill never mutates the source."""
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=30)


def _db_stats(conn: sqlite3.Connection) -> dict:
    """Cheap health fingerprint of a DB: counts + schema version. Used for both the
    manifest (source) and the restore assertion (target)."""
    cur = conn.cursor()
    out: dict = {}
    try:
        out["chunks"] = cur.execute("SELECT count(*) FROM chunks").fetchone()[0]
    except Exception:
        out["chunks"] = -1
    try:
        out["events"] = cur.execute("SELECT count(*) FROM memento_events").fetchone()[0]
    except Exception:
        out["events"] = -1
    try:
        out["vocab_rows"] = cur.execute("SELECT count(*) FROM vocab_state").fetchone()[0]
    except Exception:
        out["vocab_rows"] = -1
    try:
        out["schema_version"] = int(cur.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])
    except Exception:
        out["schema_version"] = -1
    return out


def _find_memory_md_dir() -> Path | None:
    """Locate the active auto-memory topic-file dir (~/.claude/projects/<proj>/memory)
    by the most-recently-touched MEMORY.md under ~/.claude/projects/*/memory. This is
    self-maintaining: whichever project you're working in is the freshest."""
    root = Path.home() / ".claude" / "projects"
    if not root.exists():
        return None
    best: tuple[float, Path] | None = None
    for idx in root.glob("*/memory/MEMORY.md"):
        try:
            mt = idx.stat().st_mtime
        except OSError:
            continue
        if best is None or mt > best[0]:
            best = (mt, idx.parent)
    return best[1] if best else None


def _newest_set_age_hours() -> float | None:
    if not BACKUP_DIR.exists():
        return None
    dbs = sorted(BACKUP_DIR.glob("memory_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not dbs:
        return None
    return (time.time() - dbs[0].stat().st_mtime) / 3600.0


def _rotate() -> int:
    """Keep the KEEP newest sets; delete older .db / .zip / .manifest.json. Returns #deleted."""
    dbs = sorted(BACKUP_DIR.glob("memory_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    deleted = 0
    for old in dbs[KEEP:]:
        ts = old.stem.replace("memory_", "")
        for sibling in (old, BACKUP_DIR / f"memory_md_{ts}.zip", BACKUP_DIR / f"memory_{ts}.manifest.json"):
            try:
                if sibling.exists():
                    sibling.unlink()
                    deleted += 1
            except OSError:
                pass
    return deleted


def _online_backup(src: Path, dest: Path) -> None:
    """Transactionally-consistent snapshot via SQLite's online-backup API. Safe to run
    while the hooks write (WAL). Copies all pages in one pass (no restart loop)."""
    src_conn = _open_ro(src)
    dest_conn = sqlite3.connect(dest)
    try:
        src_conn.backup(dest_conn)      # pages=-1 default: whole DB in one step
    finally:
        dest_conn.close()
        src_conn.close()


def do_backup(force: bool = False) -> int:
    if not DB_PATH.exists():
        print(f"  {Y}SKIP{X} {DB_PATH} not found — nothing to back up (Memento not initialised)")
        return 0
    age = _newest_set_age_hours()
    if not force and age is not None and age < THROTTLE_HOURS:
        print(f"  {Y}skip{X} newest backup is {age:.1f}h old (< {THROTTLE_HOURS}h throttle); use --force to override")
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now_ts()
    db_out = BACKUP_DIR / f"memory_{ts}.db"
    t0 = time.monotonic()
    _online_backup(DB_PATH, db_out)
    db_secs = time.monotonic() - t0

    # verify the snapshot we just wrote before trusting it
    with _open_ro(db_out) as v:
        integrity = v.execute("PRAGMA integrity_check").fetchone()[0]
        stats = _db_stats(v)

    # bundle the irreplaceable curated half (.md topic files)
    md_dir = _find_memory_md_dir()
    md_count = 0
    md_zip = BACKUP_DIR / f"memory_md_{ts}.zip"
    if md_dir and md_dir.exists():
        with zipfile.ZipFile(md_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for md in sorted(md_dir.glob("*.md")):
                zf.write(md, md.name)
                md_count += 1
    else:
        md_zip = None

    manifest = {
        "created_at_utc": ts,
        "db_file": db_out.name,
        "db_bytes": db_out.stat().st_size,
        "backup_secs": round(db_secs, 2),
        "integrity_check": integrity,
        **stats,
        "md_zip": md_zip.name if md_zip else None,
        "md_files": md_count,
        "md_source_dir": str(md_dir) if md_dir else None,
    }
    (BACKUP_DIR / f"memory_{ts}.manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    deleted = _rotate()
    # M1.2: opportunistic, bloat-gated reclaim while we're already doing maintenance (no-op unless bloated).
    do_vacuum(force=False)
    ok = integrity == "ok" and stats.get("chunks", -1) > 0
    tag = f"{G}backup{X}" if ok else f"{R}backup(SUSPECT){X}"
    print(f"  {tag} {db_out.name}  ({db_out.stat().st_size/1e6:.1f}MB, {stats.get('chunks')} chunks, "
          f"integrity={integrity}, {db_secs:.1f}s) + {md_count} .md files"
          f"{f' (rotated {deleted} old files)' if deleted else ''}")
    return 0 if ok else 1


def do_drill() -> int:
    """The GATE: prove a snapshot restores to a WORKING db, deterministically, every run.
    online-backup the live DB to a scratch file -> reopen -> integrity_check -> assert
    chunk count ~matches source -> assert schema version -> run a REAL FTS5 query against
    the restored copy -> drop scratch. PASS only if the restored DB actually answers a query."""
    if not DB_PATH.exists():
        print(f"  {Y}SKIP{X} {DB_PATH} not found — no DB to drill (Memento not initialised)")
        return 0

    with _open_ro(DB_PATH) as s:
        src = _db_stats(s)
    src_chunks = src.get("chunks", -1)

    scratch = MEMENTO_DIR / f".drill_{_now_ts()}.db"
    t0 = time.monotonic()
    try:
        _online_backup(DB_PATH, scratch)
        with _open_ro(scratch) as r:
            integrity = r.execute("PRAGMA integrity_check").fetchone()[0]
            restored = _db_stats(r)
            # the load-bearing proof: a REAL retrieval-shaped query on the restored index.
            # if the FTS5 index were torn, this raises or returns nothing.
            fts_hits = r.execute(
                "SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH ?", ("memory OR memento OR maintenance",)
            ).fetchone()[0]
        elapsed = time.monotonic() - t0
    except Exception as e:
        print(f"  {R}FAIL{X} drill raised: {type(e).__name__}: {str(e)[:160]}")
        _safe_unlink(scratch)
        return 1
    finally:
        _safe_unlink(scratch)

    r_chunks = restored.get("chunks", -1)
    drift = abs(r_chunks - src_chunks) / max(src_chunks, 1)
    checks = {
        "integrity ok":        integrity == "ok",
        "chunks restored":     r_chunks > 0 and drift <= CHUNK_TOLERANCE,
        "schema version":      restored.get("schema_version") == EXPECT_SCHEMA,
        "FTS index queryable": fts_hits > 0,
    }
    ok = all(checks.values())
    if ok:
        print(f"  {G}drill{X} restored {r_chunks} chunks (src {src_chunks}), integrity={integrity}, "
              f"schema v{restored.get('schema_version')}, {fts_hits} FTS hits, round-trip {elapsed:.1f}s "
              f"(RTO ~{elapsed:.1f}s)")
        return 0
    bad = ", ".join(k for k, v in checks.items() if not v)
    print(f"  {R}FAIL{X} restore round-trip failed [{bad}]  src={src_chunks} restored={r_chunks} "
          f"integrity={integrity} schema=v{restored.get('schema_version')} fts={fts_hits}")
    return 1


def _free_ratio(conn: sqlite3.Connection) -> tuple[int, int]:
    """Return (freelist_count, page_count) for the live DB."""
    fl = conn.execute("PRAGMA freelist_count").fetchone()[0]
    pc = conn.execute("PRAGMA page_count").fetchone()[0]
    return fl, pc


def do_vacuum(force: bool = False) -> int:
    """M1.2: reclaim delete-orphaned space. SQLite never shrinks on DELETE (freelist grows,
    file stays); a refresh that pruned rows leaves dead pages forever. VACUUM rewrites the file
    compactly. Bloat-gated (only when free pages exceed VACUUM_FREE_RATIO) so it's a cheap no-op
    normally and only pays the rewrite cost when there's real slack to reclaim."""
    if not DB_PATH.exists():
        print(f"  {Y}SKIP{X} {DB_PATH} not found — nothing to vacuum")
        return 0
    before = DB_PATH.stat().st_size
    conn = sqlite3.connect(DB_PATH, timeout=60)
    try:
        fl, pc = _free_ratio(conn)
        ratio = fl / max(pc, 1)
        if not force and ratio < VACUUM_FREE_RATIO:
            print(f"  {Y}skip{X} free pages {ratio*100:.1f}% < {VACUUM_FREE_RATIO*100:.0f}% threshold "
                  f"(no bloat to reclaim); use --force to override")
            return 0
        t0 = time.monotonic()
        conn.execute("VACUUM")
        secs = time.monotonic() - t0
    finally:
        conn.close()
    after = DB_PATH.stat().st_size
    reclaimed = before - after
    print(f"  {G}vacuum{X} reclaimed {reclaimed/1e6:.1f}MB (free pages were {ratio*100:.1f}%); "
          f"{before/1e6:.1f}MB -> {after/1e6:.1f}MB in {secs:.1f}s")
    return 0


def do_vacuum_drill() -> int:
    """Prove the M1.2 mechanism deterministically + fast: build a temp DB, fill it, delete most
    rows (file does NOT shrink — that's the bug VACUUM fixes), then VACUUM and assert the file
    shrank. Acceptance bar: 'DB file shrinks after delete+vacuum.' No touch to the live DB."""
    scratch = MEMENTO_DIR / f".vac_drill_{_now_ts()}.db"
    try:
        c = sqlite3.connect(scratch)
        c.execute("CREATE TABLE blob_t (id INTEGER PRIMARY KEY, payload BLOB)")
        c.executemany("INSERT INTO blob_t (payload) VALUES (?)",
                      [(b"x" * 4000,) for _ in range(4000)])  # ~16MB of rows
        c.commit()
        size_full = scratch.stat().st_size
        c.execute("DELETE FROM blob_t WHERE id % 5 != 0")     # delete 80%
        c.commit()
        size_after_delete = scratch.stat().st_size            # ~unchanged (freelist grew)
        fl = c.execute("PRAGMA freelist_count").fetchone()[0]
        c.execute("VACUUM")
        c.close()
        size_vacuumed = scratch.stat().st_size                # shrank
    except Exception as e:
        print(f"  {R}FAIL{X} vacuum drill raised: {type(e).__name__}: {str(e)[:140]}")
        _safe_unlink(scratch); return 1
    finally:
        _safe_unlink(scratch)

    delete_did_not_shrink = size_after_delete >= size_full * 0.95  # delete alone leaves the file big
    vacuum_shrank = size_vacuumed < size_after_delete * 0.6        # vacuum reclaims the 80% slack
    if delete_did_not_shrink and vacuum_shrank and fl > 0:
        print(f"  {G}vacuum-drill{X} fill {size_full/1e6:.1f}MB -> delete-80% {size_after_delete/1e6:.1f}MB "
              f"(freelist {fl}, no shrink) -> VACUUM {size_vacuumed/1e6:.1f}MB (reclaimed) — mechanism proven")
        return 0
    print(f"  {R}FAIL{X} vacuum drill: full={size_full} afterDel={size_after_delete} "
          f"vac={size_vacuumed} freelist={fl}")
    return 1


def _safe_unlink(p: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        try:
            f = Path(str(p) + suffix)
            if f.exists():
                f.unlink()
        except OSError:
            pass


def do_check_sources() -> int:
    age = _newest_set_age_hours()
    md_dir = _find_memory_md_dir()
    md_count = len(list(md_dir.glob("*.md"))) if md_dir and md_dir.exists() else 0
    n_sets = len(list(BACKUP_DIR.glob("memory_*.db"))) if BACKUP_DIR.exists() else 0
    print(f"  curated .md topic files: {md_count}  (dir: {md_dir})")
    print(f"  backup sets on disk:     {n_sets}/{KEEP}  (newest: "
          f"{f'{age:.1f}h old' if age is not None else 'NONE — never backed up'})")
    db_mb = DB_PATH.stat().st_size / 1e6 if DB_PATH.exists() else 0
    print(f"  live memory.db:          {db_mb:.1f}MB  ({DB_PATH})")
    return 0


def main() -> int:
    print(f"{B}Memory-System M1.1 - memory.db backup + restore drill{X}")
    print("=" * 62)
    argv = sys.argv[1:]
    rc = 0
    if "--check-sources" in argv:
        return do_check_sources()
    if "--vacuum-drill" in argv:
        rc |= do_vacuum_drill()
    if "--vacuum" in argv:
        rc |= do_vacuum(force="--force" in argv)
    if "--backup" in argv:
        rc |= do_backup(force="--force" in argv)
    explicit = ("--backup", "--check-sources", "--vacuum", "--vacuum-drill")
    if "--drill" in argv or not any(a in argv for a in explicit):
        rc |= do_drill()
    if rc == 0:
        print(f"\n{G}{B}  MEMORY.DB BACKUP/RESTORE: PASS{X} - a snapshot restores to a working, queryable DB.")
    else:
        print(f"\n{R}{B}  MEMORY.DB BACKUP/RESTORE: FAIL{X}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
