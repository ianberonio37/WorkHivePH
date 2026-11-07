#!/usr/bin/env python3
"""bank_cf_rows.py - close a CF row (what the critic deepwalk FOUND) on the critic's own measurement (Wave CF, 2026-11-07).

A CF row is one distinct defect: (page, persona, rubric dimension). It closes - status locking, pct 60 - only when the
defect is gone for THAT person on THAT page at BOTH a phone width and a desktop width, read by survey_ufai_rubric.js
AFTER the row's find. The evidence, all measured, none typed:

  * signed-out (persona anon) - the closer's merged signed-out sweep state (tools/close_critic_findings.anon_page_state,
    fed by tools/family_rubric_sweep.mjs --anon --page ...), which grades every dimension at 1280 AND 390 and keeps the
    worse of the two: one sweep newer than the find, without the dimension failing, covers both widths;
  * signed-in - critic batch surveys that record who was walked (`_cast`: persona, device, ids, at), in .tmp/batchsurvey
    and .tmp/cf_ev/** (tools/critic_walk_batch.mjs --ids <id> --device desktop-1280 --outdir .tmp/cf_ev/desktop), and the
    critic bank's own later rows for the same persona whose walk graded the dimension on the page and found nothing.

A row clean at one width only moves to walked (25) and says which width is owed. When every in-scope finding of a critic
row is carried by a CF row at locking (descoped N1 aside), that critic row moves to improving with the CF ids as its refs:
the trajectory roadmap now closes the critic backlog.

    python tools/bank_cf_rows.py            # dry: what would close, what is owed
    python tools/bank_cf_rows.py --apply    # write the trajectory rows and the critic rows they carry
    python tools/bank_cf_rows.py --check    # gate cf-rows-hold: a newer survey that finds a closed defect again is RED
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import registry_io as _rio  # noqa: E402
import close_critic_findings as _ccf  # noqa: E402
from critic_findings_census import page_file, DIM_RE  # noqa: E402

SURVEY_GLOBS = [".tmp/batchsurvey/*.json", ".tmp/cf_ev/**/*.json"]
FAIL_RE = re.compile(r"^([A-Z]{1,3}\d{1,2})\b")
NOTE_DEV = re.compile(r" at (\S+) in [a-z]{2}\b")
PHONE_MAX, DESKTOP_MIN = 430, 1024


def _epoch(t: str) -> float:
    if not t:
        return 0.0
    try:
        return datetime.fromisoformat(t if "T" in t else t + "T23:59:59").timestamp()
    except ValueError:
        return 0.0


def _width_of_device(dev: str) -> int:
    m = re.search(r"(\d{3,4})", dev or "")
    return int(m.group(1)) if m else 390      # 'any' walks at phone-390 (critic_walk_batch VIEW default)


def surveys() -> list:
    """Every batch survey that says who was walked: page, persona, width, time, failing dims, lens, file."""
    out = []
    for g in SURVEY_GLOBS:
        for f in glob.glob(str(ROOT / g), recursive=True):
            try:
                s = json.loads(Path(f).read_text(encoding="utf-8"))
            except Exception:
                continue
            cast = s.get("_cast") or {}
            if not cast.get("persona") or s.get("_denied"):
                continue
            vp = (s.get("viewport") or {}).get("w") or _width_of_device(cast.get("device", ""))
            out.append({"page": page_file(s.get("pageId") or ""), "persona": cast["persona"], "width": int(vp),
                        "t": _epoch(cast.get("at") or "") or os.path.getmtime(f), "lens": s.get("lens") or s.get("_lens"),
                        "failing": {m.group(1) for x in (s.get("failing") or []) for m in [FAIL_RE.match(str(x))] if m},
                        "graded": {d.get("dim") for d in (s.get("dims") or []) if isinstance(d, dict) and d.get("pct") is not None},
                        "src": os.path.relpath(f, ROOT).replace("\\", "/")})
    return out


def bank_evidence(critic_rows: list) -> list:
    """The critic bank's own later rows as evidence: persona, the page on its path, graded dims, findings per page."""
    out = []
    for r in critic_rows:
        if r.get("status") not in ("critiqued", "improving") or not r.get("banked_at"):
            continue
        cell = (r.get("cell") or "").split("|")
        persona = cell[1] if len(cell) > 1 else ""
        m = NOTE_DEV.search(r.get("clean_note") or r.get("note") or "")
        width = _width_of_device(m.group(1)) if m else int(r.get("walk_viewport_px") or 390)
        bad = {}
        for f in r.get("findings") or []:
            mm = DIM_RE.match(str(f.get("evidence") or ""))
            if mm:
                bad.setdefault(page_file(mm["page"]), set()).add(mm["dim"])
        for p in r.get("pages") or []:
            out.append({"page": p, "persona": persona, "width": width, "t": _epoch(r["banked_at"]), "lens": r.get("lens_sha"),
                        "failing": bad.get(p, set()), "graded": set(r.get("dims_graded") or []), "src": f"critic row {r['id']}"})
    return out


def verdict(cf: dict, ev: list, anon_state: dict) -> tuple:
    """(status, pct, basis-evidence text, phone_src, desktop_src) for one CF row."""
    page, persona, dim, found = cf["page"], cf["persona"], cf["dim"], _epoch(cf.get("found_at") or "")
    if persona == "anon":
        pg, st = _ccf._state_for(page, anon_state)
        if st is None:
            return None, None, "no signed-out sweep of the page yet - run family_rubric_sweep.mjs --anon --page " + page, None, None
        if float(st.get("time") or 0) <= found:
            return None, None, "the newest signed-out sweep predates the find - re-sweep the page", None, None
        if dim in (st.get("failing_dims") or set()):
            return None, None, f"the newest signed-out sweep still fails {dim}", None, None
        when = datetime.fromtimestamp(float(st["time"])).isoformat(timespec="minutes")
        src = f"tools/family_rubric_sweep.mjs --anon ({pg}, {when}, graded at 1280 and 390, the worse kept)"
        return "locking", 60, src, src, src
    mine = [e for e in ev if e["page"] == page and e["persona"] == persona and e["t"] > found
            and (dim == "SCREEN" or dim in e["graded"])]
    if not mine:
        return None, None, f"no walk of {page} as {persona} after the find has graded {dim} yet", None, None
    newest = max(mine, key=lambda e: e["t"])
    if dim != "SCREEN" and dim in newest["failing"]:
        return None, None, f"the newest walk ({newest['src']}) still fails {dim}", None, None
    clean = [e for e in mine if dim == "SCREEN" or dim not in e["failing"]]
    phone = max((e for e in clean if e["width"] <= PHONE_MAX), key=lambda e: e["t"], default=None)
    desk = max((e for e in clean if e["width"] >= DESKTOP_MIN), key=lambda e: e["t"], default=None)
    fmt = lambda e: f"{e['src']} @{e['width']}px {datetime.fromtimestamp(e['t']).isoformat(timespec='minutes')}"  # noqa: E731
    if phone and desk:
        return "locking", 60, f"phone {fmt(phone)}; desktop {fmt(desk)}", fmt(phone), fmt(desk)
    have = phone or desk
    owed = "desktop-1280" if phone else "phone-390"
    return "walked", 25, f"clean at {fmt(have)}; {owed} owed (critic_walk_batch.mjs --ids {cf['critic_ids'][0] if cf.get('critic_ids') else '?'} --device {owed} --outdir .tmp/cf_ev/{owed.split('-')[0]})", \
        (fmt(phone) if phone else None), (fmt(desk) if desk else None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    doc = _rio.load_doc()
    critic = _rio.load_critic()
    cf_rows = [t for t in doc["trajectories"] if (t.get("cf") or {}).get("kind") == "critic-finding"]
    ev = surveys() + bank_evidence(critic["rows"])
    anon_state = _ccf.anon_page_state()

    if a.check:
        red = []
        for t in cf_rows:
            if t.get("status") not in ("locking", "locked"):
                continue
            cf = t["cf"]
            banked = _epoch(cf.get("closed_at") or "")
            if cf["persona"] == "anon":
                _pg, st = _ccf._state_for(cf["page"], anon_state)
                if st and float(st.get("time") or 0) > banked and cf["dim"] in (st.get("failing_dims") or set()):
                    red.append(f"{t['id']} {cf['page']} {cf['dim']}: a newer signed-out sweep fails it again")
                continue
            newer = [e for e in ev if e["page"] == cf["page"] and e["persona"] == cf["persona"] and e["t"] > banked
                     and cf["dim"] in e["failing"]]
            if newer:
                red.append(f"{t['id']} {cf['page']} {cf['dim']} as {cf['persona']}: {newer[0]['src']} fails it again")
        closed = sum(1 for t in cf_rows if t.get("status") in ("locking", "locked"))
        if red:
            print(f"FAIL cf-rows-hold - {len(red)} closed critic find(s) found again: " + " | ".join(red[:8]))
            return 1
        print(f"PASS cf-rows-hold - {closed} of {len(cf_rows)} CF rows closed on the critic's measurement; none found again")
        return 0

    moved, owed = [], {}
    by_id = {t["id"]: t for t in cf_rows}
    for t in cf_rows:
        if t.get("status") in ("locking", "locked", "descoped"):
            continue
        st, pct, text, _p, _d = verdict(t["cf"], ev, anon_state)
        if not st:
            owed[text.split(" - ")[0][:70]] = owed.get(text.split(" - ")[0][:70], 0) + 1
            continue
        if st == t.get("status"):
            continue
        cf = t["cf"]
        basis = (f"[{date.today().isoformat()}] {st.upper()} pct -> {pct}. WALKED LIVE (Playwright headless, the critic deepwalk "
                 f"survey_ufai_rubric.js): {cf['dim']} ({cf['dim_name']}) on {cf['page']} as {cf['persona']} after the find of "
                 f"{(cf.get('found_at') or '')[:16]} ({str(cf.get('evidence'))[:120]}) - {text}. Gate cf-rows-hold.")
        moved.append((t, st, pct, basis))
    print(f"CF rows: {len(cf_rows)} · would move {len(moved)} "
          f"(locking {sum(1 for m in moved if m[1] == 'locking')}, walked {sum(1 for m in moved if m[1] == 'walked')})")
    for k, v in sorted(owed.items(), key=lambda x: -x[1])[:8]:
        print(f"  open {v:4} - {k}")
    if not a.apply:
        for t, st, _p, basis in moved[:6]:
            print(f"  {t['id']:<6} -> {st}: {basis[:200]}")
        print("  (dry - nothing written)")
        return 0
    now = datetime.now().isoformat(timespec="minutes")
    for t, st, pct, basis in moved:
        t["status"], t["pct"] = st, pct
        t["basis"] = ((t.get("basis") or "") + " || " if t.get("basis") else "") + basis
        if st == "locking":
            t["cf"]["closed_at"] = now
            arts = t.setdefault("artifacts", {})
            arts["gates"] = sorted(set(arts.get("gates") or []) | {"cf-rows-hold"})
    _rio.save_doc(doc)
    # the critic rows a CF row carries close with it: every in-scope finding carried by a CF row at locking -> improving
    locked_cells = {(t["cf"]["page"], t["cf"]["persona"], t["cf"]["dim"]): t["id"] for t in cf_rows if t.get("status") in ("locking", "locked")}
    descoped = set(getattr(_ccf, "DESCOPED_DIMS", {}) or {})
    improved = 0
    for r in critic["rows"]:
        if r.get("status") != "critiqued" or not r.get("findings") or r.get("improvement_refs"):
            continue
        cell = (r.get("cell") or "").split("|")
        persona = cell[1] if len(cell) > 1 else "any"
        refs, all_ok = set(), True
        for f in r["findings"]:
            m = DIM_RE.match(str(f.get("evidence") or ""))
            if not m:
                all_ok = False
                break
            if m["dim"] in descoped:
                continue
            cid = locked_cells.get((page_file(m["page"]), persona, m["dim"]))
            if not cid:
                all_ok = False
                break
            refs.add(cid)
        if all_ok and refs:
            r["status"] = "improving"
            r["improvement_refs"] = [f"{c} (Wave CF: the defect re-graded clean at phone and desktop, gate cf-rows-hold, "
                                     f"{date.today().isoformat()})" for c in sorted(refs, key=lambda x: int(x[2:]))]
            improved += 1
    if improved:
        with io.open(_rio.CRITIC_MAIN, encoding="utf-8") as fh:
            fh.readline()
            second = fh.readline()
        indent = max(1, len(second) - len(second.lstrip(" "))) if second.strip() else 1
        _rio.save_critic(critic, indent=indent)
    print(f"  wrote {len(moved)} CF row(s); {improved} critic row(s) -> improving, carried by their CF rows")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
