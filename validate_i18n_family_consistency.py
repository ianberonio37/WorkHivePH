#!/usr/bin/env python3
"""
i18n Family Consistency Validator (L0, ratcheted) — the SPLIT-LANGUAGE DROPDOWN.
===============================================================================
A `<select>`'s options are a FAMILY by construction: the reader sees them together, in one list,
and compares them to each other. So the language of a dropdown is a property of the WHOLE list,
never of one option — and the unit that can be wrong is the family, not the string.

★WHY THIS GATE EXISTS (measured 2026-09-29). The platform's per-page dictionaries (i18n/<page>.json,
authored, never machine-derived) are keyed by individual English STRING. Nothing ever compared the
members of one dropdown against each other, so a page could translate three options and leave four,
and every existing check stayed green. dayplanner.html shipped exactly that to a Filipino reader:

    <select id="m-category">
      Preventive Maintenance   <- English  (no translation authored)
      Corrective Maintenance   <- English  (no translation authored)
      Inspeksyon               <- Filipino
      Pagsasanay               <- Filipino
      Admin                    <- English  (no translation authored)
      Meeting                  <- English  (no translation authored)
      Iba pa                   <- Filipino

Three Filipino words sitting among four English ones, in one list, with no rule behind which is
which. That reads as breakage, not as bilingualism — worse than either pure choice, because the
reader cannot tell whether "Admin" is a different KIND of thing from "Pagsasanay" or just a word
nobody got to. 19 dropdowns across 8 pages were in some split state when this gate was written.

★AND THE RULE THAT MAKES IT CLOSABLE WITHOUT INVENTING FILIPINO: an IDENTITY entry ("Pump": "Pump")
is an authored DECISION — "this term stays English, the way a Philippine plant says it" — and this
gate counts it as DECIDED, not as a gap. That is the platform's own long-standing convention:
logbook.json records it 56 times, which is why every one of logbook's nine dropdowns is internally
coherent (a Filipino instruction line over the plant's English vocabulary) and why not one of them
is a finding here. So a split family has TWO honest closes, and neither requires guessing:
  - author the Filipino for the missing siblings, or
  - rule identity on them ("this stays English"), the logbook way.
Only an EMPTY string ("Admin": "") or a member absent from the dictionary is an open gap.

WHAT IS NOT A FINDING:
  - a placeholder (`<option value="">Select type...</option>`). It is an instruction, not a member
    of the family — "Pumili ng type..." above English options is the Taglish convention working, not
    a split. Detected structurally by the empty value attribute, never by matching its words.
  - a family that is entirely translated, entirely identity, or entirely untranslated.
  - founder-console.html, which is EN-only by design (see INTERNAL_EXEMPT in
    tools/validate_i18n_coverage.py — 47 identity entries covering ordinary words like "Health" and
    "Growth", i.e. a whole-page ruling, not per-term ones).

Output: i18n_family_report.json. Exit 1 on regression above the baseline.
Self-test: --selftest (deterministic, no filesystem scan).
"""
from __future__ import annotations
import html
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
DICT_DIR = ROOT / "i18n"
REPORT_PATH = ROOT / "i18n_family_report.json"
BASELINE_PATH = ROOT / "i18n_family_baseline.json"

SELECT_RE = re.compile(r"<select\b([^>]*)>(.*?)</select>", re.IGNORECASE | re.DOTALL)
OPTION_RE = re.compile(r"<option\b([^>]*)>([^<]*)</option>", re.IGNORECASE)
EMPTY_VALUE_RE = re.compile(r"""\bvalue\s*=\s*['"]\s*['"]""", re.IGNORECASE)
ID_RE = re.compile(r"""\bid\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# EN-only by design — a whole-page ruling, not per-term decisions. Mirrors INTERNAL_EXEMPT in
# tools/validate_i18n_coverage.py; keep the two in step.
EXEMPT_PAGES = {"founder-console.html"}

# Sentinel binding: name the L2 test `test('i18n_family_consistency: ...')` for coverage credit.
CHECK_NAMES = ["i18n_family_consistency"]

FIL, EN, GAP = "FIL", "EN", "GAP"


def classify(option_text: str, dictionary: dict) -> str:
    """FIL = an authored translation · EN = an authored 'stays English' ruling · GAP = undecided."""
    value = dictionary.get(option_text)
    if not isinstance(value, str) or not value.strip():
        return GAP                      # empty string, or the string is absent from the dictionary
    return EN if value == option_text else FIL


def families_in(markup: str, dictionary: dict) -> list:
    """Every <select> in the page, with its non-placeholder options classified."""
    out = []
    clean = COMMENT_RE.sub("", markup)
    for match in SELECT_RE.finditer(clean):
        attrs, inner = match.group(1), match.group(2)
        members = []
        for option in OPTION_RE.finditer(inner):
            # A placeholder is marked by value="" — structural, never a word match, so a real option
            # that happens to begin with "Select" is still a member of the family.
            if EMPTY_VALUE_RE.search(option.group(1)):
                continue
            text = html.unescape(option.group(2)).strip()
            if len(text) < 2 or not any(c.isalpha() for c in text):
                continue               # separators, dashes, bare numbers
            members.append(text)
        if len(members) < 2:
            continue                   # a family needs siblings to be inconsistent with
        ident = ID_RE.search(attrs)
        out.append({
            "select": ident.group(1) if ident else "?",
            "line": clean.count("\n", 0, match.start()) + 1,
            "members": [{"text": t, "state": classify(t, dictionary)} for t in members],
        })
    return out


def split_families(markup: str, dictionary: dict) -> list:
    """A family is SPLIT when at least one member is translated and at least one is undecided."""
    findings = []
    for family in families_in(markup, dictionary):
        states = {m["state"] for m in family["members"]}
        if FIL in states and GAP in states:
            family["gaps"] = [m["text"] for m in family["members"] if m["state"] == GAP]
            family["translated"] = [m["text"] for m in family["members"] if m["state"] == FIL]
            findings.append(family)
    return findings


def scan() -> tuple:
    findings, scanned = [], 0
    for page in sorted(ROOT.glob("*.html")):
        if page.name.startswith("_") or page.name in EXEMPT_PAGES:
            continue
        if ".backup." in page.name or page.name.endswith("-test.html"):
            continue
        dict_path = DICT_DIR / f"{page.stem}.json"
        if not dict_path.exists():
            continue                   # no dictionary yet = not a localized page, not a split one
        try:
            dictionary = json.loads(dict_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        scanned += 1
        for family in split_families(page.read_text(encoding="utf-8", errors="replace"), dictionary):
            family["page"] = page.name
            findings.append(family)
    return findings, scanned


def selftest() -> int:
    """Deterministic, no filesystem: a planted split must be caught, and the two closes must clear it."""
    markup = (
        '<select id="t-fam">'
        '<option value="">Select type...</option>'
        '<option value="a">Alpha</option>'
        '<option value="b">Beta</option>'
        '<option value="c">Gamma</option>'
        "</select>"
    )
    cases = [
        ("a split family is caught",
         {"Alpha": "Unang", "Beta": "", "Gamma": "Gamma"}, 1, ["Beta"]),
        ("a member absent from the dictionary is a gap, not silence",
         {"Alpha": "Unang"}, 1, ["Beta", "Gamma"]),
        ("closing by authoring Filipino clears it",
         {"Alpha": "Unang", "Beta": "Ikalawa", "Gamma": "Ikatlo"}, 0, []),
        ("closing by ruling identity clears it — the logbook way",
         {"Alpha": "Unang", "Beta": "Beta", "Gamma": "Gamma"}, 0, []),
        ("an all-English family is coherent, not a finding",
         {"Alpha": "Alpha", "Beta": "Beta", "Gamma": "Gamma"}, 0, []),
        ("an untouched family is a coverage gap, not a split",
         {}, 0, []),
        ("the placeholder is never a member",
         {"Select type...": "", "Alpha": "Unang", "Beta": "Ikalawa", "Gamma": "Ikatlo"}, 0, []),
    ]
    failed = 0
    for label, dictionary, expected, expected_gaps in cases:
        found = split_families(markup, dictionary)
        gaps = found[0]["gaps"] if found else []
        ok = len(found) == expected and gaps == expected_gaps
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if not ok:
            print(f"        expected {expected} finding(s) with gaps {expected_gaps}, got {len(found)} with {gaps}")
            failed += 1
    # A family of one cannot be inconsistent with itself.
    lone = '<select id="t-one"><option value="">Pick...</option><option value="a">Alpha</option></select>'
    ok = not split_families(lone, {"Alpha": "Unang"})
    print(f"  {'PASS' if ok else 'FAIL'}  a family of one member is never split")
    failed += 0 if ok else 1
    print(f"\n  {'SELFTEST PASS' if not failed else f'SELFTEST FAIL ({failed})'}")
    return 1 if failed else 0


def main() -> int:
    if "--selftest" in sys.argv:
        print("\ni18n Family Consistency Validator — selftest")
        print("=" * 56)
        return selftest()

    findings, scanned = scan()
    drift = len(findings)

    baseline = drift
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", drift)
        except Exception:
            baseline = drift
    else:
        BASELINE_PATH.write_text(json.dumps({"drift": drift, "established": True}, indent=2), encoding="utf-8")
    if drift < baseline:                # forward-only ratchet: it may tighten, never loosen
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": drift, "tightened": True}, indent=2), encoding="utf-8")

    open_gaps = sorted({g for f in findings for g in f["gaps"]})
    REPORT_PATH.write_text(json.dumps({
        "summary": {"pages_scanned": scanned, "split_families": drift,
                    "baseline": baseline, "distinct_open_strings": len(open_gaps)},
        "open_strings": open_gaps,
        "findings": findings,
    }, indent=2), encoding="utf-8")

    print("\ni18n Family Consistency Validator (L0)")
    print("=" * 56)
    print(f"  localized pages scanned:  {scanned}")
    print(f"  split-language families:  {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS - every dropdown is one language, or an authored mix of translations and"
              "\n         explicit 'stays English' rulings.")
        return 0
    for f in findings:
        print(f"\n  {f['page']}:{f['line']}  <select id={f['select']}>")
        for m in f["members"]:
            mark = {FIL: "FIL", EN: "EN ", GAP: " * "}[m["state"]]
            print(f"      {mark} {m['text']}")
    print(f"\n  {len(open_gaps)} distinct string(s) undecided. Close each one by authoring the Filipino")
    print("  in i18n/<page>.json, or by ruling identity (\"Term\": \"Term\") to say it stays English.")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
