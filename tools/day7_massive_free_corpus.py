"""Day 7: Aggressive L1 expansion — 15+ free public-domain industrial PDFs.

Targets sources with stable URLs:
  - OSHA publications (most are decade-stable URLs)
  - NIST nvlpubs (immutable archive pattern)
  - DOE AMO tip sheets (energy.gov/sites/...)
  - NASA technical reports (NTRS)
  - EPA industrial guidance

Any 404 is logged and skipped — partial success is still a win. The script
appends to the existing _manifest.json so day2 + day6 + day7 entries coexist.
"""
from __future__ import annotations

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

SOURCES = [
    # ── More OSHA publications (decade-stable URL pattern) ────────────────
    {"id": "osha-3132-process-safety", "code": "OSHA 3132", "title": "Process Safety Management",
     "family": "other", "jurisdiction": "US",
     "url": "https://www.osha.gov/sites/default/files/publications/osha3132.pdf",
     "notes": "OSHA Process Safety Management guidance for highly hazardous chemicals."},
    {"id": "osha-3138-permit-confined-space", "code": "OSHA 3138", "title": "Permit-Required Confined Spaces",
     "family": "other", "jurisdiction": "US",
     "url": "https://www.osha.gov/sites/default/files/publications/osha3138.pdf",
     "notes": "OSHA guide to permit-required confined space entry."},
    {"id": "osha-3151-ppe", "code": "OSHA 3151", "title": "Personal Protective Equipment",
     "family": "other", "jurisdiction": "US",
     "url": "https://www.osha.gov/sites/default/files/publications/osha3151.pdf",
     "notes": "OSHA PPE selection and use guide."},
    {"id": "osha-3133-process-safety", "code": "OSHA 3133", "title": "Process Safety Management Compliance Guidelines",
     "family": "other", "jurisdiction": "US",
     "url": "https://www.osha.gov/sites/default/files/publications/osha3133.pdf",
     "notes": "Compliance guidelines for OSHA Process Safety Management standard."},
    {"id": "osha-2236-fall-protection", "code": "OSHA 3146", "title": "Fall Protection in Construction",
     "family": "other", "jurisdiction": "US",
     "url": "https://www.osha.gov/sites/default/files/publications/osha3146.pdf",
     "notes": "OSHA fall protection guidance."},
    {"id": "osha-3162-machine-guarding", "code": "OSHA 3170", "title": "Safeguarding Equipment and Protecting Employees from Amputations",
     "family": "other", "jurisdiction": "US",
     "url": "https://www.osha.gov/sites/default/files/publications/osha3170.pdf",
     "notes": "Machine guarding to prevent amputations in industrial settings."},
    {"id": "osha-3079-respirators", "code": "OSHA 3079", "title": "Respiratory Protection",
     "family": "other", "jurisdiction": "US",
     "url": "https://www.osha.gov/sites/default/files/publications/osha3079.pdf",
     "notes": "Respiratory protection program guide for industrial workers."},
    {"id": "osha-3158-young-workers", "code": "OSHA 3158", "title": "Hazard Communication",
     "family": "other", "jurisdiction": "US",
     "url": "https://www.osha.gov/sites/default/files/publications/osha3158.pdf",
     "notes": "Hazard communication standard guide."},

    # ── NIST nvlpubs (immutable archive — these URLs don't change) ────────
    {"id": "nist-sp-800-53r5", "code": "NIST SP 800-53r5",
     "title": "Security and Privacy Controls for Information Systems and Organizations",
     "family": "other", "jurisdiction": "global",
     "url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf",
     "notes": "NIST security and privacy control catalog. Underlies OT security baselines."},
    {"id": "nist-sp-800-30r1", "code": "NIST SP 800-30r1",
     "title": "Guide for Conducting Risk Assessments",
     "family": "other", "jurisdiction": "global",
     "url": "https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-30r1.pdf",
     "notes": "NIST risk assessment methodology."},
    {"id": "nist-sp-800-37r2", "code": "NIST SP 800-37r2",
     "title": "Risk Management Framework for Information Systems and Organizations",
     "family": "other", "jurisdiction": "global",
     "url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-37r2.pdf",
     "notes": "RMF — system lifecycle approach to risk management."},
    {"id": "nist-ir-8473", "code": "NIST IR 8473",
     "title": "Cybersecurity Framework Profile for Electric Vehicle Extreme Fast Charging",
     "family": "other", "jurisdiction": "global",
     "url": "https://nvlpubs.nist.gov/nistpubs/ir/2023/NIST.IR.8473.pdf",
     "notes": "Sector-specific cybersecurity framework profile."},

    # ── DOE Advanced Manufacturing Office tip sheets ──────────────────────
    {"id": "doe-pumps-tip", "code": "DOE-AMO Pumps Tip",
     "title": "DOE AMO — Pumping System Tip Sheet",
     "family": "other", "jurisdiction": "US",
     "url": "https://www.energy.gov/sites/prod/files/2014/04/f15/pump_tip_sheet1.pdf",
     "notes": "DOE Advanced Manufacturing Office pumping system efficiency tip."},
    {"id": "doe-compressed-air-tip", "code": "DOE-AMO CompAir Tip",
     "title": "DOE AMO — Compressed Air Tip Sheet",
     "family": "other", "jurisdiction": "US",
     "url": "https://www.energy.gov/sites/prod/files/2014/04/f15/compressed_air_tip_sheet1.pdf",
     "notes": "DOE AMO compressed air system tip sheet."},
    {"id": "doe-steam-tip", "code": "DOE-AMO Steam Tip",
     "title": "DOE AMO — Steam System Tip Sheet",
     "family": "other", "jurisdiction": "US",
     "url": "https://www.energy.gov/sites/prod/files/2014/04/f15/steam_tip_sheet1.pdf",
     "notes": "DOE AMO steam system efficiency tip sheet."},

    # ── More NIST IR series — manufacturing-relevant ──────────────────────
    {"id": "nist-ir-8259", "code": "NIST IR 8259",
     "title": "Foundational Cybersecurity Activities for IoT Device Manufacturers",
     "family": "other", "jurisdiction": "global",
     "url": "https://nvlpubs.nist.gov/nistpubs/ir/2020/NIST.IR.8259.pdf",
     "notes": "NIST IoT cybersecurity guidance for manufacturers."},
]


def fetch(entry: dict) -> dict:
    out = STANDARDS_DIR / f"{entry['id']}.pdf"
    if out.exists() and out.stat().st_size > 10 * 1024:
        return {**entry, "status": "exists", "file": str(out), "size_mb": out.stat().st_size / 1024 / 1024}
    try:
        r = requests.get(entry["url"], timeout=60, stream=True,
                         headers={"User-Agent": "Mozilla/5.0 WorkHive/1.0"})
    except requests.RequestException as e:
        return {**entry, "status": f"network_{e.__class__.__name__}", "file": None}
    if r.status_code != 200:
        return {**entry, "status": f"http_{r.status_code}", "file": None}
    ct = (r.headers.get("Content-Type") or "").lower()
    if "pdf" not in ct and not entry["url"].lower().endswith(".pdf"):
        return {**entry, "status": f"not_pdf_{ct[:30]}", "file": None}
    with open(out, "wb") as f:
        total = 0
        for chunk in r.iter_content(512 * 1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)
    if total < 10 * 1024:
        out.unlink(missing_ok=True)
        return {**entry, "status": "too_small", "file": None}
    return {**entry, "status": "downloaded", "file": str(out), "size_mb": out.stat().st_size / 1024 / 1024}


def main() -> int:
    print("=" * 70)
    print("DAY 7: AGGRESSIVE L1 EXPANSION — free public-domain industrial PDFs")
    print("=" * 70)
    print(f"Output: {STANDARDS_DIR}\n")

    results = []
    ok = skip = fail = 0
    for s in SOURCES:
        print(f"[{s['code']}] {s['title']}")
        r = fetch(s)
        results.append(r)
        st = r["status"]
        if st == "downloaded":
            print(f"  [OK] {r['file']} ({r['size_mb']:.2f} MB)"); ok += 1
        elif st == "exists":
            print(f"  [SKIP] already present"); skip += 1
        else:
            print(f"  [FAIL] {st}"); fail += 1

    # Merge with existing manifest
    mp = STANDARDS_DIR / "_manifest.json"
    existing = {}
    if mp.exists():
        try:
            for r in json.loads(mp.read_text(encoding="utf-8")).get("results", []):
                if r.get("id"): existing[r["id"]] = r
        except Exception:
            pass
    for r in results:
        existing[r["id"]] = r
    mp.write_text(json.dumps({"downloaded_at": datetime.now().isoformat(),
                              "results": list(existing.values())}, indent=2), encoding="utf-8")

    print(f"\n{'='*70}\nSUMMARY: {ok} new, {skip} existing, {fail} failed (out of {len(SOURCES)})\n{'='*70}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
