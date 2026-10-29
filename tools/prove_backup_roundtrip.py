"""prove_backup_roundtrip.py - BRH 9 AE (BRH515, 2026-10-29): the daily backup is real, private and restorable.

Supabase Free keeps no daily backups. .github/workflows/backup.yml runs tools/backup_dump.sh every day against
production; this runs THAT SAME SCRIPT against the local database, with a passphrase made for the run, and proves what
the scheduled run cannot show about itself:

  B1 the file that would be uploaded is OpenPGP symmetric ciphertext (its first packet is a passphrase-encrypted
     session key), and none of the dump's text is readable in it - not a COPY line, not a table definition, not the
     name of a hive in the database
  B2 the wrong passphrase gets nothing back
  B3 decrypted, the dump holds every row of every critical table (data_backup.CRITICAL_TABLES - the tenant, the work
     log, the PM plan, stock, marketplace, the audit trail): its COPY block counts what the live table counts
  B4 a real restore: three tables' COPY blocks go back into a scratch schema, and the restored rows read exactly what
     the source reads (count and an md5 of every row), then the scratch is dropped
  TEETH each check reddens on what it exists to catch: the gzip it encrypts read as the upload, the decrypted text read
     as the upload, a block one row short, a restore one row short

Needs Docker, the Supabase CLI and gpg (Git for Windows ships it). Exit 0 = proven; 1 = a check failed or the local
database is down (never a silent pass). Reads no secret; touches no production.

    python tools/prove_backup_roundtrip.py
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from data_backup import CRITICAL_TABLES  # noqa: E402

DB = "supabase_db_workhive"
LOCAL_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
RESTORE = ["hives", "logbook", "inventory_items"]
COPY_HEAD = re.compile(rb'^COPY "public"\."([^"]+)" \(([^)]*)\) FROM stdin;$')


def _bash() -> str | None:
    if sys.platform == "win32":
        for p in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"):
            if os.path.exists(p):
                return p
    return shutil.which("bash")


def _psql(sql: str, stdin: bytes | None = None, timeout: int = 300) -> tuple[int, str]:
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At",
                        "-v", "ON_ERROR_STOP=1"] + (["-c", sql] if stdin is None else []),
                       input=stdin, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        return r.returncode, (r.stderr or b"").decode("utf-8", "replace").strip()[:400]
    return 0, (r.stdout or b"").decode("utf-8", "replace").strip()


def _gpg(passphrase: str, args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(["gpg", "--batch", "--quiet", "--pinentry-mode", "loopback", "--passphrase-fd", "0"] + args,
                          input=passphrase.encode(), capture_output=True, timeout=timeout)


def ciphertext_issues(blob: bytes, markers: list[bytes]) -> list[str]:
    """B1: OpenPGP symmetric (old-format tag 3 = 0x8c, new-format = 0xc3) and no marker readable."""
    out = []
    if not blob or blob[0] not in (0x8C, 0xC3):
        out.append(f"B1 the upload does not start with a passphrase-encrypted session key (first byte "
                   f"{blob[:1].hex() or 'none'}) - it is not OpenPGP symmetric ciphertext")
    for m in markers:
        if m and m in blob:
            out.append(f"B1 the upload carries readable dump text: {m[:40]!r}")
    return out


def copy_blocks(data_sql, wanted: set[str]) -> dict[str, tuple[str, list[bytes]]]:
    """{table: (column list, [row lines])} for each public table in wanted, streamed from data.sql's lines."""
    out, cur = {}, None
    for raw in data_sql:
        line = raw.rstrip(b"\r\n")
        if cur is None:
            m = COPY_HEAD.match(line)
            if m and m.group(1).decode() in wanted:
                cur = m.group(1).decode()
                out[cur] = (m.group(2).decode(), [])
        elif line == b"\\.":
            cur = None
        else:
            out[cur][1].append(line)
    return out


def count_issues(blocks: dict, live: dict[str, int]) -> list[str]:
    """B3: each critical table's block holds what the live table holds."""
    out = []
    for t, n in live.items():
        if t not in blocks:
            out.append(f"B3 public.{t} ({n} rows) has no COPY block in the backup")
        elif len(blocks[t][1]) != n:
            out.append(f"B3 public.{t}: the backup holds {len(blocks[t][1])} rows, the database {n}")
    return out


def _digest(source: str, cols: str) -> tuple[int, str] | None:
    rc, out = _psql(f"select count(*) || ' ' || coalesce(md5(string_agg(r, E'\\n' order by r)), '') "
                    f"from (select ({cols})::text as r from {source}) q")
    if rc != 0 or " " not in out:
        return None
    n, h = out.split(" ", 1)
    return int(n), h


def restore_issues(blocks: dict, tables: list[str], drop_one: bool = False) -> list[str]:
    """B4: the blocks go back into dr_restore.<t>; restored rows read what the source reads."""
    out = []
    rc, msg = _psql("drop schema if exists dr_restore cascade; create schema dr_restore;")
    if rc != 0:
        return [f"B4 could not make the scratch schema: {msg}"]
    try:
        for t in tables:
            if t not in blocks:
                out.append(f"B4 public.{t} has no block to restore")
                continue
            cols, rows = blocks[t]
            rows = rows[:-1] if (drop_one and rows) else rows
            rc, msg = _psql(f"create table dr_restore.{t} (like public.{t})")
            if rc != 0:
                out.append(f"B4 dr_restore.{t}: {msg}")
                continue
            feed = (f"COPY dr_restore.{t} ({cols}) FROM stdin;\n").encode() + b"\n".join(rows) + (b"\n" if rows else b"") + b"\\.\n"
            rc, msg = _psql("", stdin=feed)
            if rc != 0:
                out.append(f"B4 restoring public.{t} failed: {msg}")
                continue
            src, back = _digest(f"public.{t}", cols), _digest(f"dr_restore.{t}", cols)
            if src is None or back is None:
                out.append(f"B4 public.{t}: could not read the digests")
            elif src != back:
                out.append(f"B4 public.{t}: restored {back[0]} rows (md5 {back[1][:8]}), the source reads {src[0]} "
                           f"(md5 {src[1][:8]})")
    finally:
        _psql("drop schema if exists dr_restore cascade")
    return out


def main() -> int:
    print("Backup round trip (BRH 9 AE): the daily dump is encrypted, refuses the wrong passphrase, and restores")
    rc, up = _psql("select 1")
    if rc != 0 or up != "1":
        print("  [FAIL] the local database is not reachable - nothing proven")
        return 1
    bash = _bash()
    if not bash or not shutil.which("gpg") or not shutil.which("supabase"):
        print(f"  [FAIL] needs bash, gpg and the Supabase CLI (bash={bool(bash)} gpg={bool(shutil.which('gpg'))} "
              f"supabase={bool(shutil.which('supabase'))})")
        return 1
    work = Path(tempfile.mkdtemp(prefix="whbk-"))
    passphrase = secrets.token_urlsafe(32)
    issues: list[str] = []
    try:
        env = dict(os.environ, SUPABASE_DB_URL=LOCAL_URL, BACKUP_PASSPHRASE=passphrase,
                   TMPDIR=work.as_posix())
        r = subprocess.run([bash, (ROOT / "tools" / "backup_dump.sh").as_posix(), (work / "out").as_posix()],
                           env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1200)
        said = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.startswith(("backup ", "::error::"))]
        if r.returncode != 0:
            print("  [FAIL] tools/backup_dump.sh failed: " + (said[-1] if said else (r.stderr or r.stdout)[-300:]))
            return 1
        files = sorted((work / "out").glob("*.tar.gz.gpg"))
        leftovers = [p.name for p in (work / "out").iterdir() if p.suffix != ".gpg"]
        if len(files) != 1 or leftovers:
            print(f"  [FAIL] the script left {len(files)} encrypted file(s) and {leftovers} beside them")
            return 1
        enc = files[0]
        if any(work.glob("whbackup.*")):
            issues.append("B1 the plaintext working directory outlived the run")
        live = {}
        for t in CRITICAL_TABLES:
            rc, n = _psql(f"select count(*) from public.{t}")
            if rc == 0 and n.isdigit():
                live[t] = int(n)
        rc, hive = _psql("select name from public.hives where length(name) >= 6 order by created_at limit 1")
        blob = enc.read_bytes()
        markers = [b'COPY "public"', b"CREATE TABLE", hive.encode() if rc == 0 else b""]
        issues += ciphertext_issues(blob, markers)
        wrong = _gpg(passphrase + "x", ["--decrypt", str(enc)])
        if wrong.returncode == 0 or wrong.stdout:
            issues.append("B2 a wrong passphrase decrypted the backup")
        gz = work / "back.tar.gz"
        right = _gpg(passphrase, ["--output", str(gz), "--decrypt", str(enc)])
        if right.returncode != 0:
            issues.append("B2 the right passphrase could not decrypt the backup")
            blocks = {}
        else:
            with tarfile.open(gz, "r:gz") as tf:
                names = sorted(tf.getnames())
                if names != ["data.sql", "roles.sql", "schema.sql"]:
                    issues.append(f"B3 the backup holds {names}, not roles, schema and data")
                blocks = copy_blocks(tf.extractfile("data.sql"), set(live) | set(RESTORE))
        issues += count_issues(blocks, live)
        if blocks:
            issues += restore_issues(blocks, RESTORE)
        # TEETH - each check must redden on what it exists to catch
        teeth = []
        if gz.exists():
            head = gz.read_bytes()[:1 << 20]
            if not ciphertext_issues(head, markers):
                teeth.append("B1 passed the unencrypted gzip as the upload")
        if blocks and not ciphertext_issues(b"\x8c" + b"\n".join(blocks[RESTORE[0]][1][:5]) + b'COPY "public"', markers):
            teeth.append("B1 passed readable dump text behind an OpenPGP first byte")
        short = {t: (c, rows[:-1]) for t, (c, rows) in blocks.items()}
        if blocks and any(live.values()) and not count_issues(short, {t: n for t, n in live.items() if n}):
            teeth.append("B3 passed a backup one row short")
        if blocks and not restore_issues(blocks, RESTORE[:1], drop_one=True):
            teeth.append("B4 passed a restore one row short")
        issues += ["TEETH " + t for t in teeth]
        for i in issues:
            print("  [FAIL] " + i)
        rows = sum(len(blocks[t][1]) for t in live if t in blocks)
        print(f"  {'PASS' if not issues else 'FAIL'} - {said[-1] if said else ''}; {len(live)} critical tables, "
              f"{rows} rows, each counted in the backup; restored {', '.join(RESTORE)} row for row; the wrong "
              f"passphrase refused; 4 teeth bite" if not issues else f"  FAIL - {len(issues)} problem(s)")
        return 1 if issues else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
