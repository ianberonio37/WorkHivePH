#!/usr/bin/env python3
"""validate_osh_rule_citations.py - a cited DOLE OSHS rule number must be the rule about that subject
(gate osh-rule-citations, 2026-11-10).

★"RULE 1063 ON SAFETY AND HEALTH RECORDS" IS THE WALKWAY-SURFACE RULE (found rewriting a learn guide, Wave CF M13).
Six learn guides, the learn hub and llms.txt cited "DOLE OSHS Rule 1063" as the records rule (and as the basis of the
LOTO guide), and stated what it "requires": no paper, a time stamp, a named worker, inspector sampling. In the OSHS
table of contents (1989-amended and 2020 editions) Rule 1063 is "Walkway Surface", under Rule 1060 Premises of
Establishments; records are Rule 1050 (1054 Keeping of Records). "Rule 1090 on Mechanical Equipment" is Hazardous
Materials. The calculator family cited "OSHS PD 856" (PD 856 is the Code on Sanitation) and "Rule 1230" (Identification
of Piping System) for boilers and pressure vessels, which are Rules 1160 and 1170.

A citation is a claim a safety officer will look up. For each "Rule NNNN" whose title this gate knows, the text around it
must name that rule's subject; "PD 856" must sit beside sanitation. Unknown rule numbers are not judged.

    python tools/validate_osh_rule_citations.py [--self-test]
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = ("tools/", "tests/", "test-data-seeder/", "_fixtures/", "node_modules/", ".claude/", "supabase/migrations/",
        ".tmp/", "survey_ufai_rubric")

# OSHS rule -> words its subject is named by (titles from the OSHS table of contents)
TITLES = {
    1050: r"record|accident|illness|notif|report",
    1054: r"record",
    1060: r"premises|establishment",
    1063: r"walkway",
    1080: r"protective|ppe",
    1090: r"hazardous",
    1160: r"boiler",
    # ASME BPVC Section VIII IS the pressure-vessel code, so a standards line naming it names the subject
    1170: r"vessel|unfired|compressor|air (?:receiver|tank)|gas cylinder|Sec(?:tion|\.)\s*VIII|MAWP",
    1200: r"guard",
    1210: r"electric",
    1230: r"piping|pipe",
    1940: r"fire",
}
RULE = re.compile(r"\b(?:OSHS\s+)?Rule\s+(1\d{3})\b")
PD856 = re.compile(r"\bPD\s*856\b")
PD856_OK = re.compile(r"sanitation|sanitary|\bSTP\b|wastewater|sewage|\bDOH\b", re.I)
WIN = 160


def check_text(src: str) -> list[str]:
    out = []
    for m in RULE.finditer(src):
        n = int(m.group(1))
        subj = TITLES.get(n)
        if not subj:
            continue
        win = src[max(0, m.start() - WIN):m.end() + WIN]
        if not re.search(subj, win, re.I):
            out.append(f"Rule {n} cited away from its subject ({subj.split('|')[0]}): "
                       + repr(src[max(0, m.start() - 70):m.end() + 50].replace("\n", " ")))
    for m in PD856.finditer(src):
        win = src[max(0, m.start() - WIN):m.end() + WIN]
        if not PD856_OK.search(win):
            out.append("PD 856 is the Code on Sanitation, cited here for something else: "
                       + repr(src[max(0, m.start() - 70):m.end() + 50].replace("\n", " ")))
    return out


def shipped() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.html", "*.js", "*.txt", "*.md", "*.py", "*.ts"], cwd=ROOT,
                         capture_output=True, text=True).stdout.split()
    keep = []
    for p in out:
        if p.startswith(SKIP) or any(s in p for s in SKIP):
            continue
        if p.endswith(".md") and not p.endswith(".html.md"):
            continue
        if p.endswith(".py") and not p.startswith("python-api/"):
            continue
        if p.endswith(".ts") and not p.startswith("supabase/functions/"):
            continue
        keep.append(ROOT / p)
    return keep


def _self_test() -> int:
    fails = []
    bad = [
        "DOLE OSHS Rule 1063 on Safety and Health Records does not require paper.",
        "Learn how to create a LOTO procedure template based on DOLE OSHS Rule 1063, including the 7-step lockout sequence.",
        "Safety and Health Records, plus Rule 1090 on Mechanical Equipment safety.",
        "3. Boiler operator license per PD Act and DOLE OSHS Rule 1230. BPRT inspection required.",
        "DOLE Registration: all pressure vessels with MAWP > 15 psi must be registered with DOLE (PD 856, OSHS).",
    ]
    for s in bad:
        if not check_text(s):
            fails.append("must fail: " + s[:60])
    good = [
        "Occupational Safety and Health Standards (OSHS) Rule 1050: Notification and Keeping of Records of Accidents.",
        "Register the vessel with DOLE under OSHS Rule 1170 (Unfired Pressure Vessels) before first use.",
        "Boiler inspection under DOLE OSHS Rule 1160.",
        "DOH PD 856 (Sanitation Code) requires a Sanitary Permit for STP construction.",
        "Fire Code of the Philippines (RA 9514) and DOLE OSHS Rule 1940",
        '"standard": "ASME BPVC Sec. VIII Div.1 | ASME Sec. II Part D | DOLE OSHS Rule 1170"',
    ]
    for s in good:
        if check_text(s):
            fails.append("must pass: " + s[:60])
    print("FAIL osh-rule-citations self-test - " + "; ".join(fails) if fails
          else f"self-test OK: {len(bad)} miscited rules fail, {len(good)} correct citations pass")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    hits = {}
    for p in shipped():
        try:
            errs = check_text(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if errs:
            hits[p.relative_to(ROOT).as_posix()] = errs
    for f, errs in sorted(hits.items()):
        for e in errs[:4]:
            print(f"  BAD {f}: {e[:230]}")
    if hits:
        print(f"FAIL osh-rule-citations - {sum(len(v) for v in hits.values())} citation(s) in {len(hits)} file(s) name a "
              "DOLE OSHS rule (or PD 856) for a subject it does not cover")
        return 1
    print(f"PASS osh-rule-citations - every cited OSHS rule this gate knows ({len(TITLES)}) sits beside its own subject, "
          "and PD 856 is cited only for sanitation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
