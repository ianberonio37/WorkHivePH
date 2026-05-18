"""Day 5 — Fill visayan_term column via Groq llama-3.3-70b (free chain).

Azure Translator F0 does NOT support Cebuano (ceb), so we fall back to the
free LLM chain. Groq's llama-3.3-70b-versatile knows Cebuano well enough
for industrial maintenance terms — and at $0 cost.

Batches: 25 phrases per LLM call, JSON-structured response, idempotent
update by english_term.
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
BATCH        = 25


def translate_to_cebuano(english_terms: list[str]) -> dict[str, str]:
    """Single Groq call. Returns {english_term: cebuano_term}."""
    items_json = json.dumps([{"en": t} for t in english_terms], ensure_ascii=False)
    prompt = (
        "You are translating industrial maintenance terms from English to Cebuano (Bisaya), "
        "the language used by workers in Cebu, Davao, and most of Visayas/Mindanao. "
        "Preserve domain meaning. If a term is a proper noun, acronym, or has no natural Cebuano "
        "equivalent (e.g. 'bearing', 'motor', 'PPE'), keep the English term — that IS the Cebuano "
        "term in PH industrial practice. "
        "OUTPUT STRICT JSON: a single array of objects with keys 'en' and 'ceb'. No commentary, "
        "no markdown fences, no preamble. Exactly one object per input.\n\n"
        f"INPUT:\n{items_json}"
    )
    res = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type":  "application/json",
        },
        json={
            "model":       GROQ_MODEL,
            "messages":    [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens":  2000,
        },
        timeout=60,
    )
    if not res.ok:
        raise RuntimeError(f"Groq {res.status_code}: {res.text[:200]}")
    content = res.json()["choices"][0]["message"]["content"].strip()

    # Strip code fences if the model added them despite the instruction
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```\s*$", "", content)
    # Sometimes the model adds a preamble; grab the first JSON array we see
    m = re.search(r"\[.*\]", content, re.DOTALL)
    if not m:
        raise RuntimeError(f"No JSON array found in: {content[:300]}")

    arr = json.loads(m.group(0))
    out: dict[str, str] = {}
    for item in arr:
        en = item.get("en")
        ceb = item.get("ceb") or item.get("cebuano")
        if en and ceb:
            out[en] = str(ceb).strip()
    return out


def main() -> int:
    print("=" * 72)
    print("DAY 5: FILL multilingual_terms.visayan_term VIA GROQ llama-3.3-70b")
    print("=" * 72)

    if not GROQ_API_KEY:
        print("[FAIL] GROQ_API_KEY missing in .env")
        return 1

    conn = psycopg2.connect(host="127.0.0.1", port=54322,
                            user="postgres", password="postgres", database="postgres")
    cur = conn.cursor()

    cur.execute("""
        SELECT english_term, domain
          FROM multilingual_terms
         WHERE visayan_term IS NULL OR visayan_term = ''
         ORDER BY domain, english_term
    """)
    rows = cur.fetchall()
    print(f"Rows needing Cebuano: {len(rows)}")
    if not rows:
        print("[OK] All rows have Cebuano translations already.")
        return 0

    all_terms = [r[0] for r in rows]
    updated   = 0
    failed    = 0

    for i in range(0, len(all_terms), BATCH):
        batch = all_terms[i:i + BATCH]
        print(f"\nBatch {i // BATCH + 1} ({len(batch)} terms)...")
        try:
            translations = translate_to_cebuano(batch)
            print(f"  [OK] Groq returned {len(translations)} mappings")
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += len(batch)
            continue

        for term in batch:
            ceb = translations.get(term)
            if not ceb:
                failed += 1
                continue
            cur.execute(
                "UPDATE multilingual_terms SET visayan_term = %s "
                "WHERE english_term = %s AND (visayan_term IS NULL OR visayan_term = '')",
                (ceb, term),
            )
            updated += cur.rowcount
        conn.commit()
        time.sleep(0.3)  # gentle pacing under 128/min

    cur.execute("SELECT COUNT(*) FROM multilingual_terms WHERE visayan_term IS NOT NULL AND visayan_term != ''")
    total_ceb = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM multilingual_terms")
    total = cur.fetchone()[0]

    print(f"\n{'=' * 72}\nRESULT\n{'=' * 72}")
    print(f"  Updated this run:  {updated}")
    print(f"  Failed this run:   {failed}")
    print(f"  Total with Cebuano: {total_ceb}/{total}")

    cur.execute("SELECT english_term, tagalog_term, visayan_term FROM multilingual_terms WHERE visayan_term IS NOT NULL ORDER BY random() LIMIT 5")
    print("\nSample (random 5):")
    for en, tl, ceb in cur.fetchall():
        print(f"  {en:25s} -> tl: {tl:20s} | ceb: {ceb}")

    cur.close()
    conn.close()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
