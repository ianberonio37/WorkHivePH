"""Day 5 (BONUS L5): Extract knowledge_graph_facts triples from standards corpus.

Reads chunks from industry_standards_chunks, prompts Groq llama-3.3-70b to
extract subject/predicate/object triples in JSON, inserts into
knowledge_graph_facts (hive-scoped; uses the test hive).

Schema constraints enforced:
  subject_type / predicate / object_type: lowercase + underscores, max 31 chars
  source_type: must be 'standard' for this batch
  confidence: 0-1

Free-tier costs: ~25 chunks x 1 Groq call each = 25 calls. Free tier is
9,000/day, 128/min. Pacing handles the per-minute limit.
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
import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"
TEST_HIVE_ID = "3776bd17-97f0-4a3c-a850-11c992cb140c"   # Baguio Textile Mills, demo hive
CHUNKS_TO_PROCESS = 25  # bounded for this bonus pass

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


def extract_triples(chunk_text: str, standard_code: str) -> list[dict]:
    """One Groq call. Returns list of triple dicts."""
    prompt = (
        "You extract subject/predicate/object knowledge-graph triples from "
        "industrial standards text. The triples will be queried by a "
        "maintenance AI assistant.\n\n"
        f"SOURCE STANDARD: {standard_code}\n\n"
        "RULES:\n"
        "- Output STRICT JSON: an array of objects. No markdown, no commentary.\n"
        "- Each object has keys: subject_type, subject_ref, predicate, object_type, object_ref, claim_text, confidence (0-1).\n"
        "- subject_type / predicate / object_type MUST be lowercase snake_case, <=30 chars.\n"
        f"- Use these subject/object types when applicable: {sorted(ALLOWED_SUBJECT_TYPES)}\n"
        f"- Use these predicates when applicable: {sorted(ALLOWED_PREDICATES)}\n"
        "- subject_ref / object_ref: short noun phrases as they appear in text.\n"
        "- claim_text: one short sentence stating the triple in plain English.\n"
        "- Extract 3-8 triples per chunk. Skip the chunk if it's TOC/preface/junk.\n"
        "- confidence: 0.9 if explicit in text; 0.7 if implied; 0.5 if speculative.\n\n"
        f"CHUNK:\n{chunk_text[:3000]}"
    )
    res = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.1, "max_tokens": 1500},
        timeout=60,
    )
    if not res.ok:
        raise RuntimeError(f"Groq {res.status_code}: {res.text[:200]}")
    content = res.json()["choices"][0]["message"]["content"].strip()
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```\s*$", "", content)
    m = re.search(r"\[.*\]", content, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return []


def main() -> int:
    print("=" * 72)
    print("DAY 5 (L5): EXTRACT knowledge_graph_facts FROM standards corpus")
    print("=" * 72)
    if not GROQ_API_KEY:
        print("[FAIL] GROQ_API_KEY missing")
        return 1

    conn = psycopg2.connect(host="127.0.0.1", port=54322,
                            user="postgres", password="postgres", database="postgres")
    cur = conn.cursor()

    # Pull a spread of chunks across all standards we have full text for
    cur.execute("""
        SELECT isc.id, isc.chunk_num, isc.section, isc.text, s.standard_code, s.id
          FROM industry_standards_chunks isc
          JOIN industry_standards s ON isc.standard_id = s.id
         ORDER BY s.standard_code, isc.chunk_num
         LIMIT %s
    """, (CHUNKS_TO_PROCESS,))
    chunks = cur.fetchall()
    print(f"Processing {len(chunks)} chunks across the standards corpus")
    print()

    total_facts = 0
    failed_chunks = 0

    for ci, (chunk_id, chunk_num, section, text, std_code, std_id) in enumerate(chunks, start=1):
        label = f"{std_code} chunk {chunk_num}"
        print(f"[{ci:2d}/{len(chunks)}] {label}")
        try:
            triples = extract_triples(text, std_code)
        except Exception as e:
            print(f"        FAIL: {e}")
            failed_chunks += 1
            continue
        if not triples:
            print(f"        skipped (no triples)")
            continue

        inserted = 0
        for t in triples:
            st = sanitize_type(t.get("subject_type", ""))
            ot = sanitize_type(t.get("object_type", ""))
            pr = sanitize_type(t.get("predicate", ""))
            if not (st and ot and pr):
                continue
            sub_ref = (t.get("subject_ref") or "").strip()[:200]
            obj_ref = (t.get("object_ref") or "").strip()[:200]
            claim   = (t.get("claim_text") or "").strip()[:1000]
            conf    = float(t.get("confidence") or 0.7)
            conf    = max(0.0, min(1.0, conf))
            if not (sub_ref and obj_ref):
                continue
            try:
                cur.execute("""
                    INSERT INTO knowledge_graph_facts
                      (hive_id, subject_type, subject_ref, predicate, object_type, object_ref,
                       claim_text, confidence, source_type, source_ref, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'standard', %s, 'day5_extractor')
                """, (TEST_HIVE_ID, st, sub_ref, pr, ot, obj_ref, claim, conf,
                      f"{std_code} chunk_{chunk_num}"))
                inserted += 1
            except psycopg2.Error as e:
                conn.rollback()
                # one bad row shouldn't kill the chunk
                cur.execute("ROLLBACK")
                # reopen transaction
                continue
        conn.commit()
        total_facts += inserted
        print(f"        +{inserted} triples (running total: {total_facts})")
        time.sleep(0.6)  # 100 req/min ceiling

    cur.execute("SELECT COUNT(*) FROM knowledge_graph_facts WHERE created_by='day5_extractor'")
    total_in_table = cur.fetchone()[0]

    print(f"\n{'='*72}\nRESULT\n{'='*72}")
    print(f"  Chunks processed:    {len(chunks)}")
    print(f"  Failed chunks:       {failed_chunks}")
    print(f"  Facts inserted:      {total_facts}")
    print(f"  Total day5 facts:    {total_in_table}")

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
