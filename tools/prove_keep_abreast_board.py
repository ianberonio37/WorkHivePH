"""prove_keep_abreast_board.py - KA-B: does each keep-abreast instrument tell the truth about itself? (2026-10-30)

KA-B's thirteen rows ask one thing of thirteen instruments: the scoreboard's [IAN] components, the scoreboard itself, the
trip and the sitemap's promise each READ a live measure or say they cannot - never a typed 0/1, never a page that says one
thing while production serves another. A gate that re-reads its own source cannot answer that; an independent reading of
the same thing can. So for every row this takes the instrument's OWN answer and a SECOND, independent live reading, and
the row passes only when the two agree:

  KA354  robots.txt vs the roster   the trip's roster check, re-run against the robots.txt PRODUCTION serves
  KA355  the scoreboard on the board seo_scoreboard.py run now: it regenerates, and its production HEAD probes answered
  KA356  AIO entity resolvable       the component shares the sameAs read; the deployed index.html's Organization agrees
  KA357  GSC + Bing reporting        the component's "credential / report" against the deployed origin's verification
                                     tokens and the .env key NAMES (never a value)
  KA358  deployed to production      the component's HEAD codes against an independent HEAD of the same three URLs
  KA359  entity resolvable (sameAs)  the deployed index.html's sameAs, read from production, against the component's
  KA360  live SOV baseline           the component's reason against the file it names (present? scored when?)
  KA361  off-site channels           the component's channels against the deployed index.html a crawler receives
  KA362  listicle inclusion          the component's count against the record it names
  KA363  the sitemap's promise       production's sitemap.xml: each <lastmod> against the dateModified PRODUCTION serves
  KA364  the trip in the nightly CI  the exact command CI runs (freshness_trip.py --ci): red exactly when a trip is past grace
  KA365  the trip on the board       freshness_trip.py run now rewrites seo_trip_report.json
  KA366  the trip on the header      the roadmap's KEEP ABREAST line is the one the generator prints from that report

  python tools/prove_keep_abreast_board.py      -> keep_abreast_board_report.json; exit 1 on any row that disagrees
  python tools/prove_keep_abreast_board.py --teeth   the independent readings are planted to contradict five instruments
                                                (a missing roster agent, a 404, a profile URL, a channel, a stale header);
                                                exit 0 only if all five rows FAIL
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
PROD = "https://workhiveph.com"
TEETH = "--teeth" in sys.argv
OUT = ROOT / ("keep_abreast_board_teeth.json" if TEETH else "keep_abreast_board_report.json")
PLANTED = ("KA354", "KA358", "KA359", "KA361", "KA366")
UA = "WorkHive-KeepAbreast-Prover/1.0"


def _get(url: str, timeout: float = 20.0) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read().decode("utf-8", errors="replace")
    except Exception as e:   # noqa: BLE001 - the status IS the reading
        return getattr(e, "code", 0) or 0, ""


def _head(url: str) -> int:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.getcode()
    except Exception as e:   # noqa: BLE001
        return getattr(e, "code", 0) or 0


def _same_as(html: str) -> list[str]:
    urls = []
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>([\s\S]*?)</script>', html):
        try:
            data = json.loads(block)
        except Exception:
            continue
        nodes = data.get("@graph", [data]) if isinstance(data, dict) else data
        for n in nodes if isinstance(nodes, list) else []:
            if isinstance(n, dict) and n.get("@type") == "Organization":
                urls += [u for u in (n.get("sameAs") or []) if isinstance(u, str)]
    return urls


def _run(*cmd: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, *cmd], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    import freshness_trip as ft
    import seo_scoreboard as sb
    rows: dict[str, dict] = {}

    def put(rid: str, ok: bool, own: str, independent: str) -> None:
        rows[rid] = {"ok": bool(ok), "instrument_says": own, "independent_reading": independent}
        print(f"{'PASS' if ok else 'FAIL'} {rid}: {independent[:150]}")

    # the scoreboard, run NOW (KA355): it rewrites seo_scoreboard.json and its HEAD probes go to production
    t0 = datetime.now(timezone.utc)
    rc, out = _run("tools/seo_scoreboard.py")
    board = json.load(io.open(ROOT / "seo_scoreboard.json", encoding="utf-8"))
    gen = datetime.fromisoformat(board["generated_at"].replace("Z", "+00:00"))
    reasons = board.get("reasons") or {}
    put("KA355", rc == 0 and gen >= t0.replace(microsecond=0),
        f"generated_at {board['generated_at']}",
        f"python tools/seo_scoreboard.py ran at {t0.isoformat(timespec='seconds')} and rewrote seo_scoreboard.json "
        f"(generated_at {board['generated_at']}); its production read: {reasons.get('deployed to production', '?')}")

    # KA354: the roster against the robots.txt production serves
    code, prod_robots = _get(f"{PROD}/robots.txt")
    have = set(re.findall(r"User-agent:\s*(\S+)", prod_robots))
    local_robots = (ROOT / "robots.txt").read_text(encoding="utf-8", errors="replace")
    import glob
    from collections import Counter
    named: Counter = Counter()
    for p in glob.glob(str(ft.EXTERNAL / "*.md")):
        if ft.ROSTER_CHUNK.search(Path(p).stem):
            for tok in ft.UA_TOKEN.findall(Path(p).read_text(encoding="utf-8", errors="replace")):
                if tok not in ft.UA_NOISE and len(tok) > 3:
                    named[tok] += 1
    roster = sorted(t for t, n in named.items() if n >= 2)
    if TEETH:
        roster = roster + ["PlantedAgentBot", "PlantedAgentBot"][:1]
    missing = [t for t in roster if t not in have and t.lower() not in {h.lower() for h in have}]
    own_trips = ft.roster_trips()
    put("KA354", code == 200 and not missing and not own_trips,
        f"freshness_trip.roster_trips(): {len(own_trips)} trips",
        f"GET {PROD}/robots.txt -> {code}, {len(have)} User-agent lines; the harvested roster names {len(roster)} AI agents "
        f"(>=2 mentions) and {len(missing)} lack a line on production{(': ' + ', '.join(missing[:6])) if missing else ''}; "
        f"production robots.txt {'equals' if prod_robots.strip() == local_robots.strip() else 'DIFFERS from'} the repo's")

    # KA358: the three production URLs, HEAD-probed independently
    key = sb._indexnow_key()
    urls = [f"{PROD}/sitemap.xml", f"{PROD}/robots.txt"] + ([f"{PROD}/{key}.txt"] if key else [])
    mine = {u.rsplit('/', 1)[-1]: _head(u) for u in urls}
    if TEETH:
        mine["sitemap.xml"] = 404
    own = reasons.get("deployed to production", "")
    agree = all(f"{k} {c}" in own for k, c in mine.items())
    put("KA358", agree and all(c == 200 for c in mine.values()), own,
        "independent HEAD of the deployed origin: " + ", ".join(f"{k} {c}" for k, c in mine.items())
        + (" - the component reads the same codes" if agree else " - the component's codes DIFFER"))

    # KA359 + KA356: the Organization's sameAs as production serves index.html
    code, prod_index = _get(f"{PROD}/")
    prod_sa = _same_as(prod_index) + (["https://www.linkedin.com/company/planted"] if TEETH else [])
    local_sa = _same_as((ROOT / "index.html").read_text(encoding="utf-8", errors="replace"))
    own_sa = reasons.get("entity resolvable (sameAs)", "")
    claims_none = "sameAs: []" in own_sa
    agree = code == 200 and prod_sa == local_sa and (claims_none == (not prod_sa))
    reading = (f"GET {PROD}/ -> {code}: the deployed Organization declares sameAs {json.dumps(prod_sa)}, the repo's "
               f"{json.dumps(local_sa)}")
    put("KA359", agree, own_sa, reading + (" - the component says exactly that" if agree else " - the component disagrees"))
    # the AIO component has no reason of its own - it IS the GEO read, scaled to the pillars: n/n when sameAs resolves, 0/n
    # when it does not. Its achieved count must follow production's sameAs, never a second typed flag.
    aio = next((c for c in (board.get("components") or {}).get("AIO", []) if c[0] == "entity resolvable"), None)
    geo = next((c for c in (board.get("components") or {}).get("GEO", []) if c[0].startswith("entity resolvable")), None)
    follows = bool(aio and geo) and (aio[1] == (aio[2] if geo[1] else 0))
    put("KA356", agree and follows and bool(prod_sa) == bool(aio and aio[1]),
        f"AIO entity resolvable {aio[1] if aio else '?'}/{aio[2] if aio else '?'} beside GEO {geo[1] if geo else '?'}/{geo[2] if geo else '?'}",
        reading + f" - the AIO component scores {aio[1] if aio else '?'}/{aio[2] if aio else '?'}, the GEO sameAs read scaled to "
        f"the pillars, not a second typed flag")

    # KA357: what Google and Bing would verify by, on the deployed origin, against the component's credential claim
    g_meta = re.search(r'<meta[^>]+name=["\']google-site-verification["\'][^>]*>', prod_index or "", re.I)
    bing_xml = _head(f"{PROD}/BingSiteAuth.xml")
    own_gsc = reasons.get("GSC + Bing reporting", "")
    env_names = sb._env_keys()
    creds = {k: (k in env_names) for k in ("GSC_SERVICE_ACCOUNT_JSON", "GOOGLE_SEARCH_CONSOLE_KEY", "GSC_CREDENTIALS",
                                            "BING_WEBMASTER_API_KEY", "BING_WEBMASTER_KEY")}
    gsc_present = any(v for k, v in creds.items() if k.startswith("G"))
    bing_present = any(v for k, v in creds.items() if k.startswith("BING"))
    agree = (("Search Console: credential present" in own_gsc) == gsc_present) and (("Bing Webmaster: credential present" in own_gsc) == bing_present)
    put("KA357", agree, own_gsc,
        f"the deployed origin carries {'a' if g_meta else 'no'} google-site-verification meta and BingSiteAuth.xml answers "
        f"{bing_xml}; .env holds {'a' if gsc_present else 'no'} Search Console key and {'a' if bing_present else 'no'} Bing key "
        f"(names read, never values) - the component's credential claim {'matches' if agree else 'DOES NOT match'}")

    # KA360: the SOV baseline the component names
    f = ROOT / "geo_sov_baseline.json"
    own_sov = reasons.get("live SOV baseline run", "")
    if not f.exists():
        indep, agree = "geo_sov_baseline.json is not on disk", "never run" in own_sov
    else:
        d = json.loads(f.read_text(encoding="utf-8") or "{}")
        at = d.get("scored_at") or d.get("scored") or d.get("generated_at")
        indep, agree = f"geo_sov_baseline.json scored {at or 'never'}", (str(at)[:10] in own_sov) if at else ("never been scored" in own_sov)
    put("KA360", agree, own_sov, indep + (" - the component says so" if agree else " - the component says otherwise"))

    # KA361: the off-site channels in what a crawler receives from production
    have_ch = [n for n, rx in sb.OFFSITE.items() if re.search(rx, (prod_index or "") + (" https://www.reddit.com/r/planted" if TEETH else ""))]
    own_off = reasons.get("off-site channels active", "")
    agree = all((n in own_off.split("missing:")[0]) == (n in have_ch) for n in sb.OFFSITE) if "missing:" in own_off else False
    put("KA361", agree, own_off,
        f"the deployed index.html links {', '.join(have_ch) or 'none'} of Reddit, YouTube, G2"
        + (" - the component reads the same" if agree else " - the component disagrees"))

    # KA362: the inclusion record the component names
    rec = sb._rep("listicle_inclusions.json")
    urls_rec = [u for u in (rec.get("inclusions") or []) if isinstance(u, str) and u.startswith("http")]
    own_l = reasons.get("third-party listicle inclusion", "")
    agree = (f"{len(urls_rec)} recorded" in own_l) if urls_rec else ("none recorded" in own_l)
    put("KA362", agree, own_l, f"listicle_inclusions.json holds {len(urls_rec)} inclusion URL(s)"
        + (" - the component says so" if agree else " - the component says otherwise"))

    # KA363: production's sitemap against the dateModified production serves for each page
    from refresh_public_page import sitemap_entries
    import content_freshness_gate as cfg
    code, prod_map = _get(f"{PROD}/sitemap.xml")
    entries = sitemap_entries(prod_map) if code == 200 else []
    bad, checked = [], 0
    for e in entries:
        c, html = _get(e["loc"])
        if c != 200:
            bad.append(f"{e['loc']} -> {c}")
            continue
        dm = cfg._date_of(html)
        checked += 1
        if dm and e["lastmod"] and dm.isoformat() != e["lastmod"]:
            bad.append(f"{e['loc']}: <lastmod> {e['lastmod']}, the page serves dateModified {dm}")
        time.sleep(0.15)
    lrc, lout = _run("tools/validate_sitemap_promise.py")
    put("KA363", code == 200 and entries and not bad and lrc == 0,
        (lout.strip().splitlines() or ['?'])[-1][:200],
        f"GET {PROD}/sitemap.xml -> {code}, {len(entries)} URLs; fetched each from production: {checked} answered 200 and "
        f"{len(bad)} disagree with their <lastmod>{(' (' + '; '.join(bad[:3]) + ')') if bad else ''}")

    # KA365 + KA364: the trip, run now, and the exact command CI runs
    before = (ROOT / "seo_trip_report.json").stat().st_mtime if (ROOT / "seo_trip_report.json").exists() else 0
    trc, tout = _run("tools/freshness_trip.py")
    rep = json.load(io.open(ROOT / "seo_trip_report.json", encoding="utf-8"))
    after = (ROOT / "seo_trip_report.json").stat().st_mtime
    put("KA365", trc in (0, 1) and after > before, f"seo_trip_report.json at {rep.get('at')}",
        f"python tools/freshness_trip.py rewrote seo_trip_report.json ({rep.get('open')} open, {rep.get('overdue')} past grace, "
        f"by kind {json.dumps(rep.get('by_kind'))})")
    crc, cout = _run("tools/freshness_trip.py", "--ci")
    past = int(rep.get("overdue") or 0)
    put("KA364", (crc != 0) == (past > 0), f"--ci exit {crc}",
        f"python tools/freshness_trip.py --ci (the nightly keep-abreast job's own step, .github/workflows/ci.yml) exits {crc} "
        f"with {past} trip(s) past grace - red exactly when a trip is past its grace")

    # KA366: the header line is the generator's, printed from the report just written
    urc, uout = _run("tools/update_trajectory_scoreboard.py", "--check")
    head = next((ln for ln in (ROOT / "UFAI_TRAJECTORY_ROADMAP.md").read_text(encoding="utf-8").splitlines()
                 if "KEEP ABREAST" in ln and "trips open" in ln), "")
    if TEETH:
        head = re.sub(r"trips open \d+", "trips open 999", head)
    m = re.search(r"trips open (\d+) \((\d+) past grace\)", head)
    agree = bool(m) and int(m.group(1)) == int(rep.get("open") or -1) and int(m.group(2)) == past
    put("KA366", agree, head[:220],
        f"the roadmap header reads trips open {m.group(1) if m else '?'} ({m.group(2) if m else '?'} past grace); the report "
        f"just written says {rep.get('open')} ({past}) - " + ("the line is the generator's" if agree else "the line is STALE or typed")
        + f"; update_trajectory_scoreboard.py --check exit {urc}")

    failed = [k for k, v in rows.items() if not v["ok"]]
    if TEETH:
        caught = [k for k in PLANTED if k in failed]
        print(f"{'PASS' if len(caught) == len(PLANTED) else 'FAIL'} keep-abreast-board teeth: {len(caught)}/{len(PLANTED)} planted "
              f"contradictions caught ({', '.join(caught)})")
        OUT.write_text(json.dumps({"ran": datetime.now(timezone.utc).isoformat(timespec="seconds"), "teeth": True,
                                   "planted": list(PLANTED), "caught": caught, "rows": rows}, indent=1), encoding="utf-8")
        return 0 if len(caught) == len(PLANTED) else 1
    OUT.write_text(json.dumps({"ran": datetime.now(timezone.utc).isoformat(timespec="seconds"), "origin": PROD,
                               "rows": rows, "failed": failed}, indent=1), encoding="utf-8")
    print(f"{'FAIL' if failed else 'PASS'} keep-abreast-board: {len(rows) - len(failed)}/{len(rows)} instruments agree with an "
          f"independent live reading" + (f" (disagree: {', '.join(failed)})" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
