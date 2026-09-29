"""
validate_vendor_pricing_freshness.py — a price we quote for someone else must stay true.
=========================================================================================
Three comparison pages quote another company's prices: workhive-vs-maintainx-comparison,
workhive-vs-upkeep-free-cmms-comparison and best-free-cmms-software-philippines. Between them
they carry 26 dollar figures that belong to vendors we do not control.

WHY THIS NEEDS A GATE RATHER THAN A HABIT. Each of those pages already makes the right promise
in its own words - "Pricing verified against vendor and directory listings on 5 August 2026;
SaaS pricing moves, so confirm current terms with the vendor before deciding. This comparison is
REVIEWED QUARTERLY for pricing and feature accuracy." That sentence is a commitment with a date
and a cadence in it, and nothing anywhere enforced either. It is the shape this project has
already been burned by: a step that depends on somebody remembering does not happen
([[feedback_a_step_that_depends_on_remembering_does_not_happen]] - v_kpi_truth's hourly refresh
shipped as a root "run this manually" file). The failure mode here is specific and ugly: a
competitor raises its price, our page keeps quoting the old one, and a comparison page that was
accurate when written becomes a misleading claim about another company's product - which is a
worse thing to be wrong about than our own.

WHAT IT CHECKS, and deliberately nothing more:
  A page is IN SCOPE when it names a competitor AND quotes a dollar figure. Then:
    1. it must carry a verification date ("verified ... on <date>"), and
    2. that date must be inside its own stated cadence (quarterly / monthly / annually;
       quarterly is assumed when a page states none).

WHAT IS OUT OF SCOPE, checked before the rule was written so it does not cry wolf: a GENERIC
category price with no vendor attached. "Paid products commonly start around $20 per user per
month", "a vibration analyzer can range from $5,000 to $10,000", "often around $20 to $50 per
user per month" - three pages carry these, every one hedged and none naming whose price it is.
Those are market context, not a claim about a named company, and flagging them would demand the
pages stop giving a reader any sense of cost at all.

MEASURED 2026-09-21: 3 pages in scope, all three dated 5 August 2026 with a quarterly cadence -
47 days old, inside the window. Registers GREEN and starts failing on 3 November 2026, which is
the point: the promise now has a deadline attached to it.

RUN:  python tools/validate_vendor_pricing_freshness.py --check
      python tools/validate_vendor_pricing_freshness.py --self-test
"""
from __future__ import annotations

import datetime as _dt
import glob
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BRANDS = re.compile(
    r"\b(MaintainX|UpKeep|Fiix|Limble|eMaint|Hippo CMMS|Fracttal|MicroMain|"
    r"Maintenance Connection|Asset Panda|ManagerPlus|Brightly)\b")
PRICE = re.compile(r"\$\s?\d")
# "verified ... on 5 August 2026" / "accessed August 2026" style
VERIFIED = re.compile(r"verified[^.<>]{0,120}?on\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})", re.I)
CADENCE = re.compile(r"reviewed\s+(quarterly|monthly|annually)", re.I)

WINDOW = {"monthly": 31, "quarterly": 92, "annually": 366}
DEFAULT_CADENCE = "quarterly"


# ★PROXIMITY, NOT CO-OCCURRENCE. The first version scoped a page in when a brand appeared
# ANYWHERE and a price appeared ANYWHERE, and it immediately produced a false positive:
# what-is-workhive-complete-platform-guide names Fiix as an INTEGRATION TARGET ("two-way sync
# with SAP PM, IBM Maximo and Fiix") in one table row, and quotes a generic "often around $20 to
# $50 per user per month" in another. Neither is a claim about Fiix's price. Co-occurrence on a
# page is not association, and a gate that treats it as one cries wolf on exactly the pages that
# were careful. The price must sit near the brand it belongs to.
_WINDOW_CHARS = 200


def _prices_a_vendor(html: str) -> bool:
    """True only when a named vendor and a dollar figure are close enough to be one claim."""
    for m in BRANDS.finditer(html):
        near = html[max(0, m.start() - _WINDOW_CHARS): m.end() + _WINDOW_CHARS]
        if PRICE.search(near):
            return True
    return False


def _parse(datestr: str):
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return _dt.date(*_dt.datetime.strptime(datestr.strip(), fmt).timetuple()[:3])
        except ValueError:
            continue
    return None


def audit(today: _dt.date | None = None, pages: list[str] | None = None) -> dict:
    today = today or _dt.date.today()
    pages = pages if pages is not None else sorted(glob.glob(str(ROOT / "learn/*/index.html")))
    rows, problems = [], []
    for f in pages:
        p = Path(f)
        html = p.read_text(encoding="utf-8", errors="replace")
        if not _prices_a_vendor(html):
            continue
        rel = p.relative_to(ROOT).as_posix() if str(ROOT) in str(p) else p.name
        cad = (CADENCE.search(html).group(1).lower() if CADENCE.search(html) else DEFAULT_CADENCE)
        m = VERIFIED.search(html)
        when = _parse(m.group(1)) if m else None
        row = {"page": rel, "cadence": cad, "verified": when.isoformat() if when else None,
               "age_days": (today - when).days if when else None,
               "window": WINDOW[cad], "prices": len(PRICE.findall(html))}
        if when is None:
            row["state"] = "undated"
            problems.append(row)
        elif row["age_days"] > WINDOW[cad]:
            row["state"] = "stale"
            problems.append(row)
        else:
            row["state"] = "fresh"
        rows.append(row)
    return {"rows": rows, "problems": problems, "today": today.isoformat()}


def run(check: bool = False) -> int:
    rep = audit()
    print("=" * 70)
    print("  VENDOR PRICING FRESHNESS — is a price we quote for someone else still true?")
    print("=" * 70)
    print("  %d page(s) quote a named competitor's price   (today %s)"
          % (len(rep["rows"]), rep["today"]))
    for r in rep["rows"]:
        print("    %-9s %-52s %s/%sd  %d price(s)"
              % (r["state"], r["page"].replace("learn/", "").replace("/index.html", "")[:50],
                 r["age_days"] if r["age_days"] is not None else "--", r["window"], r["prices"]))
    print("-" * 70)
    if rep["problems"]:
        for r in rep["problems"]:
            if r["state"] == "undated":
                print("  UNDATED  %s quotes a named vendor's price with no verification date." % r["page"])
            else:
                print("  STALE    %s: verified %s, %d days ago, past its own %s window (%dd)."
                      % (r["page"], r["verified"], r["age_days"], r["cadence"], r["window"]))
        print()
        print("  FAIL — a price quoted for another company has outlived its own promise.")
        print("  FIX: re-check the vendor's published pricing, update the figures, and move the")
        print("       'verified ... on <date>' line to today. Do not move the date without")
        print("       re-checking: the date is the claim.")
        print("=" * 70)
        return 1 if check else 0
    print("  PASS — every quoted competitor price is inside its own review window.")
    print("=" * 70)
    return 0


def self_test() -> int:
    ok = True

    def ck(c, m):
        nonlocal ok
        ok &= bool(c)
        print("  %s  %s" % ("PASS" if c else "FAIL", m))

    import tempfile
    with tempfile.TemporaryDirectory() as d:
        fresh = Path(d) / "fresh.html"
        stale = Path(d) / "stale.html"
        undated = Path(d) / "undated.html"
        generic = Path(d) / "generic.html"
        fresh.write_text("MaintainX costs $20. Pricing verified against listings on 1 September 2026. "
                         "Reviewed quarterly.", encoding="utf-8")
        stale.write_text("UpKeep costs $45. Pricing verified against listings on 1 January 2026. "
                         "Reviewed quarterly.", encoding="utf-8")
        undated.write_text("Fiix costs $35 per user per month.", encoding="utf-8")
        generic.write_text("Paid products commonly start around $20 per user per month.",
                           encoding="utf-8")
        # the live false positive that forced the proximity rule: a brand named as an
        # integration target, and an unrelated generic price far away on the same page
        faraway = Path(d) / "faraway.html"
        faraway.write_text("<tr><td>Two-way sync with SAP PM, IBM Maximo and Fiix.</td></tr>"
                           + ("<p>filler</p>" * 40)
                           + "<tr><td>Often around $20 to $50 per user per month.</td></tr>",
                           encoding="utf-8")
        today = _dt.date(2026, 9, 21)
        r = audit(today, [str(fresh), str(stale), str(undated), str(generic), str(faraway)])
        states = {Path(x["page"]).name: x["state"] for x in r["rows"]}
        ck(len(r["rows"]) == 3, "a generic category price with no vendor is OUT of scope (%d in scope)"
           % len(r["rows"]))
        ck("faraway.html" not in {Path(x["page"]).name for x in r["rows"]},
           "a brand named as an integration target, far from an unrelated price, is OUT of scope")
        ck(states.get("fresh.html") == "fresh", "a price verified inside its window passes")
        ck(states.get("stale.html") == "stale", "a price past its own quarterly window is caught")
        ck(states.get("undated.html") == "undated", "a named-vendor price with no date is caught")
        ck(_parse("5 August 2026") == _dt.date(2026, 8, 5), "the date parser reads the live format")

    live = audit()
    ck(len(live["rows"]) >= 3, "finds the live comparison pages (%d)" % len(live["rows"]))
    ck(not live["problems"], "the live corpus is clean, so this registers as a ratchet")
    print("  self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--self-test" in argv:
        raise SystemExit(self_test())
    raise SystemExit(run(check="--check" in argv))
