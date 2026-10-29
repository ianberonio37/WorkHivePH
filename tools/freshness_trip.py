#!/usr/bin/env python3
"""freshness_trip.py - the trip wire that keeps SEO / AEO / GEO abreast (Wave KA, 2026-10-26).

Ian, 2026-10-26: "my SEO AEO GEO ... it's like static, I want it always keeping up to date, or that will trigger or trip
that we need ... to keep abreast also." Measured that day: the search lane had been closed since August (Wave O locked,
0 open rows); 109 of 120 sitemap <lastmod> values read May or August while 115 URLs promised `monthly`; the refresh
queue held all 6 pillars and all 4 comparisons at 78 days against a 30-day target and nothing consumed it (the census
is ADVISORY on the board); the IndexNow key was live but no deploy had ever pushed; the scoreboard was hand-generated
on 2026-09-06 and hard-coded "deployed 0/1" four releases after launch; 59 of 62 SEO evidence chunks were past their
30-day TTL; two nightly CI jobs ran and neither carried any of it.

THE TRAJECTORY REGISTRY IS THE INBOX. This tool reads what already exists (content_freshness_report.json, the
substrate's frontmatter, sitemap.xml, robots.txt against the harvested crawler-roster chunks, seo_scoreboard.json,
indexnow_receipts.json, geo_sov_baseline.json), writes seo_trip_report.json, and with --seed RE-OPENS the KA row
whose unit tripped (status back to specced, the trip in its basis) - so a trip is a row Ian meets in the roadmap, not
a log line. New rows are never created here: seed_expansion_wave4.py --add-keep-abreast seeds them from this module's
census() (one place decides the size - the BRP rule).

ON THE BOARD IT IS WARN, NEVER FAIL: a failing gate here would reward a fake date bump, which is the lie the freshness
census itself warns about. --ci exits 1 only when a trip is older than its grace (the kind's window + GRACE_DAYS), so
the nightly job reddens on neglect, not on a page's natural ageing.

    python tools/freshness_trip.py              # the trips, written to seo_trip_report.json
    python tools/freshness_trip.py --check      # the board's form: prints, exits 0
    python tools/freshness_trip.py --ci         # exits 1 when any trip is past its grace
    python tools/freshness_trip.py --seed       # re-open the KA rows whose units tripped (writes the registry)
    python tools/freshness_trip.py --self-test
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
REGISTRY = ROOT / "trajectory_registry.json"
import registry_io as _rio  # the registry UNION: main file + the cube shard (tools/registry_io.py, 2026-10-26)
REPORT = ROOT / "seo_trip_report.json"
FRESHNESS = ROOT / "content_freshness_report.json"
SITEMAP = ROOT / "sitemap.xml"
ROBOTS = ROOT / "robots.txt"
SCOREBOARD = ROOT / "seo_scoreboard.json"
INDEXNOW_RECEIPTS = ROOT / "indexnow_receipts.json"
SOV_BASELINE = ROOT / "geo_sov_baseline.json"
PROMPTS = ROOT / "prompt_audit_queries.json"
EXTERNAL = ROOT / "substrate" / "external"
SEO_DOCS = ("SEO_AEO_GEO_V3.md", "SEO_AEO_GEO_STRATEGY_V2.md", "SEO_AEO_GEO_MAXIMIZATION_ROADMAP.md", "SEO_AEO_GEO_100_ARC.md",
            "seo_assets/TACTICAL_PLAYBOOK_V2.md")
SEO_TOOLS = ("tools/seo_scoreboard.py", "tools/seo_technical_gate.py", "tools/extractability_gate.py",
             "tools/landing_extractability_gate.py", "tools/orphan_depth_gate.py", "tools/content_freshness_gate.py",
             "tools/geo_sov_audit.py", "tools/indexnow_submit.py", "tools/build_md_twins.py", "tools/aio_readiness_gate.py",
             "tools/cwv_gate.py", "tools/calc_claim_consistency_gate.py", "tools/validate_structured_data_parity.py",
             "tools/validate_answer_presence.py", "tools/validate_dated_claim_freshness.py")
GRACE_DAYS = 14
SCOREBOARD_WINDOW = 30          # the compass must be regenerated at least monthly (it is now on the board)
SOV_WINDOW = 35                 # the monthly SOV sheet, with a few days of slack
PROMISE = {"always": 1, "hourly": 1, "daily": 1, "weekly": 7, "monthly": 30, "yearly": 365, "never": 10 ** 6}
SEO_TOPIC = re.compile(r"seo|aeo|\bgeo\b|search|crawl|llms|indexnow|schema|structured|citation|perplexity|chatgpt|openai|google|"
                       r"bing|rich.result|answer.engine|generative|e-e-a-t|eeat|core.web|cwv|sitemap|robots|backlink|brand.mention|"
                       r"reddit|wikipedia|hreflang|canonical", re.I)
ROSTER_CHUNK = re.compile(r"crawler|user-agent|bots|robots", re.I)
UA_TOKEN = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*(?:Bot|bot|User|Web|Extended|SearchBot|CloudVertexBot|externalagent|AdsBot|ai))\b")
UA_NOISE = {"Robot", "Chatbot", "Bot", "User", "Web", "Extended", "Googlebot", "Bingbot", "Slackbot", "Twitterbot", "Facebot",
            "LinkedInBot", "Pinterestbot", "Discordbot", "TelegramBot", "WhatsApp", "Applebot", "YandexBot", "DuckDuckBot", "Baiduspider"}


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _rd(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def _d(s: str | None) -> date | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s or "")
    return date.fromisoformat(m.group(1)) if m else None


def _age(d: date | None, today: date) -> int | None:
    return (today - d).days if d else None


# ─── the public URLs (KA-R, KA-S) ─────────────────────────────────────────────────────────────────────────────────

def sitemap_urls() -> list[dict]:
    """Every <url> of sitemap.xml with its local file, kind and the page's own dateModified."""
    import content_freshness_gate as cfg
    src = _rd(SITEMAP)
    out = []
    for m in re.finditer(r"<url>([\s\S]*?)</url>", src):
        block = m.group(1)
        loc = (re.search(r"<loc>([^<]+)</loc>", block) or [None, ""])[1].strip()
        lastmod = (re.search(r"<lastmod>([^<]+)</lastmod>", block) or [None, ""])[1].strip()
        freq = (re.search(r"<changefreq>([^<]+)</changefreq>", block) or [None, ""])[1].strip()
        path = re.sub(r"^https?://[^/]+", "", loc).strip("/")
        if not path:
            local, slug = "index.html", "index"
        elif path.endswith(".html"):
            local, slug = path, path[:-5]
        else:
            local, slug = f"{path}/index.html", path.split("/")[-1]
        p = ROOT / local
        text = _rd(p)
        try:
            kind = cfg._classify(slug, p) if (p.exists() and (local.startswith("learn/") or local.startswith("tools/"))) else "root"
        except Exception:
            kind = "root"
        window = cfg.TARGET_DAYS.get(kind, 90)
        out.append({"loc": loc, "path": local, "slug": slug, "kind": kind, "window_days": window, "lastmod": lastmod,
                    "changefreq": freq, "date_modified": (cfg._date_of(text).isoformat() if text and cfg._date_of(text) else None),
                    "exists": p.exists()})
    return out


def sitemap_promise_trips(urls: list[dict], today: date) -> list[dict]:
    """A URL whose <lastmod> disagrees with the page's own dateModified - the sitemap telling the crawler one date and the
    page another. (Cadence - a page past its window - is the refresh queue's signal, with the kind's own window, so it is
    not repeated here under a second name.)"""
    out = []
    for u in urls:
        lm = _d(u["lastmod"])
        dm = _d(u["date_modified"])
        # ★A PAGE THAT DECLARES NO DATE TRIPPED NOTHING (2026-10-29, KA-R): 60 of the 120 URLs - 59 calculators and
        # feedback/ - had no dateModified, so this check (which needs both dates) was silent while their sitemap said
        # 2026-08-05, their footer 2026-09-08 and their text had changed 2026-10-19. Silence is not agreement.
        if u.get("exists", True) and not dm:
            out.append({"kind": "sitemap-promise", "unit": u["path"], "detail": f"the page declares no dateModified, so the "
                        f"crawler has only the sitemap's <lastmod> {lm or 'none'} and nothing on the page agrees or disagrees "
                        f"(refresh_public_page.py --declare-undated)", "age_days": None, "grace_days": 0})
            continue
        if dm and lm and dm != lm:
            out.append({"kind": "sitemap-promise", "unit": u["path"], "detail": f"<lastmod> {lm} but the page's own dateModified is {dm} - "
                        f"the sitemap tells the crawler one date and the page another (refresh_public_page.py --sync-sitemap)",
                        "age_days": _age(dm, today), "grace_days": 0})
    return out


def refresh_trips(today: date) -> list[dict]:
    """The refresh queue content_freshness_gate ranks - here each stale page is a trip with the kind's grace."""
    rep = json.loads(_rd(FRESHNESS) or "{}") if FRESHNESS.exists() else {}
    out = []
    for q in rep.get("queue") or []:
        out.append({"kind": "refresh", "unit": q["slug"], "detail": f"{q['kind']} '{q['slug']}' last modified {q['modified']}, "
                    f"{q['age_days']} days against a {q['target_days']}-day target (over by {q['over_by']})",
                    "age_days": q.get("age_days"), "grace_days": q.get("target_days", 30) + GRACE_DAYS,
                    "over_by": q.get("over_by"), "target_days": q.get("target_days")})
    if not rep:
        out.append({"kind": "refresh", "unit": "content_freshness_report.json", "detail": "no refresh census on disk - run "
                    "python tools/content_freshness_gate.py", "age_days": None, "grace_days": 0})
    return out


# ─── the evidence spine (KA-E) ────────────────────────────────────────────────────────────────────────────────────

def _frontmatter(text: str) -> dict:
    m = re.match(r"---\n([\s\S]*?)\n---", text)
    return dict(re.findall(r"^([a-zA-Z_]+):\s*(.*)$", m.group(1), re.M)) if m else {}


def cited_sources() -> dict:
    """{external-slug: [files that cite it]} across the SEO program's docs, skill and gate code."""
    files = [ROOT / f for f in SEO_DOCS + SEO_TOOLS] + [Path.home() / ".claude" / "skills" / "seo-content" / "SKILL.md"]
    cited: dict[str, list[str]] = {}
    for f in files:
        if not f.exists():
            continue
        for s in set(re.findall(r"external-[a-z0-9][a-z0-9-]+", _rd(f))):
            cited.setdefault(s, []).append(f.name)
    return cited


def spine_status(today: date) -> dict:
    """Every SEO-topic or cited external chunk with its age against its TTL."""
    cited = cited_sources()
    chunks = []
    for p in sorted(glob.glob(str(EXTERNAL / "*.md"))):
        fm = _frontmatter(_rd(Path(p)))
        slug = Path(p).stem
        is_cited = any(slug.startswith(c) or c.startswith(slug) for c in cited)
        if not (is_cited or SEO_TOPIC.search(slug + " " + fm.get("topic", ""))):
            continue
        ttl = int(re.sub(r"\D", "", fm.get("ttl_days", "30")) or 30)
        d = _d(fm.get("last_verified")) or _d(fm.get("fetched_at"))
        age = _age(d, today)
        chunks.append({"slug": slug, "ttl_days": ttl, "age_days": age, "stale": age is None or age > ttl, "cited": is_cited,
                       "cited_by": sorted(set(sum((v for c, v in cited.items() if slug.startswith(c) or c.startswith(slug)), [])))})
    return {"chunks": chunks, "cited_total": len(cited), "stale": sum(1 for c in chunks if c["stale"]), "total": len(chunks)}


def spine_trips(spine: dict) -> list[dict]:
    return [{"kind": "evidence", "unit": c["slug"], "detail": f"external chunk {c['slug']} is {c['age_days']} days old against a "
             f"{c['ttl_days']}-day TTL" + (f" and anchors {', '.join(c['cited_by'][:3])}" if c["cited_by"] else "") +
             " - re-fetch (night_crawler.py --refresh-stale); a changed source is a decision on the lever it anchors",
             "age_days": c["age_days"], "grace_days": c["ttl_days"] + GRACE_DAYS} for c in spine["chunks"] if c["stale"]]


# ─── the crawler roster (KA-B) ────────────────────────────────────────────────────────────────────────────────────

def roster_trips() -> list[dict]:
    """AI user-agents the harvested roster chunks name that robots.txt does not address."""
    have = set(re.findall(r"User-agent:\s*(\S+)", _rd(ROBOTS)))
    named: Counter = Counter()
    for p in glob.glob(str(EXTERNAL / "*.md")):
        if not ROSTER_CHUNK.search(Path(p).stem):
            continue
        for tok in UA_TOKEN.findall(_rd(Path(p))):
            if tok not in UA_NOISE and len(tok) > 3:
                named[tok] += 1
    missing = sorted(t for t, n in named.items() if n >= 2 and t not in have and t.lower() not in {h.lower() for h in have})
    return [{"kind": "roster", "unit": tok, "detail": f"the harvested crawler roster names {tok} ({named[tok]}x) and robots.txt has no "
             f"User-agent line for it - decide allow/disallow and record it", "age_days": None, "grace_days": GRACE_DAYS} for tok in missing]


# ─── the board, the push, the voice (KA-B, KA-S, KA-V) ────────────────────────────────────────────────────────────

def board_trips(today: date, urls: list[dict]) -> list[dict]:
    out = []
    sb = json.loads(_rd(SCOREBOARD) or "{}") if SCOREBOARD.exists() else {}
    gen = _d(sb.get("generated_at"))
    if not gen or _age(gen, today) > SCOREBOARD_WINDOW:
        out.append({"kind": "board", "unit": "seo_scoreboard.json", "detail": f"the five-pillar scoreboard was generated "
                    f"{gen or 'never'} ({_age(gen, today) if gen else 'n/a'} days) - run python tools/seo_scoreboard.py (it belongs on the board)",
                    "age_days": _age(gen, today), "grace_days": SCOREBOARD_WINDOW})
    rec = json.loads(_rd(INDEXNOW_RECEIPTS) or "{}") if INDEXNOW_RECEIPTS.exists() else {}
    last_push = _d(rec.get("last_submit_at") or rec.get("at"))
    newest_change = max((_d(u["lastmod"]) for u in urls if _d(u["lastmod"])), default=None)
    if rec.get("pushed"):
        # ★PER URL, ONCE THE RECEIPT KEEPS ONE (2026-10-29, KA-S): each KA-S row asks whether ITS URL was pushed after
        # ITS last change. One "last push" date answered that for no URL in particular.
        out += push_trips(urls, rec["pushed"], today)
    elif not last_push:
        out.append({"kind": "push", "unit": "indexnow", "detail": "no IndexNow receipt on disk - the index was never told about a deploy "
                    "(python tools/indexnow_submit.py --verify --submit --changed, the runbook's post-deploy step)", "age_days": None, "grace_days": 0})
    elif newest_change and last_push < newest_change:
        out.append({"kind": "push", "unit": "indexnow", "detail": f"the last IndexNow push ({last_push}) predates the newest sitemap change "
                    f"({newest_change}) - push the changed URLs", "age_days": _age(last_push, today), "grace_days": GRACE_DAYS})
    sov = json.loads(_rd(SOV_BASELINE) or "{}") if SOV_BASELINE.exists() else {}
    sov_at = _d(sov.get("at") or sov.get("generated_at") or sov.get("recorded_at"))
    if not sov_at:
        out.append({"kind": "voice", "unit": "geo_sov_baseline.json", "detail": "the AI share-of-voice sheet has never been scored "
                    "(python tools/geo_sov_audit.py --template, fill it monthly, --score) - the engines' verdict is unread",
                    "age_days": None, "grace_days": SOV_WINDOW})
    elif _age(sov_at, today) > SOV_WINDOW:
        out.append({"kind": "voice", "unit": "geo_sov_baseline.json", "detail": f"the share-of-voice sheet was last scored {sov_at} "
                    f"({_age(sov_at, today)} days) - the monthly run is overdue", "age_days": _age(sov_at, today), "grace_days": SOV_WINDOW})
    return out


def _committed_at(path: str) -> str | None:
    """ISO time of the last commit touching the page; None when it has uncommitted changes (they postdate every push)."""
    import subprocess
    try:
        dirty = subprocess.run(["git", "status", "--porcelain", "--", path], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        if dirty:
            return None
        return subprocess.run(["git", "log", "-1", "--format=%cI", "--", path], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip() or None
    except OSError:
        return None


def push_trips(urls: list[dict], pushed: dict, today: date) -> list[dict]:
    """A URL never pushed, or pushed before its last change. <lastmod> carries no time, so a push on the change's own
    day is quiet only when the page's last commit came before the push - never assumed."""
    out = []
    for u in urls:
        p = pushed.get(u["loc"]) or {}
        at = p.get("at") if isinstance(p, dict) else p
        lm, pd = _d(u["lastmod"]), _d((at or "")[:10])
        if not pd:
            why = "was never pushed to IndexNow"
        elif lm and pd < lm:
            why = f"was last pushed {pd}, before its last change ({lm})"
        elif lm and pd == lm:
            c = _committed_at(u["path"])
            why = None if (c and datetime.fromisoformat(c) <= datetime.fromisoformat(at)) else \
                f"was pushed {at} on the day it changed, and its last commit ({c or 'uncommitted'}) is not before the push"
        else:
            why = None
        if why:
            out.append({"kind": "push", "unit": u["path"], "detail": f"{u['loc']} {why} - push it after the deploy "
                        "(python tools/indexnow_submit.py --verify --submit --changed)",
                        "age_days": _age(pd or lm, today), "grace_days": GRACE_DAYS})
    return out


def prompts() -> list[dict]:
    """The SOV prompt set, English only (the standing rule): the 10 `tl` prompts stay in the file, out of the rows."""
    q = json.loads(_rd(PROMPTS) or "[]") if PROMPTS.exists() else []
    items = q if isinstance(q, list) else (q.get("queries") or q.get("prompts") or [])
    return [i for i in items if (i.get("lang") or i.get("language") or "en") != "tl"]


# ─── census + report ──────────────────────────────────────────────────────────────────────────────────────────────

def census(today: date | None = None) -> dict:
    today = today or date.today()
    urls = sitemap_urls()
    spine = spine_status(today)
    trips = refresh_trips(today) + spine_trips(spine) + sitemap_promise_trips(urls, today) + roster_trips() + board_trips(today, urls)
    for t in trips:
        t["overdue"] = t["age_days"] is not None and t["grace_days"] is not None and t["age_days"] > t["grace_days"] \
            or (t["age_days"] is None and t["grace_days"] == 0)
    sb = json.loads(_rd(SCOREBOARD) or "{}") if SCOREBOARD.exists() else {}
    rec = json.loads(_rd(INDEXNOW_RECEIPTS) or "{}") if INDEXNOW_RECEIPTS.exists() else {}
    sov = json.loads(_rd(SOV_BASELINE) or "{}") if SOV_BASELINE.exists() else {}
    fr = json.loads(_rd(FRESHNESS) or "{}") if FRESHNESS.exists() else {}
    return {
        "_doc": "KEEP ABREAST (Wave KA): the trips that keep SEO/AEO/GEO alive; tools/freshness_trip.py",
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "today": today.isoformat(),
        "urls": len(urls), "prompts_en": len(prompts()),
        "spine": {"total": spine["total"], "stale": spine["stale"], "within_ttl": spine["total"] - spine["stale"], "cited": spine["cited_total"]},
        "refresh_queue": len(fr.get("queue") or []),
        "last_push": (rec.get("last_submit_at") or rec.get("at") or "never"),
        "last_sov": (sov.get("at") or sov.get("generated_at") or "never"),
        "scoreboard_at": sb.get("generated_at") or "never",
        "trips": trips, "open": len(trips), "overdue": sum(1 for t in trips if t["overdue"]),
        "by_kind": dict(Counter(t["kind"] for t in trips)),
        "url_list": urls, "spine_chunks": spine["chunks"],
    }


def header_line(c: dict | None = None) -> str:
    """The generated roadmap header line (update_trajectory_scoreboard.py prints it; never hand-typed)."""
    c = c or (json.loads(_rd(REPORT)) if REPORT.exists() else census())
    return (f"**KEEP ABREAST** (Wave KA, `tools/freshness_trip.py`) — trips open {c['open']} ({c['overdue']} past grace) · "
            f"spine within TTL {c['spine']['within_ttl']}/{c['spine']['total']} · refresh queue {c['refresh_queue']} · "
            f"last IndexNow push {str(c['last_push'])[:10]} · last SOV {str(c['last_sov'])[:10]} · scoreboard {str(c['scoreboard_at'])[:10]}")


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def seed_reopen(c: dict) -> int:
    """Re-open the KA row whose unit tripped (a locked/locking row goes back to specced, the trip in its basis)."""
    doc = _rio.load_doc()
    by_unit = {}
    for t in doc["trajectories"]:
        ka = t.get("ka") or {}
        if ka.get("kind") == "keep-abreast":
            for trip_kind in ka.get("trips") or []:
                for unit in [ka.get("unit")] + list(ka.get("aliases") or []):
                    by_unit.setdefault((trip_kind, unit), []).append(t)
    reopened, missing = [], []
    for trip in c["trips"]:
        rows = by_unit.get((trip["kind"], trip["unit"]))
        if not rows:
            missing.append(f"{trip['kind']}:{trip['unit']}")
            continue
        for r in rows:
            if r.get("status") in ("locked", "locking", "fixing", "walked") and trip["overdue"]:
                r["status"], r["pct"] = "specced", 5
                r["basis"] = f"[{c['today']}] TRIPPED - {trip['detail'][:220]}\n" + (r.get("basis") or "")
                reopened.append(r["id"])
    if reopened:
        _rio.save_doc(doc)
    print(f"  re-opened {len(reopened)} KA row(s): {', '.join(reopened[:12])}{' ...' if len(reopened) > 12 else ''}")
    if missing:
        print(f"  {len(missing)} trip(s) have no KA row yet (run seed_expansion_wave4.py --add-keep-abreast): "
              f"{', '.join(missing[:6])}{' ...' if len(missing) > 6 else ''}")
    return 0


def self_test() -> int:
    today = date(2026, 10, 26)
    urls = [{"path": "learn/x/index.html", "lastmod": "2026-08-05", "changefreq": "monthly", "date_modified": "2026-08-24"},
            {"path": "tools/y/index.html", "lastmod": "2026-10-16", "changefreq": "yearly", "date_modified": "2026-10-16"}]
    t = sitemap_promise_trips(urls, today)
    ok = len(t) == 1 and t[0]["unit"] == "learn/x/index.html"                   # the disagreement trips; the agreeing one is clean
    # a page that declares no date trips (it used to be silent)
    ok = ok and [x["unit"] for x in sitemap_promise_trips([dict(urls[1], path="tools/z/index.html", date_modified=None)], today)] \
        == ["tools/z/index.html"]
    # per URL: never pushed and pushed-before-the-change trip; pushed the day after the change is quiet
    pu = [{"loc": "https://w/a/", "path": "a/index.html", "lastmod": "2026-10-20"},
          {"loc": "https://w/b/", "path": "b/index.html", "lastmod": "2026-10-20"},
          {"loc": "https://w/c/", "path": "c/index.html", "lastmod": "2026-10-20"}]
    got = {x["unit"] for x in push_trips(pu, {"https://w/b/": {"at": "2026-10-19T03:00:00+00:00"},
                                              "https://w/c/": {"at": "2026-10-21T03:00:00+00:00"}}, today)}
    ok = ok and got == {"a/index.html", "b/index.html"}
    ok = ok and PROMISE["monthly"] == 30 and "KEEP ABREAST" in header_line({"open": 1, "overdue": 0, "spine": {"within_ttl": 1, "total": 2},
                                                                              "refresh_queue": 0, "last_push": "never", "last_sov": "never",
                                                                              "scoreboard_at": "2026-09-06"})
    print(("PASS" if ok else "FAIL") + " freshness-trip self-test")
    return 0 if ok else 1


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="the board's form: print, exit 0")
    ap.add_argument("--ci", action="store_true", help="exit 1 when any trip is past its grace")
    ap.add_argument("--seed", action="store_true", help="re-open the KA rows whose units tripped")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    c = census()
    slim = {k: v for k, v in c.items() if k not in ("url_list", "spine_chunks")}
    _atomic_write(REPORT, json.dumps(slim, indent=1, ensure_ascii=False) + "\n")
    if a.json:
        print(json.dumps(slim, indent=1, ensure_ascii=False))
        return 0
    print("  KEEP ABREAST - the trips (Wave KA)")
    print("  " + "=" * 92)
    print(f"  {c['urls']} public URLs · spine {c['spine']['within_ttl']}/{c['spine']['total']} within TTL ({c['spine']['cited']} sources cited) · "
          f"refresh queue {c['refresh_queue']} · last push {c['last_push']} · last SOV {c['last_sov']} · scoreboard {c['scoreboard_at']}")
    print(f"  trips open {c['open']} · past grace {c['overdue']} · by kind " + " · ".join(f"{k} {v}" for k, v in c["by_kind"].items()))
    for t in sorted(c["trips"], key=lambda x: (not x["overdue"], x["kind"], -(x["age_days"] or 0)))[:25]:
        print(f"    {'OVERDUE' if t['overdue'] else 'open   '} {t['kind']:<16} {t['unit'][:44]:<44} {t['detail'][:88]}")
    if c["open"] > 25:
        print(f"    ... and {c['open'] - 25} more (seo_trip_report.json)")
    print(f"  wrote {REPORT.name}")
    if a.seed:
        return seed_reopen(c)
    if a.ci and c["overdue"]:
        print(f"  CI: {c['overdue']} trip(s) past grace - the lane is being neglected, not merely ageing")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
