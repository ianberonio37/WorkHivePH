#!/usr/bin/env python3
"""validate_analytics_page.py — Analytics Engine arc page-level invariants (A4 / AI3 / A6).

Static gate over analytics.html (+ prescriptive.py) that ratchets three deep-walk fixes so they
can't regress:

  C1 (A4 — CLS): every Plotly chart mount `<div id="${chartId}" ...>` reserves a `min-height`, so the
     deferred async draw (queueChart -> flushCharts ~350ms) can't push content down = layout shift.
  C2 (AI3 — honest labelling): the Priority-Ranking composite (crit x freq x downtime) is NEVER
     presented as a bare ISO 55001 metric ("ISO 55001 risk framework") — it must read "inspired"
     (analytics-engineer skill: a weighted composite is labelled custom, never as an ISO standard).
  C3 (A6 — no em-dash): the worker-view asset-filter <option> renders no em-dash (platform rule).

Static (no DB/deno/browser) -> runs in --fast. Self-test: --self-test proves each check has teeth.
Skills: frontend/performance (CLS), analytics-engineer (composite labelling), designer (no em-dash).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "analytics.html"
PRESC = ROOT / "python-api" / "analytics" / "prescriptive.py"
UTILS = ROOT / "utils.js"
GREEN, RED = "\033[92m", "\033[91m"; RST = "\033[0m"
SELF_TEST = "--self-test" in sys.argv[1:]
EMDASH = "—"


def check_cls(html: str) -> tuple[bool, str]:
    mounts = re.findall(r'<div id="\$\{chartId\}"[^>]*>', html)
    missing = [m for m in mounts if "min-height" not in m]
    ok = bool(mounts) and not missing
    return ok, f"{len(mounts)} chart mounts, {len(missing)} without min-height"


def check_iso(html: str, presc: str) -> tuple[bool, str]:
    bad = []
    if "ISO 55001 risk framework" in html or "ISO 55001 risk framework" in presc:
        bad.append("bare 'ISO 55001 risk framework' label present")
    # the priority card standard must qualify the composite as inspired
    if "ISO 55001-inspired" not in html:
        bad.append("analytics.html priority card missing 'ISO 55001-inspired'")
    return (not bad), ("; ".join(bad) or "composite labelled inspired, not a bare ISO metric")


def check_emdash(html: str) -> tuple[bool, str]:
    # em-dash inside any rendered <option ...>...</option> literal (user-facing copy)
    offenders = [o for o in re.findall(r"<option[^>]*>[^<]*</option>", html) if EMDASH in o]
    return (not offenders), (f"{len(offenders)} <option> with em-dash" if offenders else "no em-dash in rendered options")


def check_chart_a11y(html: str) -> tuple[bool, str]:
    # every Plotly chart mount must carry a text alternative (role=img + aria-label) for SR users
    mounts = re.findall(r'<div id="\$\{chartId\}"[^>]*>', html)
    missing = [m for m in mounts if 'role="img"' not in m or "aria-label=" not in m]
    ok = bool(mounts) and not missing
    return ok, f"{len(mounts)} chart mounts, {len(missing)} without role=img+aria-label"


def check_fetch_error_honesty(html: str) -> tuple[bool, str]:
    # A5: on a descriptive fetch failure, the OEE/MTBF/PM summary tiles must leave the
    # "Loading..." state (set to 'Unavailable'), not sit on Loading forever.
    reset = re.search(r"phase === 'descriptive'[\s\S]{0,260}Unavailable", html)
    return bool(reset), ("summary tiles reset to 'Unavailable' on descriptive fetch failure"
                         if reset else "no descriptive-failure reset — tiles can stay 'Loading...' forever")


def check_text_contrast(html: str, utils_kpi: str) -> tuple[bool, str]:
    # U5: informational white TEXT (not border-/background-color) over the dark analytics bg must use
    # opacity >= 0.5 to clear WCAG AA 4.5:1 (verified live: 0.6 → ~7.4:1). `(?<!-)color:` skips
    # border-color/background-color. Covers analytics.html + the shared renderKpiTile muted block.
    bad = []
    for label, src in (("analytics.html", html), ("utils.renderKpiTile", utils_kpi)):
        for op in re.findall(r"(?<!-)color: ?rgba\(255,\s*255,\s*255,\s*(0\.\d+)\)", src):
            if float(op) < 0.5:
                bad.append(f"{label}:{op}")
    ok = not bad
    return ok, ("all white text >= 0.5 opacity (AA over dark bg)" if ok
                else f"{len(bad)} sub-0.5 white text color(s): {bad[:5]}")


def check_mobile_table_scroll(html: str) -> tuple[bool, str]:
    # A1: the list-renderer data-tables (incl. the 6-col Priority Ranking that overflowed
    # at 390px) must sit inside a horizontal-scroll wrapper, and the wrapper CSS must exist.
    css = bool(re.search(r"\.table-scroll\s*\{[^}]*overflow-x", html))
    wrapped = len(re.findall(r'table-scroll">[^<]*<!-- table-name-allow', html))
    ok = css and wrapped >= 2  # both renderListWithShowAll table branches wrapped
    return ok, (f"table-scroll CSS + {wrapped} list-tables wrapped" if ok
                else f"css={css}, wrapped_tables={wrapped} (wide tables can overflow at 390px)")


def check_hive_id_fallback(html: str) -> tuple[bool, str]:
    # Resilience: a hive member must not silently drop to worker scope when wh_active_hive_id is
    # unset — HIVE_ID resolution must fall back to the sole wh_hives membership.
    m = re.search(r"const HIVE_ID[\s\S]{0,320}", html)
    ok = bool(m) and "wh_hives" in (m.group(0) if m else "")
    return ok, ("HIVE_ID falls back to the sole wh_hives membership" if ok
                else "HIVE_ID has no wh_hives fallback — a member can silently see worker-scoped KPIs")


def run(html: str, presc: str, utils_kpi: str) -> list[tuple[str, bool, str]]:
    return [
        ("C1 chart CLS reserve", *check_cls(html)),
        ("C2 ISO-55001 honest label", *check_iso(html, presc)),
        ("C3 no em-dash in options", *check_emdash(html)),
        ("C4 chart text-alternative (SC 1.1.1)", *check_chart_a11y(html)),
        ("C5 fetch-fail tile honesty (A5)", *check_fetch_error_honesty(html)),
        ("C6 mobile table scroll (A1)", *check_mobile_table_scroll(html)),
        ("C7 muted-text AA contrast (U5)", *check_text_contrast(html, utils_kpi)),
        ("C8 HIVE_ID single-hive fallback", *check_hive_id_fallback(html)),
    ]


def main() -> int:
    print(f"\n{'='*64}\n  Analytics arc — page invariants (A4 CLS / AI3 label / A6 em-dash)\n{'='*64}")
    if not HTML.exists() or not PRESC.exists():
        print(f"{RED}  FAIL  analytics.html or prescriptive.py not found{RST}"); return 1
    html = HTML.read_text(encoding="utf-8", errors="replace")
    presc = PRESC.read_text(encoding="utf-8", errors="replace")
    # Extract just the renderKpiTile function region (its muted text is the analytics KPI-tile
    # component); avoids false-positives from other utils.js code over different backgrounds.
    utils_kpi = ""
    if UTILS.exists():
        u = UTILS.read_text(encoding="utf-8", errors="replace")
        i = u.find("function renderKpiTile")
        utils_kpi = u[i:i + 2500] if i >= 0 else ""

    if SELF_TEST:
        # Each check must FAIL on a deliberately-broken input (teeth).
        t1 = not check_cls('<div id="${chartId}" style="width:100%;"></div>')[0]
        t2 = not check_iso('ISO 55001 risk framework', '')[0]
        t3 = not check_emdash(f'<option value="">{EMDASH} Filter {EMDASH}</option>')[0]
        t4 = not check_chart_a11y('<div id="${chartId}" style="width:100%;"></div>')[0]
        t5 = not check_fetch_error_honesty("catch { renderPhase(); }")[0]
        t6 = not check_mobile_table_scroll('<table class="data-table">x</table>')[0]
        t7 = not check_text_contrast('color:rgba(255,255,255,0.3)', '')[0]
        t8 = not check_hive_id_fallback('const HIVE_ID = localStorage.getItem("wh_active_hive_id") || null;')[0]
        print(f"  self-test: C1={t1} C2={t2} C3={t3} C4={t4} C5={t5} C6={t6} C7={t7} C8={t8} "
              f"({GREEN+'teeth OK'+RST if all([t1,t2,t3,t4,t5,t6,t7,t8]) else RED+'NO TEETH'+RST})")

    results = run(html, presc, utils_kpi)
    allok = True
    for name, ok, detail in results:
        allok = allok and ok
        print(f"  {GREEN+'PASS'+RST if ok else RED+'FAIL'+RST}  {name}: {detail}")
    print("-" * 64)
    print(f"{(GREEN if allok else RED)}  RESULT: {'GREEN — analytics page invariants hold.' if allok else 'RED — an analytics-page invariant regressed.'}{RST}")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
