"""Day 6 (L1 expansion): Download more free public-domain industrial PDFs.

US Government works are public domain — no email forms, no paywalls. This
batch targets OSHA + NIST publications most relevant to industrial maintenance
workers in PH plants.

Outputs to c:\\wh-datasets\\standards\\ (same dir as Day 2). Idempotent — skip
files already present.

After downloads land, run:
  - tools/day6_register_new_standards.py to insert industry_standards rows
  - tools/day4_chunk_standards_pdfs.py to chunk + embed
  - tools/day5_extract_kg_facts.py to extract triples
"""
from __future__ import annotations

import os
import sys
import io
import json
import requests
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

STANDARDS_DIR = Path(r"c:\wh-datasets\standards")
STANDARDS_DIR.mkdir(parents=True, exist_ok=True)

# Each entry is a discrete free PDF with a stable URL. If a URL 404s, the
# script logs it and moves on — partial success is still a win.
SOURCES = [
    # ── OSHA — Lockout/Tagout (Control of Hazardous Energy) ────────────────
    {
        "id":          "osha-3120-loto",
        "code":        "OSHA 3120",
        "title":       "Control of Hazardous Energy — Lockout/Tagout",
        "family":      "other",
        "jurisdiction":"US",
        "url":         "https://www.osha.gov/sites/default/files/publications/osha3120.pdf",
        "notes":       "US OSHA booklet on the Control of Hazardous Energy standard (29 CFR 1910.147). Free + public domain. Directly relevant to LOTO procedures in PH plants under DOLE D.O. 198-18.",
    },
    {
        "id":          "osha-3071-jha",
        "code":        "OSHA 3071",
        "title":       "Job Hazard Analysis",
        "family":      "other",
        "jurisdiction":"US",
        "url":         "https://www.osha.gov/sites/default/files/publications/osha3071.pdf",
        "notes":       "OSHA booklet on conducting a JHA. Foundational for permit-to-work + risk assessments.",
    },
    {
        "id":          "osha-3088-hand-power-tools",
        "code":        "OSHA 3080",
        "title":       "Hand and Power Tools",
        "family":      "other",
        "jurisdiction":"US",
        "url":         "https://www.osha.gov/sites/default/files/publications/osha3080.pdf",
        "notes":       "Guidance on safe use of hand + power tools in industrial settings.",
    },
    # ── NIST IR 8183 — Cybersecurity Framework Manufacturing Profile ───────
    {
        "id":          "nist-ir-8183",
        "code":        "NIST IR 8183",
        "title":       "Cybersecurity Framework Manufacturing Profile",
        "family":      "other",
        "jurisdiction":"global",
        "url":         "https://nvlpubs.nist.gov/nistpubs/ir/2017/NIST.IR.8183.pdf",
        "notes":       "NIST manufacturing-specific cybersecurity profile applying the CSF to industrial systems. Complements NIST 800-82r3.",
    },
    # ── DOE Industrial Best Practices motor tip sheet ─────────────────────
    {
        "id":          "doe-motor-tip",
        "code":        "DOE-AMO Motor Tip",
        "title":       "DOE Advanced Manufacturing Office — Motor Tip Sheets",
        "family":      "other",
        "jurisdiction":"US",
        "url":         "https://www.energy.gov/sites/prod/files/2014/04/f15/motor_tip_sheet11.pdf",
        "notes":       "DOE Advanced Manufacturing Office tip sheet on motor systems energy efficiency.",
    },
]


def already_present(out_path: Path) -> bool:
    return out_path.exists() and out_path.stat().st_size > 10 * 1024  # > 10 KB


def fetch(entry: dict) -> dict:
    out = STANDARDS_DIR / f"{entry['id']}.pdf"
    if already_present(out):
        return {**entry, "status": "exists", "file": str(out), "size_mb": out.stat().st_size / 1024 / 1024}
    try:
        res = requests.get(entry["url"], timeout=60,
                           headers={"User-Agent": "Mozilla/5.0 WorkHive-Standards-Fetch/1.0"},
                           stream=True)
    except requests.RequestException as e:
        return {**entry, "status": f"network_{e.__class__.__name__}", "file": None}

    if res.status_code != 200:
        return {**entry, "status": f"http_{res.status_code}", "file": None}

    content_type = (res.headers.get("Content-Type") or "").lower()
    if "pdf" not in content_type and not entry["url"].lower().endswith(".pdf"):
        return {**entry, "status": f"not_pdf_{content_type}", "file": None}

    with open(out, "wb") as f:
        total = 0
        for chunk in res.iter_content(chunk_size=512 * 1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)
    if total < 10 * 1024:
        out.unlink(missing_ok=True)
        return {**entry, "status": "too_small", "file": None}
    return {**entry, "status": "downloaded", "file": str(out), "size_mb": out.stat().st_size / 1024 / 1024}


def main() -> int:
    print("=" * 70)
    print("DAY 6 (L1 EXPANSION): FREE INDUSTRIAL STANDARDS DOWNLOAD")
    print("=" * 70)
    print(f"Output: {STANDARDS_DIR}\n")

    results: list[dict] = []
    ok, skip, fail = 0, 0, 0
    for s in SOURCES:
        print(f"[{s['code']}] {s['title']}")
        r = fetch(s)
        results.append(r)
        st = r["status"]
        if st == "downloaded":
            print(f"  [OK] {r['file']} ({r['size_mb']:.1f} MB)")
            ok += 1
        elif st == "exists":
            print(f"  [SKIP] already present ({r['size_mb']:.1f} MB)")
            skip += 1
        else:
            print(f"  [FAIL] {st}")
            fail += 1
        print()

    # Merge with existing manifest so day2 + day6 entries coexist
    manifest_path = STANDARDS_DIR / "_manifest.json"
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            previous = existing.get("results", [])
        except Exception:
            previous = []
    else:
        previous = []

    by_id = {r.get("id"): r for r in previous if r.get("id")}
    for r in results:
        by_id[r["id"]] = r

    manifest_path.write_text(json.dumps({
        "downloaded_at": datetime.now().isoformat(),
        "results":       list(by_id.values()),
    }, indent=2), encoding="utf-8")

    print(f"{'='*70}\nSUMMARY: {ok} downloaded, {skip} existing, {fail} failed\n{'='*70}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
