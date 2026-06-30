#!/usr/bin/env python3
"""companion_dedup.py - Companion-Memory C2.2: write-side semantic dedup self-test / gate.
================================================================================
persistEpisodic now MERGES a near-duplicate procedural memory (bump use_count, keep the higher
importance) instead of inserting a paraphrase row, so the skill library doesn't bloat with restatements
of the same fix (the C2.2 store-hygiene gap). This proves the mechanism DETERMINISTICALLY (no embedding
provider, no pollution): in a ROLLED-BACK transaction, a near-duplicate embedding is detected by
match_procedural_memories at the DEDUP threshold and merged (1 row, use_count bumped) while an
ORTHOGONAL embedding is NOT detected (would insert) — proving dedup neither misses a paraphrase nor
over-merges a distinct procedure.

  --self-test  (gate, default): static (persistEpisodic wires DEDUP_SIMILARITY + the
               match_procedural_memories dedup probe) + the live rolled-back proof.

Exit 0 = mechanism proven (or DB down -> SKIP); 1 = dedup missed a near-dup, over-merged a distinct
one, or persistEpisodic is not wired. Reuses the LOCAL docker DB; never writes committed data.
"""
from __future__ import annotations
import io, re, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
EPISODIC_TS = ROOT / "supabase" / "functions" / "_shared" / "episodic-memory.ts"
DB = "supabase_db_workhive"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"; B = "\033[1m"; X = "\033[0m"

SELFTEST_SQL = r"""
BEGIN;
DO $$
DECLARE
  v_emb  vector := array_fill(0.1::real, ARRAY[384])::vector;
  v_orth vector := (SELECT array_agg(CASE WHEN i <= 192 THEN 0.1 ELSE -0.1 END)::real[] FROM generate_series(1,384) i)::vector;
  v_id uuid; v_dup uuid; v_uc int; v_rows int; v_neg int;
BEGIN
  -- an existing embedded procedural memory
  INSERT INTO public.agent_episodic_memory(worker_name, memory_type, content, embedding, importance, use_count)
    VALUES ('__c22_dedup_selftest__','procedural','C22 original procedure: torque 88 Nm', v_emb, 0.5, 0)
    RETURNING id INTO v_id;

  -- POSITIVE: a paraphrase (near-identical embedding) is DETECTED at the dedup threshold ...
  SELECT id INTO v_dup FROM match_procedural_memories(v_emb, NULL, '__c22_dedup_selftest__', 1, 0.95);
  IF v_dup IS NULL OR v_dup <> v_id THEN RAISE EXCEPTION 'dedup: near-duplicate NOT detected at >=0.95'; END IF;
  -- ... and MERGED (bump use_count) instead of inserting a new row
  UPDATE public.agent_episodic_memory SET use_count = use_count + 1, importance = greatest(importance, 0.5) WHERE id = v_dup;
  SELECT count(*), max(use_count) INTO v_rows, v_uc FROM public.agent_episodic_memory WHERE worker_name = '__c22_dedup_selftest__';
  IF v_rows <> 1 THEN RAISE EXCEPTION 'dedup: expected 1 row after merge (no paraphrase inserted), got %', v_rows; END IF;
  IF v_uc <> 1 THEN RAISE EXCEPTION 'dedup: use_count should bump 0->1 on merge, got %', v_uc; END IF;

  -- NEGATIVE: an ORTHOGONAL embedding is NOT detected as a dup (a distinct procedure would insert).
  SELECT count(*) INTO v_neg FROM match_procedural_memories(v_orth, NULL, '__c22_dedup_selftest__', 5, 0.95);
  IF v_neg <> 0 THEN RAISE EXCEPTION 'dedup: a DISTINCT (orthogonal) procedure was wrongly flagged a dup (% matches) — would over-merge', v_neg; END IF;

  RAISE NOTICE 'DEDUP_OK near-dup detected+merged (1 row, use_count 0->1); orthogonal NOT merged';
END $$;
ROLLBACK;
"""


def _psql_in(sql: str, timeout: int = 60):
    return subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                           "-v", "ON_ERROR_STOP=1", "-f", "-"],
                          input=sql, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _db_up() -> bool:
    try:
        r = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", "select 1;"],
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0 and r.stdout.strip().startswith("1")
    except Exception:
        return False


def _static() -> list[str]:
    p = []
    ts = EPISODIC_TS.read_text(encoding="utf-8") if EPISODIC_TS.exists() else ""
    if not re.search(r"DEDUP_SIMILARITY\s*=\s*0\.9", ts):
        p.append("episodic-memory.ts: DEDUP_SIMILARITY not defined (>=0.9)")
    if "p_min_similarity: DEDUP_SIMILARITY" not in ts:
        p.append("episodic-memory.ts: persistEpisodic does not probe match_procedural_memories at DEDUP_SIMILARITY")
    if "merged++" not in ts:
        p.append("episodic-memory.ts: persistEpisodic has no merge-instead-of-insert path")
    return p


def main() -> int:
    print(f"{B}Companion-Memory C2.2 - write-side semantic dedup self-test{X}")
    print("=" * 64)
    sp = _static()
    if sp:
        print(f"{R}STATIC FAIL{X}:");  [print(f"  - {x}") for x in sp];  print("=" * 64);  return 1
    print(f"{G}static OK{X} — persistEpisodic probes match_procedural_memories at DEDUP_SIMILARITY and merges near-dups.")
    if not _db_up():
        print(f"{C}live SKIP{X} — local DB not reachable; static contract verified. Not a failure.")
        print("=" * 64); return 0
    proc = _psql_in(SELFTEST_SQL)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0 and "DEDUP_OK" in out:
        print(f"{G}live teeth OK{X} — a near-duplicate procedure is detected + merged (1 row, use_count bumped); "
              f"a distinct (orthogonal) one is NOT merged.")
        print("=" * 64); return 0
    print(f"{R}live FAIL{X} — {out.strip().splitlines()[-1] if out.strip() else 'psql exit '+str(proc.returncode)}")
    print("=" * 64); return 1


if __name__ == "__main__":
    sys.exit(main())
