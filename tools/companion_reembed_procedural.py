#!/usr/bin/env python3
"""companion_reembed_procedural.py - Companion-Memory C2.3: re-embed retry for null procedural memories.
================================================================================
A procedural memory stored with embedding=NULL (the persistEpisodic embed was best-effort and the
provider missed) is INVISIBLE to match_procedural_memories FOREVER (the RPC filters `embedding IS NOT
NULL`) — the "invisible-forever" skill-library bug. This adds the missing back-fill: find null-embedding
procedural rows, re-embed their content, and write the vector back so the proven fix becomes retrievable.

  --self-test  (gate) prove the MECHANISM deterministically, no embedding provider + no pollution: in a
               ROLLED-BACK transaction, insert a procedural row with embedding=NULL, assert
               match_procedural_memories does NOT return it (invisible), write a vector (the re-embed
               step), assert it IS now returned (searchable). RAISE EXCEPTION on mismatch -> exit 1.
  --backfill   operational: SELECT procedural rows WHERE embedding IS NULL, embed each via
               tools/embedding_helper (Jina / local / the BGE embed_server in prod), UPDATE. Degrades-to-
               SKIP if no embedding provider is reachable (never fabricates a vector in prod data).
  (default)    --self-test.

Exit 0 = mechanism proven (or backfill done / SKIP); 1 = the re-embed did NOT make the row searchable.
Reuses the LOCAL docker DB + the existing embedding_helper; never fabricates a real embedding.
"""
from __future__ import annotations
import io, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
DB = "supabase_db_workhive"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"; B = "\033[1m"; X = "\033[0m"

SELFTEST_SQL = r"""
BEGIN;
DO $$
DECLARE
  v_emb vector := array_fill(0.1::real, ARRAY[384])::vector;
  v_id uuid; v_cnt int;
BEGIN
  INSERT INTO public.agent_episodic_memory(worker_name, memory_type, content, embedding, importance)
    VALUES ('__c23_reembed_selftest__','procedural','C23REEMBED canary procedure: torque 142 Nm', NULL, 0.9)
    RETURNING id INTO v_id;

  -- A null-embedding procedural memory is INVISIBLE to the matcher (the invisible-forever bug).
  SELECT count(*) INTO v_cnt FROM match_procedural_memories(v_emb, NULL, '__c23_reembed_selftest__', 10, 0.55);
  IF v_cnt <> 0 THEN RAISE EXCEPTION 'PRE: a null-embedding procedural row must be INVISIBLE, got % match(es)', v_cnt; END IF;

  -- The re-embed step (the back-fill writes the provider's vector; here a deterministic one).
  UPDATE public.agent_episodic_memory SET embedding = v_emb WHERE id = v_id;

  -- It is now SEARCHABLE.
  SELECT count(*) INTO v_cnt FROM match_procedural_memories(v_emb, NULL, '__c23_reembed_selftest__', 10, 0.55);
  IF v_cnt <> 1 THEN RAISE EXCEPTION 'POST: a re-embedded procedural row must be SEARCHABLE, got % match(es)', v_cnt; END IF;

  RAISE NOTICE 'REEMBED_OK null-procedural invisible(0) -> re-embedded -> searchable(1)';
END $$;
ROLLBACK;
"""


def _psql_in(sql: str, timeout: int = 60):
    return subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                           "-v", "ON_ERROR_STOP=1", "-f", "-"],
                          input=sql, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _psql(sql: str, timeout: int = 30):
    return subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _db_up() -> bool:
    try:
        r = _psql("select 1;", timeout=10)
        return r.returncode == 0 and r.stdout.strip().startswith("1")
    except Exception:
        return False


def do_self_test() -> int:
    print(f"{B}Companion-Memory C2.3 - re-embed-retry self-test{X}")
    print("=" * 62)
    if not _db_up():
        print(f"  {Y}SKIP{X} local DB ({DB}) not reachable. Not a failure.")
        return 0
    proc = _psql_in(SELFTEST_SQL)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0 and "REEMBED_OK" in out:
        print(f"  {G}OK{X} a null-embedding procedural memory is invisible to match_procedural_memories, "
              f"and becomes searchable after re-embedding (rolled-back, zero pollution).")
        print("=" * 62)
        return 0
    print(f"  {R}FAIL{X} {out.strip().splitlines()[-1] if out.strip() else 'psql exit '+str(proc.returncode)}")
    print("=" * 62)
    return 1


def do_backfill() -> int:
    print(f"{B}Companion-Memory C2.3 - re-embed null procedural memories (operational){X}")
    print("=" * 62)
    if not _db_up():
        print(f"  {Y}SKIP{X} local DB not reachable."); return 0
    n_null = _psql("select count(*) from public.agent_episodic_memory where memory_type='procedural' and embedding is null;")
    try:
        cnt = int((n_null.stdout or "0").strip())
    except ValueError:
        cnt = 0
    print(f"  null-embedding procedural rows: {cnt}")
    if cnt == 0:
        print(f"  {G}nothing to back-fill{X} — every procedural memory is embedded (searchable).")
        return 0
    # Fetch the null rows' id+content, embed via the configured provider, update.
    sys.path.insert(0, str(TOOLS))
    try:
        from embedding_helper import embed_text
    except Exception as e:
        print(f"  {Y}SKIP{X} embedding_helper unavailable ({type(e).__name__}); cannot re-embed now. "
              f"Set JINA_API_KEY / start the BGE embed_server, then re-run --backfill."); return 0
    rows = _psql("select id||'\t'||replace(content,chr(9),' ') from public.agent_episodic_memory "
                 "where memory_type='procedural' and embedding is null limit 200;")
    done = skipped = 0
    for line in (rows.stdout or "").splitlines():
        if "\t" not in line:
            continue
        rid, content = line.split("\t", 1)
        vec = None
        try:
            vec = embed_text(content)
        except Exception:
            vec = None
        if not vec:
            skipped += 1
            continue
        lit = "[" + ",".join(f"{float(x):.6f}" for x in vec[:384]) + "]"
        up = _psql(f"update public.agent_episodic_memory set embedding='{lit}'::vector where id='{rid}';")
        done += 1 if up.returncode == 0 else 0
    print(f"  re-embedded {done}/{cnt} (skipped {skipped} — provider returned no vector).")
    if done == 0 and skipped:
        print(f"  {Y}note{X} no embedding provider reachable; back-fill is a no-op until one is configured.")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if "--backfill" in argv:
        return do_backfill()
    return do_self_test()


if __name__ == "__main__":
    sys.exit(main())
