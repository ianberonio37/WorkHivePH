"""
AV-Adoption Ratchet (L0) — FULLSTACK_COMPONENT_LIBRARY_ROADMAP Layer AV.
================================================================================
TWO floors, split on 2026-09-30 (LXP-AU x assistive-tech walk):

  AV1  the offline CHROME set — offline-banner / offline-queue / connectivity-widget /
       device-fingerprint — ships as ONE unit on every non-exempt family page. A page
       carrying SOME of them, or NONE of them, fails.
  AV2  session-hygiene floor — session-timeout.js (15-min soft prompt + 60-min HARD
       identity clear) on every family page whose own CODE shows an identity or
       tenant-row signal. Derived per page, so it needs no exempt list.

★WHY THE SPLIT. AV1 used to ship all FIVE scripts as one all-or-nothing unit, so a single
per-page ruling covered both the visible chrome and the security floor. The registry
exempted three founder surfaces as "chrome-less by design" — sound for the four that ARE
chrome, wrong for session-timeout.js, which paints nothing until a session actually ends.
agentic-rag-observability.html is the proof case: exempt from all five while reading
whWorker() / wh_last_worker and querying .from('agentic_rag_traces') behind a hive gate, so
a founder idling on a shared plant tablet was never prompted and never hard-cleared, and for
someone who cannot see the screen there was no overlay to announce. Splitting AV2 out means
"this surface has no chrome" no longer says "this surface needs no session hygiene".

★THE BLIND SPOT THIS ALSO FIXES. The previous version classified pages with
`elif have:` — so a page carrying NONE of the set was neither an adopter nor a partial and
raised NOTHING, while the docstring claimed it "fails any page dropping ANY of the five".
Six family pages sat in exactly that hole and the gate reported PASS beside
`adopters: 33, need: 39`. A page dropping the WHOLE unit is now the loudest failure, not the
silent one; the six were genuinely chrome-less and are now EXPLICITLY exempt in
av_component_registry.json rather than invisibly absent.

Floors are forward-only and auto-tighten. Output: av_adoption_gate_report.json.
Exit 1 on a drop, else 0.
"""
from __future__ import annotations

import datetime
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
CHROME = ["offline-banner.js", "offline-queue.js", "connectivity-widget.js", "device-fingerprint.js"]
HYGIENE = "session-timeout.js"
BASELINE = ROOT / "av_adoption_baseline.json"
REPORT = ROOT / "av_adoption_gate_report.json"

# A page that can hold or act on a signed-in identity. Matched against source with comments
# REMOVED: a comment naming wh_last_worker is prose about the key, not a read of it, and this
# file's own fix comments name it three times. Quoting a comment is not reading the code.
IDENTITY_SIGNALS = [
    r"wh_last_worker",
    r"whWorker\s*\(",
    r"wh_hive_id",
    r"wh_hive_role",
    r"\.from\(\s*['\"]",
]


def _tag(filename: str) -> re.Pattern:
    """A real <script src="...<filename>"> TAG, not the bare filename.

    ★TWO REASONS, BOTH LEARNED THE HARD WAY ON 2026-09-30.
    (1) A substring test passes on PROSE. The fix comments this very walk added to three pages name
        session-timeout.js in explanatory text, so `"session-timeout.js" in src` would have let a page
        satisfy a security floor with a comment about the security floor. Measured: all 35 need-set pages
        carry a real tag today, so the hole is not yet exploited - which is exactly when to close it.
    (2) The first version of this gate stripped comments before matching, to stop a comment naming
        wh_last_worker from counting as a read. `re.sub(r"<!--.*?-->", " ", src, flags=re.S)` then ate
        real markup: a stray "<!--" inside a JS string made the non-greedy match run to the next "-->"
        and swallow whatever lay between, which is how it reported that inventory.html and logbook.html
        load no utils.js when both plainly do (inventory:649, logbook:1557). So: no comment stripping.
        Identity SIGNALS are matched on raw source, where a false positive only over-demands a guard on
        a page that merely discusses identity - the safe direction - and PRESENCE is matched on the tag,
        where prose cannot reach.
    """
    return re.compile(r"""<script[^>]*\bsrc\s*=\s*['"][^'"]*""" + re.escape(filename) + r"""[^'"]*['"]""",
                      re.I)


CHROME_TAGS = {s: _tag(s) for s in CHROME}
HYGIENE_TAG = _tag(HYGIENE)


def main() -> int:
    reg = json.loads((ROOT / "av_component_registry.json").read_text(encoding="utf-8"))
    comps = {c["id"]: c for c in reg["components"]}
    exempt = set(comps["AV1"].get("exempt", []))
    hyg_exempt = set(comps.get("AV2", {}).get("exempt", []))

    fam = json.loads((ROOT / "family_rubric_baseline.json").read_text(encoding="utf-8"))
    all_pages = sorted(set(fam["pages"].keys() if isinstance(fam["pages"], dict) else fam["pages"]))
    pages = sorted(set(all_pages) - exempt)

    failures = []

    # ── AV1: the offline chrome set, as one unit ────────────────────────────────────────────
    adopters, partial, dropped = [], {}, {}
    for p in pages:
        f = ROOT / p
        if not f.exists():
            continue
        src = f.read_text(encoding="utf-8", errors="ignore")
        have = [x for x in CHROME if CHROME_TAGS[x].search(src)]
        if len(have) == len(CHROME):
            adopters.append(p)
        elif have:
            partial[p] = sorted(set(CHROME) - set(have))
        else:
            # Previously invisible: `elif have:` was false here, so the page raised nothing at all.
            dropped[p] = sorted(CHROME)

    for p, missing in partial.items():
        failures.append(f"AV1 {p} PARTIAL set — missing: {', '.join(missing)} (the set ships as one unit)")
    for p in dropped:
        failures.append(
            f"AV1 {p} carries NONE of the offline chrome set — either adopt all {len(CHROME)}, or add it to "
            f"av_component_registry AV1.exempt with a reason (this case used to pass silently)")

    # ── AV2: session hygiene, keyed to each page's own identity signals ─────────────────────
    # A script only ONE family page loads is that page's own code split into a file, so its identity reads are the
    # page's: OPC (1d6ecd88) moved founder-console's queue reads into operator-actions.js, and the console - which
    # still loads session-timeout.js - left the need-set and read as a lost adopter (2026-10-23).
    loaders: dict[str, list[str]] = {}
    for p in all_pages:
        if (ROOT / p).exists():
            for js in re.findall(r'<script[^>]*\bsrc="([\w.-]+\.js)"', (ROOT / p).read_text(encoding="utf-8", errors="ignore")):
                loaders.setdefault(js, []).append(p)
    owned = {by[0]: [] for by in loaders.values() if len(by) == 1}
    for js, by in loaders.items():
        if len(by) == 1 and (ROOT / js).exists():
            owned[by[0]].append((ROOT / js).read_text(encoding="utf-8", errors="ignore"))
    hyg_need, hyg_have, hyg_missing = [], [], []
    for p in all_pages:
        f = ROOT / p
        if not f.exists() or p in hyg_exempt:
            continue
        raw = f.read_text(encoding="utf-8", errors="ignore")
        code = "\n".join([raw] + owned.get(p, []))
        if not any(re.search(sig, code) for sig in IDENTITY_SIGNALS):
            continue  # no identity and no tenant read: not in the need-set
        hyg_need.append(p)
        (hyg_have if HYGIENE_TAG.search(raw) else hyg_missing).append(p)

    for p in hyg_missing:
        failures.append(
            f"AV2 {p} reads an identity or tenant row but does not load {HYGIENE} — no 15-min prompt and no "
            f"60-min hard identity clear, so a shared tablet keeps the session and nothing announces it")

    # ── forward-only floors ────────────────────────────────────────────────────────────────
    floors = {}
    if BASELINE.exists():
        try:
            floors = json.loads(BASELINE.read_text(encoding="utf-8")).get("floors", {})
        except Exception:
            floors = {}
    f_av1, f_av2 = floors.get("AV1", 0), floors.get("AV2", 0)
    # A page deleted from the platform is not a page that stopped adopting (component-adoption's rule, 1b382d9e):
    # when the whole shortfall is adopters gone from disk, the floor follows them down by exactly that many.
    try:
        base_rows = {r["id"]: r for r in json.loads(BASELINE.read_text(encoding="utf-8")).get("rows", [])}
    except Exception:
        base_rows = {}
    rebased = []
    for cid, have_n, floor in (("AV1", len(adopters), f_av1), ("AV2", len(hyg_have), f_av2)):
        gone = [p for p in base_rows.get(cid, {}).get("adopters", []) if not (ROOT / p).exists()]
        if have_n < floor and gone and have_n >= floor - len(gone):
            rebased.append(f"{cid} {floor} -> {have_n} (adopter page(s) deleted: {', '.join(gone)})")
            if cid == "AV1": f_av1 = have_n
            else: f_av2 = have_n
    for r in rebased:
        print(f"  REBASED {r}")
    if len(adopters) < f_av1:
        failures.append(f"AV1 adoption fell {f_av1} -> {len(adopters)}")
    if len(hyg_have) < f_av2:
        failures.append(f"AV2 session-hygiene adoption fell {f_av2} -> {len(hyg_have)}")

    ok = not failures
    if ok:
        BASELINE.write_text(json.dumps({
            "_doc": "Layer AV adoption baselines. Floors forward-only. AV1 = offline chrome set; "
                    "AV2 = session-timeout.js hygiene floor (split 2026-09-30).",
            "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "rows": [
                {"id": "AV1", "mode": "measured", "adopters_n": len(adopters), "need_n": len(pages),
                 "pct": round(100 * len(adopters) / len(pages)) if pages else None,
                 "adopters": adopters, "gap": sorted(set(pages) - set(adopters))},
                {"id": "AV2", "mode": "measured", "adopters_n": len(hyg_have), "need_n": len(hyg_need),
                 "pct": round(100 * len(hyg_have) / len(hyg_need)) if hyg_need else None,
                 "adopters": hyg_have, "gap": hyg_missing},
            ],
            "floors": {"AV1": max(len(adopters), f_av1), "AV2": max(len(hyg_have), f_av2)},
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    REPORT.write_text(json.dumps({
        "ok": ok,
        "av1": {"adopters": len(adopters), "need": len(pages), "partial": sorted(partial), "dropped": sorted(dropped)},
        "av2": {"adopters": len(hyg_have), "need": len(hyg_need), "missing": hyg_missing},
        "adopters": len(adopters), "need": len(pages),  # kept: existing readers key off these
        "failures": failures,
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"av-adoption AV1 (offline chrome set): {len(adopters)}/{len(pages)} adopters (floor {f_av1})")
    print(f"av-adoption AV2 (session hygiene):    {len(hyg_have)}/{len(hyg_need)} adopters (floor {f_av2})")
    for f in failures:
        print(f"  FAIL {f}")
    print("  " + ("PASS (both forward-only floors held)" if ok else f"{len(failures)} FAILURE(S)"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
