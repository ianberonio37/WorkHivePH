#!/usr/bin/env python3
"""
Day 2: Download FREE public industrial standards + maintenance guides.

Sources (all 100% free, no purchase required):
- NASA Reliability Centered Maintenance Guide
- US DOE Operations & Maintenance Best Practices Guide
- US DOE Motor Systems Tip Sheets
- NIST 800-82 Industrial Control Systems Security
- SKF Bearing Maintenance Handbook
- OSHA Electrical Safety Standards
- NFPA 70E (free read-only)
- US Army TM 5-698 Reliability/Maintainability
- US Navy NAVAIR Maintenance Manual references
- NIST Building Energy Standards

Stored at: c:\\wh-datasets\\standards\\
"""

import os
import sys
import io
import json
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Output directory
STANDARDS_DIR = Path(r"c:\wh-datasets\standards")
STANDARDS_DIR.mkdir(parents=True, exist_ok=True)

# Free standards catalog
FREE_STANDARDS = [
    {
        "id": "doe-omguide",
        "name": "DOE Operations & Maintenance Best Practices Guide",
        "code": "DOE/EE-0815",
        "url": "https://www.energy.gov/sites/default/files/2013/10/f3/omguide_complete.pdf",
        "discipline": "general_maintenance",
        "relevance": "Mechanical, HVAC, Electrical - 320 pages of comprehensive O&M practices",
        "section_keywords": ["MTBF", "MTTR", "OEE", "predictive maintenance", "RCM"]
    },
    {
        "id": "nasa-rcm",
        "name": "NASA Reliability Centered Maintenance Guide for Facilities and Collateral Equipment",
        "code": "NASA-RCM-2008",
        "url": "https://www.nasa.gov/sites/default/files/atoms/files/nasa_rcmguide.pdf",
        "discipline": "reliability",
        "relevance": "RCM methodology, failure mode analysis, maintenance task selection",
        "section_keywords": ["RCM", "FMEA", "failure mode", "criticality"]
    },
    {
        "id": "nist-800-82",
        "name": "NIST Guide to Industrial Control Systems Security",
        "code": "NIST SP 800-82r3",
        "url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-82r3.pdf",
        "discipline": "ics_security",
        "relevance": "Industrial control system security, SCADA, PLC, DCS",
        "section_keywords": ["ICS", "SCADA", "PLC", "industrial security"]
    },
    {
        "id": "skf-bearing-handbook",
        "name": "SKF Bearing Maintenance Handbook",
        "code": "SKF-BMH-2018",
        "url": "https://cdn.skfmediahub.skf.com/api/public/0901d196807d4bff/pdf_preview_medium/0901d196807d4bff_pdf_preview_medium.pdf",
        "discipline": "mechanical",
        "relevance": "Bearing failure analysis, replacement intervals, lubrication",
        "section_keywords": ["bearing", "lubrication", "failure", "vibration"]
    },
    {
        "id": "epri-pdm-handbook",
        "name": "EPRI Plant Maintenance Handbook (Public Access Sample)",
        "code": "EPRI-PDM",
        "url": "https://www.epri.com/research/products/000000003002012971",
        "discipline": "predictive_maintenance",
        "relevance": "Predictive maintenance, vibration analysis, oil analysis, thermography",
        "section_keywords": ["predictive", "vibration", "thermography", "oil analysis"]
    },
    {
        "id": "us-army-tm-5-698",
        "name": "US Army TM 5-698-1 Reliability/Availability of Electrical and Mechanical Systems",
        "code": "TM 5-698",
        "url": "https://armypubs.army.mil/epubs/DR_pubs/DR_a/pdf/web/tm5_698_1.pdf",
        "discipline": "reliability",
        "relevance": "Reliability engineering, availability calculations, MTBF",
        "section_keywords": ["reliability", "availability", "MTBF", "redundancy"]
    },
    {
        "id": "iso-iec-standards-map",
        "name": "ISO/IEC Standards Cross-Reference (Wikipedia + Public Domain Summaries)",
        "code": "ISO-IEC-MAP",
        "url": "internal_seed",
        "discipline": "reference",
        "relevance": "Cross-reference for ISO 14224, ISO 13381, IEC 60364, IEC 61508, etc.",
        "section_keywords": ["ISO 14224", "ISO 13381", "IEC 60364", "IEC 61508"]
    }
]

print("\n" + "="*80)
print("DAY 2: FREE INDUSTRIAL STANDARDS DOWNLOAD")
print("="*80)
print(f"Output directory: {STANDARDS_DIR}\n")

results = []
successful = 0
failed = 0

for std in FREE_STANDARDS:
    std_id = std["id"]
    name = std["name"]
    url = std["url"]
    output_file = STANDARDS_DIR / f"{std_id}.pdf"

    print(f"\n[{std['code']}] {name}")
    print(f"  Discipline: {std['discipline']}")
    print(f"  URL: {url}")

    if url == "internal_seed":
        print(f"  [SKIP] Internal seed - no download needed")
        results.append({**std, "status": "seed_only", "file": None})
        continue

    if output_file.exists():
        size_mb = output_file.stat().st_size / 1024 / 1024
        print(f"  [SKIP] Already exists ({size_mb:.1f} MB)")
        results.append({**std, "status": "exists", "file": str(output_file), "size_mb": size_mb})
        successful += 1
        continue

    try:
        print(f"  Downloading...")
        response = requests.get(url, stream=True, timeout=60, headers={
            "User-Agent": "Mozilla/5.0 (compatible; WorkHive-Standards-Downloader/1.0)"
        })

        if response.status_code == 200:
            with open(output_file, 'wb') as f:
                total = 0
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
                        if total % (10*1024*1024) == 0:
                            print(f"    Downloaded: {total/1024/1024:.0f} MB")

            size_mb = output_file.stat().st_size / 1024 / 1024
            print(f"  [OK] Saved: {output_file.name} ({size_mb:.1f} MB)")
            results.append({**std, "status": "downloaded", "file": str(output_file), "size_mb": size_mb})
            successful += 1
        else:
            print(f"  [FAIL] HTTP {response.status_code}")
            results.append({**std, "status": f"http_{response.status_code}", "file": None})
            failed += 1

    except Exception as e:
        print(f"  [ERROR] {e}")
        results.append({**std, "status": f"error: {e}", "file": None})
        failed += 1

# Save manifest
manifest_file = STANDARDS_DIR / "_manifest.json"
with open(manifest_file, 'w', encoding='utf-8') as f:
    json.dump({
        "downloaded_at": datetime.now().isoformat(),
        "successful": successful,
        "failed": failed,
        "results": results
    }, f, indent=2)

print(f"\n{'='*80}")
print(f"SUMMARY: {successful}/{len(FREE_STANDARDS)} successful, {failed} failed")
print(f"{'='*80}")
print(f"Manifest: {manifest_file}")
print(f"\nNext: python tools/day2_seed_industry_standards.py")
