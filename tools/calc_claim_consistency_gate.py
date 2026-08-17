"""
calc_claim_consistency_gate.py — the site must tell ONE story about its own size.
=================================================================================
Nothing checked whether the numbers WorkHive states about itself are true, so they
drifted apart quietly while every other gate stayed green. At first honest run the
public surface claimed the calculator suite was **51, 53, 58, and 60** calculators
across **6, 7, and 8** disciplines — four different sizes for one product, with
`learn/free-engineering-calculators-philippine-plants` contradicting ITSELF (60 in
four places, 53 in three) and its visible "Updated 17 May" disagreeing with its own
`dateModified` of 5 August.

WHY THIS IS A GEO/AEO DEFECT AND NOT A TYPO: an answer engine quotes a specific
figure, and the AIO pillar it feeds is scored on **multi-source credibility**. A
site that states its own headline number four different ways cannot be corroborated
against itself, and the engine has no way to pick the right one — so the safe move
for the engine is to cite someone else. The freshness stamps matter for the same
reason: Perplexity favours recent content, and a page whose visible date and schema
date disagree gives it two answers to a question with one true value.

THE TWO SSOTs, deliberately kept separate because they count DIFFERENT THINGS:
  workbench   `validate_engdesign_registry` / CALC_TYPES_UI in engineering-design.js
              -> the in-app calc types (BOM + SOW + diagram). Currently 55 / 6.
  pages       `build_calc_pages.CALC_DATA` -> the standalone crawlable pages under
              /tools/<slug>-calculator/. Currently 60 / 8.
A page may legitimately quote EITHER, so the gate does not demand one number — it
demands that every number quoted MATCHES ONE OF THEM. Anything else is stale.

CHECKS
  calc_count        every "<N> ... calculators" claim equals a real count
  discipline_count  every "<N> disciplines" claim equals a real discipline count
  date_agreement    a page's visible "Updated" stamp equals its JSON-LD dateModified
  discipline_sum    the per-discipline counts on the suite page sum to the total

Words are counted as well as digits ("eight disciplines"), because the drift hid in
both forms and a digits-only regex would have passed the page that said "Six".
Skill-matrix pages say "5 disciplines" about SKILLS, so a discipline claim only
counts when calculator language sits within 120 characters of it.

RATCHETED forward-only, then driven to zero in the same session it was written.

CLI:
    python tools/calc_claim_consistency_gate.py
    python tools/calc_claim_consistency_gate.py --self-test
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

REPORT = ROOT / "calc_claim_consistency_report.json"
BASELINE = ROOT / "calc_claim_consistency_baseline.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORD = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}

# "<N> ... calculators" / "<N> calc types" — the qualifier words in between are the
# ones the site actually uses ("58 standards-referenced calculators included").
CALC_CLAIM = re.compile(
    r"\b(\d{2}|" + "|".join(WORD) + r")\s+"
    r"(?:free\s+|specific\s+|standards-referenced\s+|engineering\s+|design\s+)*"
    r"calc(?:ulators?|\s+types?)\b", re.I)
DISC_CLAIM = re.compile(r"\b(\d{1,2}|" + "|".join(WORD) + r")\s+disciplines?\b", re.I)
# a discipline claim is only about calculators if calculator language is nearby
NEAR_CALC = re.compile(r"calc|engineering design", re.I)
NEAR_WINDOW = 120

DATE_MOD_LD = re.compile(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})"')
VISIBLE_UPD = re.compile(r'(?:Last updated|Updated)\s*<time datetime="(\d{4}-\d{2}-\d{2})"')


def _n(tok: str) -> int:
    return WORD.get(tok.lower(), 0) or int(tok)


def truth() -> dict:
    """Both SSOTs. Derived, never typed."""
    pages = disciplines = 0
    per_disc: dict[str, int] = {}
    try:
        import build_calc_pages as b
        pages = len(b.CALC_DATA)
        for v in b.CALC_DATA.values():
            per_disc[v["discipline"]] = per_disc.get(v["discipline"], 0) + 1
        disciplines = len(per_disc)
    except Exception:
        pass
    wb_calcs, wb_disc = 0, 0
    try:                                     # the workbench registry, via its own gate
        import validate_engdesign_registry as ve
        for fn in ("registry_counts", "counts", "calc_counts"):
            if hasattr(ve, fn):
                c = getattr(ve, fn)()
                wb_calcs = c.get("calcs", c.get("total", 0))
                wb_disc = c.get("disciplines", 0)
                break
    except Exception:
        pass
    if not wb_calcs:                         # fall back to parsing the registry directly
        try:
            js = (ROOT / "engineering-design.js").read_text(encoding="utf-8", errors="replace")
            m = re.search(r"CALC_TYPES_UI\s*=\s*\{(.*?)\n\s*\};", js, re.S)
            if m:
                block = m.group(1)
                wb_disc = len(re.findall(r"^\s{2,4}['\"]?[A-Z][^'\"\n:]*['\"]?\s*:\s*\[", block, re.M))
                wb_calcs = len(re.findall(r"\bid\s*:\s*['\"]", block)) or \
                           len(re.findall(r"\{\s*name\s*:", block))
        except Exception:
            pass
    return {"pages": pages, "page_disciplines": disciplines, "per_discipline": per_disc,
            "workbench_calcs": wb_calcs, "workbench_disciplines": wb_disc}


def _pages() -> list[str]:
    try:
        import seo_technical_gate as st
        pl = list(st.indexable_pages())
    except Exception:
        pl = [str(p.relative_to(ROOT).as_posix()) for p in ROOT.glob("learn/*/index.html")]
    return pl + ["llms.txt"]


def audit() -> dict:
    t = truth()
    # A claim passes if the SSOT justifies it. That includes the PER-DISCIPLINE counts:
    # "electrical and power (15 calculators: ...)" is a true statement, and the first
    # version of this gate flagged 15 as stale — flagging correct copy is how a gate
    # earns the habit of being ignored. Accepting them costs little, because the drift
    # this exists to catch (51, 53, 58) matches no per-discipline count either.
    ok_calc = ({v for v in (t["pages"], t["workbench_calcs"]) if v}
               | set(t["per_discipline"].values()))
    ok_disc = {v for v in (t["page_disciplines"], t["workbench_disciplines"]) if v}
    bad_calc, bad_disc, bad_date = [], [], []

    for rel in _pages():
        f = ROOT / rel
        if not f.exists():
            continue
        s = f.read_text(encoding="utf-8", errors="replace")

        for m in CALC_CLAIM.finditer(s):
            v = _n(m.group(1))
            if ok_calc and v not in ok_calc:
                bad_calc.append({"page": rel, "claim": m.group(0).strip(), "value": v})

        for m in DISC_CLAIM.finditer(s):
            lo, hi = max(0, m.start() - NEAR_WINDOW), m.end() + NEAR_WINDOW
            if not NEAR_CALC.search(s[lo:hi]):
                continue                       # a skills/other discipline claim
            v = _n(m.group(1))
            if ok_disc and v not in ok_disc:
                bad_disc.append({"page": rel, "claim": m.group(0).strip(), "value": v})

        ld = DATE_MOD_LD.search(s)
        vis = VISIBLE_UPD.findall(s)
        if ld and vis:
            off = sorted({d for d in vis if d != ld.group(1)})
            if off:
                bad_date.append({"page": rel, "dateModified": ld.group(1), "visible": off})

    per = t["per_discipline"]
    sum_ok = (sum(per.values()) == t["pages"]) if per else True
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "truth": t,
            "accepted_calc_counts": sorted(ok_calc), "accepted_discipline_counts": sorted(ok_disc),
            "calc_count": len(bad_calc), "discipline_count": len(bad_disc),
            "date_agreement": len(bad_date), "discipline_sum": 0 if sum_ok else 1,
            "bad_calc": bad_calc[:25], "bad_disc": bad_disc[:25], "bad_date": bad_date[:25]}


CHECKS = ("calc_count", "discipline_count", "date_agreement", "discipline_sum")


def run() -> int:
    rep = audit()
    REPORT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    base = {}
    if BASELINE.exists():
        try:
            base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception:
            base = {}
    t = rep["truth"]
    print("=" * 70)
    print("  CALCULATOR CLAIM CONSISTENCY — the site's story about its own size")
    print("=" * 70)
    print(f"  SSOT pages     : {t['pages']} calculators / {t['page_disciplines']} disciplines"
          f"   (build_calc_pages.CALC_DATA)")
    print(f"  SSOT workbench : {t['workbench_calcs']} calc types / {t['workbench_disciplines']} disciplines"
          f"   (CALC_TYPES_UI)")
    print(f"  a claim passes if it equals one of {rep['accepted_calc_counts']} "
          f"calculators or {rep['accepted_discipline_counts']} disciplines")
    print("-" * 70)
    regressed = False
    for c in CHECKS:
        cur, prior = rep[c], base.get(c, rep[c])
        flag = "OK  " if cur == 0 else "WARN"
        if cur > prior:
            flag, regressed = "FAIL", True
        print(f"    {flag}  {c:<18} {cur}   (baseline {prior})")
    for r in rep["bad_calc"][:8]:
        print(f"      stale count  {r['page']}: \"{r['claim']}\"")
    for r in rep["bad_disc"][:8]:
        print(f"      stale disc   {r['page']}: \"{r['claim']}\"")
    for r in rep["bad_date"][:8]:
        print(f"      date split   {r['page']}: schema {r['dateModified']} vs visible {r['visible']}")
    print("=" * 70)
    if regressed:
        print("  FAIL — a new inconsistent claim about the platform's own size.")
        return 1
    BASELINE.write_text(json.dumps(
        {c: min(base.get(c, rep[c]), rep[c]) for c in CHECKS} |
        {"established": base.get("established", rep["generated_at"])}, indent=2), encoding="utf-8")
    total = sum(rep[c] for c in CHECKS)
    print("  PASS — every claim matches a derived count." if total == 0
          else f"  PASS — no regression, but {total} claim(s) still disagree with the SSOTs.")
    return 0


def self_test() -> int:
    ok = True

    def ck(c, m):
        nonlocal ok
        ok &= bool(c)
        print(f"  {'PASS' if c else 'FAIL'}  {m}")

    ck(_n("eight") == 8 and _n("58") == 58, "word and digit forms both parse")
    ck(bool(CALC_CLAIM.search("58 standards-referenced calculators included")),
       "matches a qualifier-laden claim (the phrasing that escaped the first sweep)")
    ck(bool(CALC_CLAIM.search("51 calc types across 6 disciplines")), "matches 'calc types'")
    ck(bool(DISC_CLAIM.search("Six disciplines: HVAC and cooling")),
       "matches the WORD form (the page that said 'Six', not '6')")
    s = "A technician who reached Level 3 in 4 of 5 disciplines earns promotion."
    m = DISC_CLAIM.search(s)
    lo, hi = max(0, m.start() - NEAR_WINDOW), m.end() + NEAR_WINDOW
    ck(not NEAR_CALC.search(s[lo:hi]), "a SKILLS discipline claim is not a calculator claim")
    t = truth()
    ck(t["pages"] > 0 and t["page_disciplines"] > 0, f"page SSOT derives ({t['pages']}/{t['page_disciplines']})")
    ck(sum(t["per_discipline"].values()) == t["pages"], "per-discipline counts sum to the total")
    r = audit()
    ck(isinstance(r["calc_count"], int), f"audit runs (calc_count={r['calc_count']}, "
                                        f"disc={r['discipline_count']}, dates={r['date_agreement']})")
    print("  self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(self_test() if "--self-test" in sys.argv[1:] else run())
