#!/usr/bin/env python3
"""refresh_public_page.py - a refresh is a PAIRED WRITE across five surfaces, and never a date-only one (Wave KA, 2026-10-26).

A public page carries its freshness in five places that drifted apart because each was written by a different hand:
  1. JSON-LD "dateModified"            what the crawler and the answer engines read
  2. the visible "Last updated" line   what the person reads (fix_learn_freshness.py gave the twelve that lacked it the line)
  3. sitemap.xml <lastmod>             what the index schedules on - typed as `today` at scaffold time and never again,
                                       so 109 of 120 read May or August on 2026-10-26
  4. the markdown twin <page>.md       what an agent fetches (build_md_twins.py)
  5. the IndexNow push                 what tells the index the page changed - AFTER the deploy: the moved <lastmod> is
                                       the queue `indexnow_submit.py --verify --submit --changed` drains, with a receipt

★THE REFUSAL IS THE POINT. content_freshness_gate.py says it plainly: bumping dateModified without editing the content is
a lie to the crawler and the reader, trivially detectable by diffing against the previous crawl. So `--stamp` refuses
when the page's CONTENT hash (the HTML with its dates masked) equals the hash recorded at the last stamp, and moves all
five surfaces together only when the content really changed. `--sync-sitemap` is the one exception that is not a bump:
it writes each <lastmod> FROM the page's own dateModified (and the kind's changefreq), which only states what the page
already declares - the derivation the sitemap-promise gate then holds.

    python tools/refresh_public_page.py <slug> --dry-run      # what would move, and whether the content changed
    python tools/refresh_public_page.py <slug> --stamp        # move the five surfaces (refuses a date-only change)
    python tools/refresh_public_page.py --sync-sitemap        # derive every <lastmod>/<changefreq> from the pages
    python tools/refresh_public_page.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
SITEMAP = ROOT / "sitemap.xml"
STAMPS = ROOT / "public_page_stamps.json"      # slug -> {"content_sha": ..., "stamped": "YYYY-MM-DD"}
DATE_RX = re.compile(r'("dateModified"\s*:\s*")(\d{4}-\d{2}-\d{2})(")')
# Both visible lines: the footer's "Last updated" and the byline's "Updated" (27 learn pages carry the byline one; a stamp
# that moved only the footer left the article saying two different dates on one screen).
LAST_UPDATED_RX = re.compile(r'((?:Last updated|Updated) <time datetime=")(\d{4}-\d{2}-\d{2})(">)([^<]*)(</time>)')
CHANGEFREQ_FOR_WINDOW = {30: "monthly", 90: "monthly", 365: "yearly"}


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def page_path(slug: str) -> Path | None:
    for cand in (ROOT / "learn" / slug / "index.html", ROOT / "tools" / slug / "index.html", ROOT / slug / "index.html",
                 ROOT / f"{slug}.html"):
        if cand.exists():
            return cand
    return None


def content_sha(html: str) -> str:
    """The page with every date it declares masked, so a date-only edit hashes the same as no edit."""
    masked = DATE_RX.sub(r"\1DATE\3", html)
    masked = LAST_UPDATED_RX.sub(r"\1DATE\3DATE\5", masked)
    masked = re.sub(r"\d{1,2} [A-Z][a-z]{2} 20\d\d", "DATE", masked)
    return hashlib.sha256(masked.encode("utf-8")).hexdigest()[:16]


def _head_html(p: Path) -> str | None:
    """The page as committed at HEAD (None when it is new or git is unavailable)."""
    try:
        r = subprocess.run(["git", "show", f"HEAD:{p.relative_to(ROOT).as_posix()}"], cwd=ROOT, capture_output=True)
    except OSError:
        return None
    return r.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n") if r.returncode == 0 else None


def human_date(d: date) -> str:
    return f"{d.day} {d.strftime('%b %Y')}"


def stamp_page(html: str, d: date) -> str:
    html = DATE_RX.sub(lambda m: f"{m.group(1)}{d.isoformat()}{m.group(3)}", html)
    html = LAST_UPDATED_RX.sub(lambda m: f"{m.group(1)}{d.isoformat()}{m.group(3)}{human_date(d)}{m.group(5)}", html)
    return html


def sitemap_entries(src: str) -> list[dict]:
    out = []
    for m in re.finditer(r"<url>([\s\S]*?)</url>", src):
        b = m.group(1)
        out.append({"span": m.span(), "loc": (re.search(r"<loc>([^<]+)</loc>", b) or [None, ""])[1].strip(),
                    "lastmod": (re.search(r"<lastmod>([^<]+)</lastmod>", b) or [None, ""])[1].strip(),
                    "changefreq": (re.search(r"<changefreq>([^<]+)</changefreq>", b) or [None, ""])[1].strip()})
    return out


def local_of(loc: str) -> str:
    path = re.sub(r"^https?://[^/]+", "", loc).strip("/")
    return "index.html" if not path else (path if path.endswith(".html") else f"{path}/index.html")


def set_sitemap(src: str, loc: str, lastmod: str | None, changefreq: str | None) -> str:
    def repl(m):
        b = m.group(1)
        if f"<loc>{loc}</loc>" not in b:
            return m.group(0)
        if lastmod:
            b = re.sub(r"<lastmod>[^<]*</lastmod>", f"<lastmod>{lastmod}</lastmod>", b) if "<lastmod>" in b \
                else b.replace("</loc>", f"</loc>\n    <lastmod>{lastmod}</lastmod>", 1)
        if changefreq:
            b = re.sub(r"<changefreq>[^<]*</changefreq>", f"<changefreq>{changefreq}</changefreq>", b) if "<changefreq>" in b \
                else b.replace("</lastmod>", f"</lastmod>\n    <changefreq>{changefreq}</changefreq>", 1)
        return f"<url>{b}</url>"
    return re.sub(r"<url>([\s\S]*?)</url>", repl, src)


def sync_sitemap(dry_run: bool) -> int:
    """Every <lastmod> from the page's OWN dateModified; <changefreq> from the kind's window. Nothing invented."""
    import content_freshness_gate as cfg
    src = SITEMAP.read_text(encoding="utf-8")
    moved, kept, nodate = [], 0, []
    for e in sitemap_entries(src):
        local = local_of(e["loc"])
        p = ROOT / local
        text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        dm = cfg._date_of(text) if text else None
        slug = local.split("/")[-2] if local.endswith("/index.html") and "/" in local else local[:-5]
        # the learn and tools HUBS are not articles: they keep the cadence they declare (weekly - a hub changes often)
        is_hub = local in ("learn/index.html", "tools/index.html")
        kind = cfg._classify(slug, p) if (local.startswith("learn/") or local.startswith("tools/")) and p.exists() and not is_hub else None
        freq = CHANGEFREQ_FOR_WINDOW.get(cfg.TARGET_DAYS.get(kind, 0)) if kind else None
        want_lm = dm.isoformat() if dm else None
        if want_lm is None:
            nodate.append(local)
        if (want_lm and want_lm != e["lastmod"]) or (freq and freq != e["changefreq"]):
            moved.append((local, e["lastmod"], want_lm or e["lastmod"], e["changefreq"], freq or e["changefreq"]))
            src = set_sitemap(src, e["loc"], want_lm, freq)
        else:
            kept += 1
    print(f"  sitemap: {len(moved)} entr{'y' if len(moved) == 1 else 'ies'} move, {kept} already agree, {len(nodate)} page(s) declare no date "
          f"(their <lastmod> is kept as is)")
    for local, a, b, fa, fb in moved[:15]:
        print(f"    {local:<60} lastmod {a} -> {b}" + (f"  changefreq {fa} -> {fb}" if fa != fb else ""))
    if len(moved) > 15:
        print(f"    ... and {len(moved) - 15} more")
    if dry_run or not moved:
        return 0
    tmp = SITEMAP.with_suffix(".xml.tmp")
    tmp.write_text(src, encoding="utf-8", newline="\n")
    os.replace(tmp, SITEMAP)
    print(f"  wrote {SITEMAP.name}")
    return 0


def refresh(slug: str, dry_run: bool, today: date | None = None) -> int:
    today = today or date.today()
    p = page_path(slug)
    if not p:
        print(f"  no page for slug '{slug}'")
        return 2
    html = p.read_text(encoding="utf-8", errors="replace")
    stamps = json.loads(STAMPS.read_text(encoding="utf-8")) if STAMPS.exists() else {}
    sha = content_sha(html)
    prev = stamps.get(slug, {})
    # ★A FIRST STAMP HAD NO BASELINE, SO IT COULD NOT REFUSE (2026-10-27): with no prior stamp recorded, `changed`
    # was always true and a date-only bump passed on every page's first refresh. The committed page is the baseline
    # then - the content the crawler last saw shipped - so a first stamp must still differ from HEAD's content.
    base_sha, base_from = prev.get("content_sha"), "the last stamp"
    if not base_sha:
        head = _head_html(p)
        base_sha, base_from = (content_sha(head), "the committed page (HEAD)") if head is not None else (None, "nothing")
    changed = base_sha != sha
    cur = (DATE_RX.search(html) or [None, None, None])[2]
    print(f"  {p.relative_to(ROOT).as_posix()}: content {sha} ({'CHANGED' if changed else 'UNCHANGED'} since {base_from}"
          f"{' - first stamp' if not prev else ''}); dateModified {cur}")
    if not changed:
        print(f"  REFUSED: the content hash equals {base_from} - a date-only change is a lie to the crawler and the reader. "
              "Edit the page (new facts, corrected claims), then stamp.")
        return 1
    loc = next((e["loc"] for e in sitemap_entries(SITEMAP.read_text(encoding="utf-8")) if local_of(e["loc"]) == p.relative_to(ROOT).as_posix()), None)
    print(f"  would move: dateModified -> {today}; Last updated -> {human_date(today)}; sitemap <lastmod> {loc or '(not in sitemap)'} -> {today}; "
          f"twin rebuilt (build_md_twins.py); IndexNow queued for the post-deploy --changed push")
    if dry_run:
        return 0
    new_html = stamp_page(html, today)
    tmp = p.with_suffix(".html.tmp")
    tmp.write_text(new_html, encoding="utf-8", newline="\n")
    os.replace(tmp, p)
    if loc:
        src = SITEMAP.read_text(encoding="utf-8")
        tmp2 = SITEMAP.with_suffix(".xml.tmp")
        tmp2.write_text(set_sitemap(src, loc, today.isoformat(), None), encoding="utf-8", newline="\n")
        os.replace(tmp2, SITEMAP)
    stamps[slug] = {"content_sha": content_sha(new_html), "stamped": today.isoformat()}
    tmp3 = STAMPS.with_suffix(".json.tmp")
    tmp3.write_text(json.dumps(stamps, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp3, STAMPS)
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_md_twins.py")], cwd=ROOT, capture_output=True, text=True)
    print(f"  twins: {'rebuilt' if r.returncode == 0 else 'build_md_twins.py exit ' + str(r.returncode)}")
    # ★THE PUSH WAITS FOR THE DEPLOY (2026-10-27). This used to POST the URL here, before the refreshed page existed on
    # production - telling the index to re-fetch content it would not find (and, through --verify swallowing --submit,
    # it never actually POSTed at all). The moved <lastmod> IS the queue: the runbook's post-deploy
    # `indexnow_submit.py --verify --submit --changed` sends every URL whose lastmod is newer than the last receipt.
    if loc:
        print(f"  IndexNow: queued - {loc} goes out with the post-deploy `indexnow_submit.py --verify --submit --changed`")
    print(f"  stamped {slug} at {today}")
    return 0


# ★A PAGE THAT DECLARES NO DATE HAS NO FRESHNESS SURFACES TO AGREE (2026-10-29, KA-R). 60 of the 120 sitemap URLs - 59
# calculator pages and feedback/ - carried no dateModified at all: the sitemap said 2026-08-05 (or 05-17), the
# calculators' footer said "Last updated 2026-09-08" (a sweep's date), and the files' visible text last changed
# 2026-10-19. sync_sitemap() skipped them (nodate) and freshness_trip's promise check needs both dates, so no gate saw
# it. --declare-undated gives each one the date its READABLE TEXT last changed (git history, every date masked, so a
# date-only commit never counts) - a fact read from the repository, never today's date - and writes it into the page's
# JSON-LD, its visible "Last updated" line and the sitemap together.
VISIBLE_TEXT_DATES = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}\b|"
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}\b")
LD_NODE_RX = re.compile(r'("@type"\s*:\s*"(?:SoftwareApplication|CollectionPage|WebPage|Article|TechArticle|BlogPosting)"\s*,)'
                        r'(\s*)')


def readable_text(html: str) -> str:
    """What a reader and a crawler read - the visible text and the JSON-LD - with every date masked."""
    import html as _h
    ld = " ".join(re.findall(r'(?is)<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html))
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = _h.unescape(re.sub(r"<[^>]+>", " ", s)) + " " + ld
    s = re.sub(r'"(?:dateModified|datePublished)"\s*:\s*"[^"]*"', "", s)
    return re.sub(r"\s+", " ", VISIBLE_TEXT_DATES.sub("DATE", s)).strip()


def text_changed_on(p: Path) -> date | None:
    """The commit date of the newest commit whose readable text differs from its parent's (None without history)."""
    rel = p.relative_to(ROOT).as_posix()
    log = subprocess.run(["git", "log", "--format=%H %cs", "--", rel], cwd=ROOT, capture_output=True, text=True)
    commits = [ln.split() for ln in log.stdout.splitlines() if ln.strip()]
    prev_sha, prev_day = None, None
    for sha, day in commits:                       # newest first
        src = subprocess.run(["git", "show", f"{sha}:{rel}"], cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")
        h = hashlib.sha256(readable_text(src).encode()).hexdigest()
        if prev_sha is not None and h != prev_sha:
            return date.fromisoformat(prev_day)    # the newer commit changed the text
        prev_sha, prev_day = h, day
    return date.fromisoformat(prev_day) if prev_day else None   # the first commit wrote it


def declare_undated(dry_run: bool) -> int:
    import content_freshness_gate as cfg
    src = SITEMAP.read_text(encoding="utf-8")
    done, refused = [], []
    for e in sitemap_entries(src):
        p = ROOT / local_of(e["loc"])
        if not p.exists():
            continue
        html = p.read_text(encoding="utf-8")
        if cfg._date_of(html):
            continue
        cur = html.replace("\r\n", "\n")
        head = _head_html(p)
        if head is not None and readable_text(head) != readable_text(cur):
            refused.append(f"{p.relative_to(ROOT).as_posix()}: its text changed since HEAD - commit the change first, so "
                           "the date read from history is the date of that change")
            continue
        d = text_changed_on(p)
        if not d:
            refused.append(f"{p.relative_to(ROOT).as_posix()}: no git history to read a date from")
            continue
        new, n = LD_NODE_RX.subn(lambda m: f'{m.group(1)}{m.group(2)}"dateModified": "{d.isoformat()}",{m.group(2)}', cur, count=1)
        if not n:
            refused.append(f"{p.relative_to(ROOT).as_posix()}: no JSON-LD page node to carry dateModified")
            continue
        new = LAST_UPDATED_RX.sub(lambda m: f"{m.group(1)}{d.isoformat()}{m.group(3)}{human_date(d)}{m.group(5)}", new)
        if not dry_run:
            p.write_text(new, encoding="utf-8", newline="\n")
        done.append((p.relative_to(ROOT).as_posix(), e["lastmod"], d.isoformat()))
    for path, old, d in done:
        print(f"  {'would declare' if dry_run else 'declared'} {path}: dateModified {d} (sitemap said {old})")
    for r in refused:
        print("  REFUSED " + r)
    if done and not dry_run:
        sync_sitemap(False)
    print(f"{len(done)} page(s) {'would be' if dry_run else ''} declared, {len(refused)} refused")
    return 1 if refused else 0


def self_test() -> int:
    a = '<script type="application/ld+json">{"dateModified": "2026-08-05"}</script><p>Last updated <time datetime="2026-08-05">5 Aug 2026</time></p><p>OEE is 85%</p>'
    b = stamp_page(a, date(2026, 10, 26))
    ok = content_sha(a) == content_sha(b)                                   # a date-only change hashes the same
    ok = ok and content_sha(a) != content_sha(a.replace("85%", "86%"))     # a fact change does not
    ok = ok and '"dateModified": "2026-10-26"' in b and "26 Oct 2026" in b
    by = '<span>Published <time datetime="2026-05-17">17 May 2026</time></span><span>Updated <time datetime="2026-08-24">24 Aug 2026</time></span>'
    ok = ok and stamp_page(by, date(2026, 10, 27)).count("27 Oct 2026") == 1 and "17 May 2026" in stamp_page(by, date(2026, 10, 27))
    sm = '<urlset><url>\n    <loc>https://x/learn/a/</loc>\n    <lastmod>2026-05-17</lastmod>\n    <changefreq>monthly</changefreq>\n  </url></urlset>'
    out = set_sitemap(sm, "https://x/learn/a/", "2026-08-24", "monthly")
    ok = ok and "<lastmod>2026-08-24</lastmod>" in out and local_of("https://x/learn/a/") == "learn/a/index.html" and local_of("https://x/") == "index.html"
    print(("PASS" if ok else "FAIL") + " refresh-public-page self-test")
    return 0 if ok else 1


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--sync-sitemap", action="store_true")
    ap.add_argument("--declare-undated", action="store_true",
                    help="give each sitemap page that declares no date the date its readable text last changed")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.sync_sitemap:
        return sync_sitemap(dry_run=a.dry_run)
    if a.declare_undated:
        return declare_undated(dry_run=a.dry_run)
    if not a.slug:
        ap.print_help()
        return 2
    return refresh(a.slug, dry_run=not a.stamp)


if __name__ == "__main__":
    sys.exit(main())
