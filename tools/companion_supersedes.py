"""
Companion-Memory C2.1 — store-level supersedes down-rank self-test / gate.
=========================================================================
Proves the SAFETY mechanism: when an episodic memory is CORRECTED/replaced, the
obsolete row must be down-ranked at retrieval so it cannot co-surface as current
with its reversal (an outdated procedure presented as current is a maintenance
hazard). Native port of Memento M3.2's `supersedes` (tools/memory_supersedes.py,
×0.4 penalty) onto the Companion's pg+pgvector store.

Two layers of proof:
  1. STATIC (always): the migration adds `superseded_by` and the
     match_procedural_memories RPC applies the ×0.4 penalty; _shared/episodic-memory.ts
     defines SUPERSEDE_PENALTY, applies it GUARDED in recallEpisodic, and exposes
     supersedeEpisodic(). Deterministic; no stack needed.
  2. LIVE TEETH (degrade-to-SKIP if the local DB is down): inside ONE transaction
     that is ROLLED BACK (zero pollution), seed two identical-embedding procedural
     memories, prove match_procedural_memories returns BOTH (count=2), mark one
     `superseded_by` the other, prove it now returns ONLY the replacement (count=1)
     — the obsolete row's penalized similarity (1.0×0.4=0.4) falls below the 0.55
     gate. RAISE EXCEPTION on any mismatch -> psql exits non-zero -> gate FAILs.

Exit: 0 = static OK and (live proof passed OR DB down -> SKIP); 1 = a static
assertion missing OR the live down-rank did not work (a real defect).
"""
from __future__ import annotations
import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "supabase" / "migrations" / "20260624000002_episodic_supersedes.sql"
EPISODIC_TS = ROOT / "supabase" / "functions" / "_shared" / "episodic-memory.ts"
DB_CONTAINER = "supabase_db_workhive"

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"

LIVE_SQL = r"""
BEGIN;
DO $$
DECLARE
  v_emb vector := array_fill(0.1::real, ARRAY[384])::vector;
  v_old uuid; v_new uuid; v_cnt int; v_remaining uuid;
BEGIN
  INSERT INTO public.agent_episodic_memory(worker_name, memory_type, content, embedding, importance)
    VALUES ('__supersedes_selftest__','procedural','TESTSUPERSEDE old procedure', v_emb, 0.5) RETURNING id INTO v_old;
  INSERT INTO public.agent_episodic_memory(worker_name, memory_type, content, embedding, importance)
    VALUES ('__supersedes_selftest__','procedural','TESTSUPERSEDE new procedure', v_emb, 0.5) RETURNING id INTO v_new;

  SELECT count(*) INTO v_cnt FROM match_procedural_memories(v_emb, NULL, '__supersedes_selftest__', 10, 0.55);
  IF v_cnt <> 2 THEN RAISE EXCEPTION 'PRE: expected 2 procedural matches before supersede, got %', v_cnt; END IF;

  UPDATE public.agent_episodic_memory SET superseded_by = v_new, superseded_at = now() WHERE id = v_old;

  SELECT count(*) INTO v_cnt FROM match_procedural_memories(v_emb, NULL, '__supersedes_selftest__', 10, 0.55);
  IF v_cnt <> 1 THEN RAISE EXCEPTION 'POST: expected 1 match after supersede (replacement only), got %', v_cnt; END IF;

  SELECT id INTO v_remaining FROM match_procedural_memories(v_emb, NULL, '__supersedes_selftest__', 10, 0.55);
  IF v_remaining <> v_new THEN RAISE EXCEPTION 'POST: remaining match is the obsolete row, not the replacement'; END IF;

  RAISE NOTICE 'SUPERSEDE_OK before=2 after=1 remaining=replacement (obsolete dropped below 0.55 gate via x0.4)';
END $$;
ROLLBACK;
"""


def _static_checks() -> list[str]:
    problems: list[str] = []
    mig = MIGRATION.read_text(encoding="utf-8") if MIGRATION.exists() else ""
    if not mig:
        problems.append(f"migration missing: {MIGRATION.name}")
    else:
        if "superseded_by" not in mig:
            problems.append("migration: no superseded_by column")
        if "0.4" not in mig or "match_procedural_memories" not in mig:
            problems.append("migration: match_procedural_memories ×0.4 supersede penalty not found")
    ts = EPISODIC_TS.read_text(encoding="utf-8") if EPISODIC_TS.exists() else ""
    if not ts:
        problems.append(f"episodic-memory.ts missing: {EPISODIC_TS}")
    else:
        if not re.search(r"SUPERSEDE_PENALTY\s*=\s*0\.4", ts):
            problems.append("episodic-memory.ts: SUPERSEDE_PENALTY = 0.4 not defined")
        if "superseded_by ? SUPERSEDE_PENALTY" not in ts:
            problems.append("episodic-memory.ts: guarded penalty not applied in recallEpisodic ranking")
        if "export async function supersedeEpisodic" not in ts:
            problems.append("episodic-memory.ts: supersedeEpisodic() helper not exported")
        if "last_used_at, superseded_by" not in ts:
            problems.append("episodic-memory.ts: recall SELECT does not fetch superseded_by")
    return problems


def _live_proof() -> tuple[str, str]:
    """Returns (status, detail). status in {PASS, SKIP, FAIL}."""
    try:
        proc = subprocess.run(
            ["docker", "exec", "-i", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
             "-v", "ON_ERROR_STOP=1", "-f", "-"],
            input=LIVE_SQL, capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        return "SKIP", "docker not found"
    except subprocess.TimeoutExpired:
        return "FAIL", "psql timed out"
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        low = out.lower()
        if ("could not connect" in low or "no such container" in low or "is not running" in low
                or "error during connect" in low or "cannot connect to the docker" in low):
            return "SKIP", "local DB container down (degrade-to-SKIP, not a failure)"
        return "FAIL", out.strip().splitlines()[-1] if out.strip() else f"psql exit {proc.returncode}"
    if "SUPERSEDE_OK" in out:
        return "PASS", "before=2 after=1 (obsolete dropped below the 0.55 gate)"
    return "FAIL", "psql exited 0 but the SUPERSEDE_OK proof line was absent"


def main() -> int:
    print(f"\n{BOLD}Companion-Memory C2.1 supersedes self-test{RESET}")
    print("=" * 70)
    problems = _static_checks()
    if problems:
        print(f"{RED}STATIC FAIL{RESET}:")
        for p in problems:
            print(f"  - {p}")
        print("=" * 70)
        return 1
    print(f"{GREEN}static OK{RESET} — migration superseded_by + RPC ×0.4 penalty; "
          f"episodic-memory.ts SUPERSEDE_PENALTY + guarded recall down-rank + supersedeEpisodic().")

    status, detail = _live_proof()
    if status == "PASS":
        print(f"{GREEN}live teeth OK{RESET} — a superseded procedure ranks below its replacement: {detail}")
        print("=" * 70)
        return 0
    if status == "SKIP":
        print(f"{CYAN}live teeth SKIP{RESET} — {detail}. Static contract verified; not a failure.")
        print("=" * 70)
        return 0
    print(f"{RED}live teeth FAIL{RESET} — {detail}")
    print("  The supersede down-rank did NOT take effect — an obsolete procedure can still co-surface.")
    print("=" * 70)
    return 1


if __name__ == "__main__":
    sys.exit(main())
