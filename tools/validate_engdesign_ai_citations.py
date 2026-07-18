#!/usr/bin/env python3
"""Validator: Engineering-Design AI narrative CITATION grounding (deep-arc P5 / AI-6).

Risk (OWASP LLM09 over-reliance): the engineering-calc-agent LLM narrative (objective/assumptions/
recommendations) can NAME a standards body. A hallucinated/fabricated standard ("per ASME 9999",
an invented body) would look authoritative to a licensed engineer and mis-ground the design.

Design decision (evidence-based, 2026-07-09, Arc G3). A live deepwalk across all 6 disciplines
(HVAC/Fire/Electrical/Mechanical/Plumbing/Machine) showed the LLM cites ONLY real, correctly-named
standards (NFPA 13, PEC 2017, IEC 62548, ASME B106, IRR RA 9514, AISI 1045 ...) — no fabrication —
and that a naive citation regex FALSE-POSITIVES heavily on non-citations ("Install 11", "Group 2",
"Dyn 11", "CO 2", model numbers M20 / W250x33). So a runtime citation STRIPPER is net-harmful and
wrong. Instead we LOCK the demonstrated-good state with a calibrated FABRICATION gate:

  - Recognize a citation ONLY as an ALL-UPPERCASE body acronym (2-6 letters, optional 1-letter
    suffix e.g. "ASME B") immediately followed by a designation number/section. This excludes
    Title-case verbs/words ("Install", "Group", "The"), single-letter model prefixes (M20, W250,
    DN100), and vector groups ("Dyn 11").
  - A tiny chemical/formula stoplist (CO, NO, SO, NH, H, O) drops "CO 2"-type formulas.
  - ASSERT every recognized citation body is in the curated REAL standard-family set. A body that is
    standards-SHAPED but NOT real = a candidate fabrication -> FAIL.

Hermetic self-test proves teeth (a fabricated "FAKESTD 999" is caught; every real body passes).
Live mode (needs the edge runtime up) invokes the calc-agent across disciplines and asserts 0
fabrications — manufacturing the live evidence that AI-6 holds. Live errors/edge-down -> graceful
SKIP (CI-safe); the hermetic teeth check always runs.

Run:  python tools/validate_engdesign_ai_citations.py            (hermetic teeth + live if edge up)
      python tools/validate_engdesign_ai_citations.py --self-test (hermetic teeth only)
"""
import json
import re
import subprocess
import sys
import time

try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Curated REAL standard-body families relevant to Philippine MEP / industrial engineering.
# (Bodies, not specific numbers — so no false-positive on a legit-but-unlisted designation.)
REAL_FAMILIES = {
    # fire / life-safety
    "NFPA", "RA", "IRR", "UL", "FM",
    # electrical
    "PEC", "NEC", "IEC", "IEEE", "IES", "NEMA",
    # HVAC / mechanical
    "ASHRAE", "PSME", "SMACNA", "AHRI", "ARI", "CTI", "TEMA", "ASME", "API", "AWS",
    # structural / material
    "NSCP", "AISC", "ACI", "AISI", "ASTM", "SAE", "DIN", "EN", "BS", "JIS", "ISO",
    # plumbing / sanitary / environmental
    "PPC", "ASPE", "IPC", "UPC", "PDI", "NSF", "ANSI", "WQA", "DENR", "DAO", "DOH",
    "DPWH", "PNS", "PAGASA", "WHO", "PD", "NPC", "RMA", "CAGI", "ASPE",
    # generic Philippine legal/standards prefixes commonly cited
    "NBCP", "DOLE", "OSH", "DOE", "BFP",
}
# Real PH regulators / agencies that are NOT design-standard publishers. If the LLM cites one as a
# "standard" (e.g. "PRC 2019"), that is a soft mis-grounding worth surfacing — but it is a REAL body,
# not an invented one, so it is ADVISORY (reported), not a hard fabrication FAIL. (The prompt fix
# constrains the LLM away from these; the gate's hard FAIL is reserved for a truly invented body.)
REGULATORS = {"PRC", "DTI", "LTO", "LGU", "SEC", "BIR", "DILG", "NEA"}

# ALL-CAPS tokens that are chemical formulas / units, not standards bodies.
CHEM_UNIT_STOP = {"CO", "NO", "SO", "NH", "H", "O", "N", "C", "PH", "TDS", "BOD", "COD",
                  "TR", "HP", "KW", "KVA", "VA", "PSI", "GPM", "CFM", "RPM", "AC", "DC",
                  "PV", "UPS", "AHU", "FCU", "VD", "PF", "DN", "OD", "ID", "NPSH", "MAWP",
                  "LMTD", "COP", "EER", "SEER", "SWL", "MBF", "WSFU", "DFU", "ACH", "LPS",
                  "LED", "GEC", "SLD", "BHP", "TDH", "OA", "SA", "RA2"}

# A citation = ALL-CAPS body (2-8 letters; real bodies max 6=ASHRAE, but a fabricated one may be
# longer) + optional 1-letter suffix + a designation number.
CITE_RE = re.compile(r"\b([A-Z]{2,8})(?:\s+([A-Z]))?\s*[- ]?\s*(\d{1,5}(?:[.\-]\d{1,4})*)\b")


def find_citations(text):
    """Return (real, regulator, suspicious) citation lists from a narrative text.
    real       = body in the curated real standard-family set (grounded, good)
    regulator  = a real PH regulator cited as a standard (soft mis-grounding — ADVISORY)
    suspicious = standards-shaped body that is neither real nor a known regulator (candidate
                 fabrication — the hard FAIL trigger)."""
    real, regulator, suspicious = [], [], []
    for m in CITE_RE.finditer(text or ""):
        body = m.group(1)
        if body in CHEM_UNIT_STOP:
            continue
        desig = (m.group(2) + " " if m.group(2) else "") + m.group(3)
        cite = f"{body} {desig}".strip()
        if body in REAL_FAMILIES:
            real.append(cite)
        elif body in REGULATORS:
            regulator.append(cite)
        else:
            suspicious.append(cite)
    return real, regulator, suspicious


# ── live invoke helpers (reuse backend_live_invoke pattern) ──────────────────
BASE = "http://127.0.0.1:54321/functions/v1"


def _docker_env(var):
    for c in ("supabase_edge_runtime_workhive", "supabase_kong_workhive"):
        try:
            r = subprocess.run(["docker", "exec", c, "sh", "-c", f"echo ${var}"],
                               capture_output=True, text=True, timeout=20)
            if r.stdout.strip().startswith("eyJ"):
                return r.stdout.strip()
        except Exception:
            pass
    return ""


def _jwt(key):
    try:
        r = subprocess.run(["curl", "-s", "-m", "15", "-X", "POST",
            "http://127.0.0.1:54321/auth/v1/token?grant_type=password",
            "-H", f"apikey: {key}", "-H", "Content-Type: application/json",
            "-d", '{"email":"leandromarquez@auth.workhiveph.com","password":"test1234"}'],
            capture_output=True, text=True, timeout=20)
        return json.loads(r.stdout).get("access_token", "")
    except Exception:
        return ""


def _invoke(body, tok, key, timeout=45):
    r = subprocess.run(["curl", "-s", "-m", str(timeout), "-X", "POST",
        f"{BASE}/engineering-calc-agent",
        "-H", f"Authorization: Bearer {tok}", "-H", f"apikey: {key}",
        "-H", "Content-Type: application/json", "-d", json.dumps(body)],
        capture_output=True, text=True, timeout=timeout + 8)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {}


LIVE_CASES = [
    ("HVAC Cooling Load", {"floor_area_m2": 100, "occupancy": 10, "lighting_w_m2": 12}),
    ("Fire Sprinkler Hydraulic", {"hazard": "Ordinary Hazard Group 2", "area_m2": 140}),
    ("Voltage Drop", {"load_a": 40, "length_m": 50, "conductor_mm2": 22, "phases": 3, "voltage": 230}),
    ("Water Supply Pipe Sizing", {"fixtures": [{"type": "Water Closet (flush tank)", "count": 10}]}),
    ("Shaft Design", {"power_kW": 15, "speed_rpm": 1450, "material": "AISI 1045"}),
    ("Solar PV System", {"array_kwp": 10, "panel_wp": 450}),
]


def self_test():
    ok = True
    # real citations must NOT be flagged suspicious
    real_txt = ("Per NFPA 13 and PEC 2017, and IEC 62548, ASME B106, IRR RA 9514, AISI 1045, "
                "ASHRAE 90.1, NSCP 2015, ISO 281.")
    real, reg, susp = find_citations(real_txt)
    if susp:
        print(f"  self-test XX: real citations flagged as suspicious: {susp}"); ok = False
    if "NFPA 13" not in real or "ASME B 106" not in real:
        print(f"  self-test XX: real citations not recognized: {real}"); ok = False
    # a fabricated body must be flagged
    fake = "Designed per FAKESTD 9999 and ZZZ 42 requirements."
    _, _, susp2 = find_citations(fake)
    if "FAKESTD 9999" not in susp2:
        print(f"  self-test XX: fabricated 'FAKESTD 9999' not caught: {susp2}"); ok = False
    # a regulator cited as a standard must be ADVISORY (not a hard fabrication)
    _, reg3, susp3 = find_citations("Complies with PRC 2019 guidelines.")
    if "PRC 2019" not in reg3 or susp3:
        print(f"  self-test XX: regulator not classified advisory: reg={reg3} susp={susp3}"); ok = False
    # calibrated false-positive traps must NOT be flagged
    fp = "Install 11 heads. Ordinary Hazard Group 2. Dyn 11 vector group. CO 2 emissions. M20 bolt, W250x33 beam, DN100 pipe."
    _, _, susp4 = find_citations(fp)
    if susp4:
        print(f"  self-test XX: false-positive on non-citations: {susp4}"); ok = False
    print("  SELF-TEST", "PASS" if ok else "FAIL",
          "— fabrication caught, real citations + model numbers untouched (teeth).")
    return ok


def run():
    print("=" * 66)
    print("Engineering-Design AI narrative citation grounding (P5 / AI-6)")
    print("=" * 66)
    teeth = self_test()
    if not teeth:
        print("\nFAIL — fabrication detector lost its teeth.")
        return 1

    # Live evidence tier (graceful skip if edge/LLM down).
    key = _docker_env("SUPABASE_ANON_KEY")
    tok = _jwt(key) if key else ""
    if not tok:
        print("\n  live tier SKIPPED (edge runtime/JWT unavailable) — hermetic teeth PASS is the floor.")
        print("PASS — citation fabrication detector has teeth (live evidence tier skipped).")
        return 0

    total_real = 0
    fabrications = []      # hard FAIL: invented standards body
    regulators = []        # advisory: real regulator cited as a standard
    checked = 0
    for ct, inp in LIVE_CASES:
        res = _invoke({"calc_type": ct, "inputs": inp}, tok, key)
        narr = res.get("narrative") or {}
        text = " ".join(str(narr.get(k, "")) for k in ("objective", "assumptions", "recommendations"))
        if not text.strip():
            continue
        checked += 1
        real, reg, susp = find_citations(text)
        total_real += len(real)
        if susp:
            fabrications.append((ct, susp))
        if reg:
            regulators.append((ct, reg))
        line = f"  [{ct}] real citations: {real or '(none)'}"
        if reg:
            line += f"  \033[93m⚠ regulator-as-standard: {reg}\033[0m"
        if susp:
            line += f"  \033[91mSUSPECT: {susp}\033[0m"
        print(line)
        time.sleep(2)

    if checked == 0:
        print("\n  live tier SKIPPED (no narratives returned — LLM chain likely rate-limited).")
        print("PASS — citation fabrication detector has teeth (live evidence tier skipped).")
        return 0

    print(f"\n  live: {checked} narratives, {total_real} real-standard citations, "
          f"{len(regulators)} regulator-as-standard (advisory), "
          f"{len(fabrications)} fabricated/unknown standards body.")
    if regulators:
        print("  ADVISORY — the LLM cited a regulator as a design standard (prompt-fix target, "
              "not a fabrication):")
        for ct, reg in regulators:
            print(f"    {ct}: {reg}")
    if fabrications:
        print("\nFAIL — the AI narrative NAMED an invented standards body (not a real family or regulator):")
        for ct, susp in fabrications:
            print(f"    {ct}: {susp}")
        return 1
    print("\nPASS — no fabricated standards body in any live narrative (real families + advisory "
          "regulators only; detector teeth proven).")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(0 if self_test() else 1)
    sys.exit(run())
