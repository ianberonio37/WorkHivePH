#!/usr/bin/env python3
"""validate_i18n_coverage.py — P11 i18n adoption scanner (bug-hunt denominator v2, 2026-07-17).

The platform localizes EN+FIL via `data-i="key"` attributes (static HTML) and `_t('key')` /
`WH_LANG` / the `wh-locale-change` re-render (JS strings). This gate measures per USER-FACING page
how adopted that shared i18n system is — the P11 dimension the per-page battery was missing.

It counts i18n MARKERS (`data-i=` + `_t(` + `whT(`) per page and classifies adoption:
  covered  >= 25 markers  ·  partial 5-24  ·  thin 1-4  ·  none 0
Internal / admin surfaces (founder-console) are EN-only by design -> listed EXEMPT, not a gap.

Heuristic v1 caveat: marker COUNT is a proxy for adoption, not an exact translated/total %. A page
with 0 markers genuinely has no i18n; the bands are for triage. A v2 could compute
translated-strings / total-visible-strings for a true %.

ADVISORY / non-blocking (always exits 0) — surfaces the P11 backlog + a platform adoption %, ratchets
as pages get localized. Self-test: --selftest (deterministic, no fs scan).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAGES_DIR = REPO / "i18n" / "pages"   # the emitted per-page FIL dictionaries utils.js fetches (EX-TL)
EXCLUDE = ("node_modules", "remotion_scenes", "video_marketing_app", ".backup", "-test.")
# EN-only by design (internal admin / dev / utility surfaces) — not user-facing product, exempt from
# the user-facing i18n requirement (listed as exempt, not counted as a gap).
INTERNAL_EXEMPT = {
    "founder-console.html", "architecture.html", "design-system.html", "symbol-gallery.html",
    "validator-catalog.html", "llm-observability.html", "agentic-rag-observability.html",
    "offline-fallback.html", "promo-poster.html", "status.html",
    # platform-actions.html = an internal governance ACTION-QUEUE console (noindex, not in the user nav,
    # approve/verify/resolve + a Founder Ops dashboard link) — EN-only like founder-console, not a
    # user-facing product surface. Exempt, not a gap (2026-07-19 disposition).
    "platform-actions.html",
}

MARKER_RE = re.compile(r"data-i(?:18n)?=|\b_t\(|\bwhT\(", re.I)
INFRA_RE = re.compile(r"WH_LANG|wh-locale-change|window\._t\b|function\s+_t\b", re.I)
# EN-BY-DESIGN disposition (2026-07-19): a formal engineering document / EN publication whose BODY is
# EN-by-design (only its UI chrome is translatable) is NOT a coverage gap — flagging it is the
# "declared-a-bug-before-recalling-the-disposition" error ([[feedback_recall_the_disposition_before_declaring_a_bug]]).
# The page DECLARES it inline (a `translate="no"` masthead + an explicit comment). project-report.html
# (formal engineering report) + ph-intelligence.html (EN publication) both declare it. Detected, not a gap.
DISPOSITION_RE = re.compile(
    r"EN[-\s]by[-\s]design|EN publication by design|report BODY is (?:an\s+)?EN\b"
    r"|formal engineering document", re.I)


def classify(markers: int) -> str:
    if markers >= 25:
        return "covered"
    if markers >= 5:
        return "partial"
    if markers >= 1:
        return "thin"
    return "none"


DATA_I_KEY_RE = re.compile(r"""data-i(?:18n)?=["']([A-Za-z0-9_]+)["']""")
DICT_KEY_RE = re.compile(r"""["']?([A-Za-z_][\w]*)["']?\s*:""")
# A page with its OWN i18n engine (index/hive/analytics define `function _t` + their own big dictionary)
# resolves data-i keys via THAT engine, not WH_FIL_PAGE — so the unresolved-marker check does not apply
# (it can't model their dictionary; flagging them = false positive). Only SHARED-mechanism pages
# (WH_FIL_PAGE + utils.js whI18nApply, no own engine) are checked.
OWN_ENGINE_RE = re.compile(r"function\s+_t\b|const\s+_t\b|window\._t\s*=")


def common_keys() -> set:
    """Keys in utils.js WH_FIL_COMMON — a data-i marker matching one auto-translates (no page dict needed)."""
    try:
        t = (REPO / "utils.js").read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return set()
    m = re.search(r"WH_FIL_COMMON\s*=\s*\{(.*?)\};", t, re.S)
    return set(DICT_KEY_RE.findall(m.group(1))) if m else set()


def page_dict_keys(html: str) -> set:
    """Keys declared in the page's own WH_FIL_PAGE dict — supports BOTH `= { … }` and the
    `= Object.assign(WH_FIL_PAGE || {}, { … })` merge form (resume.html uses the latter; missing it
    false-flagged every key as unresolved)."""
    keys = set()
    # Form A: WH_FIL_PAGE = { key: … }
    for m in re.finditer(r"WH_FIL_PAGE\s*=\s*\{(.*?)\}", html, re.S):
        keys |= set(DICT_KEY_RE.findall(m.group(1)))
    # Form B: WH_FIL_PAGE = Object.assign(<prev>, { key: … })  — capture the 2nd-arg object literal.
    for m in re.finditer(r"WH_FIL_PAGE\s*=\s*Object\.assign\(.*?,\s*\{(.*?)\}\s*\)", html, re.S):
        keys |= set(DICT_KEY_RE.findall(m.group(1)))
    return keys


def emitted_page_keys(stem: str) -> set:
    """Keys in the EMITTED per-page dictionary i18n/pages/<stem>.fil.json.

    THE GATE'S VOCABULARY WENT STALE WHEN THE MECHANISM MOVED (found 2026-09-10, Filipino walk).
    EX-TL (2026-09-07) moved every `p_*` key out of the inline `WH_FIL_PAGE` block and into a file
    utils.js fetches under FIL — precisely because the inline block was paid by every English reader.
    This resolver was never taught the new source, so it kept scoring pages against COMMON + the inline
    block alone and reported 899 markers as SILENTLY BROKEN when the overwhelming majority resolve
    fine from the emitted file. An advisory gate that cries 899 is a gate no one reads, and the real
    handful it was built to catch (public-feed / plant-connections / ai-quality) were buried in it.
    Same class as the momentum guard's ★×16: when a mechanism grows a new source, every instrument
    that reads it must grow in the SAME change, or the instrument silently starts measuring the past.
    """
    if not stem:
        return set()
    f = PAGES_DIR / f"{stem}.fil.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return set(d) if isinstance(d, dict) else set()


# A key the RUNTIME owns, declared absent on purpose. The convention mirrors this codebase's
# other inline dispositions (empty-catch-allow, canonical-allow, attribution-allow): the source
# states the reason beside the decision. The trailing colon is required so that an unexplained
# absence stays BROKEN - the exemption is the explanation, not the phrase.
RUNTIME_OWNED_RE = re.compile(r"(p_[a-z0-9_]+)\s+is\s+deliberately\s+ABSENT\s*:", re.I)


def runtime_owned_keys(html: str) -> set:
    """Keys the page declares it owns at RUNTIME, so a static dictionary entry would be wrong.

    assistant.html's grounding chip is the case this was written for: whether answers are
    grounded is decided from the session, and a 2026-09-15 critique found the static table
    OVERWRITING the runtime's "not grounded" warning with a grounding claim. The entry was
    removed and _setAssistantScopeChip given both languages. Reporting that as a broken
    translation invites exactly the fix that breaks it again.
    """
    return set(RUNTIME_OWNED_RE.findall(html))


def scan_text(html: str, common: set | None = None, stem: str = "") -> dict:
    markers = len(MARKER_RE.findall(html))
    r = {"markers": markers, "infra": bool(INFRA_RE.search(html)),
         "verdict": classify(markers), "en_by_design": bool(DISPOSITION_RE.search(html))}
    # UNRESOLVED-marker detection (2026-07-19): a `data-i="key"` whose key is NOT in WH_FIL_COMMON and
    # NOT in the page's WH_FIL_PAGE renders EN even in Filipino mode — a SILENTLY-BROKEN translation the
    # marker-count heuristic missed. Found on public-feed / plant-connections / ai-quality (each had 2).
    # A key resolves from ANY of the three live sources; the emitted file is the one added 2026-09-07.
    if common is not None and not OWN_ENGINE_RE.search(html):
        resolvable = common | page_dict_keys(html) | emitted_page_keys(stem)
        owned = runtime_owned_keys(html)
        used = set(DATA_I_KEY_RE.findall(html))
        r["unresolved"] = sorted(k for k in used if k not in resolvable and k not in owned)
        # Kept and reported separately: a deliberate absence is a decision to keep VISIBLE, not
        # to swallow. Only keys actually USED on the page count - a stale comment naming a key
        # nobody renders exempts nothing.
        r["runtime_owned"] = sorted(k for k in used if k in owned)
    return r


def main() -> int:
    pages = [p for p in sorted(REPO.glob("*.html")) if not any(x in p.name for x in EXCLUDE)]
    common = common_keys()
    rows, exempt, broken, owned = [], [], [], []
    for p in pages:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        r = scan_text(txt, common, stem=p.stem)
        if r.get("unresolved"):
            broken.append((p.name, r["unresolved"]))
        if r.get("runtime_owned"):
            owned.append((p.name, r["runtime_owned"]))
        # Exempt: internal/admin surfaces (by name) OR a formal doc that DECLARES EN-by-design inline.
        if p.name in INTERNAL_EXEMPT or r["en_by_design"]:
            r["exempt_reason"] = "internal" if p.name in INTERNAL_EXEMPT else "en-by-design"
            exempt.append((p.name, r))
        else:
            rows.append((p.name, r))
    userfacing = len(rows)
    covered = sum(1 for _, r in rows if r["verdict"] == "covered")
    partial = sum(1 for _, r in rows if r["verdict"] == "partial")
    thin = sum(1 for _, r in rows if r["verdict"] == "thin")
    none = sum(1 for _, r in rows if r["verdict"] == "none")
    adoption = round(100 * covered / userfacing) if userfacing else 0
    print("i18n coverage (P11 · EN/FIL adoption of the shared data-i/_t system)")
    print(f"  user-facing pages: {userfacing}  ·  covered: {covered}  partial: {partial}  "
          f"thin: {thin}  none: {none}  ·  adoption(covered/total): {adoption}%")
    gaps = [(n, r) for n, r in rows if r["verdict"] in ("thin", "none")]
    for n, r in sorted(gaps, key=lambda x: x[1]["markers"]):
        print(f"  ⚠ {n:<34} {r['markers']:>3} markers  ({r['verdict']}"
              f"{'' if r['infra'] else ', no i18n infra'})")
    if exempt:
        internal = [n for n, r in exempt if r.get("exempt_reason") == "internal"]
        endesign = [n for n, r in exempt if r.get("exempt_reason") == "en-by-design"]
        if internal:
            print(f"  exempt (internal/admin, EN-only by design): {', '.join(internal)}")
        if endesign:
            print(f"  exempt (formal doc, DECLARES EN-by-design body — not a gap): {', '.join(endesign)}")
    if gaps:
        print("  FIX (lever ladder P5): adopt the shared data-i/_t system on the gap pages — "
              "it's the SAME shared component, not per-page translation. ADVISORY, ratchets.")
    if owned:
        print(f"  runtime-owned (declared deliberately ABSENT, both languages written in code — "
              f"a dictionary entry here would be wrong):")
        for n, ks in sorted(owned):
            print(f"      {n}: {', '.join(ks)}")
    if broken:
        print(f"  ✗ BROKEN translations — {sum(len(k) for _, k in broken)} data-i marker(s) with NO "
              f"WH_FIL_COMMON/WH_FIL_PAGE entry (render EN in Filipino):")
        for n, ks in sorted(broken):
            print(f"      {n}: {', '.join(ks)}")
    return 0  # advisory


def selftest() -> int:
    fails = []
    covered = 'x' + (' data-i="k"' * 30) + '<script>WH_LANG;_t("y")</script>'
    if scan_text(covered)["verdict"] != "covered":
        fails.append("30 data-i + infra should be 'covered'")
    partial = ' data-i="a" data-i="b" _t("c") _t("d") _t("e") '
    if scan_text(partial)["verdict"] != "partial":
        fails.append(f"5 markers should be 'partial', got {scan_text(partial)['verdict']}")
    none = "<p>Plain page, no i18n at all.</p>"
    if scan_text(none)["verdict"] != "none":
        fails.append("0 markers should be 'none'")
    if scan_text(none)["infra"]:
        fails.append("a page with no infra should report infra=False")
    if scan_text(none)["en_by_design"]:
        fails.append("a plain page must NOT be flagged en-by-design")
    endesign = '<h1 translate="no">Report</h1><!-- the report BODY is EN-by-design (formal engineering document) -->'
    if not scan_text(endesign)["en_by_design"]:
        fails.append("an inline EN-by-design disposition must be detected")
    # unresolved-marker detection: `foo` is neither in COMMON({save}) nor the page dict({bar}) -> broken.
    unres = '<b data-i="save">S</b><b data-i="bar">B</b><b data-i="foo">F</b><script>WH_FIL_PAGE={bar:"x"}</script>'
    got = scan_text(unres, {"save"}).get("unresolved")
    if got != ["foo"]:
        fails.append(f"unresolved detection: expected ['foo'], got {got}")
    # THE EMITTED PER-PAGE DICTIONARY IS THE THIRD SOURCE (EX-TL 2026-09-07). A key that lives ONLY
    # there must resolve; missing it is what made this gate report 899 broken markers on 2026-09-10.
    # Asserted against a REAL emitted file so the test fails if the mechanism moves again.
    real = next(iter(sorted(PAGES_DIR.glob("*.fil.json"))), None)
    if real is None:
        fails.append("no i18n/pages/*.fil.json found — the emitted-dictionary source has moved")
    else:
        d = json.loads(real.read_text(encoding="utf-8"))
        k = next((x for x in d if x.startswith("p_")), None)
        if k is None:
            fails.append(f"{real.name} holds no p_ key to test the emitted-dictionary resolver with")
        else:
            html = f'<b data-i="{k}">X</b><b data-i="zzz_absent">Y</b>'
            got = scan_text(html, set(), stem=real.name[:-len(".fil.json")]).get("unresolved")
            if got != ["zzz_absent"]:
                fails.append(f"emitted-dictionary resolution: expected ['zzz_absent'], got {got}")
    # A key declared deliberately ABSENT is exempt; one merely mentioned is NOT. Without the
    # second half the phrase alone would become the exemption and any comment could grant it.
    owned_html = ('<b data-i="p_owned_1234">X</b><b data-i="p_plain_5678">Y</b>'
                  '<script>// p_owned_1234 is deliberately ABSENT: the runtime owns both sentences.</script>')
    got = scan_text(owned_html, set())
    if got.get("unresolved") != ["p_plain_5678"]:
        fails.append(f"runtime-owned exemption: expected only p_plain_5678 unresolved, got "
                     f"{got.get('unresolved')}")
    if got.get("runtime_owned") != ["p_owned_1234"]:
        fails.append(f"runtime-owned should be reported separately, got {got.get('runtime_owned')}")
    no_reason = ('<b data-i="p_owned_1234">X</b>'
                 '<script>// p_owned_1234 is deliberately ABSENT</script>')
    if scan_text(no_reason, set()).get("unresolved") != ["p_owned_1234"]:
        fails.append("an absence with NO reason (no colon) must stay BROKEN")
    # The real page this was written for must resolve through the exemption, not through luck.
    try:
        real_html = (REPO / "assistant.html").read_text(encoding="utf-8", errors="ignore")
        if "p_livehivedatabasedonyourlogbo_6885" not in runtime_owned_keys(real_html):
            fails.append("assistant.html's deliberately-absent grounding key is no longer "
                         "recognised — the comment or the convention moved")
    except Exception as e:
        fails.append(f"could not read assistant.html for the real-page assertion: {e}")
    if fails:
        print("✗ validate_i18n_coverage selftest FAILED:")
        for f in fails:
            print("   - " + f)
        return 1
    print("✓ validate_i18n_coverage selftest passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else main())
