#!/usr/bin/env python3
"""compliance-claim-honesty - T171: what an ISO-minded evaluator would check (2026-08-26).

SWEPT ALL 115 PUBLIC PAGES for certification and compliance language. The headline
result is good and worth stating precisely, because "we claim no certifications" is
easy to assert and was never verified: there is NO WorkHive self-certification
anywhere - no SOC 2, no ISO 27001, no "GDPR-compliant", no HIPAA, no PCI-DSS, no
"bank-grade" or "military-grade" security. Every one of the 30 hits was either a
standard the CUSTOMER is audited against (ISO 9001/14001/45001, DOLE OSHS), a PERSON's
credential (TESDA NC II/III, CMRP, PSME/IIEE), or the skill matrix's own "certified
level" vocabulary. The honest posture the walk recorded is now measured.

★THE ONE REAL OVERCLAIM WAS A CATEGORY ERROR, not a boast. dole-iso-audit-trail-from-
logbook said "WorkHive Logbook entries with corrective-action tags SATISFY Clause
10.2", "PM compliance dashboard SATISFIES Clause 7.1.5", "...SATISFY Clause 9.1.1". A
clause is satisfied by an ORGANIZATION's management system, evidenced by records - a
tool holds the evidence, it cannot confer conformity. The sentence reads as
reassurance, and a plant that believed it could walk into a surveillance audit
thinking a feature had covered them. Rewritten to "give you the records Clause 10.2
asks you to retain" / "evidences Clause 9.1.1", with a callout stating the distinction
outright. Same value claimed, no false comfort.

TWO ASSERTIONS:
  clause  No page may say a product feature satisfies/meets/fulfils a numbered Clause
          or Rule. Note what is deliberately NOT caught: "the digital record satisfies
          three properties" and "export patterns that satisfy auditors" are both fine
          and both appear on that same page - a record CAN satisfy a property and an
          export CAN satisfy an auditor's sampling need. The pattern requires a
          numbered clause as the object, because that is the only form that is a
          category error.
  selfcert No page may claim WorkHive holds a certification it does not hold. Zero
          today; this is guard-the-absence, since a certification claim is the single
          most tempting sentence to add to a sales page and the most expensive to be
          wrong about.

Usage: python tools/validate_compliance_claim_honesty.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# a FEATURE satisfying a NUMBERED clause - the category error
CLAUSE = re.compile(r"(satisf\w+|meets?|fulfil\w*|complies with|conforms? to)\s+(?:\w+\s+){0,2}"
                    r"(Clause|Rule)\s*\d", re.I)
# WorkHive itself holding a certification
SELFCERT = re.compile(r"(WorkHive|we|our platform|the platform)\s+(?:is|are|has been|holds?)\s+"
                      r"(?:\w+\s+){0,2}(SOC ?2|ISO ?27001|PCI[- ]DSS|HIPAA)[\s-]*(certified|compliant|"
                      r"attested|audited)?", re.I)
BUZZ = re.compile(r"\b(bank[- ]grade|military[- ]grade|unhackable|100% secure)\b", re.I)


def visible(src: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", src, flags=re.I | re.S)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))


def main() -> int:
    files = sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html"))
                   + glob.glob(str(ROOT / "tools" / "*" / "index.html"))
                   + [str(ROOT / "index.html"), str(ROOT / "about" / "index.html"),
                      str(ROOT / "privacy-policy" / "index.html"),
                      str(ROOT / "terms-of-service" / "index.html")])
    files = [f for f in files if Path(f).exists()]
    if not files:
        print("SKIP compliance-claim-honesty - no public pages found")
        return 0

    clause, selfcert = [], []
    for f in files:
        name = Path(f).parent.name if Path(f).name == "index.html" else Path(f).name
        txt = visible(io.open(f, encoding="utf-8", errors="replace").read())
        for m in CLAUSE.finditer(txt):
            clause.append(f"{name}: \"...{txt[max(0, m.start() - 55):m.end() + 30].strip()}...\"")
        for rx in (SELFCERT, BUZZ):
            for m in rx.finditer(txt):
                selfcert.append(f"{name}: \"...{txt[max(0, m.start() - 40):m.end() + 40].strip()}...\"")

    print(f"  public pages swept: {len(files)} | feature-satisfies-clause: {len(clause)} | "
          f"self-certification: {len(selfcert)}")
    fails = clause + selfcert
    if fails:
        print(f"FAIL compliance-claim-honesty - {len(fails)} claim(s) that would not survive an audit:")
        for x in fails[:10]:
            print("    - " + x)
        if len(fails) > 10:
            print(f"    ... and {len(fails) - 10} more")
        print("    A clause is satisfied by an organisation's management system, evidenced by records -")
        print("    software holds the evidence, it cannot confer conformity. Say 'gives you the records")
        print("    Clause 10.2 asks you to retain', and never claim a certification the platform lacks.")
        return 1
    print(f"PASS compliance-claim-honesty - across {len(files)} public pages, no feature claims to satisfy "
          f"a clause and the platform claims no certification it does not hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
