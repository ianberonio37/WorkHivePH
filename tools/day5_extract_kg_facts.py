"""Day 5 (BONUS L5): Extract knowledge_graph_facts triples from standards corpus.

Reads chunks from industry_standards_chunks, runs them through the 14-model
fallback chain (tools/lib/ai_chain.py — mirrors _shared/ai-chain.ts) to extract
subject/predicate/object triples in JSON, inserts into knowledge_graph_facts
(hive-scoped; uses the test hive).

Schema constraints enforced:
  subject_type / predicate / object_type: lowercase + underscores, max 31 chars
  source_type: must be 'standard' for this batch
  confidence: 0-1

Why the chain (not just Groq): the previous version pinned to one Groq model
and died at the 12K TPM ceiling. The chain rolls Groq -> Cerebras -> OpenRouter
automatically on 429.

Per-row SAVEPOINT insert: any one bad triple rolls back ONLY that row, not the
whole chunk's good triples.
"""
from __future__ import annotations

import os
import sys
import io
import re
import json
import time
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))   # so `tools.lib.ai_chain` imports cleanly
load_dotenv(ROOT / ".env")

from tools.lib.ai_chain import call_ai, AIChainError   # noqa: E402

# Hive IDs change on every full reseed — look it up at runtime by name.
DEMO_HIVE_NAME = "Baguio Textile Mills"
CHUNKS_TO_PROCESS = 150   # full standards corpus (NIST 100 + US Army 50)

# Schema allowlist (mirrors CHECK constraints + common-sense subset)
ALLOWED_SUBJECT_TYPES = {
    "asset", "failure_mode", "sop", "worker", "part", "lesson",
    "system", "control", "hazard", "process",
}
ALLOWED_PREDICATES = {
    "causes", "detects", "requires", "mitigates", "related_to",
    "prevents", "monitors", "uses", "applies_to", "documents", "warns_against",
}
ALLOWED_OBJECT_TYPES = ALLOWED_SUBJECT_TYPES  # same vocabulary on both sides


def sanitize_type(s: str) -> str:
    """Force CHECK-compliant form: lowercase, underscores, <=31 chars."""
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:31] or "concept"


def extract_triples(chunk_text: str, standard_code: str) -> tuple[list[dict], str]:
    """Run chunk through the AI chain. Returns (triples, provider_label)."""
    prompt = (
        "Extract subject/predicate/object knowledge-graph triples from this "
        "industrial standards text. The triples will be queried by a maintenance "
        "AI assistant.\n\n"
        f"SOURCE STANDARD: {standard_code}\n\n"
        "RULES:\n"
        "- Output STRICT JSON. Either an object like {\"triples\": [...]} OR a bare array. No markdown, no commentary.\n"
        "- Each triple has keys: subject_type, subject_ref, predicate, object_type, object_ref, claim_text, confidence (0-1).\n"
        "- subject_type / predicate / object_type MUST be lowercase snake_case, <=30 chars.\n"
        f"- Prefer these subject/object types: {sorted(ALLOWED_SUBJECT_TYPES)}\n"
        f"- Prefer these predicates: {sorted(ALLOWED_PREDICATES)}\n"
        "- subject_ref / object_ref: short noun phrases as they appear in text.\n"
        "- claim_text: one short sentence stating the triple in plain English.\n"
        "- Extract 3-8 triples per chunk. Empty array if the chunk is TOC/preface/junk.\n"
        "- confidence: 0.9 if explicit in text; 0.7 if implied; 0.5 if speculative.\n\n"
        f"CHUNK:\n{chunk_text[:3000]}"
    )
    content, label = call_ai(prompt, temperature=0.1, max_tokens=1500, json_mode=True)
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```\s*$", "", content)

    # Try to parse as object first (response_format=json_object often returns that)
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            for key in ("triples", "facts", "data", "items", "result"):
                if isinstance(parsed.get(key), list):
                    return parsed[key], label
            return [], label
        if isinstance(parsed, list):
            return parsed, label
    except json.JSONDecodeError:
        pass

    # Fallback: find a JSON array anywhere in the text
    m = re.search(r"\[.*\]", content, re.DOTALL)
    if not m:
        return [], label
    try:
        return json.loads(m.group(0)), label
    except json.JSONDecodeError:
        return [], label


def main() -> int:
    print("=" * 72)
    print("DAY 5 (L5): EXTRACT knowledge_graph_facts FROM standards corpus")
    print("Provider chain: Groq -> Cerebras -> OpenRouter (tools/lib/ai_chain.py)")
    print("=" * 72)

    conn = psycopg2.connect(host="127.0.0.1", port=54322,
                            user="postgres", password="postgres", database="postgres")
    # autocommit=True so each INSERT is its own transaction — a bad row can't
    # poison the others. No SAVEPOINT bookkeeping needed.
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT id FROM hives WHERE name = %s LIMIT 1", (DEMO_HIVE_NAME,))
    row = cur.fetchone()
    if not row:
        cur.execute("SELECT id, name FROM hives LIMIT 1")
        row = cur.fetchone()
        if not row:
            print("[FAIL] No hives in DB. Run the seeder first.")
            return 1
        print(f"[INFO] '{DEMO_HIVE_NAME}' not found; using fallback hive '{row[1]}'")
    hive_id = str(row[0])
    print(f"Hive id: {hive_id}")
    print()

    # Pull a spread of chunks across all standards we have full text for
    cur.execute("""
        SELECT isc.id, isc.chunk_num, isc.section, isc.text, s.standard_code, s.id
          FROM industry_standards_chunks isc
          JOIN industry_standards s ON isc.standard_id = s.id
         ORDER BY s.standard_code, isc.chunk_num
         LIMIT %s
    """, (CHUNKS_TO_PROCESS,))
    chunks = cur.fetchall()
    print(f"Processing {len(chunks)} chunks across the standards corpus\n")

    total_facts   = 0
    failed_chunks = 0
    providers_seen: dict[str, int] = {}

    for ci, (chunk_id, chunk_num, section, text, std_code, std_id) in enumerate(chunks, start=1):
        label = f"{std_code} chunk {chunk_num}"
        print(f"[{ci:2d}/{len(chunks)}] {label}")

        try:
            triples, provider_label = extract_triples(text, std_code)
            providers_seen[provider_label] = providers_seen.get(provider_label, 0) + 1
        except AIChainError as e:
            print(f"        FAIL chain exhausted: {str(e)[:160]}")
            failed_chunks += 1
            continue
        except Exception as e:
            print(f"        FAIL {e.__class__.__name__}: {e}")
            failed_chunks += 1
            continue

        if not triples:
            print(f"        skipped (no triples)  [{provider_label}]")
            continue

        inserted = 0
        skipped  = 0
        errored  = 0
        for t in triples:
            st = sanitize_type(t.get("subject_type", ""))
            ot = sanitize_type(t.get("object_type", ""))
            pr = sanitize_type(t.get("predicate", ""))
            sub_ref = (t.get("subject_ref") or "").strip()[:200]
            obj_ref = (t.get("object_ref") or "").strip()[:200]
            claim   = (t.get("claim_text") or "").strip()[:1000]
            try:
                conf = max(0.0, min(1.0, float(t.get("confidence") or 0.7)))
            except (TypeError, ValueError):
                conf = 0.7

            if not (st and ot and pr and sub_ref and obj_ref):
                skipped += 1
                continue

            # autocommit=True means each INSERT is its own transaction — a bad
            # row can't poison the others. No SAVEPOINT bookkeeping needed.
            try:
                cur.execute("""
                    INSERT INTO knowledge_graph_facts
                      (hive_id, subject_type, subject_ref, predicate, object_type, object_ref,
                       claim_text, confidence, source_type, source_ref, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'standard', %s, 'day5_extractor')
                """, (hive_id, st, sub_ref, pr, ot, obj_ref, claim, conf,
                      f"{std_code} chunk_{chunk_num}"))
                inserted += 1
            except psycopg2.Error as e:
                errored += 1
                if errored <= 1:   # log the first error per chunk to diagnose
                    print(f"          DB err: {e.__class__.__name__}: {str(e)[:160]}")
                    print(f"          row: st={st!r} pr={pr!r} ot={ot!r} sub={sub_ref[:40]!r} obj={obj_ref[:40]!r}")
                continue

        total_facts += inserted
        notes = []
        if skipped: notes.append(f"{skipped} skipped")
        if errored: notes.append(f"{errored} errored")
        print(f"        +{inserted} triples ({', '.join(notes) or 'clean'}) [{provider_label}]   running total: {total_facts}")
        time.sleep(0.4)

    cur.execute("SELECT COUNT(*) FROM knowledge_graph_facts WHERE created_by='day5_extractor'")
    total_in_table = cur.fetchone()[0]

    print(f"\n{'='*72}\nRESULT\n{'='*72}")
    print(f"  Chunks processed:    {len(chunks)}")
    print(f"  Failed chunks:       {failed_chunks}")
    print(f"  Facts inserted:      {total_facts}")
    print(f"  Total day5 facts:    {total_in_table}")
    if providers_seen:
        print(f"\n  Providers used (rolled through chain on rate limits):")
        for p, n in sorted(providers_seen.items(), key=lambda x: -x[1]):
            print(f"    {p}: {n} chunks")

    # Breakdown by predicate
    cur.execute("""
        SELECT predicate, COUNT(*) FROM knowledge_graph_facts
         WHERE created_by='day5_extractor'
         GROUP BY predicate ORDER BY 2 DESC LIMIT 10
    """)
    print("\nTop predicates:")
    for pred, cnt in cur.fetchall():
        print(f"  {pred}: {cnt}")

    cur.execute("""
        SELECT subject_ref, predicate, object_ref, claim_text
          FROM knowledge_graph_facts
         WHERE created_by='day5_extractor'
         ORDER BY random() LIMIT 5
    """)
    print("\nSample triples:")
    for s, p, o, claim in cur.fetchall():
        print(f"  {s[:30]:30s} --{p:20s}--> {o[:30]}")
        if claim:
            print(f"     ({claim[:100]})")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
