"""Day 4: Chunk downloaded standards PDFs + embed into industry_standards_chunks.

Targeted chunking strategy — NOT a naive page dump:
  1. pdfplumber extracts page-by-page text
  2. Concatenate, then split by paragraph (double-newline)
  3. Greedily pack into chunks of ~300 words bounded at paragraph edges
  4. Cap at 150 chunks per PDF (keeps RAG search recall focused)
  5. Embed via Voyage->Jina chain (replicated from day3 script)
  6. Insert into industry_standards_chunks with FK to industry_standards row

Mapping (extend MAP below as new PDFs become available):
  nist-800-82.pdf       -> NIST SP 800-82r3      (in industry_standards)
  us-army-tm-5-698.pdf  -> (no direct row — skipped for now)
  epri-pdm-handbook.pdf -> (was a redirect page — empty — skipped)

Usage:
    python tools/day4_chunk_standards_pdfs.py
    python tools/day4_chunk_standards_pdfs.py --max-chunks 50   # smaller test
    python tools/day4_chunk_standards_pdfs.py --reembed          # rebuild all
"""
from __future__ import annotations

import os
import sys
import io
import re
import time
import argparse
import json
from pathlib import Path
from typing import Optional

import psycopg2
import pdfplumber
import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
STANDARDS_DIR = Path(r"c:\wh-datasets\standards")
TARGET_DIM = 384
DEFAULT_MAX_CHUNKS = 150
TARGET_WORDS_PER_CHUNK = 300

# ── PDF -> industry_standards mapping ────────────────────────────────────
PDF_MAP = {
    "nist-800-82.pdf":             "NIST SP 800-82r3",
    "us-army-tm-5-698.pdf":        "US Army TM 5-698-1",
    "osha-3120-loto.pdf":          "OSHA 3120",
    "osha-3071-jha.pdf":           "OSHA 3071",
    "osha-3088-hand-power-tools.pdf": "OSHA 3080",
    "nist-ir-8183.pdf":            "NIST IR 8183",
    "doe-motor-tip.pdf":           "DOE-AMO Motor Tip",
    # "epri-pdm-handbook.pdf": None,  # zero-byte (was a redirect)
}

# ── Voyage->Jina embedding chain (mirrors day3 script) ───────────────────
def voyage_embed(text: str, api_key: str) -> list[float]:
    res = requests.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={"input": [text], "model": "voyage-3.5-lite", "output_dimension": 512, "input_type": "document"},
        timeout=30,
    )
    if not res.ok:
        raise RuntimeError(f"voyage {res.status_code}: {res.text[:160]}")
    vec = res.json().get("data", [{}])[0].get("embedding")
    if not isinstance(vec, list) or len(vec) < TARGET_DIM:
        raise RuntimeError(f"voyage bad shape: {type(vec).__name__}")
    return vec[:TARGET_DIM]


def jina_embed(text: str, api_key: str) -> list[float]:
    res = requests.post(
        "https://api.jina.ai/v1/embeddings",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={"model": "jina-embeddings-v3", "input": [text], "task": "retrieval.passage", "dimensions": TARGET_DIM},
        timeout=30,
    )
    if not res.ok:
        raise RuntimeError(f"jina {res.status_code}: {res.text[:160]}")
    vec = res.json().get("data", [{}])[0].get("embedding")
    if not isinstance(vec, list) or len(vec) != TARGET_DIM:
        raise RuntimeError(f"jina bad shape: {type(vec).__name__}")
    return vec


PROVIDERS = [
    ("voyage", "VOYAGE_API_KEY", voyage_embed),
    ("jina",   "JINA_API_KEY",   jina_embed),
]


def generate_embedding(text: str) -> tuple[list[float], str]:
    errors: list[str] = []
    for name, env_key, call in PROVIDERS:
        api_key = os.getenv(env_key)
        if not api_key or api_key.startswith("PASTE_"):
            continue
        try:
            return call(text, api_key), name
        except Exception as e:
            errors.append(f"{name}: {e}")
    raise RuntimeError(f"All providers failed: {' | '.join(errors)}" if errors else "No provider configured")


# ── PDF extraction + smart chunking ──────────────────────────────────────
def extract_pdf_text(pdf_path: Path) -> str:
    """Pull all page text into a single flowing string."""
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                txt = page.extract_text() or ""
            except Exception as e:
                print(f"    page {i+1} extract failed: {e}")
                continue
            pages.append(txt)
    return "\n\n".join(pages)


SECTION_HDR = re.compile(r"^(\d+(?:\.\d+)*)\s+([A-Z][^\n]{3,80})", re.MULTILINE)


def chunk_text(raw: str, max_chunks: int) -> list[tuple[str, Optional[str]]]:
    """Greedily pack paragraphs into chunks of ~TARGET_WORDS_PER_CHUNK words.
    Returns list of (chunk_text, section_label_or_None)."""
    # Normalize whitespace
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]

    # Find section headers for labeling
    section_at: dict[int, str] = {}     # paragraph_index -> section_label
    last_section: Optional[str] = None
    for i, p in enumerate(paragraphs):
        m = SECTION_HDR.match(p)
        if m:
            last_section = f"{m.group(1)} {m.group(2)[:60]}"
        if last_section:
            section_at[i] = last_section

    # Greedy pack
    chunks: list[tuple[str, Optional[str]]] = []
    buf: list[str] = []
    buf_words = 0
    buf_section: Optional[str] = None

    for i, p in enumerate(paragraphs):
        if buf_section is None and i in section_at:
            buf_section = section_at[i]
        words = len(p.split())
        if buf and buf_words + words > TARGET_WORDS_PER_CHUNK:
            chunks.append(("\n\n".join(buf), buf_section))
            if len(chunks) >= max_chunks:
                break
            buf = []
            buf_words = 0
            buf_section = section_at.get(i)
        buf.append(p)
        buf_words += words

    if buf and len(chunks) < max_chunks:
        chunks.append(("\n\n".join(buf), buf_section))

    return chunks


# ── Main batch ────────────────────────────────────────────────────────────
def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-chunks", type=int, default=DEFAULT_MAX_CHUNKS,
                        help=f"Max chunks per PDF (default {DEFAULT_MAX_CHUNKS})")
    parser.add_argument("--reembed", action="store_true",
                        help="Clear existing chunks for these standards and rebuild")
    args = parser.parse_args(argv)

    print("=" * 72)
    print("DAY 4: CHUNK + EMBED standards PDFs -> industry_standards_chunks")
    print("=" * 72)
    print(f"Max chunks per PDF: {args.max_chunks}")
    print(f"Source folder:      {STANDARDS_DIR}")

    if not (os.getenv("VOYAGE_API_KEY") or os.getenv("JINA_API_KEY")):
        print("[FAIL] No embedding API keys in .env")
        return 1

    conn = psycopg2.connect(host="127.0.0.1", port=54322,
                            user="postgres", password="postgres", database="postgres")
    conn.autocommit = False
    cur = conn.cursor()

    grand_total_chunks = 0
    by_provider: dict[str, int] = {}

    for pdf_name, std_code in PDF_MAP.items():
        pdf_path = STANDARDS_DIR / pdf_name
        if not pdf_path.exists() or pdf_path.stat().st_size < 1024:
            print(f"\n[SKIP] {pdf_name} (missing or empty)")
            continue

        # Look up parent industry_standards row
        cur.execute(
            "SELECT id FROM public.industry_standards WHERE standard_code = %s",
            (std_code,),
        )
        row = cur.fetchone()
        if not row:
            print(f"\n[SKIP] {pdf_name} -> '{std_code}' not in industry_standards")
            continue
        standard_id = row[0]

        # If --reembed, wipe existing chunks for this standard
        if args.reembed:
            cur.execute(
                "DELETE FROM public.industry_standards_chunks WHERE standard_id = %s",
                (standard_id,),
            )
            conn.commit()
            print(f"\n[RESET] Cleared existing chunks for {std_code}")

        # Skip if chunks already exist (idempotent default)
        cur.execute(
            "SELECT COUNT(*) FROM public.industry_standards_chunks WHERE standard_id = %s",
            (standard_id,),
        )
        existing = cur.fetchone()[0]
        if existing > 0 and not args.reembed:
            print(f"\n[SKIP] {std_code} already has {existing} chunks (use --reembed to rebuild)")
            continue

        print(f"\n{'-' * 72}")
        print(f"Processing: {pdf_name} ({pdf_path.stat().st_size / 1024 / 1024:.1f} MB)")
        print(f"  -> {std_code} ({standard_id})")
        print(f"{'-' * 72}")

        # 1. Extract
        print("  Extracting PDF text...")
        raw = extract_pdf_text(pdf_path)
        print(f"  Extracted: {len(raw):,} chars")

        # 2. Chunk
        print("  Chunking...")
        chunks = chunk_text(raw, args.max_chunks)
        print(f"  Generated {len(chunks)} chunks")

        # 3. Embed + insert
        inserted = 0
        for i, (chunk_text_val, section) in enumerate(chunks, start=1):
            try:
                vec, provider = generate_embedding(chunk_text_val[:8000])
                by_provider[provider] = by_provider.get(provider, 0) + 1
                vec_literal = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
                cur.execute(
                    """INSERT INTO public.industry_standards_chunks
                       (standard_id, chunk_num, section, text, embedding, source_pdf)
                       VALUES (%s, %s, %s, %s, %s::vector, %s)
                       ON CONFLICT (standard_id, chunk_num) DO UPDATE
                         SET section = EXCLUDED.section,
                             text = EXCLUDED.text,
                             embedding = EXCLUDED.embedding""",
                    (standard_id, i, section, chunk_text_val, vec_literal, pdf_name),
                )
                conn.commit()
                inserted += 1
                if i % 20 == 0 or i == len(chunks):
                    print(f"  [{i:3d}/{len(chunks)}] {provider} (section: {section or 'unlabeled'})")
            except Exception as e:
                conn.rollback()
                print(f"  [{i:3d}/{len(chunks)}] FAIL: {e}")

            # Gentle pacing
            time.sleep(0.10)

        print(f"  [OK] Inserted {inserted}/{len(chunks)} chunks")
        grand_total_chunks += inserted

    cur.close()
    conn.close()

    print("\n" + "=" * 72)
    print("RESULT")
    print("=" * 72)
    print(f"  Total chunks inserted: {grand_total_chunks}")
    print(f"  By provider:           {dict(by_provider)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
