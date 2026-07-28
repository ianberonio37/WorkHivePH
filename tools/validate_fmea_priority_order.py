#!/usr/bin/env python3
"""
validate_fmea_priority_order.py — AH7: a severity-9 failure mode must never be buried by RPN.

THE DEFECT THIS LOCKS OUT. RPN is Severity x Occurrence x Detection, so a rare, easily-detected
SAFETY failure scores lower than a frequent, hard-to-spot nuisance. Measured on the seeded fleet
before the fix: 17 modes carry severity >= 9 and ALL 17 sat below the median RPN — "Cable
insulation breakdown" (S9, consequence_class=safety, RPN 108) ranked below "Coupling misalignment
beyond 0.05 mm" (S6, production, RPN 180) on every asset page and every printed report.

This is the known weakness of RPN and the platform had already written it down: standards.json
iec_60812_2018.rpn notes that AIAG-VDA 2019 favours Action Priority over RPN, and the printed
report cites AIAG-VDA 2019 in its own header. We documented the caveat and then sorted by RPN.

WHAT THIS GATE HOLDS:
  1. the Action Priority helpers still exist in asset-hub.html;
  2. BOTH surfaces order through _fmeaPriorityOrder — the screen and the printed report must not
     disagree about which failure matters most, which would be worse than the original bug;
  3. the report still carries the sentence telling an auditor why the table is not in RPN order;
  4. the band logic itself, re-implemented here and checked against the cases that motivated it —
     including the exact real pair above;
  5. LIVE: the substrate the bands stand on — rpn still GENERATED from S x O x D, and S/O/D each
     still bounded 1..10. Deliberately NOT "sort by our own rule then assert our own rule holds",
     which is a tautology that can never fail; if the CHECKs or the generated column go away,
     "severity >= 9" and "RPN >= 200" quietly stop meaning anything and the bands become
     decoration. The count of modes plain rpn DESC would still bury is reported alongside, so the
     reason this rule exists stays visible instead of turning into folklore.

Live tier SKIPS cleanly (exit 0) without docker; the static checks always run. Self-test: --selftest.
"""
from __future__ import annotations
import io, json, re, subprocess, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "asset-hub.html"


def action_priority(severity, occurrence, detection, rpn=None):
    """Mirror of _fmeaActionPriority in asset-hub.html. Kept in step by the checks below."""
    s = int(severity or 0)
    n = int(rpn if rpn is not None else (s * int(occurrence or 0) * int(detection or 0)))
    if s >= 9:
        return "H"
    if n >= 200:
        return "H"
    if s >= 7:
        return "M"
    if n >= 100:
        return "M"
    return "L"


_RANK = {"H": 0, "M": 1, "L": 2}


def priority_rank(row):
    return (_RANK[action_priority(row.get("severity"), row.get("occurrence"),
                                  row.get("detection"), row.get("rpn"))],
            -int(row.get("rpn") or 0))


def psql(sql):
    try:
        p = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres",
                            "-d", "postgres", "-t", "-A", "-F", "|", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=45)
        return None if p.returncode != 0 else (p.stdout or "").strip()
    except Exception:
        return None


def selftest():
    probs = []
    # The exact pair that motivated the whole change.
    if action_priority(9, 3, 4, 108) != "H":
        probs.append("S9 safety mode at RPN 108 must be H — that is the burial this gate exists for")
    if action_priority(6, 6, 5, 180) == "H":
        probs.append("S6 production nuisance at RPN 180 must not outrank the S9 safety mode")
    if priority_rank({"severity": 9, "occurrence": 3, "detection": 4, "rpn": 108}) >= \
       priority_rank({"severity": 6, "occurrence": 6, "detection": 5, "rpn": 180}):
        probs.append("ordering does not put the S9 mode first")
    # Band boundaries.
    if action_priority(8, 5, 5, 200) != "H":     probs.append("RPN 200 must be H")
    if action_priority(5, 5, 4, 100) != "M":     probs.append("RPN 100 must be M")
    if action_priority(7, 2, 2, 28)  != "M":     probs.append("severity 7 must be at least M")
    if action_priority(4, 3, 3, 36)  != "L":     probs.append("low everything must be L")
    # It must never DEMOTE: anything previously in the top RPN band stays H.
    if action_priority(1, 10, 10, 250) != "H":   probs.append("a top-band RPN must stay H")
    # Ties inside a band fall back to RPN.
    a = priority_rank({"severity": 5, "occurrence": 5, "detection": 5, "rpn": 125})
    b = priority_rank({"severity": 5, "occurrence": 4, "detection": 6, "rpn": 120})
    if not a < b:
        probs.append("within a band, higher RPN must come first")
    print("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs))
    return 1 if probs else 0


def main():
    if "--selftest" in sys.argv:
        return selftest()

    print(f"\n{BOLD}FMEA PRIORITY ORDER (a severity-9 mode must not be buried by RPN){RESET}")
    print("-" * 74)
    fails = 0
    src = PAGE.read_text(encoding="utf-8", errors="replace") if PAGE.exists() else ""

    static = [
        ("helper present", "function _fmeaActionPriority(" in src),
        ("orderer present", "function _fmeaPriorityOrder(" in src),
        # Two call sites: the on-page list load and the printed report.
        ("both surfaces ordered", len(re.findall(r"_fmeaPriorityOrder\(", src)) >= 3),
        ("report explains the order", "Ordered by <strong>Action Priority</strong>" in src),
        ("report cites the standard", "AIAG-VDA 2019 introduced Action Priority" in src),
        ("AP badge rendered", "fmea-ap-" in src),
    ]
    for label, ok in static:
        if ok:
            print(f"  {GREEN}PASS{RESET}  {label}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {label}")

    # ── LIVE ───────────────────────────────────────────────────────────────
    # NOT "sort by my own rule, then assert my own rule holds" — that is a tautology that can
    # never fail. What is checked instead is the SUBSTRATE the banding stands on: if the 1..10
    # CHECKs or the generated RPN go away, "severity >= 9" and "RPN >= 200" stop meaning
    # anything and the bands become decoration. Those can genuinely regress, so they are worth
    # a gate; and the burial count under plain rpn DESC is reported so the reason for the rule
    # stays visible rather than becoming folklore.
    live_checks = 0
    if psql("SELECT 1;") is None:
        print(f"  {YELLOW}SKIP{RESET}  docker psql unavailable — DB invariants not checked")
    else:
        gen = psql("SELECT COALESCE(generation_expression,'') FROM information_schema.columns "
                   "WHERE table_name='rcm_fmea_modes' AND column_name='rpn';") or ""
        gen_ok = all(t in gen.lower() for t in ("severity", "occurrence", "detection"))
        live_checks += 1
        if gen_ok:
            print(f"  {GREEN}PASS{RESET}  rpn is still generated from severity x occurrence x detection")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  rpn is no longer generated from S x O x D — the bands "
                  f"and every RPN on screen can now disagree with their own inputs")

        cons = psql("SELECT string_agg(pg_get_constraintdef(oid), ' ') FROM pg_constraint "
                    "WHERE conrelid='public.rcm_fmea_modes'::regclass AND contype='c';") or ""
        for col in ("severity", "occurrence", "detection"):
            live_checks += 1
            bounded = re.search(rf"\({col} >= 1\) AND \({col} <= 10\)", cons)
            if bounded:
                print(f"  {GREEN}PASS{RESET}  {col} still bounded 1..10")
            else:
                fails += 1
                print(f"  {RED}FAIL{RESET}  {col} is no longer bounded 1..10 — 'severity >= 9' "
                      f"stops being a meaningful threshold")

        raw = psql("SELECT asset_id, severity, rpn FROM public.rcm_fmea_modes "
                   "WHERE severity IS NOT NULL;") or ""
        by_asset: dict = {}
        for line in raw.splitlines():
            parts = line.split("|")
            if len(parts) != 3:
                continue
            try:
                by_asset.setdefault(parts[0], []).append((int(parts[1]), int(parts[2])))
            except ValueError:
                continue
        # How many severity-9 modes the OLD rpn-DESC order would have buried. Informational —
        # it is the size of the problem, and if it ever reaches 0 naturally the rule is simply
        # costing nothing rather than being wrong.
        would_bury = sum(
            1
            for rows in by_asset.values()
            for sev, rpn in rows
            if sev >= 9 and any(s2 < sev and r2 > rpn for s2, r2 in rows)
        )
        total = sum(len(v) for v in by_asset.values())
        print(f"  {GREEN}INFO{RESET}  {would_bury} severity-9 mode(s) across {len(by_asset)} assets "
              f"would rank below a lower-severity mode under plain rpn DESC "
              f"({total} modes scanned)")

    print(f"\n  Summary: {len(static) + live_checks - fails} pass · {fails} fail")
    (ROOT / "fmea_priority_order_report.json").write_text(
        json.dumps({"validator": "fmea_priority_order",
                    "modes_checked": live_checks, "fail": fails}, indent=2), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
