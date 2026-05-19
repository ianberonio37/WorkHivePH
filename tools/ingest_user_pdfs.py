"""Ingest user-dropped PDFs into the platform standards corpus.

Workflow:
  1. Drop any PDF in c:\\wh-datasets\\standards\\user_uploaded\\
  2. Run: python tools/ingest_user_pdfs.py
  3. Each PDF is auto-registered, embedded, chunked, KG-extracted, embedded.

Designed for the case where you have PH-specific OEM manuals, internal
SOPs, vendor catalogs that aren't on any public CDN — but that you DO
have on your laptop. Solves the OEM-URL-hit-rate problem (17% on Day 9)
by skipping URL guessing entirely.

Naming convention:
  Filename       cummins-t030-rev2024.pdf
  Auto code      USER-CUMMINS-T030-REV2024
  Title          (from PDF metadata, or first non-blank text line)
  source_url     user_upload:cummins-t030-rev2024.pdf
  family         'other'   (user can override with --family flag)
  jurisdiction   'global'  (user can override with --jurisdiction flag)

Idempotent:
  - Filename → standard_code mapping is deterministic
  - INSERT uses ON CONFLICT DO UPDATE
  - Chunking + extraction skip rows already done
  - Embedding skips already-embedded rows

Pipeline reused (no new code paths):
  day3 embedder, day4 chunker (with OCR fallback), day5 extractor + embedder.
  This script orchestrates them via subprocess. Single source of truth for
  each pipeline step; this is just the upload-driven entry point.
"""
from __future__ import annotations

import os
import re
import sys
import io
import argparse
import subprocess
from pathlib import Path

import psycopg2
import pdfplumber

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DROP_DIR = Path(r"c:\wh-datasets\standards\user_uploaded")
DROP_DIR.mkdir(parents=True, exist_ok=True)

# day4 chunker reads PDFs from c:\wh-datasets\standards (its STANDARDS_DIR).
# We keep the user_uploaded subfolder for organization but also copy/symlink
# the files into STANDARDS_DIR so day4 can find them by basename.
STANDARDS_DIR = Path(r"c:\wh-datasets\standards")


def code_from_filename(stem: str) -> str:
    """cummins-t030-rev2024 -> USER-CUMMINS-T030-REV2024.
    Bounded to 50 chars, uppercase, non-alphanumeric -> hyphen."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").upper()
    return f"USER-{cleaned}"[:50]


def title_from_pdf(pdf_path: Path) -> str:
    """Try PDF /Title metadata, else first non-blank text line, else filename."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            meta_title = (pdf.metadata or {}).get("Title", "") or ""
            if meta_title and meta_title.strip():
                return meta_title.strip()[:200]
            # Fallback: first non-blank line from first page
            if pdf.pages:
                text = pdf.pages[0].extract_text() or ""
                for line in text.splitlines():
                    line = line.strip()
                    if line:
                        return line[:200]
    except Exception:
        pass
    return pdf_path.stem.replace("-", " ").replace("_", " ").title()[:200]


def _val(s: str) -> str:
    return (s or "").strip()


def register_pdf(cur, pdf_path: Path, family: str, jurisdiction: str) -> tuple[str, bool]:
    """Insert/update industry_standards row for one PDF. Returns (code, was_new)."""
    code  = code_from_filename(pdf_path.stem)
    title = title_from_pdf(pdf_path)
    url   = f"user_upload:{pdf_path.name}"
    notes = (
        f"User-uploaded PDF ({pdf_path.stat().st_size // 1024} KB). "
        f"Ingested via tools/ingest_user_pdfs.py. "
        f"Replace this note if you want to record source/manufacturer details."
    )
    cur.execute(
        """
        INSERT INTO industry_standards (standard_code, family, title, jurisdiction, source_url, notes)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (standard_code) DO UPDATE
          SET title       = EXCLUDED.title,
              source_url  = EXCLUDED.source_url
        RETURNING (xmax = 0) AS was_new
        """,
        (code, family, title, jurisdiction, url, notes),
    )
    return code, cur.fetchone()[0]


def update_pdf_map(new_entries: dict[str, str]) -> None:
    """Add (basename, standard_code) entries to day4's PDF_MAP.

    The chunker's PDF_MAP is the source of truth for what gets chunked.
    Rather than maintain two lists, we append to it. Edits are bounded:
    we only insert between the existing markers, and only entries that
    aren't already present.
    """
    chunker_path = ROOT / "tools" / "day4_chunk_standards_pdfs.py"
    text = chunker_path.read_text(encoding="utf-8")

    # Find the closing brace of PDF_MAP. The chunker has a comment line
    #   # "epri-pdm-handbook.pdf": None,  # zero-byte (was a redirect)
    # just before the closing brace. We insert above the closing brace.
    closing_marker = '    # "epri-pdm-handbook.pdf": None,  # zero-byte (was a redirect)\n}'
    if closing_marker not in text:
        print("  [warn] couldn't find PDF_MAP close marker; not updating day4 chunker")
        return

    lines_to_add: list[str] = []
    for basename, code in new_entries.items():
        # Skip if already present (idempotent)
        if f'"{basename}":' in text:
            continue
        lines_to_add.append(f'    # User-uploaded {basename}\n    "{basename}": "{code}",\n')

    if not lines_to_add:
        return

    inserted = "".join(lines_to_add) + closing_marker
    text = text.replace(closing_marker, inserted)
    chunker_path.write_text(text, encoding="utf-8")
    print(f"  PDF_MAP extended with {len(lines_to_add)} new entries")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", default="other",
                        help="industry_standards.family (default: other)")
    parser.add_argument("--jurisdiction", default="global",
                        help="industry_standards.jurisdiction (default: global)")
    parser.add_argument("--max-chunks", type=int, default=50,
                        help="cap on chunks per PDF (default: 50)")
    parser.add_argument("--skip-extract", action="store_true",
                        help="register + chunk only; skip KG triple extraction")
    args = parser.parse_args(argv)

    print("=" * 72)
    print("INGEST USER-UPLOADED PDFs")
    print("=" * 72)
    print(f"Drop folder: {DROP_DIR}")

    pdfs = sorted(DROP_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"\nNo PDFs found in {DROP_DIR}.")
        print("Drop PDF files into that folder, then run this script.")
        return 0

    print(f"Found {len(pdfs)} PDF(s):")
    for p in pdfs: print(f"  - {p.name} ({p.stat().st_size // 1024} KB)")
    print()

    # Copy each PDF into STANDARDS_DIR so day4 chunker can find it.
    # (day4 reads from STANDARDS_DIR/<basename>.pdf based on PDF_MAP keys.)
    new_pdf_map: dict[str, str] = {}
    conn = psycopg2.connect(host="127.0.0.1", port=54322,
                            user="postgres", password="postgres", database="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    for pdf in pdfs:
        target = STANDARDS_DIR / pdf.name
        if not target.exists():
            target.write_bytes(pdf.read_bytes())
            print(f"  Copied {pdf.name} -> {target}")

        code, was_new = register_pdf(cur, pdf, args.family, args.jurisdiction)
        print(f"  {'+' if was_new else '~'} industry_standards: {code}")
        new_pdf_map[pdf.name] = code

    cur.close(); conn.close()
    print()

    # Extend day4's PDF_MAP
    update_pdf_map(new_pdf_map)

    # Run downstream pipeline steps.
    here = ROOT
    def run(label: str, cmd: list[str]) -> int:
        print(f"\n--- {label} ---")
        return subprocess.call([sys.executable] + cmd, cwd=here)

    rc1 = run("Embed new industry_standards rows",
              ["tools/day3_embed_industry_standards.py"])
    rc2 = run(f"Chunk PDFs (--max-chunks {args.max_chunks})",
              ["tools/day4_chunk_standards_pdfs.py", "--max-chunks", str(args.max_chunks)])
    rc3 = 0
    rc4 = 0
    if not args.skip_extract:
        rc3 = run("Extract KG triples (writes to platform_knowledge_graph_facts)",
                  ["tools/day5_extract_kg_facts.py"])
        rc4 = run("Embed new platform KG facts",
                  ["tools/day5_embed_kg_facts.py"])

    print("\n" + "=" * 72)
    print("INGEST COMPLETE")
    print("=" * 72)
    print(f"  Registered:       {len(new_pdf_map)} PDFs")
    print(f"  Pipeline RCs:     embed={rc1} chunk={rc2} extract={rc3} embed_facts={rc4}")
    print(f"  Drop folder:      {DROP_DIR}")
    print(f"  Standards corpus: c:\\wh-datasets\\standards\\")

    return 0 if all(c == 0 for c in (rc1, rc2, rc3, rc4)) else 1


if __name__ == "__main__":
    sys.exit(main())
