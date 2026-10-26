"""
Component-Adoption Ratchet (L0) — FULLSTACK_COMPONENT_LIBRARY_ROADMAP §2.3 F-P2.
================================================================================
FAMILY_UFAI §10.4 item 4, built: "gate adoption so it ratchets — an unadopted
component silently rots back to 0." Same forward-only shape as
validate_design_tokens.py L3/L4, but per canonical primitive:

  A1  ADOPTION FLOOR (FAIL) — for every MEASURED row of
      design_component_registry.json, the live adopter count must be >= the
      floor in component_adoption_baseline.json. A page dropping whListSkeleton
      / .wh-disclose / whFmt* is a regression, not a choice.
  A2  AUTO-TIGHTEN — adoption above the floor re-baselines UPWARD automatically
      (the ratchet only ever climbs; no one has to remember to re-baseline).
  A3  REGISTRY INTEGRITY (FAIL) — floors ↔ registry rows must match 1:1.
      Deleting a registry row (or its floor) to dodge the ratchet is itself a
      failure; retiring a component is an Ian-gated registry edit + explicit
      re-baseline (delete component_adoption_baseline.json floors entry in the
      same change, with the roadmap updated).
  A4  NO INLINE REDEFINITIONS (FAIL) — a page defining `function whFmtDate(`
      etc. inline shadows utils.js (Frontend skill: two implementations drift
      silently). Currently 0; forward-clean.

Adoption is RECOMPUTED LIVE via tools/component_adoption_census.run_census()
— never read from a stale report (QA skill: stale *_report.json is a false-
alarm class).

Output: component_adoption_gate_report.json (+ rewrites
component_adoption_baseline.json on tighten). Exit 1 on A1/A3/A4, else 0.
"""
from __future__ import annotations

import datetime
import io
import json
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from component_adoption_census import run_census, class_used  # noqa: E402

BASELINE = ROOT / "component_adoption_baseline.json"
REPORT = ROOT / "component_adoption_gate_report.json"

# ★A FLOOR THAT COUNTED LOOKALIKES (BRH.10 AJ, 2026-10-26). The census matched `\bcls\b`, and \b treats "-" as a word
# edge, so oh-tile and rag-tile credited the .tile family (FC1) to index.html and analytics-report.html, which never
# used it. With the class matched as a whole token FC1 reads 19, and its floor of 21 was two pages that were never
# adopters - a measurement corrected, not adoption lost. Each correction is one entry: it applies only while the floor
# still holds the inflated value and the census shows exactly that shortfall, and the run says so.
REMEASURED = {
    "FC1": {"from": 21, "to": 19, "date": "2026-10-26",
            "pages": ["analytics-report.html", "index.html"],
            "why": "credited for oh-tile / rag-tile by a matcher that treated '-' as a word edge"},
}


def matcher_findings() -> list[str]:
    """A5: the census credits a class only as a whole token of the class attribute."""
    cases = [('<div class="heat-card">', "card", False), ('<span class="stat-pill x">', "pill", False),
             ('<div class="oh-tile-num">', "tile", False), ('<div class="a card b">', "card", True),
             ('<button class="filter-chip active">', "filter-chip", True),
             # marketplace's live chips: a template glued to the name is still the class
             ('<button class="filter-chip${_cat === c ? \' active\' : \'\'}">', "filter-chip", True),
             ("<span class='wh-num big'>", "wh-num", True)]
    return [f"A5: class_used({src!r}, {cls!r}) is {not want}, want {want} - the census credits lookalike classes"
            for src, cls, want in cases if class_used(src, cls) is not want]


def write_baseline(rows, drift, n_pages, tightened: bool):
    measured = [r for r in rows if r["mode"] == "measured"]
    BASELINE.write_text(json.dumps({
        "_doc": "Component adoption baseline (Layer F). Floors are FORWARD-ONLY: "
                "validate_component_adoption.py fails any drop and auto-tightens any rise. "
                "Regenerate view: python tools/component_adoption_census.py",
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "family_pages": n_pages,
        "rows": rows,
        "drift": drift,
        "floors": {r["id"]: r["adopters_n"] for r in measured},
        "tightened": tightened,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    rows, drift, n_pages = run_census()
    measured = {r["id"]: r for r in rows if r["mode"] == "measured"}
    failures: list[str] = []
    tightened: list[str] = []

    if not BASELINE.exists():
        write_baseline(rows, drift, n_pages, tightened=False)
        print(f"component-adoption: first run — baseline created ({len(measured)} floors). PASS")
        return 0

    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    floors: dict = base.get("floors", {})
    base_rows = {r["id"]: r for r in base.get("rows", []) if r.get("mode") == "measured"}
    remeasured: list[str] = []
    for cid, fix in REMEASURED.items():
        if floors.get(cid) == fix["from"] and cid in measured and measured[cid]["adopters_n"] == fix["to"] \
                and not set(fix["pages"]) & set(measured[cid]["adopters"]):
            floors[cid] = fix["to"]
            remeasured.append(f"{cid} {fix['from']} -> {fix['to']} ({fix['date']}: {', '.join(fix['pages'])} {fix['why']})")
    failures.extend(matcher_findings())

    # A3 registry integrity — both directions
    for cid in floors:
        if cid not in measured:
            failures.append(f"A3: floor '{cid}' has NO registry row (component deleted/renamed "
                            "without an explicit re-baseline)")
    for cid in measured:
        if cid not in floors:
            # a NEW registry row simply gains a floor (that's growth, not failure)
            tightened.append(f"{cid} (new row, floor={measured[cid]['adopters_n']})")

    # A1 floors / A2 tighten
    rebased: list[str] = []
    for cid, r in measured.items():
        floor = floors.get(cid)
        if floor is None:
            continue
        if r["adopters_n"] < floor:
            lost = sorted(set(base_rows.get(cid, {}).get("adopters", [])) - set(r["adopters"]))
            # ★A PAGE DELETED FROM THE PLATFORM IS NOT A PAGE THAT STOPPED ADOPTING (2026-10-21). d7ecce37 deleted three
            # dev pages (architecture, symbol-gallery, validator-catalog); validator-catalog was a disclosure adopter, so
            # FI1 "fell 38 -> 37" and this gate stayed red for a week over a page that no longer exists. When the WHOLE
            # shortfall is adopters gone from disk, the floor follows them down by exactly that many and says so; any
            # page still on disk that dropped the component fails as before.
            gone = [p for p in lost if not (ROOT / p).exists()]
            if gone and r["adopters_n"] >= floor - len(gone):
                rebased.append(f"{cid} {floor} -> {r['adopters_n']} (adopter page(s) deleted: {', '.join(gone)})")
            else:
                failures.append(f"A1: {cid} ({r['name']}) adoption fell {floor} -> {r['adopters_n']}"
                                + (f" — dropped by: {', '.join(lost[:6])}" if lost else ""))
        elif r["adopters_n"] > floor:
            tightened.append(f"{cid} {floor} -> {r['adopters_n']}")

    # A4 inline redefinitions
    for d in drift:
        failures.append(f"A4: {d['page']} {d['note']} [{d['component']}]")

    ok = not failures
    if ok:
        write_baseline(rows, drift, n_pages, tightened=bool(tightened))

    REPORT.write_text(json.dumps({
        "ok": ok, "checked": len(measured), "failures": failures, "tightened": tightened, "rebased_for_deleted_pages": rebased, "remeasured": remeasured,
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"component-adoption: {len(measured)} measured rows"
          + (f", tightened {len(tightened)}" if tightened else ""))
    for m in remeasured:
        print(f"  REMEASURED {m}")
    for b in rebased:
        print(f"  REBASED {b}")
    for f in failures:
        print(f"  FAIL {f}")
    print("  " + ("PASS (forward-only floors held)" if ok else f"{len(failures)} FAILURE(S)"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
